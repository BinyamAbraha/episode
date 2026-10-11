"""Measured local integration benchmark. Run with Episode API and worker active."""

import sys, os, time, json, platform, statistics, resource, subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from episode.storage import root, source_root, connect, rows, now, REVISION
from episode.service import enqueue, version
from episode.consumer import VersionDataset

url = os.environ.get("EPISODE_URL", "http://127.0.0.1:8765")
client = httpx.Client(base_url=url, timeout=60)


def measure(fn, n):
    samples = []
    for _ in range(n):
        t = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t) * 1000)
    ordered = sorted(samples[1:])
    return {
        "first_measured_ms": samples[0],
        "repeat_median_ms": statistics.median(samples[1:]),
        "repeat_p95_ms": ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))],
        "samples_ms": samples,
        "runs": n,
        "cache": "first measured call and subsequent repeats; OS and app caches not flushed",
    }


def get(path):
    r = client.get(path)
    r.raise_for_status()
    return r


versions = client.get("/api/versions").json()
with connect() as db:
    candidates = rows(db, "SELECT id,manifest FROM versions ORDER BY created")
full = next(
    v["id"] for v in candidates if len(json.loads(v["manifest"])["episodes"]) == 50
)
manifest = version(full)
results = {
    "generated": now(),
    "hardware": {
        "processor": subprocess.check_output(
            ["sysctl", "-n", "machdep.cpu.brand_string"], text=True
        ).strip(),
        "memory_bytes": int(
            subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)
        ),
        "os": platform.mac_ver()[0],
        "architecture": platform.machine(),
    },
    "software": {
        "python": platform.python_version(),
        "ffmpeg": subprocess.check_output(
            ["ffmpeg", "-version"], text=True
        ).splitlines()[0],
        "packages": subprocess.check_output(
            [sys.executable, "-m", "pip", "freeze"], text=True
        ).splitlines(),
    },
    "dataset": {
        "revision": REVISION,
        "version": full,
        "episodes": 50,
        "samples": 11939,
        "cameras": 2,
        "source_bytes": sum(a["bytes"] for a in manifest["assets"]),
    },
    "concurrency": 1,
    "cold_cache": "Not measured. No machine-wide cache flush performed. First measured calls are not claimed as cold.",
    "metrics": {},
}
for name, path, n in [
    ("catalog_filter", "/api/episodes?review=accepted", 21),
    ("episode_open", "/api/episodes/25", 11),
    ("decoded_frame", "/api/episodes/25/frame/observation.images.side?time=0.5", 9),
]:
    results["metrics"][name] = measure(lambda: get(path), n)
loader = VersionDataset(manifest, source_root())
results["metrics"]["decoded_training_window"] = measure(
    lambda: next(loader.windows("train", first_per_episode=True)), 5
)
start = time.perf_counter()
job = enqueue(args={"limit": 50})
while time.perf_counter() - start < 180:
    with connect() as db:
        row = db.execute("SELECT * FROM jobs WHERE id=?", (job,)).fetchone()
    if row["state"] in ["failed", "cancelled", "interrupted"]:
        raise RuntimeError(dict(row))
    if row["state"] == "succeeded":
        break
    time.sleep(0.1)
else:
    raise RuntimeError("Worker benchmark timed out; check worker ownership")
elapsed = time.perf_counter() - start
results["metrics"]["repeat_import"] = {
    "seconds": elapsed,
    "episodes_per_second": 50 / elapsed,
    "samples_per_second": 11939 / elapsed,
    "scope": "queue to completed reimport; assets, previews and full-stream scan caches already present; includes hash checks, signal rules, PTS association and endpoint decodes",
    "job": job,
}
results["memory"] = {
    "benchmark_process_peak_rss_bytes": resource.getrusage(
        resource.RUSAGE_SELF
    ).ru_maxrss,
    "scope": "macOS ru_maxrss bytes for benchmark Python process; excludes API and worker. No whole-application peak claim.",
}
results["disk"] = {
    name: sum(p.stat().st_size for p in (root() / name).rglob("*") if p.is_file())
    for name in [
        "sources",
        "derived",
        "cache",
        "venv",
        "web-tools",
        "runtime",
        "evidence",
    ]
}
path = root() / "evidence/benchmark.json"
path.write_text(json.dumps(results, indent=2) + "\n")
print(json.dumps(results, indent=2))
