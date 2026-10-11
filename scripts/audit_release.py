"""Audit the Git index, not private working files or external artifacts."""

import subprocess, re, json
from pathlib import Path

r = Path(__file__).resolve().parents[1]
files = subprocess.check_output(["git", "ls-files", "-z"], cwd=r).decode().split("\0")
files = [f for f in files if f]
errors = []
for f in files:
    p = r / f
    if p.is_symlink():
        errors.append("Symlink in public index: " + f)
        continue
    if f.startswith(("docs/learning/", "docs/private/")) or p.name == "AGENTS.md":
        errors.append("Private path tracked: " + f)
    if p.suffix in [".mp4", ".webm", ".parquet", ".sqlite", ".db"]:
        errors.append("Bulk source/media tracked: " + f)
    if p.stat().st_size > 2 * 1024**2:
        errors.append("Oversized public file: " + f)
    if p.suffix not in [".png", ".jpg", ".jpeg"]:
        text = p.read_text(errors="replace")
        if re.search(
            r"gh[pousr]_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----",
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
if errors:
    raise SystemExit("\n".join(errors))
print(
    json.dumps(
        {
            "tracked_files": len(files),
            "status": "passed",
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
