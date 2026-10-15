# Local analysis and assisted annotation

Episode analyzes preserved recordings using deterministic OpenCV diagnostics and optional local Qwen3-VL inference. The model proposes annotations. A human reviewer remains responsible for semantic judgments. No model output automatically accepts an episode or changes its outcome.

## Setup and execution

The core application environment remains separate from the optional analysis environment. All model files, caches, environments and temporary files belong under EPISODE_STORAGE. Reserve 15 GiB external headroom for setup. Python 3.11 and Apple Silicon are required for the pinned MLX path.

```sh
python3.11 scripts/setup_analysis.py
"$EPISODE_STORAGE/analysis-venv/bin/python" -B scripts/download_model.py
./scripts/episode analyze --mode diagnostics --all
./scripts/episode analyze --mode vlm --episodes 0 1 2 3 4
./scripts/episode worker
```

If the normal application worker is already running, do not start another worker. Results appear under Analysis and suggestions in the inspector. Jobs exposes current decoding/inference/publication stages and cancellation. Explicit setup downloads weights; inference is offline. Pinning details: [model lock](model-lock.json), [analysis dependencies](../requirements-analysis.lock).

The model conversion used mlx-vlm 0.3.4. Transformers 4.57.1 requires PyTorch and torchvision to construct its Qwen processor even when the model runs with MLX. These dependencies are isolated and are not used for policy training. Versions are pinned after the executed compatibility check. The downloaded model artifact is approximately 3.11 GB including tokenizer/configuration files. Source recordings are not copied into each analysis.

## Evidence and rules

Eight uniformly spaced source timestamps per camera are decoded against original PTS. RGB frames are resized to 320 by 240 using Lanczos. Sixteen samples per episode feed luminance, dark/clipped-pixel fractions, Laplacian variance, frame-difference and optical-flow measurements. This is sparse diagnostic sampling, not exhaustive blur or frozen-frame detection. Optical flow between widely spaced samples can be unreliable and is only a descriptive proxy.

The model sees a contact sheet with four samples per camera, IDs and timestamps. Its structured response contains a summary and interval suggestions. One repair attempt is allowed when evidence/schema validation fails. Every attempt, full prompt, model hashes, settings, software versions and input/output hashes are retained. Output that still fails validation produces an inspectable error with no suggestions.

Source state/action ranges and mean absolute changes are calculated independently. Gap transitions are excluded. Values retain unknown native units; no calibrated velocity, contact, force or synchronization claim is made. All thresholds are review hints rather than automatic exclusion criteria. See [contract](analysis-contract.md).

## Review and reproducibility

Accepting or editing a suggestion appends an interval annotation and decision in one SQLite transaction. Rejecting records a reason without an annotation. A suggestion has one terminal decision. Corrections after approval can be recorded as a new manual annotation; full supersession is deferred. Outcome suggestions remain hypotheses until the separate episode review form is used.

```sh
./scripts/episode analysis-results 0
./scripts/episode suggestion-review SUGGESTION_ID edit --reason "Observed interval corrected" --label grasp_attempt --start 1 --end 2
./scripts/episode selection "Reviewed grasp intervals" --annotation-label grasp_attempt
./scripts/episode version "Reviewed selection" --selection SELECTION_ID
```

Saved selections can filter exact annotation label, reviewed outcome and pending suggestions. A new version snapshots approved model-assisted annotations and their analysis provenance. Prior manifests are unchanged. Inference results are keyed by implementation, source hashes, mode, model revision, package versions and configuration. Identical retries reuse completed results. Complete episodes publish atomically; partial files cannot appear as a complete result. Older runs are selectable in the inspector.

One worker supervises one analysis subprocess. Cancellation terminates that subprocess and keeps previously published episodes. An advisory process lock prevents concurrent analysis; a parent watchdog exits orphaned analysis after worker death. Restart marks the interrupted job for retry. A one-hour job timeout bounds work. Disk checks refuse inference below 1 GiB internal headroom and terminate processing below 512 MiB; they do not manage macOS swap. MLX receives a 6 GiB allocator limit and 256 MiB cache limit. These are not guarantees of whole-machine memory use.

Published analysis evidence is retained. Cleanup currently does not remove analysis artifacts, including interrupted attempts; automatic analysis retention is deferred to avoid deleting evidence referenced by versions. Human corrections do not overwrite model outputs.

## Evaluation

```sh
"$EPISODE_STORAGE/venv/bin/python" -B -m episode.evaluation --output "$EPISODE_STORAGE/evidence/analysis-evaluation.json" --template docs/private/references.json
"$EPISODE_STORAGE/venv/bin/python" -B -m episode.evaluation --episodes 5 6 7 8 9 --references docs/private/held-out.json --output "$EPISODE_STORAGE/evidence/held-out-evaluation.json"
```

Reference templates refuse overwrite. A reviewer must supply references from original recordings, independently of model suggestions, with explicit human origin and reviewer attribution. Episodes 0 through 4 are development pilot episodes. Reserve episodes 5 through 9 for held-out human evaluation; do not tune the prompt on their reference labels. Their model runs are an explicit follow-up workflow. Development labels are excluded from held-out metrics. No references means null metrics and a visible not-evaluated status.

Outcome agreement, confusion and non-abstaining coverage are separate. Optional reference intervals use matching labels and start/end tolerance of 0.5 seconds, with one-to-one matching. Metrics are conditional on the supplied reference set, not evidence of broad robotics generalization. A timed human comparison is required before claiming review-time savings. Reference origin is attested by the reviewer, not independently verified.

## Verification

```sh
"$EPISODE_STORAGE/analysis-venv/bin/python" -B -m pytest -q -p no:cacheprovider --basetemp "$EPISODE_STORAGE/tmp/pytest-analysis"
```

Routine core CI skips OpenCV-specific tests when the optional environment is absent. The full optional suite must be run for an analysis release. Real-model and browser checks use local datasets and are explicit integration workflows. [Measured results](analysis-results.md) separate completed checks from missing human evaluation.
