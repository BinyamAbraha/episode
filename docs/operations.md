# Local operations and retention

`python3.11 scripts/start.py --port 8765` owns one API child and one worker child. Both use configured Episode storage. The worker holds an OS file lock for its lifetime and processes one job at a time. Closing the supervisor stops only its own children. A preexisting occupied port fails startup. No Relay service or machine-wide setting is changed.

The API binds to loopback. Trusted host checks and same-origin mutation checks restrict browser writes. Paths resolve under configured roots; clients use episode/camera identifiers rather than arbitrary paths. This is a local application, not a hardened authenticated multiuser internet service. Do not expose the backend publicly. Use the read-only replay for public hosting.

Import stages distinguish downloading, validation, preview derivation and publication. An interrupted or failed job cannot commit incomplete catalog rows. Previously complete catalog entries remain. Missing storage returns an actionable failure and does not recreate the external path internally. Remount the drive before retrying. Recovery marks abandoned running jobs interrupted and creates a new job on explicit retry. Completed source assets are reused only after checksum verification.

A job cancellation is checked at safe boundaries. A running decoder or network operation may finish before cancellation takes effect; subprocess and network calls have timeouts. Graceful shutdown does not guarantee immediate cancellation of every third-party filesystem call on a failing mount. No automatic data deletion is attempted during storage failure.

Every successful validation publication records rule settings, checked assets, episode/sample totals and findings in `validation_runs`. Original media has a retained all-frame decode-scan record; PTS association covers every declared sample. Current findings are a convenient catalog view; prior run reports preserve validation evidence.

Retention defaults to retaining all source assets, derived media, manifests, reviews and evidence. Versions reference large videos without copying them. To inspect old staging remnants, stop the worker and run `./scripts/episode cleanup`. To remove the listed remnants, use `./scripts/episode cleanup --apply`. Cleanup only recognizes exact project-generated partial filenames older than one hour, checks version references, rejects symlink escapes and requires exclusive worker ownership. It does not remove final assets, unknown files or old environments. Keeping storage conservative is preferable to implicit deletion in this small release.

Back up the external `runtime/catalog.sqlite` with SQLite's backup mechanism while connected, plus `sources`, version exports and required derivatives. Do not copy a live WAL database as if its main file alone were complete. Restoring the catalog without source assets does not restore a usable dataset.

Persistent workers wait and retry catalog connection when the storage marker is unavailable. This keeps missing-storage handling distinct from successful processing; one-shot workers fail promptly. The controlled recovery test does not claim a physical unplug/remount test.
