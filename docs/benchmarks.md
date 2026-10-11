# Local benchmark report

Measured 2026-10-11T07:05:36.967496+00:00. Hardware: Apple M4, 16 GiB RAM, macOS 27.0, ARM64. Python 3.11.15; FFmpeg 8.1.2. Exact Python package versions and raw timings are in [benchmark.json](../evidence/benchmark.json).

The pinned source has 50 episodes, 11,939 samples, two cameras and 86123896 preserved source bytes. Concurrency was one. The benchmark ran after the browser suite completed. No cache flush was performed: the first measured call and subsequent repetitions are separated below, but neither is claimed to be a cold OS-cache measurement.

| Task | First measured (ms) | Repeat median (ms) | Repeat p95 (ms) | Calls |
| --- | ---: | ---: | ---: | ---: |
| catalog filter | 1.81 | 0.81 | 1.03 | 21 |
| episode open | 5.87 | 5.38 | 5.63 | 11 |
| decoded frame | 64.09 | 60.47 | 67.28 | 9 |
| decoded training window | 439.35 | 434.58 | 435.32 | 5 |

Repeat import completed in 6.01 seconds from queue submission to success, approximately 8.32 episodes/second. Source assets, previews and full-stream decode-scan caches already existed. The run rechecked hashes, signal rules, all sample-to-PTS associations and endpoint decoding. This is not download throughput or a first-import benchmark.

The standalone full-version verification checked 2,961 signal windows and decoded 400 images in 22.35 seconds. Decode scope is the first complete four-sample window of every episode across both cameras. [Exact verification record](../evidence/release-verification.json).

The benchmark Python process reported peak RSS of 126.34 MiB using macOS ru_maxrss. This excludes the separate API and worker and is not a whole-application peak-memory claim.

## Retained disk footprint

| Area | MiB |
| --- | ---: |
| sources | 82.14 |
| derived | 49.33 |
| cache | 913.36 |
| venv | 188.77 |
| web-tools | 104.45 |
| runtime | 1.58 |
| evidence | 2.29 |

These are summed file lengths at measurement time, including retained derivative variants and package/browser caches. They are not APFS allocated-block measurements or promised upper limits.

## Reproduce and interpret

Run the API and worker, import all 50 episodes, and create/verify a full version. Then run `make benchmark`. It measures local HTTP catalog/episode/frame endpoints and a decoded consumer window, then queues a repeat import. Raw samples are retained rather than reporting only a favorable minimum.

Small samples make the reported p95 descriptive rather than a reliable tail-latency service objective. True cold-cache performance, whole-application peak RSS, network download throughput, concurrent users and distributed scaling were not measured. Per-frame FFmpeg process creation dominates the decoded-window path; batching decoder work is a plausible future optimization, not an implemented result.
