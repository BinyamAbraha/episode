# Canonical data model

Source identity is dataset repository plus immutable revision. Assets have source-relative path, expected content hash, actual SHA-256, byte length and publication state. Changes under a logical source identity are conflicts, not duplicates. Robot type and feature names, shapes and dtypes are preserved; units, frames, session identity and physical synchronization remain unknown when undocumented.

Episode identity is source identity plus source episode index. Metadata resolves half-open sample ranges and each camera's shared-file index and video start/end offsets. Source timestamps, episode-relative timestamps, video PTS and UTC processing times are separate fields. No wall-clock recording time is inferred.

SQLite owns transactional source, asset, episode, job, finding, review revision, annotation revision, selection and version indexes. Preserved Parquet owns signal samples. Immutable JSON manifests own version content including source revisions, hashes, membership, adapter/schema versions, rules, annotation snapshots, transforms, normalization, algorithm/seed/groups and explicit splits. Verification and benchmark records reference the manifest hash and remain separate.

## Persisted records

The first release supports one pinned dataset/revision. Integer episode keys and source-relative asset keys are scoped to that adapter, not claimed as a general multi-source identity scheme.

| Record | Identity and stored fields | Mutability |
| --- | --- | --- |
| Source | revision ID, repository, revision, original info JSON, UTC import time | Source bytes pinned; one catalog identity |
| Asset | relative path, SHA-256, byte length, source revision | Repeated bytes reused; changed identity rejected |
| Episode | source episode index, source revision, metadata JSON, task, duration, sample count, exact sequence-family hash | Idempotent catalog publication |
| Camera stream | original feature name and metadata chunk/file indices, from/to timestamps, feature shape/dtype | Preserved inside source and episode metadata |
| State/action sample | episode/frame/global index, relative timestamp, original state/action arrays, task index | Preserved Parquet; never rewritten by review |
| Job | UUID, kind, JSON arguments, state/stage, completed/total units, error, UTC creation/update times, cancellation flag | Mutable processing state |
| Validation run | UUID, job ID, rule configuration, result JSON with hashes and findings, UTC time | Appended on atomic publication |
| Finding | episode, rule ID, severity, interval, observed value, threshold, explanation, fixture flag | Current catalog projection; prior runs retained |
| Review | revision ID, episode, status, outcome, reason, UTC time | Append-only |
| Interval annotation | revision ID, episode, start/end seconds, label, note, UTC time | Append-only additions; editing/supersession deferred |
| Selection | ID, name, criteria JSON, UTC creation time | Saved query; membership evaluated at use |
| Version | SHA-256 ID, name, canonical JSON manifest, UTC creation time | No mutation API; hash verified when read |
| Verification | ID, version hash, measured result JSON, UTC time | Appended independently of version content |
| Benchmark | generated time, hardware/software, dataset/version identity, raw timings, cache/concurrency, scoped RSS/disk values | External JSON artifact; audited copy in release evidence |

All timestamps recording application activity are timezone-aware UTC ISO-8601 strings. Source relative times and video PTS remain numeric seconds with their distinct meanings. An unknown recording date is not replaced by import time.

`feature_metadata` carries original names, dtypes, dimensions and declared robot type. Undocumented units, coordinate frame, control semantics, physical synchronization and session identity are explicit JSON null values. Equal dimensions do not establish compatible robots or actions.

## Manifest contract

`episode.version/1` records adapter/schema versions, source repository/revision, canonical feature metadata, exact episode IDs, asset paths/hashes/lengths, selection criteria, review and annotation revisions, split algorithm/seed/grouping/membership, validation thresholds, window/stride/padding/alignment settings, and training normalization statistics. The version hash covers canonical JSON with sorted keys and disallowed nonfinite numbers. A verification result references that hash without rewriting it.

A consumer batch records episode and split identity, contiguous frame indices, relative timestamps, float32 state/action and normalized arrays, boolean masks, uint8 RGB camera arrays, and per-image requested/selected/decoded PTS. A dropped incomplete or gapped window produces no batch; no silent padding or interpolation is applied.
