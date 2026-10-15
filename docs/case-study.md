# Episode: reproducible robotics data curation

The engineering problem is making a small recorded demonstration dataset inspectable and reproducible without treating camera playback, technical validity and training readiness as the same condition.

Episode imports a pinned 50-episode LeRobot v3 source into a local catalog. Its inspector connects real camera previews to named state/action signals. Review events and interval annotations append history. Publishing a dataset version freezes membership, relevant history, hashes, rules, transforms and explicit splits. A standalone consumer verifies that the manifest can produce actual signal windows and decoded images.

## Decisions and evidence

The dataset card described an obsolete v2.1 layout. Pinned metadata and Parquet inspection established the actual v3.0 shared-file contract. The adapter uses episode metadata for half-open row boundaries and per-camera offsets. It preserves the source's so100_follower identifier despite so101 in the repository name. Unknown physical units and control semantics remain explicit unknowns.

Original AV1 recordings remain unchanged. VP9 previews were chosen after the browser test exposed unsupported H.264 in the pinned Chromium build. Original decoded-frame inspection checks reported PTS; preview playback makes a narrower approximate-seeking claim. Full-stream decode scans and sample-to-PTS checks establish file-level consistency, not physical camera synchronization.

SQLite transactions provide catalog publication and immutable version snapshots. A single locked worker avoids unnecessary distributed infrastructure. Interrupted jobs remain distinguishable from successful publication. The source is only about 82 MiB, so preserving shared assets and referencing them from versions avoids large copies without introducing object-store services.

Whole-episode splits prevent neighboring-frame leakage across train and evaluation. Exact state/action sequence families stay together. Missing session metadata prevents a session-level separation claim. Normalization is fitted on training members only and stored with the version.

The full-source consumer verification checked 2,961 signal windows and decoded 400 original images from all 50 episodes. Its 40/5/5 split and bounded decode scope are recorded with the version hash. An exported manifest was also read without the application catalog. This is a verified custom NumPy/FFmpeg consumer, not an unexecuted claim of LeRobot-reader compatibility.

See [verification](verification.md) for executed tests and [benchmarks](benchmarks.md) for hardware, cache conditions, measurements and raw evidence. No policy was trained; no offline metric is presented as robot task success. No cloud deployment or production operation is claimed.

## Remaining limits

The adapter intentionally supports one pinned source contract. The source contains one task, lacks session/units/synchronization metadata, and does not justify broad robot compatibility claims. Per-frame FFmpeg processes are simple to verify but unsuitable as a high-throughput training design without further measurement and optimization. Multiuser authorization, additional formats and distributed processing remain future work.

## Evidence-linked local analysis

The analysis extension addresses the gap between technical integrity and behavioral interpretation. OpenCV computes sparse image diagnostics; a pinned local Qwen3-VL model proposes intervals from timestamped camera evidence. Strict validation rejects malformed citations and intervals. A reviewer must approve or edit suggestions before they become annotations, and new dataset versions preserve both the original model statement and the recorded decision.

The isolated inference environment keeps heavy processor dependencies out of the core application. A single supervised subprocess bounds concurrency and supports cancellation. Eight model-visible frames per episode reduce cost but can miss fast manipulation events. The application therefore exposes source video alongside evidence and preserves unknown outcomes.

Full-dataset diagnostics covered 50 episodes and 800 samples in 57.98 summed processing seconds. The final five-episode development pilot produced 14 schema-valid suggestions with 10.69 to 14.00 seconds of inference per episode. The initial pilot rejected malformed outputs, motivating an audited repair path. These are processing and output-validity results; semantic accuracy and reviewer time savings still require human evaluation. See [analysis results](analysis-results.md).
