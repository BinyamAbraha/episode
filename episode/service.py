"""Pinned adapter, catalog queries, append-only curation and immutable versions."""

import json, hashlib, time, uuid, urllib.request, os
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from .storage import *
from .validation import validate, RULES
from .media import probe, preview, decode, frame_times, validate_stream
from bisect import bisect_left

CAMERAS = ["observation.images.side", "observation.images.up"]
SOURCE_LOCK = Path(__file__).resolve().parents[1] / "docs/source-lock.json"


def feature_metadata(info):
    return {
        "robot_type": info["robot_type"],
        "session_identity": None,
        "physical_synchronization": None,
        "features": {
            name: {
                "source_name": name,
                "dtype": f["dtype"],
                "shape": f["shape"],
                "names": f.get("names"),
                "units": f.get("units"),
                "coordinate_frame": f.get("coordinate_frame"),
                "control_semantics": f.get("control_semantics"),
            }
            for name, f in info["features"].items()
        },
    }


def asset_path(relative):
    p = (source_root() / relative).resolve()
    if not p.is_relative_to(source_root().resolve()):
        raise ValueError("Invalid source path")
    return p


def media_path(meta, camera):
    if camera not in CAMERAS:
        raise ValueError("Unknown camera")
    return asset_path(
        f'videos/{camera}/chunk-{meta[f"videos/{camera}/chunk_index"]:03d}/file-{meta[f"videos/{camera}/file_index"]:03d}.mp4'
    )


def samples(meta):
    p = asset_path(
        f'data/chunk-{meta["data/chunk_index"]:03d}/file-{meta["data/file_index"]:03d}.parquet'
    )
    return pq.read_table(
        p, filters=[("episode_index", "=", meta["episode_index"])]
    ).to_pylist()


def update_job(id, stage, completed=0, total=0):
    with connect() as db:
        row = db.execute("SELECT cancel FROM jobs WHERE id=?", (id,)).fetchone()
        if row and row[0]:
            raise InterruptedError("Cancelled at safe boundary")
        db.execute(
            "UPDATE jobs SET stage=?,completed=?,total=?,updated=? WHERE id=?",
            (stage, completed, total, now(), id),
        )


def enqueue(kind="import", args=None):
    if kind not in ["import", "verify"]:
        raise ValueError("Unknown job kind")
    id = uuid.uuid4().hex
    with connect() as db:
        db.execute(
            "INSERT INTO jobs(id,kind,args,state,stage,created,updated) VALUES(?,?,?,?,?,?,?)",
            (id, kind, canonical(args or {}), "queued", "queued", now(), now()),
        )
    return id


def import_source(job, limit=50):
    if not 1 <= limit <= 50:
        raise ValueError("Import limit must be 1 to 50")
    start = time.perf_counter()
    sr = source_root()
    sr.mkdir(parents=True, exist_ok=True)
    lock = json.loads(SOURCE_LOCK.read_text())
    if lock["revision"] != REVISION:
        raise ValueError("Pinned source revision mismatch")
    files = [
        {"path": a["path"], "size": a["bytes"], "lfs": {"oid": a["sha256"]}}
        for a in lock["assets"]
    ]
    assets = []
    for i, a in enumerate(files):
        update_job(job, "downloading", i, len(files))
        p = asset_path(a["path"])
        p.parent.mkdir(parents=True, exist_ok=True)
        expected = a.get("lfs", {}).get("oid")
        if not p.exists():
            temp = p.with_suffix(p.suffix + ".partial")
            with urllib.request.urlopen(
                f'https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/{a["path"]}',
                timeout=30,
            ) as response, temp.open("wb") as f:
                while block := response.read(1024 * 1024):
                    root()
                    f.write(block)
            if temp.stat().st_size != a["size"] or (
                expected and digest(temp) != expected
            ):
                raise ValueError("Source checksum mismatch: " + a["path"])
            temp.replace(p)
        sha = digest(p)
        if p.stat().st_size != a["size"] or (expected and sha != expected):
            raise ValueError("Changed preserved asset: " + a["path"])
        with connect() as db:
            old = db.execute(
                "SELECT sha256 FROM assets WHERE path=?", (a["path"],)
            ).fetchone()
            if old and old[0] != sha:
                raise ValueError("Logical asset identity conflict: " + a["path"])
        assets.append((a["path"], sha, p.stat().st_size, REVISION))
    info = json.loads((sr / "meta/info.json").read_text())
    if info["codebase_version"] != "v3.0":
        raise ValueError("Adapter only supports inspected v3.0 contract")
    metadata = pq.read_table(
        sr / "meta/episodes/chunk-000/file-000.parquet"
    ).to_pylist()[:limit]
    if len({m["episode_index"] for m in metadata}) != len(metadata):
        raise ValueError("Duplicate episode metadata identity")
    table = pq.read_table(sr / "data/chunk-000/file-000.parquet")
    for name in ["action", "observation.state"]:
        if (
            not pa.types.is_list(table.schema.field(name).type)
            or table.schema.field(name).type.value_type != pa.float32()
        ):
            raise ValueError("Declared float32 feature dtype mismatch: " + name)
    media = {}
    for camera in CAMERAS:
        p = media_path(metadata[0], camera)
        update_job(job, "validating media", 0, 2)
        media[camera] = probe(p)
        validate_stream(p, info["features"][camera]["shape"])
        decode(p, 0)
        media[camera]["timestamps"] = frame_times(p)
        update_job(job, "deriving preview", len(media) - 1, 2)
        preview(p)
    episodes = []
    findings = []
    for i, m in enumerate(metadata):
        update_job(job, "validating", i, len(metadata))
        data = samples(m)
        found = validate(data, info, m)
        indexes = [r["index"] for r in data]
        if indexes != list(range(m["dataset_from_index"], m["dataset_to_index"])):
            raise ValueError("Invalid declared half-open source row boundary")
        for camera in CAMERAS:
            offset = m[f"videos/{camera}/from_timestamp"]
            end = m[f"videos/{camera}/to_timestamp"]
            duration = float(media[camera]["format"]["duration"])
            if (
                offset < 0
                or end > duration + RULES["alignment_seconds"]
                or abs((end - offset) - len(data) / info["fps"])
                > RULES["alignment_seconds"]
            ):
                found.append(
                    dict(
                        rule="media.coverage",
                        severity="error",
                        start=0,
                        end=len(data) / info["fps"],
                        observed=[offset, end, duration],
                        threshold=RULES["alignment_seconds"],
                        explanation="Camera offsets do not cover the declared episode.",
                    )
                )
            pts = media[camera]["timestamps"]
            for row in data:
                target = offset + row["timestamp"]
                j = bisect_left(pts, target)
                nearest = min(
                    (pts[k] for k in [j - 1, j] if 0 <= k < len(pts)),
                    key=lambda t: abs(t - target),
                )
                if abs(nearest - target) > RULES["alignment_seconds"]:
                    found.append(
                        dict(
                            rule="media.association",
                            severity="error",
                            start=row["timestamp"],
                            end=row["timestamp"],
                            observed=abs(nearest - target),
                            threshold=RULES["alignment_seconds"],
                            explanation="No camera frame is near the associated source sample.",
                        )
                    )
                    break
            decode(media_path(m, camera), offset + data[-1]["timestamp"])
        family = hashlib.sha256(
            canonical([[r["observation.state"], r["action"]] for r in data]).encode()
        ).hexdigest()
        compact = {k: v for k, v in m.items() if not k.startswith("stats/")}
        episodes.append(
            (
                m["episode_index"],
                REVISION,
                canonical(compact),
                "; ".join(m["tasks"]),
                len(data) / info["fps"],
                len(data),
                family,
            )
        )
        findings.extend(
            (
                m["episode_index"],
                f["rule"],
                f["severity"],
                f["start"],
                f["end"],
                canonical(f["observed"]),
                canonical(f["threshold"]),
                f["explanation"],
            )
            for f in found
        )
    update_job(job, "publishing", len(episodes), len(episodes))
    with connect() as db:
        db.execute(
            "INSERT OR IGNORE INTO sources VALUES(?,?,?,?,?)",
            (REVISION, REPO, REVISION, canonical(info), now()),
        )
        db.executemany("INSERT OR IGNORE INTO assets VALUES(?,?,?,?)", assets)
        for row in episodes:
            db.execute("INSERT OR IGNORE INTO episodes VALUES(?,?,?,?,?,?,?)", row)
            db.execute("DELETE FROM findings WHERE episode=? AND fixture=0", (row[0],))
        db.executemany(
            "INSERT INTO findings(episode,rule,severity,start,end,observed,threshold,explanation) VALUES(?,?,?,?,?,?,?,?)",
            findings,
        )
        report = {
            "episodes": len(episodes),
            "samples": sum(e[5] for e in episodes),
            "findings": [
                dict(
                    zip(
                        [
                            "episode",
                            "rule",
                            "severity",
                            "start",
                            "end",
                            "observed",
                            "threshold",
                            "explanation",
                        ],
                        f,
                    )
                )
                for f in findings
            ],
            "asset_hashes": {a[0]: a[1] for a in assets},
            "checks": [
                "source checksums",
                "schema and temporal rules",
                "all source-frame decode scan",
                "every sample to camera PTS association",
                "episode-end decode",
            ],
        }
        db.execute(
            "INSERT INTO validation_runs VALUES(?,?,?,?,?)",
            (uuid.uuid4().hex, job, canonical(RULES), canonical(report), now()),
        )
    return {
        "episodes": len(episodes),
        "seconds": time.perf_counter() - start,
        "source_bytes": sum(a[2] for a in assets),
    }


def catalog(criteria=None):
    c = criteria or {}
    with connect() as db:
        result = rows(
            db,
            """SELECT e.*,COALESCE(r.status,'unreviewed') review,COALESCE(r.outcome,'unknown') outcome,
        (SELECT count(*) FROM findings f WHERE f.episode=e.id AND f.fixture=0) findings,
        (SELECT count(*) FROM findings f WHERE f.episode=e.id AND f.severity='error' AND f.fixture=0) errors
        FROM episodes e LEFT JOIN reviews r ON r.id=(SELECT max(id) FROM reviews WHERE episode=e.id) ORDER BY e.id""",
        )
    for e in result:
        e.pop("metadata")
    return [
        e
        for e in result
        if (
            not c.get("search")
            or c["search"].lower() in (str(e["id"]) + " " + e["task"]).lower()
        )
        and (not c.get("review") or e["review"] == c["review"])
        and (not c.get("findings") or e["findings"] > 0)
        and (not c.get("valid_only") or e["errors"] == 0)
        and e["duration"] >= float(c.get("min_duration", 0))
        and e["duration"] <= float(c.get("max_duration", 1e9))
    ]


def episode(id):
    with connect() as db:
        row = db.execute("SELECT * FROM episodes WHERE id=?", (id,)).fetchone()
        if not row:
            raise ValueError("Episode not found")
        out = dict(row)
        out["metadata"] = json.loads(out["metadata"])
        out["samples"] = samples(out["metadata"])
        out["findings"] = rows(
            db, "SELECT * FROM findings WHERE episode=? AND fixture=0", (id,)
        )
        out["reviews"] = rows(
            db, "SELECT * FROM reviews WHERE episode=? ORDER BY id DESC", (id,)
        )
        out["annotations"] = rows(
            db, "SELECT * FROM annotations WHERE episode=? ORDER BY id", (id,)
        )
        out["info"] = json.loads(
            db.execute("SELECT info FROM sources WHERE id=?", (REVISION,)).fetchone()[0]
        )
        out["feature_metadata"] = feature_metadata(out["info"])
        out["cameras"] = [
            {
                "key": c,
                "label": c.split(".")[-1],
                "offset": out["metadata"][f"videos/{c}/from_timestamp"],
                "url": f"/api/episodes/{id}/media/{c}",
            }
            for c in CAMERAS
        ]
        return out


def review(id, status, outcome, reason):
    episode(id)
    if status not in ["accepted", "excluded", "unreviewed"] or outcome not in [
        "unknown",
        "success",
        "failure",
    ]:
        raise ValueError("Invalid review state")
    if not reason.strip():
        raise ValueError("Record a reason for the review")
    with connect() as db:
        db.execute(
            "INSERT INTO reviews(episode,status,outcome,reason,created) VALUES(?,?,?,?,?)",
            (id, status, outcome, reason.strip(), now()),
        )


def annotate(id, start, end, label, note):
    e = episode(id)
    if not 0 <= start < end <= e["duration"]:
        raise ValueError("Interval must lie inside episode with start < end")
    if not label.strip():
        raise ValueError("Annotation label is required")
    with connect() as db:
        db.execute(
            "INSERT INTO annotations(episode,start,end,label,note,created) VALUES(?,?,?,?,?,?)",
            (id, start, end, label.strip(), note, now()),
        )


def split_groups(episodes, seed):
    groups = {}
    for e in episodes:
        groups.setdefault(e["family"], []).append(e["id"])
    if len(groups) < 3:
        raise ValueError("At least three independent episode groups are required")
    order = sorted(
        groups, key=lambda k: hashlib.sha256(f"{seed}:{k}".encode()).hexdigest()
    )
    n = len(order)
    n_test = max(1, int(n * 0.1))
    n_val = max(1, int(n * 0.1))
    splits = {"train": [], "validation": [], "test": []}
    for i, k in enumerate(order):
        splits[
            "test" if i < n_test else "validation" if i < n_test + n_val else "train"
        ].extend(groups[k])
    return {k: sorted(v) for k, v in splits.items()}


def create_version(name, criteria, seed=17):
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        for asset in rows(db, "SELECT * FROM assets"):
            if digest(asset_path(asset["path"])) != asset["sha256"]:
                raise ValueError("Cannot publish a version from changed source assets")
        chosen = catalog(criteria)
        chosen = [e for e in chosen if not e["errors"] and e["review"] != "excluded"]
        if not name.strip():
            raise ValueError("Version name is required")
        splits = split_groups(chosen, seed)
        state = []
        action = []
        for id in splits["train"]:
            data = episode(id)["samples"]
            state.extend(r["observation.state"] for r in data)
            action.extend(r["action"] for r in data)
        norm = {}
        for key, values in [("observation.state", state), ("action", action)]:
            a = np.asarray(values, dtype=np.float64)
            std = a.std(axis=0)
            norm[key] = {
                "mean": a.mean(axis=0).tolist(),
                "std": np.where(std == 0, 1, std).tolist(),
                "fit_split": "train",
                "samples": len(a),
            }
        ids = [e["id"] for e in chosen]
        manifest = {
            "schema": "episode.version/1",
            "adapter": "lerobot-v3-pinned/1",
            "name": name.strip(),
            "created": now(),
            "source": {"repository": REPO, "revision": REVISION},
            "feature_metadata": feature_metadata(
                json.loads(
                    db.execute(
                        "SELECT info FROM sources WHERE id=?", (REVISION,)
                    ).fetchone()[0]
                )
            ),
            "episodes": ids,
            "assets": rows(db, "SELECT * FROM assets ORDER BY path"),
            "criteria": criteria,
            "reviews": [
                r
                for r in rows(db, "SELECT * FROM reviews ORDER BY id")
                if r["episode"] in ids
            ],
            "annotations": [
                a
                for a in rows(db, "SELECT * FROM annotations ORDER BY id")
                if a["episode"] in ids
            ],
            "split": {
                "algorithm": "sha256-family-order-80-10-10/1",
                "seed": seed,
                "grouping": "exact state/action sequence hash; sessions unknown",
                "membership": splits,
            },
            "rules": RULES,
            "transforms": {
                "window": 4,
                "stride": 4,
                "padding": "drop",
                "alignment": "recorded state[t], action[t]",
                "gap_policy": "reject",
                "images": "original RGB uint8",
            },
            "normalization": norm,
        }
        raw = canonical(manifest)
        id = hashlib.sha256(raw.encode()).hexdigest()
        db.execute("INSERT INTO versions VALUES(?,?,?,?)", (id, name, raw, now()))
        return id


def version(id):
    with connect() as db:
        r = db.execute("SELECT manifest FROM versions WHERE id=?", (id,)).fetchone()
    if not r:
        raise ValueError("Version not found")
    raw = r[0]
    if hashlib.sha256(raw.encode()).hexdigest() != id:
        raise ValueError("Version content hash mismatch")
    return json.loads(raw)


def verify_version(id, job=None):
    from .consumer import VersionDataset

    v = version(id)
    started = time.perf_counter()
    loader = VersionDataset(v, source_root())
    count = 0
    decoded = 0
    windows = 0
    split_counts = {}
    batch_shapes = {}
    max_error = 0
    for split, ids in v["split"]["membership"].items():
        split_counts[split] = 0
        for batch in loader.windows(split, decode_images=False):
            windows += 1
        for batch in loader.windows(split, first_per_episode=True):
            if job:
                update_job(job, "decoding consumer batches", count, len(v["episodes"]))
            assert batch["episode"] in ids
            batch_shapes = {
                k: list(batch[k][None].shape)
                for k in [
                    "images",
                    "state",
                    "action",
                    "normalized_state",
                    "normalized_action",
                    "mask",
                ]
            }
            max_error = max(max_error, max(t["error_seconds"] for t in batch["timing"]))
            decoded += int(np.prod(batch["images"].shape[:2]))
            count += 1
            split_counts[split] += 1
    if count != len(v["episodes"]):
        raise ValueError("Some selected episodes produced no complete window")
    result = {
        "status": "passed",
        "consumer": "Episode VersionDataset numpy + FFmpeg/1",
        "lerobot_compatibility": "not tested",
        "version": id,
        "episodes": count,
        "validated_signal_windows": windows,
        "decoded_images": decoded,
        "decoded_window_policy": "first complete window of every selected episode; all signal windows checked",
        "batch_shapes": batch_shapes,
        "split_episodes": split_counts,
        "max_association_error_seconds": max_error,
        "seconds": time.perf_counter() - started,
        "cache_condition": "OS cache uncontrolled; source hashes read before decoding",
        "concurrency": 1,
    }
    if job:
        update_job(job, "publishing verification", count, count)
    with connect() as db:
        db.execute(
            "INSERT INTO verifications(version,result,created) VALUES(?,?,?)",
            (id, canonical(result), now()),
        )
    return result
