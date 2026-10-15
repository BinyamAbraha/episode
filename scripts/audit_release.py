"""Audit the Git index, not private working files or external artifacts."""

import subprocess, re, json, sys
from pathlib import Path

r = Path(__file__).resolve().parents[1]
files = subprocess.check_output(["git", "ls-files", "-z"], cwd=r).decode().split("\0")
files = [f for f in files if f]
errors = []
for f in files:
    p = r / f
    mode = (
        subprocess.check_output(["git", "ls-files", "--stage", "--", f], cwd=r)
        .decode()
        .split()[0]
    )
    if mode == "120000":
        errors.append("Symlink in public index: " + f)
        continue
    if (
        f.startswith(("docs/learning/", "docs/private/"))
        or p.name == "AGENTS.md"
        or (p.name.startswith(".env") and p.name != ".env.example")
        or p.suffix in {".pem", ".key"}
    ):
        errors.append("Private path tracked: " + f)
    if p.suffix in [".mp4", ".webm", ".parquet", ".sqlite", ".db", ".safetensors"]:
        errors.append("Bulk source/media tracked: " + f)
    data = subprocess.check_output(["git", "show", ":" + f], cwd=r)
    if len(data) > 2 * 1024**2:
        errors.append("Oversized public file: " + f)
    if p.suffix not in [".png", ".jpg", ".jpeg"]:
        text = data.decode(errors="replace")
        if re.search(
            r"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----",
            text,
        ):
            errors.append("Possible credential: " + f)
        if "/Users/" in text and f != "scripts/audit_release.py":
            errors.append("Personal absolute path: " + f)
        if "\u2014" in text:
            errors.append("Em dash: " + f)
        if p.suffix == ".md":
            for link in re.findall(r"\]\(([^)]+)\)", text):
                target = link.split("#")[0].strip("<>")
                if not target or "://" in target or target.startswith("mailto:"):
                    continue
                resolved = (p.parent / target).resolve()
                if (
                    not resolved.is_file()
                    or not resolved.is_relative_to(r)
                    or str(resolved.relative_to(r)) not in files
                ):
                    errors.append(
                        "Untracked or missing public link: " + f + " -> " + target
                    )
history_commits = []
if "--history" in sys.argv:
    history_commits = (
        subprocess.check_output(["git", "rev-list", "--all"], cwd=r)
        .decode()
        .splitlines()
    )
    seen = set()
    for commit in history_commits:
        entries = subprocess.check_output(
            ["git", "ls-tree", "-rz", commit], cwd=r
        ).split(b"\0")
        for entry in filter(None, entries):
            metadata, name = entry.split(b"\t", 1)
            mode, kind, oid = metadata.decode().split()
            name = name.decode()
            identity = (name, oid)
            if identity in seen:
                continue
            seen.add(identity)
            if (
                name.startswith(("docs/learning/", "docs/private/"))
                or Path(name).name == "AGENTS.md"
                or (
                    Path(name).name.startswith(".env")
                    and Path(name).name != ".env.example"
                )
                or mode == "120000"
                or Path(name).suffix
                in {
                    ".pem",
                    ".key",
                    ".sqlite",
                    ".db",
                    ".parquet",
                    ".mp4",
                    ".webm",
                    ".safetensors",
                }
            ):
                errors.append("Private or bulk path in history: " + name)
            if kind != "blob":
                continue
            data = subprocess.check_output(["git", "cat-file", "blob", oid], cwd=r)
            if len(data) > 2 * 1024**2:
                errors.append("Oversized historical file: " + name)
            if Path(name).suffix not in {".png", ".jpg", ".jpeg"}:
                text = data.decode(errors="replace")
                if re.search(
                    r"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----",
                    text,
                ):
                    errors.append("Possible historical credential: " + name)
                if "/Users/" in text and name != "scripts/audit_release.py":
                    errors.append("Historical personal absolute path: " + name)
if errors:
    raise SystemExit("\n".join(errors))
print(
    json.dumps(
        {
            "tracked_files": len(files),
            "status": "passed",
            "history_commits_checked": len(history_commits),
            "checks": [
                "private path exclusion",
                "symlink exclusion",
                "bulk and size policy",
                "credential patterns",
                "personal paths",
                "writing punctuation",
                "local public links",
            ],
        },
        indent=2,
    )
)
