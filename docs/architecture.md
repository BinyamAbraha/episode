# Architecture and decisions

React/TypeScript renders a loopback FastAPI service. SQLite holds metadata and append-only review history. PyArrow reads selected Parquet columns. FFmpeg/ffprobe perform bounded media operations. One separate worker handles durable jobs; the API does not own background processing. Dataset assets, media derivatives, environments and package caches use configurable external paths.

No DuckDB initially: this 50-episode catalog does not justify a second query engine. No torch in the application environment: consumer verification uses actual numpy batches and original decoded RGB frames. Optional pinned LeRobot-reader testing belongs in an isolated environment. Path allowlists map asset identifiers to configured roots; clients cannot provide SQL or arbitrary filesystem paths. Loopback binding and same-origin mutation checks protect local operations.

Future scale: object storage with immutable keys, transactional catalog server and leased workers could replace local assets/SQLite when measured concurrency or capacity requires it. Costs include distributed transactions, credentials, retries and media delivery. None is implemented or deployed.

## Implemented flow

```mermaid
flowchart LR
  HF[Pinned source revision] -->|size and SHA-256| S[Preserved external assets]
  Q[SQLite job queue] --> W[One locked worker]
  S --> W
  W --> V[Schema, time, PTS and decode validation]
  V -->|atomic publication| C[SQLite episode catalog]
  W --> P[VP9 preview and PTS indexes]
  C --> API[Loopback FastAPI]
  P --> API
  API --> UI[React inspector and curation]
  UI --> H[Append-only review and annotation history]
  H --> M[Content-hashed immutable version]
  S --> L[Standalone VersionDataset consumer]
  M --> L
  L --> E[Version-linked verification evidence]
```

Source paths come from a tracked source lock, not user-supplied file paths. Each asset is checked against the pinned SHA-256, including metadata and the card. Canonical feature metadata preserves names/dimensions and explicitly carries null units, coordinate frames, control semantics and session identity where undocumented. Versions snapshot this metadata alongside source hashes.

Version creation holds a SQLite write transaction while checking preserved asset hashes, capturing curation state, assigning splits and computing statistics. This intentionally favors a consistent small-data snapshot over concurrent write throughput. The measured catalog latency does not justify adding an analytical query service for this release.

The manifest consumer accepts an exported JSON file and source root. It checks source hashes, independently reads metadata and episode rows, and yields explicit window identities, masks, normalized/raw signals and original decoded images. It does not consult current catalog reviews. Verification records are separate from immutable content so adding a later measurement cannot alter a dataset version.

## Optional local analysis

The durable worker supervises an isolated Python subprocess containing OpenCV and MLX-VLM. Source hashes and original-media PTS remain authoritative. Derived frame evidence feeds deterministic diagnostics and a sparse model contact sheet. Strict JSON/evidence validation gates suggestion publication. Full output attempts, settings and artifact hashes remain available. A bounded repair attempt can fix malformed responses but cannot prove their visual interpretation.

The API reads immutable analyses and pending suggestions. Explicit accept/edit/reject decisions append transactional history; accepted intervals become annotations. New dataset versions include the linked analysis provenance. The core environment does not import the heavy inference libraries. See [analysis contract](analysis-contract.md) and [measured results](analysis-results.md).

```mermaid
flowchart LR
  S[Preserved source and PTS] --> D[Sampled RGB evidence]
  D --> CV[OpenCV diagnostics]
  D --> VLM[Offline pinned VLM]
  VLM --> G[Schema and evidence validation]
  G --> A[Immutable analysis and pending suggestions]
  CV --> A
  A --> UI[Inspector evidence review]
  UI --> H[Explicit decision and approved annotation]
  H --> V[Immutable dataset version provenance]
```
