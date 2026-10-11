#!/usr/bin/env python3
"""Install locally, keeping environments, caches and browsers outside source."""
import os, sys, shutil, subprocess, argparse
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument(
    "--storage",
    default=os.environ.get("EPISODE_STORAGE", "/Volumes/External Storage/Episode"),
)
p.add_argument("--init-storage", action="store_true")
a = p.parse_args()
r = Path(__file__).resolve().parents[1]
e = Path(a.storage).expanduser().resolve()
if e.is_relative_to(r):
    raise SystemExit("Bulk storage must be outside the source repository")
if str(e).startswith("/Volumes/") and not Path(*e.parts[:3]).is_mount():
    raise SystemExit("External volume is not mounted")
if not (e / ".episode-storage").exists():
    if not a.init_storage:
        raise SystemExit(
            "Storage is not initialized. Use --init-storage with an empty project-owned directory."
        )
    if e.exists() and any(e.iterdir()):
        raise SystemExit("Refusing to adopt a nonempty directory")
    e.mkdir(parents=True, exist_ok=True)
    (e / ".episode-storage").write_text("Episode project-owned storage v1\n")
if shutil.disk_usage(e).free < 2 * 1024**3:
    raise SystemExit("At least 2 GiB of free bulk storage is required for setup")
for d in [
    "sources",
    "derived",
    "runtime",
    "tmp",
    "cache/pip",
    "cache/npm",
    "cache/browsers",
    "evidence",
    "web-tools",
]:
    (e / d).mkdir(parents=True, exist_ok=True)
env = dict(
    os.environ,
    TMPDIR=str(e / "tmp"),
    PIP_CACHE_DIR=str(e / "cache/pip"),
    npm_config_cache=str(e / "cache/npm"),
    PLAYWRIGHT_BROWSERS_PATH=str(e / "cache/browsers"),
    PYTHONDONTWRITEBYTECODE="1",
)
if not (e / "venv/bin/python").exists():
    subprocess.run([sys.executable, "-m", "venv", str(e / "venv")], check=True, env=env)
subprocess.run(
    [
        str(e / "venv/bin/python"),
        "-m",
        "pip",
        "install",
        "-r",
        str(r / "requirements.lock"),
    ],
    check=True,
    env=env,
    timeout=300,
)
for name in ["package.json", "package-lock.json"]:
    shutil.copy2(r / "web" / name, e / "web-tools" / name)
subprocess.run(
    ["npm", "ci", "--prefix", str(e / "web-tools"), "--no-audit", "--no-fund"],
    check=True,
    env=env,
    timeout=300,
)
link = r / "web/node_modules"
target = e / "web-tools/node_modules"
if link.is_symlink():
    if link.resolve() != target.resolve():
        raise SystemExit(
            "Existing dependency link points elsewhere; preserve it and choose an explicit setup location"
        )
elif link.exists():
    raise SystemExit(
        "Existing local node_modules is preserved. Move it outside source before setup."
    )
else:
    link.symlink_to(target, target_is_directory=True)
subprocess.run(
    ["node", str(target / "@playwright/test/cli.js"), "install", "chromium"],
    check=True,
    env=env,
    timeout=300,
)
subprocess.run(
    ["npm", "run", "--prefix", str(r / "web"), "build"],
    check=True,
    env=env,
    timeout=120,
)
print(
    "Setup complete. Set EPISODE_STORAGE to this storage root when using a nondefault path."
)
