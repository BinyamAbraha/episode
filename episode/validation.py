"""Pure, deterministic checks shared by real imports and labelled fault fixtures."""

import numpy as np

RULES = {
    "gap_periods": 1.5,
    "alignment_seconds": 1 / 60 + 0.001,
    "origin_seconds": 0.001,
}


def validate(samples, info, metadata):
    findings = []

    def add(rule, severity, observed, threshold, explanation, start=0, end=None):
        findings.append(
            dict(
                rule=rule,
                severity=severity,
                start=float(start),
                end=float(start if end is None else end),
                observed=observed,
                threshold=threshold,
                explanation=explanation,
            )
        )

    required = [
        "timestamp",
        "frame_index",
        "episode_index",
        "index",
        "observation.state",
        "action",
    ]
    if not samples or any(k not in samples[0] for k in required):
        add(
            "schema.required",
            "error",
            list(samples[0]) if samples else [],
            required,
            "Required sample fields are missing.",
        )
        return findings
    t = np.asarray([r["timestamp"] for r in samples], dtype=float)
    if not np.isfinite(t).all():
        add(
            "time.finite",
            "error",
            "nonfinite",
            "finite",
            "Timestamp values must be finite.",
        )
        return findings
    if abs(t[0]) > RULES["origin_seconds"]:
        add(
            "time.origin",
            "error",
            float(t[0]),
            0,
            "Source episode timestamps must begin near zero.",
            t[0],
        )
    delta = np.diff(t)
    period = 1 / info["fps"]
    for i in np.where(delta <= 0)[0]:
        add(
            "time.order",
            "error",
            float(delta[i]),
            "> 0",
            "Timestamp order prevents unambiguous temporal windows.",
            t[i],
            t[i + 1],
        )
    for i in np.where(delta > period * RULES["gap_periods"])[0]:
        add(
            "time.gap",
            "warning",
            float(delta[i]),
            period * RULES["gap_periods"],
            "Unexpected sample gap; windows spanning it must be rejected.",
            t[i],
            t[i + 1],
        )
    ids = [(r["episode_index"], r["frame_index"]) for r in samples]
    if len(set(ids)) != len(ids):
        add(
            "sample.duplicate",
            "error",
            len(ids) - len(set(ids)),
            0,
            "Repeated episode/frame identity is ambiguous.",
        )
    if len(samples) != metadata["length"] or any(
        r["episode_index"] != metadata["episode_index"] for r in samples
    ):
        add(
            "episode.boundary",
            "error",
            len(samples),
            metadata["length"],
            "Metadata length or source identity disagrees with selected rows.",
        )
    if [r["frame_index"] for r in samples] != list(range(len(samples))):
        add(
            "sample.sequence",
            "error",
            "noncontiguous",
            "0..length-1",
            "Frame identities must be contiguous within the episode.",
        )
    for key in ["observation.state", "action"]:
        shape = info["features"][key]["shape"]
        try:
            values = np.asarray([r[key] for r in samples], dtype=float)
        except (ValueError, TypeError):
            values = np.zeros((0,))
        if values.shape != (len(samples), *shape):
            add(
                "feature.dimension",
                "error",
                list(values.shape),
                [len(samples), *shape],
                key + " does not match its own declared schema.",
            )
            continue
        bad = np.where(~np.isfinite(values).all(axis=1))[0]
        for i in bad:
            add(
                "feature.finite",
                "error",
                key,
                "finite",
                key + " contains a nonfinite number.",
                t[i],
            )
        if not len(bad) and np.max(np.ptp(values, axis=0)) < 0.01:
            add(
                "signal.low_motion",
                "descriptive",
                key,
                0.01,
                "Small numeric variation; units are unknown and this does not establish task quality.",
                t[0],
                t[-1],
            )
    return findings
