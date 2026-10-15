"""Evaluation requires explicitly supplied human references, never model-as-ground-truth."""

import argparse, json, hashlib
from pathlib import Path
from .storage import canonical, REVISION, now
from .analysis import list_analyses


def evaluate(references, runs, tolerance=0.5):
    if references.get("source_revision") != REVISION:
        raise ValueError("Reference source revision mismatch")
    entries = references.get("episodes", [])
    if len({x["episode"] for x in entries}) != len(entries):
        raise ValueError("Duplicate reference episode")
    confusion = {}
    matched = predicted = expected = correct = covered = total = 0
    for ref in entries:
        if ref.get("role") != "held_out":
            continue
        if (
            ref.get("origin") != "human"
            or not ref.get("reviewer")
            or ref.get("outcome") not in ["success", "failure", "unknown"]
        ):
            raise ValueError(
                "Held-out references require human origin, reviewer and explicit outcome"
            )
        run = runs.get(ref["episode"])
        if not run or run["id"] != ref["analysis_id"]:
            raise ValueError("Reference analysis ID is missing or changed")
        suggestions = (run["result"].get("semantic") or {}).get("suggestions", [])
        outcomes = [s["outcome"] for s in suggestions if s["label"] == "outcome"]
        prediction = outcomes[0] if len(outcomes) == 1 else "unknown"
        key = ref["outcome"] + " -> " + prediction
        confusion[key] = confusion.get(key, 0) + 1
        total += 1
        correct += prediction == ref["outcome"]
        covered += prediction != "unknown"
        if "intervals" in ref:
            gold = ref["intervals"]
            candidate = [s for s in suggestions if s["label"] != "outcome"]
            used = set()
            predicted += len(candidate)
            expected += len(gold)
            for p in candidate:
                options = [
                    (abs(p["start"] - g["start"]) + abs(p["end"] - g["end"]), i)
                    for i, g in enumerate(gold)
                    if i not in used
                    and p["label"] == g["label"]
                    and abs(p["start"] - g["start"]) <= tolerance
                    and abs(p["end"] - g["end"]) <= tolerance
                ]
                if options:
                    used.add(min(options)[1])
                    matched += 1
    return {
        "schema": "episode.analysis-evaluation/1",
        "created": now(),
        "reference_sha256": hashlib.sha256(canonical(references).encode()).hexdigest(),
        "human_reference_episodes": total,
        "status": (
            "measured" if total else "not evaluated: human references not supplied"
        ),
        "outcome_agreement": correct / total if total else None,
        "non_abstaining_coverage": covered / total if total else None,
        "confusion": confusion,
        "interval_tolerance_seconds": tolerance,
        "interval_precision": matched / predicted if predicted else None,
        "interval_recall": matched / expected if expected else None,
        "matched_intervals": matched,
        "predicted_intervals": predicted,
        "reference_intervals": expected,
        "human_review_time_savings": None,
        "limitations": [
            "Small single-task sample; no population accuracy claim.",
            "Human origin is reviewer attestation, not independently verified.",
            "Review-time savings require a separate timed human study.",
        ],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--episodes", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    p.add_argument("--template")
    p.add_argument("--references")
    p.add_argument("--output", required=True)
    a = p.parse_args()
    runs = {
        eid: next((r for r in list_analyses(eid) if r["mode"] == "vlm"), None)
        for eid in a.episodes
    }
    template = {
        "source_revision": REVISION,
        "instructions": "Fill independently from original recordings before reading model suggestions. Do not label model output as human references. Keep role assignments fixed.",
        "episodes": [
            {
                "episode": eid,
                "analysis_id": r["id"],
                "role": "development" if eid < 5 else "held_out",
                "origin": None,
                "reviewer": None,
                "outcome": None,
            }
            for i, (eid, r) in enumerate(runs.items())
            if r
        ],
    }
    if a.template:
        with Path(a.template).open("x") as f:
            f.write(json.dumps(template, indent=2) + "\n")
    references = (
        json.loads(Path(a.references).read_text())
        if a.references
        else {"source_revision": REVISION, "episodes": []}
    )
    report = evaluate(references, runs)
    report["pilot"] = [
        {
            "episode": eid,
            "analysis_id": r["id"],
            "seconds": r["result"]["seconds"],
            "inference_seconds": r["result"].get("inference_seconds"),
            "peak_process_rss_bytes": r["result"]["peak_process_rss_bytes"],
            "peak_mlx_memory_bytes": r["result"].get("peak_mlx_memory_bytes"),
            "attempts": len(r["result"].get("attempts", [])),
            "suggestions": len(r["suggestions"]),
            "model_output_error": r["result"].get("model_output_error"),
        }
        for eid, r in runs.items()
        if r
    ]
    Path(a.output).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
