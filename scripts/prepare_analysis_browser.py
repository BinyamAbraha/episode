"""Create an isolated browser-test catalog; preserve real reviews and versions."""

import os, sys, sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from episode.storage import root, connect

source = root()
target = source / "analysis-browser"
if target.exists() and "--reset" not in sys.argv:
    raise SystemExit(
        "Test directory already exists; choose a new explicit test directory before rebuilding"
    )
if (
    target.exists()
    and (target / ".episode-storage").read_text()
    != "Episode isolated browser test storage\n"
):
    raise SystemExit("Refusing to reset an unrecognized directory")
for name in ["runtime", "tmp", "evidence"]:
    (target / name).mkdir(parents=True, exist_ok=True)
(target / ".episode-storage").write_text("Episode isolated browser test storage\n")
for name in ["sources", "derived", "venv", "analysis-venv", "models", "cache"]:
    if not (target / name).exists():
        (target / name).symlink_to(source / name, target_is_directory=True)
with connect() as src, sqlite3.connect(target / "runtime/catalog.sqlite") as dst:
    src.backup(dst)
    # Test-only mutable state. Immutable original catalog remains unchanged.
    for table in [
        "suggestion_decisions",
        "reviews",
        "annotations",
        "jobs",
        "selections",
        "versions",
        "verifications",
    ]:
        dst.execute("DELETE FROM " + table)
print(target)
