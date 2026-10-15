# Verification evidence

## Executed checks

- Backend: `"$EPISODE_STORAGE/venv/bin/python" -B -m pytest -q -p no:cacheprovider --basetemp "$EPISODE_STORAGE/tmp/pytest"`: 23 passed in 0.62 seconds. One upstream Starlette/AnyIO deprecation warning; no test failure.
- Frontend: `npm run --prefix web build`: TypeScript check and Vite production build passed.
- Browser: `PLAYWRIGHT_BROWSERS_PATH="$EPISODE_STORAGE/cache/browsers" TMPDIR="$EPISODE_STORAGE/tmp" npm run --prefix web test`: five passed in 7.8 seconds. Real playback, seeking, keyboard controls, annotations, selections, immutable versions, comparison, worker verification, desktop/narrow layouts and read-only replay were exercised. Axe reported no violations in tested WCAG A/AA views. [Machine-readable summary](../evidence/browser-summary.json).
- Real source: all eight required files matched pinned SHA-256 values; both original streams completed full-frame decode scans. Every source sample was checked against the corresponding camera PTS timeline. [Source validation](../evidence/source-validation.json).
- Full-source consumer: version `15ff55345d322bbaebaec82b082ec36750442eabdc65cd4bcc48fc643a9663c7` passed with 50 episodes, 40/5/5 splits, 2,961 signal windows and 400 decoded original images in 22.35 seconds. [Record](../evidence/release-verification.json).
- Export independence: `scripts/consume.py` loaded an exported real manifest and decoded a training window without reading catalog review state. Images were `[2,4,480,640,3]` uint8; raw/normalized signals were `[4,6]` float32.
- Setup: `python3.11 scripts/setup.py` completed against the configured external environment. `./scripts/episode doctor` and `python3.11 scripts/start.py --port 8765` were exercised.

## Failure properties

Synthetic tests cover independent state/action dimensions, required fields, ordering, gaps, shifted origins, nonfinite actions, duplicate identities/episodes, idempotency, changed and missing assets, interruption before publication, restart/cancellation, missing-storage retry, immutable history snapshots, deterministic family splits, training-only normalization, exported consumer membership, path traversal, cross-origin/host rejection, invalid intervals, atomic validation reports and conservative cleanup. Fixtures are separate from preserved source recordings.

## Scope and checks not run

Routine fixture tests stub media decoding; real integration checks separately execute FFmpeg. The consumer scans every signal window but decodes a bounded window from each episode. All-frame scan results do not establish physical camera synchronization. Automated accessibility is supplemented by rendered desktop/narrow review, but manual screen-reader testing was not performed.

A pinned LeRobot reader, fresh-machine installation, physical drive unplug during processing, policy training, robot task-success evaluation, true cold-cache performance and remote CI execution were not run. Storage-loss behavior was tested with controlled failures without disconnecting the user's drive. The prepared CI workflow runs small fixtures and builds; no remote success is claimed before execution.

The public-index release audit passed, including private paths, symlinks, bulk/size checks, credential patterns, personal paths and local documentation links. Pinned Black and Prettier checks passed. The final `make test` and `make build` commands were also exercised successfully.

## Assisted analysis extension

The counts above describe the original release. The extension adds OpenCV diagnostics, local model execution, reviewed suggestions and version provenance. Final optional backend verification: 33 passed; core-only verification: 30 passed, three optional analysis tests skipped. The expanded browser suite exercises six journeys, including approved edited labels, rejection, frozen provenance and recorded model replay. See [analysis results](analysis-results.md) for measured resources, exact scope and unexecuted human evaluation. Public release checks are repeated for the extension.
