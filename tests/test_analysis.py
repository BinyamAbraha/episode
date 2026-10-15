import json
import numpy as np
import pytest
from PIL import Image
from episode import analysis as a, service, storage


def output(**changes):
    s = {
        "label": "outcome",
        "start": 0,
        "end": 0.4,
        "outcome": "unknown",
        "explanation": "Object occluded",
        "evidence": ["side-0"],
    }
    s.update(changes)
    return json.dumps({"summary": "Sparse evidence", "suggestions": [s]})


def test_strict_model_evidence():
    evidence = [{"id": "side-0", "time": 0}]
    assert (
        a.parse_output(output(), 0.4, evidence)["suggestions"][0]["outcome"]
        == "unknown"
    )
    for bad in [
        output(end=9),
        output(evidence=["invented"]),
        output(start=0.2),
        output(label="grasp_attempt", outcome="success"),
        output(start=float("nan")),
    ]:
        with pytest.raises(ValueError):
            a.parse_output(bad, 0.4, evidence)


def test_diagnostics_controlled_images():
    pytest.importorskip("cv2")
    black = Image.new("RGB", (320, 240))
    values = a.visual_metrics(black, black)
    rules = {h["rule"] for h in a.hints(values)}
    assert {"image.dark", "image.low_texture_or_blur", "image.similar_samples"} <= rules
    white = Image.new("RGB", (320, 240), "white")
    assert "image.clipped" in {h["rule"] for h in a.hints(a.visual_metrics(white))}
    assert values["flow_pixels_per_sample"] == 0


def seed_suggestion():
    body = json.loads(output())["suggestions"][0]
    with a.dbopen() as db:
        db.execute(
            "INSERT INTO analyses VALUES(?,?,?,?,?)",
            (
                "a" * 64,
                0,
                "vlm",
                storage.canonical(
                    {"identity": {"source_revision": storage.REVISION}, "evidence": []}
                ),
                storage.now(),
            ),
        )
        db.execute(
            "INSERT INTO suggestions VALUES(?,?,?,?)",
            ("a" * 64 + ":0", "a" * 64, 0, storage.canonical(body)),
        )
    return "a" * 64 + ":0"


def test_decision_atomic_and_version_immutable(imported):
    sid = seed_suggestion()
    old = service.create_version("before", {})
    assert service.has_pending(0)
    result = a.decide(sid, "edit", "Human corrected interval", "reviewed grasp", 0, 0.2)
    assert result["annotation"]
    assert not service.has_pending(0)
    assert service.catalog({"annotation_label": "reviewed grasp"})[0]["id"] == 0
    assert service.version(old)["analysis_provenance"] == []
    new = service.create_version("after", {})
    assert service.version(new)["analysis_provenance"][0]["decision"] == "edit"
    with pytest.raises(ValueError, match="already reviewed"):
        a.decide(sid, "accept", "again")
    assert service.episode(0)["reviews"] == []


def test_bad_decision_rolls_back(imported):
    sid = seed_suggestion()
    with pytest.raises(ValueError):
        a.decide(sid, "edit", "bad bounds", "x", 0, 900)
    assert service.episode(0)["annotations"] == []
    assert service.has_pending(0)
    a.decide(sid, "reject", "insufficient evidence")
    assert service.episode(0)["annotations"] == []


def test_gap_changes_excluded():
    data = [
        {"timestamp": t, "observation.state": [v], "action": [v, 0]}
        for t, v in [(0, 0), (0.03, 1), (1, 1000)]
    ]
    result = a.signal_metrics(data, 30)
    assert result["action"]["mean_absolute_change"] == [1, 0]
    assert result["action"]["excluded_gap_transitions"] == 1


def test_atomic_analysis_retry_and_source_preservation(imported, monkeypatch):
    pytest.importorskip("cv2")
    monkeypatch.setattr(
        a,
        "decode_details",
        lambda p, t: (
            Image.new("RGB", (640, 480)),
            b"",
            {"decoded_pts": t, "error_seconds": 0},
        ),
    )
    job = service.enqueue("analyze", {"episodes": [0], "mode": "diagnostics"})
    before = {
        r["path"]: storage.digest(service.asset_path(r["path"]))
        for r in storage.rows(storage.connect(), "SELECT * FROM assets")
    }
    rid = a.analyze(0, "diagnostics", job)
    assert a.analyze(0, "diagnostics", job) == rid
    assert len(a.list_analyses(0)) == 1
    assert before == {p: storage.digest(service.asset_path(p)) for p in before}
    real = service.update_job

    def crash(job, stage, *args):
        if stage.startswith("publishing"):
            raise InterruptedError("fixture crash")
        return real(job, stage, *args)

    monkeypatch.setattr(service, "update_job", crash)
    with pytest.raises(InterruptedError):
        a.analyze(1, "diagnostics", job)
    assert a.list_analyses(1) == []
    assert len(a.list_analyses(0)) == 1


def test_evaluation_requires_human_references():
    from episode.evaluation import evaluate

    refs = {"source_revision": storage.REVISION, "episodes": []}
    assert evaluate(refs, {})["outcome_agreement"] is None
    refs["episodes"] = [
        {
            "episode": 0,
            "role": "held_out",
            "origin": "model",
            "reviewer": "model",
            "outcome": "success",
            "analysis_id": "x",
        }
    ]
    with pytest.raises(ValueError, match="human"):
        evaluate(refs, {})
    refs["episodes"][0]["origin"] = "human"
    refs["episodes"][0]["reviewer"] = "fixture reviewer"
    report = evaluate(
        refs,
        {
            0: {
                "id": "x",
                "result": {
                    "semantic": {
                        "suggestions": [{"label": "outcome", "outcome": "unknown"}]
                    }
                },
            }
        },
    )
    assert report["outcome_agreement"] == 0
    assert report["non_abstaining_coverage"] == 0


def test_analysis_api_boundaries(imported):
    from fastapi.testclient import TestClient
    from episode.api import app

    client = TestClient(app)
    assert (
        client.post(
            "/api/analysis-jobs", json={"episodes": [900], "mode": "vlm"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/analysis-jobs", json={"episodes": [], "mode": "vlm"}
        ).status_code
        == 422
    )
    assert client.get("/api/analyses/not-a-hash/evidence/x.png").status_code == 404
    sid = seed_suggestion()
    assert (
        client.post(
            "/api/suggestions/" + sid + "/decision",
            json={"decision": "edit", "reason": "bad"},
        ).status_code
        == 400
    )
    assert service.episode(0)["annotations"] == []


def test_cancel_terminates_owned_subprocess(imported, monkeypatch):
    import sys, subprocess

    python = imported / "analysis-venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\nexec /bin/sleep 30\n")
    python.chmod(0o755)
    job = service.enqueue("analyze", {"episodes": [0], "mode": "diagnostics"})
    with storage.connect() as db:
        db.execute("UPDATE jobs SET cancel=1 WHERE id=?", (job,))
    children = []
    original = subprocess.Popen

    def capture(*args, **kwargs):
        child = original(*args, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(a.subprocess, "Popen", capture)
    with pytest.raises(InterruptedError, match="cancelled"):
        a.supervise(job)
    assert len(children) == 1 and children[0].poll() is not None
    assert a.list_analyses(0) == []


def test_model_repair_retains_attempts_and_rejects_unrepaired_output(
    imported, monkeypatch
):
    pytest.importorskip("cv2")
    monkeypatch.setattr(
        a,
        "decode_details",
        lambda p, t: (
            Image.new("RGB", (640, 480)),
            b"",
            {"decoded_pts": t, "error_seconds": 0},
        ),
    )
    responses = iter(["not json", output()])
    monkeypatch.setattr(
        a, "infer", lambda *args: (next(responses), "fixture prompt", 0.01)
    )
    job = service.enqueue("analyze", {"episodes": [0], "mode": "vlm"})
    a.analyze(0, "vlm", job, (None, None, {"fixture": True}))
    result = a.list_analyses(0)[0]
    assert len(result["result"]["attempts"]) == 2
    assert result["result"]["attempts"][0]["raw_output"] == "not json"
    assert len(result["suggestions"]) == 1
    monkeypatch.setattr(a, "infer", lambda *args: ("not json", "fixture prompt", 0.01))
    a.analyze(1, "vlm", job, (None, None, {"fixture": True}))
    failed = a.list_analyses(1)[0]
    assert failed["result"]["model_output_error"]
    assert failed["suggestions"] == []
