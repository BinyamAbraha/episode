"""Conservative cleanup: exact known staging names, with exclusive ownership."""

import json, fcntl, time
from .storage import root, connect, rows, source_root
from .service import SOURCE_LOCK


def cleanup_staging(apply=False):
    lockfile = root() / "runtime/worker.lock"
    with lockfile.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(
                "Stop the Episode worker before inspecting or cleaning staging files"
            )
        lockdata = json.loads(SOURCE_LOCK.read_text())
        with connect() as db:
            protected = {
                a["path"]
                for v in rows(db, "SELECT manifest FROM versions")
                for a in json.loads(v["manifest"])["assets"]
            }
        candidates = []
        for asset in lockdata["assets"]:
            original = source_root() / asset["path"]
            paths = [
                original.with_suffix(original.suffix + ".partial"),
                root() / "derived" / (asset["sha256"] + ".partial.webm"),
            ]
            for p in paths:
                if (
                    p.is_symlink()
                    or not p.is_file()
                    or time.time() - p.stat().st_mtime < 3600
                ):
                    continue
                if not p.resolve().is_relative_to(root().resolve()):
                    raise ValueError("Staging path escapes owned storage")
                if (
                    p.is_relative_to(source_root())
                    and str(p.relative_to(source_root())) in protected
                ):
                    continue
                candidates.append(
                    {"path": str(p.relative_to(root())), "bytes": p.stat().st_size}
                )
                if apply:
                    p.unlink()
        return {
            "mode": "applied" if apply else "dry-run",
            "staging": candidates,
            "retained_assets": "All final source assets, previews and version content retained",
        }
