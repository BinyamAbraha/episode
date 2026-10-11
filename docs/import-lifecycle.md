# Import and job lifecycle

One worker holds an OS file lock and transactionally claims SQLite jobs, executing one heavy job at a time. Stages include queued, downloading, validating media, deriving preview, validating, publishing and succeeded; terminal alternatives are failed, cancelled and interrupted. Progress reports stage and completed units, never estimated training readiness.

Downloads write project-owned staging files then hash-verify and atomically rename. A retry reuses verified assets. Catalog rows become visible only in the final transaction. Existing complete imports remain available after a failed new job. Restart recovery marks abandoned work interrupted and allows explicit retry. Cancellation is cooperative between bounded subprocesses and assets. Every subprocess and network operation has a timeout.

The configured root must carry a project ownership marker. Missing external storage must fail without silently creating a replacement root on the internal disk. Cleanup is limited to unreferenced project-owned staging artifacts; retained version assets cannot be deleted.

Catalog-row and exact-family index preparation occurs during validation. Publication is the final SQLite transaction. A separate indexing progress stage is not exposed in this release.
