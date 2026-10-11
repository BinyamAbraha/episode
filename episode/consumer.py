"""Standalone manifest consumer. No catalog or mutable annotation dependency."""

import json, hashlib
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
from .storage import canonical, digest
from .media import decode_details


class VersionDataset:
    def __init__(self, manifest, source_root, verify_hashes=True):
        self.manifest = (
            json.loads(Path(manifest).read_text())
            if isinstance(manifest, (str, Path))
            else manifest
        )
        self.root = Path(source_root).resolve()
        self.version = hashlib.sha256(canonical(self.manifest).encode()).hexdigest()
        if self.manifest["schema"] != "episode.version/1":
            raise ValueError("Unsupported manifest schema")
        self.info = json.loads(self.path("meta/info.json").read_text())
        self.metadata = {
            m["episode_index"]: m
            for m in pq.read_table(
                self.path("meta/episodes/chunk-000/file-000.parquet")
            ).to_pylist()
        }
        membership = self.manifest["split"]["membership"]
        flat = sum(membership.values(), [])
        if len(set(flat)) != len(flat) or set(flat) != set(self.manifest["episodes"]):
            raise ValueError("Invalid split membership")
        if verify_hashes:
            for a in self.manifest["assets"]:
                if digest(self.path(a["path"])) != a["sha256"]:
                    raise ValueError("Version asset changed: " + a["path"])

    def path(self, relative):
        p = (self.root / relative).resolve()
        if not p.is_relative_to(self.root):
            raise ValueError("Invalid manifest asset path")
        return p

    def windows(self, split, decode_images=True, first_per_episode=False):
        if split not in ["train", "validation", "test"]:
            raise ValueError("Unknown split")
        width = self.manifest["transforms"]["window"]
        stride = self.manifest["transforms"]["stride"]
        for eid in self.manifest["split"]["membership"][split]:
            m = self.metadata[eid]
            table = pq.read_table(
                self.path(
                    f'data/chunk-{m["data/chunk_index"]:03d}/file-{m["data/file_index"]:03d}.parquet'
                ),
                filters=[("episode_index", "=", eid)],
            )
            data = table.to_pylist()
            for start in range(0, len(data) - width + 1, stride):
                chunk = data[start : start + width]
                t = np.array([r["timestamp"] for r in chunk], dtype=np.float64)
                if np.any(np.diff(t) <= 0) or np.any(
                    np.diff(t)
                    > self.manifest["rules"]["gap_periods"] / self.info["fps"]
                ):
                    continue
                if any(r["episode_index"] != eid for r in chunk):
                    raise ValueError("Window crosses episode")
                arrays = {
                    k: np.array([r[k] for r in chunk], dtype=np.float32)
                    for k in ["observation.state", "action"]
                }
                normalized = {}
                for k, a in arrays.items():
                    if (
                        a.shape != (width, *self.info["features"][k]["shape"])
                        or not np.isfinite(a).all()
                    ):
                        raise ValueError("Invalid consumer feature " + k)
                    stats = self.manifest["normalization"][k]
                    normalized[k] = (
                        (a - np.asarray(stats["mean"])) / np.asarray(stats["std"])
                    ).astype(np.float32)
                out = {
                    "episode": eid,
                    "split": split,
                    "frame_indices": [r["frame_index"] for r in chunk],
                    "timestamps": t,
                    "state": arrays["observation.state"],
                    "action": arrays["action"],
                    "normalized_state": normalized["observation.state"],
                    "normalized_action": normalized["action"],
                    "mask": np.ones(width, dtype=bool),
                }
                if decode_images:
                    images = []
                    timing = []
                    for camera in ["observation.images.side", "observation.images.up"]:
                        p = self.path(
                            f'videos/{camera}/chunk-{m[f"videos/{camera}/chunk_index"]:03d}/file-{m[f"videos/{camera}/file_index"]:03d}.mp4'
                        )
                        seq = []
                        for row in chunk:
                            image, _, association = decode_details(
                                p,
                                m[f"videos/{camera}/from_timestamp"] + row["timestamp"],
                            )
                            a = np.asarray(image)
                            if (
                                a.shape != tuple(self.info["features"][camera]["shape"])
                                or a.dtype != np.uint8
                            ):
                                raise ValueError("Image schema mismatch")
                            seq.append(a)
                            timing.append(association)
                        images.append(np.stack(seq))
                    out["images"] = np.stack(images)
                    out["timing"] = timing
                yield out
                if first_per_episode:
                    break
