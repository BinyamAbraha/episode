# Analysis and assisted review contract

Required extension: deterministic image/signal diagnostics; a five-episode local VLM pilot; evidence-linked suggestions; append-only accept/edit/reject decisions; annotation-aware selection and immutable provenance; measured resource evidence, tests and evaluation tooling. Optional segmentation, embeddings and VLA training remain deferred.

Execution: one durable worker, one analysis job at a time. Analysis uses an isolated external Python environment. Model inference is a bounded subprocess with offline local weights, a timeout and cancellation. Complete episode results publish atomically; retry reuses the content-addressed result. A failed new analysis cannot remove an older result. Outputs never modify preserved assets or human outcomes.

Inputs: pinned source revision, verified source hashes, original decoded RGB frames and recorded numeric samples. Uniform sparse preview sampling is distinct from training transforms. Each frame records camera, requested episode time, actual source PTS, source hash and derived image hash. Nominal timestamps do not prove physical synchronization. Sparse sampling can miss fast events.

Diagnostics: luminance mean, dark/clipped pixel fraction, Laplacian variance, adjacent sampled-frame absolute difference and optical-flow magnitude at 320 by 240. Thresholds are heuristic review hints, not calibrated quality scores. Numeric ranges and absolute changes retain unknown native units. State and action schemas are separate. No cross-gap derivatives or inferred physical velocities.

VLM rubric: task-phase/outcome hypotheses supported by explicit evidence IDs; success/failure/unknown; unknown required when evidence is insufficient. JSON validation rejects invalid evidence, labels, bounds and nonfinite times. Raw output remains inspectable. No model confidence is presented as a probability. Model identity, immutable revision, artifact hashes, package versions, full prompt and decoding settings are recorded.

Review: suggestions start pending. A required reason accompanies accept/edit/reject. Accepted/edited intervals append a normal annotation and a linked decision in one transaction. They do not silently change the episode outcome. One terminal decision per suggestion; correction can be recorded as a separate manual annotation. Prior dataset manifests never change. New versions snapshot analysis and decision provenance linked to accepted annotations.

Evaluation: human reference labels must be explicitly supplied by a reviewer; neither model output nor agent-generated judgments are human ground truth. Separate prompt-development and held-out reference episodes. Report outcome agreement/confusion, abstention coverage and interval matching within declared tolerances only for available references. Human review-time savings require a timed human study. Until supplied, these checks are marked not run.

Resource policy: all packages/models/caches/tmp live on configured external storage. Reserve 15 GiB external headroom before installation; bound inference tokens and images, one process, use a small memory limit in MLX. Refuse inference under critical memory pressure or insufficient internal headroom; no system cleanup or reconfiguration. No paid service is used.
