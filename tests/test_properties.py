import json, copy, hashlib
import numpy as np
import pytest
from episode import storage, service, worker
from episode.validation import validate
from episode.fixtures import base, demonstrations


def test_independent_dimensions_and_faults():
    data, info, meta = base()
    assert validate(data, info, meta) == []
    expected = {
        "timestamp gap": "time.gap",
        "shifted timestamp origin": "time.origin",
        "nonfinite action": "feature.finite",
        "duplicate sample identity": "sample.duplicate",
    }
    for f in demonstrations():
        assert expected[f["name"]] in f["rules"]
    data[2]["action"] = [1, 2]
    assert any(f["rule"] == "feature.dimension" for f in validate(data, info, meta))


def test_schema_boundary_and_order():
    data, info, meta = base()
    data[1]["timestamp"] = data[0]["timestamp"]
    meta["length"] = 99
    rules = {f["rule"] for f in validate(data, info, meta)}
    assert {"time.order", "episode.boundary"} <= rules
    assert validate([], info, meta)[0]["rule"] == "schema.required"


def test_idempotency_preserves_source(imported):
    before = {
        a["path"]: a["sha256"]
        for a in storage.rows(storage.connect(), "SELECT * FROM assets")
    }
    service.import_source(service.enqueue(), 6)
    assert len(service.catalog()) == 6
    assert before == {p: storage.digest(service.asset_path(p)) for p in before}


def test_changed_asset_is_conflict(imported):
    service.asset_path("data/chunk-000/file-000.parquet").write_bytes(b"changed")
    with pytest.raises(ValueError, match="Changed preserved"):
        service.import_source(service.enqueue(), 6)
    assert len(service.catalog()) == 6


def test_interruption_before_publish_has_no_partial_catalog(store, monkeypatch):
    original = service.update_job

    def update(id, stage, *a):
        if stage == "publishing":
            raise RuntimeError("injected interruption")
        return original(id, stage, *a)

    monkeypatch.setattr(service, "update_job", update)
    with pytest.raises(RuntimeError, match="injected"):
        service.import_source(service.enqueue(), 6)
    assert service.catalog() == []
    monkeypatch.setattr(service, "update_job", original)
    service.import_source(service.enqueue(), 6)
    assert len(service.catalog()) == 6


def test_restart_and_cancellation(store):
    old = service.enqueue()
    cancelled = service.enqueue()
    with storage.connect() as db:
        db.execute("UPDATE jobs SET state='running' WHERE id=?", (old,))
        db.execute("UPDATE jobs SET cancel=1 WHERE id=?", (cancelled,))
    worker.run(once=True)
    with storage.connect() as db:
        assert (
            db.execute("SELECT state FROM jobs WHERE id=?", (old,)).fetchone()[0]
            == "interrupted"
        )
        assert (
            db.execute("SELECT state FROM jobs WHERE id=?", (cancelled,)).fetchone()[0]
            == "cancelled"
        )
    assert service.catalog() == []


def test_missing_storage_does_not_recreate(store):
    (store / ".episode-storage").unlink()
    with pytest.raises(RuntimeError, match="unavailable"):
        storage.connect()
    assert not (store / ".episode-storage").exists()


def test_missing_asset_fails_without_publication(store, monkeypatch):
    service.asset_path("videos/observation.images.side/chunk-000/file-000.mp4").unlink()

    def unavailable(*a, **k):
        raise OSError("injected offline source")

    monkeypatch.setattr(service.urllib.request, "urlopen", unavailable)
    with pytest.raises(OSError, match="offline"):
        service.import_source(service.enqueue(), 6)
    assert service.catalog() == []


def test_duplicate_episode_metadata_rejected(store):
    import pyarrow.parquet as pq, pyarrow as pa

    path = service.asset_path("meta/episodes/chunk-000/file-000.parquet")
    table = pq.read_table(path).to_pylist()
    table[1]["episode_index"] = 0
    pq.write_table(pa.Table.from_pylist(table), path)
    inv = storage.source_root() / "inventory.json"
    value = json.loads(inv.read_text())
    for a in value:
        if a["path"] == "meta/episodes/chunk-000/file-000.parquet":
            a.update(size=path.stat().st_size, lfs={"oid": storage.digest(path)})
    inv.write_text(json.dumps(value))
    service.SOURCE_LOCK.write_text(
        json.dumps(
            {
                "revision": storage.REVISION,
                "assets": [
                    {"path": a["path"], "bytes": a["size"], "sha256": a["lfs"]["oid"]}
                    for a in value
                ],
            }
        )
    )
    with pytest.raises(ValueError, match="Duplicate episode"):
        service.import_source(service.enqueue(), 6)
    assert not service.catalog()


def test_versions_freeze_review_and_annotations(imported):
    service.review(0, "accepted", "unknown", "Checked camera coverage")
    service.annotate(0, 0, 0.2, "approach", "human note")
    id = service.create_version("first", {})
    before = storage.canonical(service.version(id))
    service.review(0, "excluded", "unknown", "Changed curation purpose")
    service.annotate(0, 0.2, 0.3, "revisit", "new note")
    assert storage.canonical(service.version(id)) == before
    newer = service.version(service.create_version("second", {}))
    assert 0 not in newer["episodes"]
    assert 0 in service.version(id)["episodes"]


def test_deterministic_family_splits():
    e = [{"id": i, "family": str(i // 2)} for i in range(20)]
    a = service.split_groups(e, 17)
    b = service.split_groups(list(reversed(e)), 17)
    assert a == b
    assert all(
        any(i in ids and i + 1 in ids for ids in a.values()) for i in range(0, 20, 2)
    )
    assert len(set(sum(a.values(), []))) == 20
    with pytest.raises(ValueError):
        service.split_groups(e[:4], 17)


def test_train_only_normalization_and_consumer(imported):
    id = service.create_version("consumer", {})
    v = service.version(id)
    data = [
        r["observation.state"]
        for eid in v["split"]["membership"]["train"]
        for r in service.episode(eid)["samples"]
    ]
    np.testing.assert_allclose(
        v["normalization"]["observation.state"]["mean"], np.mean(data, axis=0)
    )
    result = service.verify_version(id)
    assert result["status"] == "passed"
    assert result["decoded_images"] == 48
    assert result["batch_shapes"]["images"] == [1, 2, 4, 480, 640, 3]
    assert result["batch_shapes"]["normalized_action"] == [1, 4, 3]
    assert result["validated_signal_windows"] == 18


def test_manifest_hash_rejects_mutation(imported):
    id = service.create_version("protected", {})
    with storage.connect() as db:
        db.execute("UPDATE versions SET manifest='{}' WHERE id=?", (id,))
    with pytest.raises(ValueError, match="hash mismatch"):
        service.version(id)


def test_path_traversal(store):
    with pytest.raises(ValueError):
        service.asset_path("../../secrets")


def test_exported_consumer_without_catalog(imported, tmp_path):
    from episode.consumer import VersionDataset

    id = service.create_version("exported", {})
    manifest = service.version(id)
    path = tmp_path / "export.json"
    path.write_text(storage.canonical(manifest))
    loader = VersionDataset(path, storage.source_root())
    batches = list(loader.windows("train", decode_images=False))
    assert batches and all(
        b["episode"] in manifest["split"]["membership"]["train"] for b in batches
    )
    assert all(
        b["state"].dtype == np.float32 and b["normalized_state"].dtype == np.float32
        for b in batches
    )
    assert all(
        b["frame_indices"]
        == list(range(b["frame_indices"][0], b["frame_indices"][0] + 4))
        for b in batches
    )


def test_api_security_and_input_constraints(imported, monkeypatch):
    from fastapi.testclient import TestClient
    from episode.api import app

    client = TestClient(app)
    assert (
        client.post(
            "/api/episodes/0/review",
            json={"status": "accepted", "reason": "test"},
            headers={"origin": "https://untrusted.example"},
        ).status_code
        == 403
    )
    assert (
        client.get("/api/episodes", headers={"host": "untrusted.example"}).status_code
        == 400
    )
    assert (
        client.post(
            "/api/episodes/0/annotations",
            json={"start": 0.3, "end": 0.1, "label": "bad"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/episodes/0/review", json={"status": "invalid", "reason": "bad"}
        ).status_code
        == 422
    )
    assert client.get("/api/missing").status_code == 404


def test_media_offset_association_detects_shift(store, monkeypatch):
    monkeypatch.setattr(
        service, "frame_times", lambda p: [10 + i / 30 for i in range(72)]
    )
    service.import_source(service.enqueue(), 6)
    assert all(e["errors"] for e in service.catalog())
    with pytest.raises(ValueError, match="three"):
        service.create_version("cannot publish invalid", {})


def test_validation_run_is_published_atomically(imported):
    with storage.connect() as db:
        reports = storage.rows(db, "SELECT * FROM validation_runs")
    assert len(reports) == 1
    report = json.loads(reports[0]["result"])
    assert report["episodes"] == 6 and report["samples"] == 72
    assert report["findings"] == [] and report["asset_hashes"]


def test_cleanup_never_removes_retained_source(imported, monkeypatch):
    import os, time
    from episode import retention

    monkeypatch.setattr(retention, "SOURCE_LOCK", service.SOURCE_LOCK)
    service.create_version("retained", {})
    p = service.asset_path("data/chunk-000/file-000.parquet")
    partial = p.with_suffix(".parquet.partial")
    partial.write_bytes(b"unfinished")
    os.utime(partial, (time.time() - 7200, time.time() - 7200))
    unrelated = storage.root() / "unrelated.partial"
    unrelated.write_bytes(b"preserve")
    preview = retention.cleanup_staging()
    assert partial.exists() and len(preview["staging"]) == 1
    retention.cleanup_staging(True)
    assert not partial.exists() and p.exists() and unrelated.exists()


def test_unknown_semantics_are_explicit(imported):
    meta = service.episode(0)["feature_metadata"]
    assert meta["robot_type"] == "fixture" and meta["session_identity"] is None
    assert meta["features"]["action"]["shape"] == [3]
    assert meta["features"]["action"]["units"] is None
    assert meta["features"]["action"]["control_semantics"] is None


def test_changed_assets_block_version_publication(imported):
    service.asset_path(
        "videos/observation.images.side/chunk-000/file-000.mp4"
    ).write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed source"):
        service.create_version("blocked", {})
    with storage.connect() as db:
        assert db.execute("SELECT count(*) FROM versions").fetchone()[0] == 0


def test_cli_review_and_annotation(imported, monkeypatch, capsys):
    from episode.cli import main

    monkeypatch.setattr(
        "sys.argv",
        ["episode", "review", "0", "accepted", "--reason", "CLI fixture check"],
    )
    main()
    monkeypatch.setattr(
        "sys.argv", ["episode", "annotate", "0", "0", "0.2", "approach"]
    )
    main()
    assert service.episode(0)["reviews"][0]["status"] == "accepted"
    assert service.episode(0)["annotations"][0]["label"] == "approach"


def test_worker_waits_for_missing_storage_without_recreating_it(store, monkeypatch):
    attempts = []
    original = worker.connect

    def reconnect():
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("Episode storage is unavailable")
        return original()

    monkeypatch.setattr(worker, "connect", reconnect)
    monkeypatch.setattr(worker.time, "sleep", lambda _: None)
    with worker.durable_connect() as db:
        assert db.execute("SELECT count(*) FROM episodes").fetchone()[0] == 0
    assert len(attempts) == 2
    attempts.clear()
    with pytest.raises(RuntimeError, match="unavailable"):
        worker.durable_connect(once=True)
