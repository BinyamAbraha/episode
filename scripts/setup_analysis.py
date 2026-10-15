#!/usr/bin/env python3
"""Install optional analysis tools entirely in project-owned bulk storage."""
import os, sys, subprocess, shutil
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
root = Path(os.environ.get("EPISODE_STORAGE", "/Volumes/External Storage/Episode"))
if not (root / ".episode-storage").is_file():
    raise SystemExit("Storage unavailable")
if shutil.disk_usage(root).free < 15 * 1024**3:
    raise SystemExit("Need 15 GiB external headroom")
env = dict(
    os.environ,
    TMPDIR=str(root / "tmp"),
    PIP_CACHE_DIR=str(root / "cache/pip"),
    HF_HOME=str(root / "cache/huggingface"),
    PYTHONDONTWRITEBYTECODE="1",
)
python = root / "analysis-venv/bin/python"
if not python.exists():
    subprocess.run(
        [sys.executable, "-m", "venv", str(python.parent.parent)], check=True, env=env
    )
lock = repo / "requirements-analysis.lock"
subprocess.run(
    [
        str(python),
        "-m",
        "pip",
        "install",
        "-r",
        str(lock if lock.exists() else repo / "requirements-analysis.txt"),
    ],
    check=True,
    env=env,
)
if not lock.exists():
    lock.write_text(
        subprocess.check_output(
            [str(python), "-m", "pip", "freeze"], text=True, env=env
        )
    )
print("Analysis environment installed. Model download is separate.")
