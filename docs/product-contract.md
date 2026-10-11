# Product contract

Episode serves a local robotics data engineer reviewing recorded demonstrations. An episode is one task attempt with observations, actions and metadata. Required journey: import a pinned source; inspect real cameras and named signals; investigate findings; review and annotate; save criteria; publish an immutable selection with splits; decode real batches; compare versions.

Acceptance requires idempotent imports, hash-preserved assets, atomic publication, recoverable bounded jobs, explicit failures when storage disappears, deterministic fault detections, immutable annotation snapshots, episode-isolated windows and splits, train-only statistics, working browser journeys, accessibility checks and measured performance evidence. Every visible metric comes from catalog or measured results. No physical robot, live control, paid services or large training run is required.

Technical validity, human review and task outcome are independent. Outcome defaults to unknown. Recorded public replay must disclose source version and generation time and must not simulate live writes.
