import hashlib, json
from pathlib import Path
import pytest
import pyarrow as pa
import pyarrow.parquet as pq
from PIL import Image
from episode import storage, service, consumer


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "ROOT", tmp_path)
    (tmp_path / ".episode-storage").write_text("test-owned")
    for d in ["runtime", "derived", "sources"]:
        (tmp_path / d).mkdir()
    source = tmp_path / "sources" / storage.REVISION
    source.mkdir()
    info = {
        "codebase_version": "v3.0",
        "fps": 30,
        "robot_type": "fixture",
        "features": {
            "observation.state": {
                "shape": [2],
                "names": ["x", "y"],
                "dtype": "float32",
            },
            "action": {"shape": [3], "names": ["a", "b", "c"], "dtype": "float32"},
        },
    }
    for camera in service.CAMERAS:
        info["features"][camera] = {"shape": [480, 640, 3], "dtype": "video"}
    data = []
    metadata = []
    for eid in range(6):
        for i in range(12):
            data.append(
                {
                    "episode_index": eid,
                    "frame_index": i,
                    "index": eid * 12 + i,
                    "task_index": 0,
                    "timestamp": i / 30,
                    "observation.state": [eid + i / 10, 1.0],
                    "action": [eid + i / 5, 0.0, 1.0],
                }
            )
        m = {
            "episode_index": eid,
            "data/chunk_index": 0,
            "data/file_index": 0,
            "dataset_from_index": eid * 12,
            "dataset_to_index": (eid + 1) * 12,
            "length": 12,
            "tasks": ["fixture pick"],
        }
        for camera in service.CAMERAS:
            m.update(
                {
                    f"videos/{camera}/chunk_index": 0,
                    f"videos/{camera}/file_index": 0,
                    f"videos/{camera}/from_timestamp": eid * 0.4,
                    f"videos/{camera}/to_timestamp": (eid + 1) * 0.4,
                }
            )
        metadata.append(m)
    schema = pa.schema(
        [
            ("episode_index", pa.int64()),
            ("frame_index", pa.int64()),
            ("index", pa.int64()),
            ("task_index", pa.int64()),
            ("timestamp", pa.float32()),
            ("observation.state", pa.list_(pa.float32())),
            ("action", pa.list_(pa.float32())),
        ]
    )
    for path in ["data/chunk-000", "meta/episodes/chunk-000"]:
        (source / path).mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pylist(data, schema=schema),
        source / "data/chunk-000/file-000.parquet",
    )
    pq.write_table(
        pa.Table.from_pylist(metadata),
        source / "meta/episodes/chunk-000/file-000.parquet",
    )
    (source / "meta/info.json").write_text(json.dumps(info))
    for camera in service.CAMERAS:
        p = source / f"videos/{camera}/chunk-000/file-000.mp4"
        p.parent.mkdir(parents=True)
        p.write_bytes(b"deterministic fake media")
    inventory = [
        {
            "type": "file",
            "path": str(p.relative_to(source)),
            "size": p.stat().st_size,
            "lfs": {"oid": storage.digest(p)},
        }
        for p in source.rglob("*")
        if p.is_file()
    ]
    (source / "inventory.json").write_text(json.dumps(inventory))
    lock = tmp_path / "source-lock.json"
    lock.write_text(
        json.dumps(
            {
                "revision": storage.REVISION,
                "assets": [
                    {"path": a["path"], "bytes": a["size"], "sha256": a["lfs"]["oid"]}
                    for a in inventory
                ],
            }
        )
    )
    monkeypatch.setattr(service, "SOURCE_LOCK", lock)
    monkeypatch.setattr(service, "frame_times", lambda p: [i / 30 for i in range(72)])
    monkeypatch.setattr(service, "validate_stream", lambda p, shape: {"frames": 72})
    monkeypatch.setattr(service, "probe", lambda p: {"format": {"duration": "2.4"}})
    monkeypatch.setattr(service, "preview", lambda p: p)
    monkeypatch.setattr(
        service, "decode", lambda p, t: (Image.new("RGB", (640, 480)), b"fixture")
    )
    monkeypatch.setattr(
        consumer,
        "decode_details",
        lambda p, t: (
            Image.new("RGB", (640, 480)),
            b"fixture",
            {"error_seconds": 0, "decoded_pts": t},
        ),
    )
    return tmp_path


@pytest.fixture
def imported(store):
    job = service.enqueue(args={"limit": 6})
    service.import_source(job, 6)
    return store
