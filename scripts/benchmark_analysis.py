"""Summarize executed analysis runs. No synthetic timing or semantic accuracy."""

import sys, json, platform, subprocess, statistics
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from episode.storage import root, connect, rows, now
from episode.analysis import list_analyses

r = root()
diagnostics = []
pilot = []
for eid in range(50):
    runs = list_analyses(eid)
    d = next((x for x in runs if x["mode"] == "diagnostics"), None)
    if d:
        diagnostics.append(d)
    if eid < 5:
        v = next((x for x in runs if x["mode"] == "vlm"), None)
        if v:
            pilot.append(v)
hints = {}
for d in diagnostics:
    for sample in d["result"]["diagnostics"]:
        for h in sample["hints"]:
            hints[h["rule"]] = hints.get(h["rule"], 0) + 1
sizes = {}
for name in ["analysis-venv", "models", "derived/analysis"]:
    sizes[name] = (
        int(subprocess.check_output(["du", "-sk", str(r / name)], text=True).split()[0])
        * 1024
    )
with connect() as db:
    jobs = rows(
        db,
        "SELECT id,args,state,stage,completed,total,created,updated FROM jobs WHERE kind='analyze' ORDER BY created",
    )
record = {
    "generated": now(),
    "hardware": {
        "chip": subprocess.check_output(
            ["sysctl", "-n", "machdep.cpu.brand_string"], text=True
        ).strip(),
        "memory_bytes": int(
            subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)
        ),
        "platform": platform.platform(),
    },
    "concurrency": 1,
    "cache_condition": "OS cache uncontrolled. Model loaded once and reused within each pilot job. No cold-cache claim.",
    "diagnostics": {
        "episodes": len(diagnostics),
        "decoded_samples": sum(len(d["result"]["evidence"]) for d in diagnostics),
        "episode_processing_seconds_sum": sum(
            d["result"]["seconds"] for d in diagnostics
        ),
        "episode_processing_seconds_median": statistics.median(
            d["result"]["seconds"] for d in diagnostics
        ),
        "descriptive_hint_counts": hints,
        "analysis_ids": [d["id"] for d in diagnostics],
    },
    "pilot": {
        "episodes": len(pilot),
        "valid_outputs": sum(d["result"]["semantic"] is not None for d in pilot),
        "suggestions": sum(len(d["suggestions"]) for d in pilot),
        "inference_seconds": [d["result"]["inference_seconds"] for d in pilot],
        "peak_mlx_memory_bytes": max(
            d["result"].get("peak_mlx_memory_bytes", 0) for d in pilot
        ),
        "peak_process_rss_bytes": max(
            d["result"]["peak_process_rss_bytes"] for d in pilot
        ),
        "analysis_ids": [d["id"] for d in pilot],
    },
    "allocated_disk_bytes": sizes,
    "jobs": jobs,
    "semantic_evaluation": "Not evaluated: no human references",
    "review_time_savings": "Not measured",
    "limits": [
        "RSS and MLX allocator peaks describe different accounting domains; do not add them as total system RAM.",
        "Processing sums exclude model loading, queueing and worker startup.",
        "Sparse diagnostics cannot establish defects or task outcomes.",
    ],
}
Path("evidence/analysis-benchmark.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps({k: v for k, v in record.items() if k not in ["jobs"]}, indent=2))
