"""Explicit network setup; the application only performs offline inference."""

import os, json, sys
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo))
from episode.storage import root, digest
from episode.analysis import MODEL_REPO, MODEL_REVISION

r = root()
os.environ["HF_HOME"] = str(r / "cache/huggingface")
os.environ["HF_HUB_DISABLE_XET"] = "1"
from huggingface_hub import snapshot_download

p = Path(
    snapshot_download(
        MODEL_REPO,
        revision=MODEL_REVISION,
        local_dir=r / "models" / MODEL_REVISION,
        allow_patterns=["*.json", "*.safetensors", "*.txt", "*.jinja", "README.md"],
        max_workers=2,
    )
)
lock = {
    "repository": MODEL_REPO,
    "revision": MODEL_REVISION,
    "license": "Apache-2.0",
    "files": [
        {"path": str(f.relative_to(p)), "sha256": digest(f), "bytes": f.stat().st_size}
        for f in sorted(p.iterdir())
        if f.is_file()
    ],
}
(r / "models/model-lock.json").write_text(json.dumps(lock, indent=2) + "\n")
(repo / "docs/model-lock.json").write_text(json.dumps(lock, indent=2) + "\n")
print(
    json.dumps(
        {"revision": MODEL_REVISION, "bytes": sum(f["bytes"] for f in lock["files"])}
    )
)
