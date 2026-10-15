# Release scope

Implemented: environment/storage diagnostics; pinned-source contracts; one-episode browser slice followed by all 50 episodes; durable jobs and recovery; original-media validation and shared-cursor inspection; review history and interval annotations; saved criteria; immutable versions and comparison; grouped splits and standalone consumer verification; measured benchmarks; attributed read-only replay and release documentation.

Evidence: [verification](verification.md), [benchmark report](benchmarks.md), [source provenance](provenance.md), [operations](operations.md).

The [public repository](https://github.com/BinyamAbraha/episode) is published and fixture-only CI has passed remotely; see [verification](verification.md). Public replay hosting remains prepared but unpublished. No public backend deployment is claimed.

Optional future work: persistent batched video decoding after measurement, additional format adapters, session-aware grouping when real session metadata exists, explicit annotation supersession/editing, multiuser authentication and transaction architecture, and small CPU prediction experiments. Kubernetes, distributed queues, broad cloud deployments and large policy training are outside this release.

## Assisted analysis release

Implemented: isolated local model environment, pinned weights and hashes, full-dataset sparse diagnostics, five-episode VLM pilot, evidence-linked suggestions, explicit review decisions, annotation-aware selections and immutable provenance, local evaluation tooling, browser/accessibility checks and recorded replay extension. [Contract](analysis-contract.md), [usage](analysis.md), [measurements and limits](analysis-results.md).

Not evaluated: semantic accuracy against human references, held-out phase/outcome performance and human review-time savings. Reference labels require a human reviewer. Segmentation, embeddings and VLA/policy training remain optional deferred extensions.
