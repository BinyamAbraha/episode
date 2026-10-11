"""Labelled in-memory fault demonstrations, separate from preserved assets."""

from copy import deepcopy
from .validation import validate


def base():
    info = {
        "fps": 30,
        "features": {"observation.state": {"shape": [2]}, "action": {"shape": [3]}},
    }
    data = [
        {
            "episode_index": 0,
            "frame_index": i,
            "index": i,
            "timestamp": i / 30,
            "observation.state": [i / 10, 1.0],
            "action": [i / 5, 0.0, 1.0],
        }
        for i in range(12)
    ]
    return data, info, {"episode_index": 0, "length": 12}


def demonstrations():
    original, info, meta = base()
    out = []
    for name in [
        "timestamp gap",
        "shifted timestamp origin",
        "nonfinite action",
        "duplicate sample identity",
    ]:
        data = deepcopy(original)
        if name == "timestamp gap":
            for r in data[6:]:
                r["timestamp"] += 0.2
        elif name == "shifted timestamp origin":
            for r in data:
                r["timestamp"] += 0.5
        elif name == "nonfinite action":
            data[6]["action"][1] = float("nan")
        else:
            data[6]["frame_index"] = data[5]["frame_index"]
        findings = validate(data, info, meta)
        out.append(
            {
                "name": name,
                "injected": True,
                "rules": sorted({f["rule"] for f in findings}),
                "findings": findings,
            }
        )
    return out
