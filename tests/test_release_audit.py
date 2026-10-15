"""Publication checks must inspect staged bytes and retained Git history."""

import shutil
import subprocess
import sys
from pathlib import Path


def test_audit_staged_bytes_and_deleted_history(tmp_path):
    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=tmp_path, check=True, capture_output=True
        )

    def audit():
        return subprocess.run(
            [sys.executable, "scripts/audit_release.py", "--history"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )

    git("init")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    (tmp_path / "scripts").mkdir()
    shutil.copyfile(
        Path(__file__).resolve().parents[1] / "scripts/audit_release.py",
        tmp_path / "scripts/audit_release.py",
    )
    git("add", ".")
    git("commit", "-m", "Clean fixture")
    assert audit().returncode == 0
    suspect = tmp_path / "config.txt"
    suspect.write_text("github_pat_" + "x" * 40)
    git("add", "config.txt")
    suspect.write_text("Clean working copy does not change staged bytes")
    result = audit()
    assert (
        result.returncode != 0
        and "Possible credential: config.txt" in result.stdout + result.stderr
    )
    git("add", "config.txt")
    git("commit", "-m", "Clean configuration")
    private = tmp_path / "docs/private/note.md"
    private.parent.mkdir(parents=True)
    private.write_text("Fixture private note")
    git("add", ".")
    git("commit", "-m", "Historical fixture")
    git("rm", "docs/private/note.md")
    git("commit", "-m", "Remove fixture from current tree")
    result = audit()
    assert (
        result.returncode != 0
        and "Private or bulk path in history: docs/private/note.md"
        in result.stdout + result.stderr
    )
