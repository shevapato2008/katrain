# Timed five-value name research pilot

Read-only pilot, 2026-10-04 UTC. Exactly three existing identity-clear Go professionals were timed: 吴清源 (`player:1`), 赵治勋 (`player:608`), and 李昌镐 (`player:143`). No database, source data, or application code was changed.

## Result bundles

| Player | ID | cn | tw | jp | ko | en | identity confidence |
|---|---:|---|---|---|---|---|---|
| 吴清源 / Go Seigen | 1 | 吴清源 | 吳清源 | 呉清源 | 우칭위안 | Go Seigen | high |
| 赵治勋 / Cho Chikun | 608 | 赵治勋 | 趙治勳 | 趙 治勲 | 조치훈 | Cho Chikun | high |
| 李昌镐 / Lee Chang-ho | 143 | 李昌镐 | 李昌鎬 | イ・チャンホ（李昌鎬） | 이창호 | Lee Chang-ho | high |

Each value and URL is recorded in the paired JSON artifact. Sources are Wikipedia language page titles where available, otherwise official association or specialist Go sources already captured in the repository. Existing identity anchors were read from prior source-only evidence; no owner was inferred or written.

## Timing

| Player | Lookup | Cross-language identity verification | Normalization | Final bundle | Measured phase sum |
|---|---:|---:|---:|---:|---:|
| 吴清源 | 2.083 s | 0.097 s | 0.101 s | 0.079 s | 2.360 s |
| 赵治勋 | 9.960 s | 0.094 s | 0.076 s | 0.079 s | 10.209 s |
| 李昌镐 | 2.192 s | 0.081 s | 0.076 s | 0.075 s | 2.424 s |
| **Mean** | **4.745 s** | **0.091 s** | **0.084 s** | **0.078 s** | **4.998 s/player** |

The summed measured phase latency is 14.993 s total, or 4.998 s per player. The sequential human wall interval was `2026-10-04T12:07:12.988Z`–`2026-10-04T12:07:54.194Z` (41.206 s), or 13.735 s per player. The wall estimate includes orchestration and tool gaps; the phase sum is tool-operation latency. No operations were parallelized in this pilot, so it does not estimate a parallel worker schedule.

## Warnings

The Zhao Japanese Wikipedia open returned an internal error during the timed batch. The official Nihon Ki-in profile and Korea Baduk Association record already captured in the repository identify the same 1956-born professional, so this is a fetch/tool warning rather than identity ambiguity. Zhao `cn` is marked medium source confidence because the Chinese Wikipedia page is a traditional-rendered article/redirect and the prior memo records a pending verified mainland official body capture. The identity itself remains clear; no HOLD is raised for person identity.

Source reuse: [Wu evidence](kifu-name-wu-evidence-status.md), [Zhao east follow-up](kifu-name-zhao-608-east-followup-2026-10-02.md), [Zhao matrix](kifu-name-zhao-11lang-matrix.md), [Lee pilot](kifu-name-lee-chang-ho-research-pilot.md), and [Lee current preimages](kifu-name-lee-34-current-preimages-2026-10-02.md).
