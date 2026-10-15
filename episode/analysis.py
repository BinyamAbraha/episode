"""Immutable, evidence-linked analysis. Semantic suggestions are never human labels."""

import hashlib, json, os, re, resource, shutil, subprocess, sys, time, threading, fcntl
from pathlib import Path
from typing import Literal
import numpy as np
from PIL import Image, ImageDraw
from pydantic import BaseModel, ConfigDict, Field
from .storage import root, connect, rows, canonical, digest, now, REVISION
from . import service
from .media import decode_details

MODEL_REPO = "mlx-community/Qwen3-VL-4B-Instruct-4bit"
MODEL_REVISION = "2fd8dacbdb8f1e54b8c005f081ec5bf79c56376b"
CONFIG = {
    "schema": "episode.analysis/1",
    "samples_per_camera": 8,
    "image_size": [320, 240],
    "dark_pixel": 16,
    "clipped_pixel": 240,
    "fraction_threshold": 0.8,
    "blur_variance_threshold": 40,
    "repeat_mae_threshold": 0.2,
    "max_tokens": 700,
    "temperature": 0.0,
    "model_evidence_indices": [0, 2, 5, 7],
    "prompt_version": "pickplace-evidence/3",
    "max_attempts": 2,
}
SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses(id TEXT PRIMARY KEY, episode INTEGER NOT NULL, mode TEXT NOT NULL, result TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS suggestions(id TEXT PRIMARY KEY, analysis TEXT NOT NULL REFERENCES analyses(id), episode INTEGER NOT NULL, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS suggestion_decisions(id INTEGER PRIMARY KEY, suggestion TEXT UNIQUE NOT NULL REFERENCES suggestions(id), decision TEXT NOT NULL, reason TEXT NOT NULL, annotation INTEGER REFERENCES annotations(id), created TEXT NOT NULL);
"""


def dbopen():
    db = connect()
    db.executescript(SCHEMA)
    return db


class Suggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: Literal[
        "approach",
        "grasp_attempt",
        "transport",
        "release",
        "possible_failure",
        "outcome",
    ]
    start: float = Field(ge=0, allow_inf_nan=False)
    end: float = Field(gt=0, allow_inf_nan=False)
    outcome: Literal["unknown", "success", "failure"] = "unknown"
    explanation: str = Field(min_length=1, max_length=1200)
    evidence: list[str] = Field(min_length=1, max_length=8)


class ModelOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1, max_length=2000)
    suggestions: list[Suggestion] = Field(max_length=8)


def parse_output(raw, duration, evidence):
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    result = ModelOutput.model_validate_json(text)
    available = {x["id"]: x for x in evidence}
    for s in result.suggestions:
        if not s.start < s.end <= duration:
            raise ValueError("Model interval outside episode")
        if any(i not in available for i in s.evidence):
            raise ValueError("Model cited unknown evidence")
        if any(
            not s.start - 0.04 <= available[i]["time"] <= s.end + 0.04
            for i in s.evidence
        ):
            raise ValueError("Cited evidence outside suggested interval")
        if s.label != "outcome" and s.outcome != "unknown":
            raise ValueError(
                "Only outcome suggestions can assign an outcome hypothesis"
            )
    return result.model_dump()


def visual_metrics(rgb, previous=None):
    import cv2

    gray = cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2GRAY)
    result = {
        "luminance_mean": float(gray.mean()),
        "dark_fraction": float((gray < CONFIG["dark_pixel"]).mean()),
        "clipped_fraction": float((gray > CONFIG["clipped_pixel"]).mean()),
        "laplacian_variance": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
    }
    if previous is not None:
        prev = cv2.cvtColor(np.asarray(previous), cv2.COLOR_RGB2GRAY)
        result["adjacent_sample_mae"] = float(
            np.abs(gray.astype(float) - prev.astype(float)).mean()
        )
        flow = cv2.calcOpticalFlowFarneback(prev, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        result["flow_pixels_per_sample"] = float(np.linalg.norm(flow, axis=2).mean())
    return result


def hints(metrics):
    result = []
    for key, rule, threshold, low in [
        ("dark_fraction", "image.dark", 0.8, False),
        ("clipped_fraction", "image.clipped", 0.8, False),
        ("laplacian_variance", "image.low_texture_or_blur", 40, True),
        ("adjacent_sample_mae", "image.similar_samples", 0.2, True),
    ]:
        if key in metrics and (
            (metrics[key] < threshold) if low else (metrics[key] > threshold)
        ):
            result.append(
                {
                    "rule": rule,
                    "observed": metrics[key],
                    "threshold": threshold,
                    "severity": "descriptive",
                    "explanation": "Heuristic review hint. Scene texture, intentional stillness and sampling can explain this value.",
                }
            )
    return result


def signal_metrics(samples, fps):
    t = np.array([x["timestamp"] for x in samples])
    good = (np.diff(t) > 0) & (np.diff(t) <= 1.5 / fps)
    result = {}
    for k in ["observation.state", "action"]:
        a = np.array([x[k] for x in samples], dtype=float)
        if not np.isfinite(a).all():
            raise ValueError("Cannot analyze nonfinite source signals")
        changes = np.abs(np.diff(a, axis=0))[good]
        result[k] = {
            "range": np.ptp(a, axis=0).tolist(),
            "mean_absolute_change": (
                changes.mean(axis=0).tolist() if len(changes) else None
            ),
            "units": "unknown native units",
            "excluded_gap_transitions": int((~good).sum()),
        }
    return result


def list_analyses(eid):
    with dbopen() as db:
        result = rows(
            db, "SELECT * FROM analyses WHERE episode=? ORDER BY created DESC", (eid,)
        )
        for a in result:
            a["result"] = json.loads(a["result"])
            a["suggestions"] = rows(
                db,
                """SELECT s.*,d.decision,d.reason,d.annotation,n.label approved_label,n.start approved_start,n.end approved_end FROM suggestions s LEFT JOIN suggestion_decisions d ON d.suggestion=s.id LEFT JOIN annotations n ON n.id=d.annotation WHERE s.analysis=?""",
                (a["id"],),
            )
            for s in a["suggestions"]:
                s["body"] = json.loads(s["body"])
    return result


def decide(sid, decision, reason, label=None, start=None, end=None):
    if decision not in ["accept", "edit", "reject"] or not reason.strip():
        raise ValueError("Decision and reason are required")
    with dbopen() as db:
        db.execute("BEGIN IMMEDIATE")
        s = db.execute("SELECT * FROM suggestions WHERE id=?", (sid,)).fetchone()
        if not s:
            raise ValueError("Suggestion not found")
        if db.execute(
            "SELECT 1 FROM suggestion_decisions WHERE suggestion=?", (sid,)
        ).fetchone():
            raise ValueError("Suggestion already reviewed")
        body = json.loads(s["body"])
        aid = None
        if decision != "reject":
            duration = db.execute(
                "SELECT duration FROM episodes WHERE id=?", (s["episode"],)
            ).fetchone()[0]
            if decision == "edit":
                if label is None or start is None or end is None:
                    raise ValueError("Edited label and interval are required")
            else:
                label, start, end = body["label"], body["start"], body["end"]
            if (
                not label.strip()
                or len(label) > 100
                or not 0 <= start < end <= duration
            ):
                raise ValueError("Invalid approved interval")
            aid = db.execute(
                "INSERT INTO annotations(episode,start,end,label,note,created) VALUES(?,?,?,?,?,?)",
                (
                    s["episode"],
                    start,
                    end,
                    label.strip(),
                    f"Reviewed suggestion {sid}. {reason.strip()}",
                    now(),
                ),
            ).lastrowid
        db.execute(
            "INSERT INTO suggestion_decisions(suggestion,decision,reason,annotation,created) VALUES(?,?,?,?,?)",
            (sid, decision, reason.strip(), aid, now()),
        )
    return {"annotation": aid}


def snapshot(db, ids):
    # Called under the version publication transaction; provenance is self-contained.
    result = []
    for s in rows(
        db,
        """SELECT s.*,d.decision,d.reason,d.annotation,d.created reviewed_at,a.result FROM suggestions s JOIN suggestion_decisions d ON d.suggestion=s.id JOIN analyses a ON a.id=s.analysis WHERE d.annotation IS NOT NULL ORDER BY s.id""",
    ):
        if s["episode"] in ids:
            s["body"] = json.loads(s["body"])
            s["result"] = json.loads(s["result"])
            result.append(s)
    return result


def preflight():
    if shutil.disk_usage("/").free < 1024**3:
        raise RuntimeError(
            "Inference requires at least 1 GiB internal free space; free space yourself or close other workloads. No cleanup was performed."
        )
    if shutil.disk_usage(root()).free < 2 * 1024**3:
        raise RuntimeError("Analysis needs at least 2 GiB external headroom")
    p = subprocess.run(["memory_pressure"], capture_output=True, text=True, timeout=5)
    m = re.search(r"System-wide memory free percentage:\s*(\d+)", p.stdout)
    if m and int(m[1]) < 25:
        raise RuntimeError(
            "Memory pressure too high for inference; close other memory-intensive apps"
        )


def load_model():
    preflight()
    lockpath = root() / "models/model-lock.json"
    if not lockpath.is_file():
        raise RuntimeError(
            "Model not installed. Run scripts/download_model.py in the analysis environment"
        )
    lock = json.loads(lockpath.read_text())
    path = root() / "models" / MODEL_REVISION
    if lock["revision"] != MODEL_REVISION:
        raise ValueError("Unexpected model revision")
    for f in lock["files"]:
        if digest(path / f["path"]) != f["sha256"]:
            raise ValueError("Model artifact checksum changed")
    import mlx.core as mx

    mx.set_memory_limit(6 * 1024**3)
    mx.set_cache_limit(256 * 1024**2)
    from mlx_vlm import load

    return (*load(str(path)), lock)


def infer(model, processor, sheet, evidence, duration, repair=None):
    from mlx_vlm import generate
    from mlx_vlm.prompt_utils import apply_chat_template

    prompt = (
        "Inspect this contact sheet of a recorded robot pick-and-place attempt. The task is to put a pink Lego brick into a transparent box. "
        "Rows are cameras; columns are increasing episode times. Each tile has an evidence ID and time. "
        "Do not assume task success from the task instruction. Occlusion and sparse frames can make outcome unknown. "
        'Return ONLY JSON, no markdown: {"summary":"...","suggestions":[{"label":"outcome","start":0,"end":'
        + str(duration)
        + ',"outcome":"unknown","explanation":"...","evidence":["side-0","up-7"]}]}. '
        "Allowed labels: approach, grasp_attempt, transport, release, possible_failure, outcome. "
        "For non-outcome labels set outcome to unknown. At most 4 suggestions. Use only listed evidence IDs within the suggested interval. "
        "Times must satisfy 0 <= start < end <= " + str(duration) + ". "
        "Outcome success requires visible evidence of placement in the box, failure requires visible evidence, otherwise unknown. "
        "Do not output confidence scores. Available evidence: "
        + canonical([{"id": x["id"], "time": round(x["time"], 6)} for x in evidence])
    )
    prompt += " Every suggestion MUST contain all six keys: label, start, end, outcome, explanation, evidence. Evidence must be a nonempty list. Provide at most two suggestions, including exactly one outcome."
    if repair:
        prompt += (
            " Your previous response failed validation. Correct its structure and evidence without inventing observations. Previous response: "
            + repair[0]
            + " Validation error: "
            + repair[1]
        )
    formatted = apply_chat_template(processor, model.config, prompt, num_images=1)
    started = time.perf_counter()
    output = generate(
        model,
        processor,
        formatted,
        [str(sheet)],
        max_tokens=CONFIG["max_tokens"],
        temperature=0.0,
        verbose=False,
    )
    raw = output.text if hasattr(output, "text") else str(output)
    return raw, prompt, time.perf_counter() - started


def analyze(eid, mode, job, model_bundle=None):
    started = time.perf_counter()
    e = service.episode(eid)
    with connect() as db:
        assets = rows(db, "SELECT * FROM assets ORDER BY path")
    for a in assets:
        if digest(service.asset_path(a["path"])) != a["sha256"]:
            raise ValueError("Preserved source changed; analysis refused")
    import importlib.metadata as md

    software = {p: md.version(p) for p in ["numpy", "Pillow", "opencv-python"]}
    if mode == "vlm":
        software.update(
            {
                p: md.version(p)
                for p in ["mlx", "mlx-vlm", "transformers", "torch", "torchvision"]
            }
        )
    identity = {
        "implementation_sha256": digest(Path(__file__)),
        "software": software,
        "episode": eid,
        "source_revision": REVISION,
        "assets": assets,
        "config": CONFIG,
        "mode": mode,
        "model_revision": MODEL_REVISION if mode == "vlm" else None,
    }
    rid = hashlib.sha256(canonical(identity).encode()).hexdigest()
    with dbopen() as db:
        if db.execute("SELECT 1 FROM analyses WHERE id=?", (rid,)).fetchone():
            return rid
    directory = root() / "derived/analysis" / rid
    directory.mkdir(parents=True, exist_ok=True)
    evidence = []
    images = {}
    metrics = []
    times = np.linspace(
        0, float(e["samples"][-1]["timestamp"]), CONFIG["samples_per_camera"]
    )
    for c in e["cameras"]:
        previous = None
        for i, t in enumerate(times):
            progress(job, f'decoding episode {eid}: {c["label"]} {i+1}/8')
            rgb, _, timing = decode_details(
                service.media_path(e["metadata"], c["key"]), c["offset"] + float(t)
            )
            rgb = rgb.resize(tuple(CONFIG["image_size"]), Image.Resampling.LANCZOS)
            fid = f'{c["label"]}-{i}'
            file = directory / (fid + ".png")
            rgb.save(file)
            record = {
                "id": fid,
                "camera": c["key"],
                "time": float(t),
                "timing": timing,
                "sha256": digest(file),
                "file": file.name,
            }
            evidence.append(record)
            images[fid] = rgb
            values = visual_metrics(rgb, previous)
            metrics.append(
                {
                    "evidence": fid,
                    "time": float(t),
                    "camera": c["label"],
                    "values": values,
                    "hints": hints(values),
                }
            )
            previous = rgb
    result = {
        "identity": identity,
        "evidence": evidence,
        "diagnostics": metrics,
        "signals": signal_metrics(e["samples"], e["info"]["fps"]),
        "semantic": None,
        "limitations": [
            "Sparse samples can miss events.",
            "Image hints are heuristic.",
            "Units and physical camera synchronization are unknown.",
        ],
    }
    if mode == "vlm":
        selected = [
            x
            for x in evidence
            if int(x["id"].rsplit("-", 1)[1]) in CONFIG["model_evidence_indices"]
        ]
        sheet = Image.new("RGB", (1280, 520), "white")
        draw = ImageDraw.Draw(sheet)
        for n, x in enumerate(selected):
            col = n % 4
            row = n // 4
            sheet.paste(images[x["id"]], (col * 320, row * 260 + 20))
            draw.text(
                (col * 320 + 4, row * 260 + 3),
                f'{x["id"]} | {x["time"]:.3f} s',
                fill="black",
            )
        sheetpath = directory / "contact-sheet.png"
        sheet.save(sheetpath)
        progress(job, f"inference episode {eid}")
        model, processor, lock = model_bundle
        result["model"] = lock
        result["contact_sheet_sha256"] = digest(sheetpath)
        result["attempts"] = []
        repair = None
        for attempt in range(CONFIG["max_attempts"]):
            progress(job, f"inference episode {eid}, attempt {attempt+1}")
            raw, prompt, seconds = infer(
                model, processor, sheetpath, selected, e["duration"], repair
            )
            record = {"raw_output": raw, "prompt": prompt, "seconds": seconds}
            result["attempts"].append(record)
            result["raw_output"], result["prompt"] = raw, prompt
            try:
                result["semantic"] = parse_output(raw, e["duration"], selected)
                break
            except (ValueError, TypeError) as ex:
                record["validation_error"] = str(ex)
                repair = (raw, str(ex))
        result["inference_seconds"] = sum(x["seconds"] for x in result["attempts"])
        if not result["semantic"]:
            result["model_output_error"] = repair[1]
    import importlib.metadata as md

    result["software"] = software
    if mode == "vlm":
        import mlx.core as mx

        result["peak_mlx_memory_bytes"] = mx.get_peak_memory()
    result["seconds"] = time.perf_counter() - started
    result["peak_process_rss_bytes"] = resource.getrusage(
        resource.RUSAGE_SELF
    ).ru_maxrss
    result["cache_condition"] = (
        "OS cache uncontrolled; decoded samples regenerated; model reused within job"
    )
    result["created"] = now()
    progress(job, f"publishing episode {eid}")
    with dbopen() as db:
        db.execute("BEGIN IMMEDIATE")
        active = db.execute(
            "SELECT state,cancel FROM jobs WHERE id=?", (job,)
        ).fetchone()
        if (
            not active
            or active["cancel"]
            or active["state"] in ["interrupted", "cancelled", "failed"]
        ):
            raise InterruptedError("Job no longer owns publication")
        db.execute(
            "INSERT OR IGNORE INTO analyses VALUES(?,?,?,?,?)",
            (rid, eid, mode, canonical(result), now()),
        )
        for i, s in enumerate((result["semantic"] or {}).get("suggestions", [])):
            sid = rid + ":" + str(i)
            db.execute(
                "INSERT OR IGNORE INTO suggestions VALUES(?,?,?,?)",
                (sid, rid, eid, canonical(s)),
            )
    return rid


def progress(job, stage):
    with connect() as db:
        row = db.execute(
            "SELECT completed,total FROM jobs WHERE id=?", (job,)
        ).fetchone()
    service.update_job(
        job, stage, row["completed"] if row else 0, row["total"] if row else 0
    )


def run_job(job):
    with connect() as db:
        row = db.execute("SELECT args FROM jobs WHERE id=?", (job,)).fetchone()
    if not row:
        raise ValueError("Unknown job")
    args = json.loads(row[0])
    ids = args["episodes"]
    mode = args["mode"]
    if mode not in ["diagnostics", "vlm"] or not 1 <= len(ids) <= 50:
        raise ValueError("Invalid analysis request")
    service.update_job(
        job, "loading model" if mode == "vlm" else "starting diagnostics", 0, len(ids)
    )
    load_started = time.perf_counter()
    model = load_model() if mode == "vlm" else None
    print(
        canonical(
            {"model_load_seconds": time.perf_counter() - load_started, "job": job}
        ),
        flush=True,
    )
    for n, eid in enumerate(ids):
        rid = analyze(eid, mode, job, model)
        print(canonical({"episode": eid, "analysis": rid}), flush=True)
        service.update_job(job, "episode complete", n + 1, len(ids))


def supervise(job):
    python = root() / "analysis-venv/bin/python"
    if not python.exists():
        raise RuntimeError(
            "Analysis environment missing. Run scripts/setup_analysis.py"
        )
    log = root() / "runtime" / ("analysis-" + job + ".log")
    env = dict(
        os.environ,
        TMPDIR=str(root() / "tmp"),
        HF_HOME=str(root() / "cache/huggingface"),
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        PYTHONDONTWRITEBYTECODE="1",
        TOKENIZERS_PARALLELISM="false",
        EPISODE_ANALYSIS_PARENT=str(os.getpid()),
    )
    with log.open("w") as out:
        child = subprocess.Popen(
            [str(python), "-B", "-m", "episode.analysis", job],
            stdout=out,
            stderr=out,
            env=env,
        )
        start = time.monotonic()
        try:
            while child.poll() is None:
                with connect() as db:
                    cancel = db.execute(
                        "SELECT cancel FROM jobs WHERE id=?", (job,)
                    ).fetchone()[0]
                if cancel:
                    raise InterruptedError(
                        "Analysis cancelled; completed episode results retained"
                    )
                if shutil.disk_usage("/").free < 512 * 1024**2:
                    raise RuntimeError(
                        "Analysis stopped: internal free space below 512 MiB"
                    )
                if time.monotonic() - start > 3600:
                    raise RuntimeError(
                        "Analysis exceeded one-hour job limit; completed episodes retained"
                    )
                time.sleep(0.5)
            if child.returncode:
                raise RuntimeError("Analysis failed: " + log.read_text()[-2500:])
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()


def main():
    owner = os.environ.get("EPISODE_ANALYSIS_PARENT")

    def guard():
        while owner:
            if os.getppid() != int(owner):
                os._exit(70)
            time.sleep(0.5)

    threading.Thread(target=guard, daemon=True).start()
    with (root() / "runtime/analysis.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another analysis process is active")
        run_job(sys.argv[1])


if __name__ == "__main__":
    main()
