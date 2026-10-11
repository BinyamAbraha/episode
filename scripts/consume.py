"""Exercise an exported manifest without reading the application catalog."""

import sys, argparse, json, itertools
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from episode.consumer import VersionDataset

p = argparse.ArgumentParser()
p.add_argument("manifest")
p.add_argument("source_root")
p.add_argument("--split", choices=["train", "validation", "test"], default="train")
p.add_argument("--windows", type=int, default=1)
a = p.parse_args()
if not 1 <= a.windows <= 100:
    raise SystemExit("Choose 1 to 100 decoded windows for this verification command")
d = VersionDataset(a.manifest, a.source_root)
for batch in itertools.islice(d.windows(a.split), a.windows):
    print(
        json.dumps(
            {
                "version": d.version,
                "episode": batch["episode"],
                "split": batch["split"],
                "frame_indices": batch["frame_indices"],
                "shapes": {
                    k: list(batch[k].shape)
                    for k in [
                        "images",
                        "state",
                        "action",
                        "normalized_state",
                        "normalized_action",
                        "mask",
                    ]
                },
                "max_timing_error": max(t["error_seconds"] for t in batch["timing"]),
            }
        )
    )
