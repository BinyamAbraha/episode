# Dataset provenance

Candidate: https://huggingface.co/datasets/lerobot/svla_so101_pickplace
Pinned revision: f641879e22172be7e8161d5e6c1503c2d2feb657

The card declares Apache-2.0. Retain the original card, source attribution and an Apache-2.0 license copy in redistributable artifacts; identify preview transcodes as modifications. No additional author citation is provided by the card. Public media must be visually reviewed before inclusion.

Verified remote metadata: v3.0, 50 episodes, 11,939 samples, nominal 30 FPS, two 640 by 480 AV1 camera streams, six named state and six named action values. The card's embedded v2.1 layout is stale. Dataset name says so101 while actual robot_type says so100_follower; preserve the latter. Units, coordinate frames, session grouping and exact action control semantics are not documented. A .pos name alone does not establish degrees, radians or control mode.

Shared assets total approximately 82 MiB. Even the first episode requires the two shared video files with this simple adapter. Initial budget: 100 MiB source, up to 500 MiB previews, 3 GiB external dependencies/caches, 1 GiB temporary/browser artifacts. These are estimates pending measurement. Internal source budget below 100 MiB. No bulk artifact belongs in Git.
