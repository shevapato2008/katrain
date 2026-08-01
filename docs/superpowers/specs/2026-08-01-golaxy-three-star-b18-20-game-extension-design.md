# Golaxy 3-Star b18 20-Game Extension Design

## Goal

Extend the existing valid evidence for pure KataGo b18 against Golaxy 星阵3星 so that both `b18@32` and `b18@64` contain exactly 20 conclusive games. The fixed execution order is `b18@32` first, followed by `b18@64`.

## Frozen inputs

- Opponent: Golaxy 星阵3星, API wire level `3300`.
- Player model: pure `b18`; no HumanSL profile and no `humanSLProfile` request field.
- Candidate settings: `maxVisits=32` and `maxVisits=64` only.
- Game and query settings: 19x19, Chinese rules, komi 7.5, no handicap, `wideRootNoise=0.04`,
  `reportAnalysisWinratesAs=BLACK`, and a 400-move cap.
- Adjudication: reuse the same `play_one_game` terminal classification and strict runner wrapper used by v3-v5.
  Verified Golaxy resign is a conclusive player win; verified pass or player pass is scored; move-cap games are scored.
  `inconclusive_score`, `inconclusive_unsettled`, and `inconclusive_unstable` do not enter the denominator and repeat the
  same color. Although `play_one_game` represents malformed/unverified terminal and unavailable player moves as
  `inconclusive_terminal` and `inconclusive_engine`, the strict wrapper treats both as non-replenishable runtime drift:
  they close the reservation with `stopped` and terminate rather than silently sampling past an engine/protocol error.
  This preserves the user-approved rule that any remote or engine error stops the campaign.
- Referee: pure `b28`, SHA-256 `798da8fe3e9819f09535240b1bc29cb3047a4fa981433c56c491e57007a3d3f0`.
  Score at 200 visits, then recheck every non-resign conclusive score at 800 visits; an unsettled recheck,
  missing/non-finite score, or absolute score change of at least 1.0 becomes `inconclusive_unstable`.
- Engine identity: selected model `b18`, `model_sha256_verified=true`, model SHA-256
  `9d7a6afed8ff5b74894727e156f04f0cd36060a24824892008fbb6e0cba51f1d`.
- Parent ledger: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/golaxy_b18_binary_stars_20260726/binary_search_v5.jsonl`.
- Parent SHA-256: `9a5796b624924266efa6eb6937a4cb4833468bfa0270e5f115fc6d2714fc4082`.
- Existing valid evidence: `b18@32` is 1–3 with B/W balance 2/2; `b18@64` is 7–3 with B/W balance 5/5.
- Expected new valid games: at most 16 for `b18@32`, then at most 10 for `b18@64`.

The continuation must reject a changed parent hash, changed model identity, changed wire level, changed game/query or
adjudication parameter, or evidence whose counts and color balance do not match these frozen inputs. The v6 header
stores these values and the complete health identity snapshot.

## Ledger and recovery

Create a new append-only v6 continuation ledger. Do not modify v5. Its header records the protocol version, direct parent path and SHA-256, frozen target and ordering, engine identity snapshot, and execution rules.

The v6 initial prefix contains only the 14 relevant conclusive v5 results for 星阵3星 `b18@32` and `b18@64`, copied as provenance-bearing `carry_result` records in parent order. Unrelated candidates and levels are not imported. Every carry must be validated against the SHA-verified parent row.

For each live attempt, append and fsync a reservation before starting the game. Close it with exactly one result or
stopped record. A caught, definite runtime failure after reservation appends `stopped` to that ledger and terminates.
If process restart discovers an unmatched reservation, freeze the ledger permanently: do not append a synthetic stop
and do not resume it. Only after explicit operator authorization may a later-version continuation bind the frozen
ledger SHA, inherit its closed results, and explicitly record the excluded uncertain reservation. A stopped campaign
likewise requires explicit authorization and a new continuation ledger; neither case is silently retried.

A preflight failure occurring before reservation creates no attempt-bound stopped row and leaves a newly initialized
ledger safe to retry. It may be recorded only as a non-attempt campaign event whose schema cannot be mistaken for a
closed reservation.

## Scheduling

The scheduler is deterministic:

1. Select `b18@32` until it has 20 conclusive results.
2. Then select `b18@64` until it has 20 conclusive results.
3. Stop complete when both targets are met; never schedule a 21st conclusive game.

Colors alternate within each candidate based on its conclusive count. Because inherited evidence is balanced, the first new game for each candidate is black, followed by white. An inconclusive game does not advance the conclusive count and therefore repeats the same color. Maintain a five-second cooldown between attempts.

## Fail-closed live execution

Before any reservation, verify `http://127.0.0.1:8000/health`, both frozen b18 player and b28 referee SHAs,
`selected_model` and `model_sha256_verified=true` for the applicable request, the exact effective player query
(`model=b18`, no HumanSL profile, requested visit count), the exact referee query (`model=b28`, 200 or 800 visits), and
the Golaxy level binding. Revalidate the applicable engine wrapper identity attestation on every analysis response, not
merely at startup. Use one game at a time with no parallel requests.

Only a definite runtime/remote failure caught by the same live process after reservation appends an attempt-bound
`stopped` record and terminates. This includes HTTP/business error `7002`, rate limit, quota error, malformed response,
or engine identity drift. A restart-discovered unmatched or otherwise uncertain reservation is never appended to; it
is handled only by the frozen-ledger continuation process above. There is no automatic retry.

Conclusive wins and losses count toward 20. Inconclusive adjudications remain in the ledger but do not enter the denominator.

## Verification and reporting

Unit tests cover parent/hash validation, selective carry import, exact inherited results, fixed candidate order, color alternation, inconclusive same-color replay, exact stop at 20, and fail-closed recovery. Existing engine/query validation is reused rather than weakened.

This is a **descriptive extension** chosen after observing the inherited 1–3 and 7–3 results, not an independently
preregistered 20-game confirmation. For each candidate, report inherited results and newly added results separately,
then the combined 20-game result; the combined figure must not be presented as an independent confirmatory estimate or
used to retroactively select a visits threshold.

Also report new attempts, inconclusive games, black/white counts, completion status, ledger path, and final SHA-256.
Record the completed evidence in `EXPERIMENTS.md` only after the ledger passes replay validation.
