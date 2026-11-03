# TEST first release: correctness passes, 200ms gate fails

Measured 2026-10-27, official TEST `127.0.0.1:8001`, published revision `dc17489e2269926b34da5f040a74990d2f4db3c9`, image `8754652a8d475d65d2671573683553ec940f0380590f206da0262691a120768c`. Release owner confirmed the three concurrent indexes ready before measurement.

All 11 old/new public contract comparisons passed across total, all 20 ordered items, display/rank/report fields, preview detail fields, and first preview SGF SHA-256. Explicit `player_id=25` returned 504, unknown ID returned 0, and conflicting q/ID returned 422. Two separate event/fuzzy queries returned successful complete responses, outside player timing aggregates.

First observed list request after restart (the probe's first connection): Wang Xinghao cn HTTP **974.94ms**, handler 953.625ms, display 799.369ms, candidate 109.550ms. This is a single observation, not a cold-start distribution. The health check had already passed before the probe.

Warm public Wang first-page language requests were **452.84–792.65ms** HTTP; page 2 was **850.88ms**; Ke Jie was **2580.99ms**. Handler/worker Server-Timing excludes FastAPI serialization; the separate full HTTP timings include reading the full response body.

At the release owner's stop instruction, the temporary probe was interrupted by SIGINT (exit 130). No product process was signalled. It had completed **27** browser searches, all in **1-client server-loopback without network emulation**. The first eight distinct player samples already demonstrated the failure; the later completed samples are retained in raw evidence rather than discarded. No helper/profile load overlapped these samples, per the release owner. **4-client and 40ms-CDP groups were not run and are not validated.**

All 27 browser samples passed real correctness checks: correct new first card/selection/title/total, actual board moves/colors/currentMove/size equal to real `sgfToMoves` parsing, canvas draw after the new response, two animation frames and nontransparent pixels. No browser page errors were recorded. These are successful paints that fail the latency budget, not functional failures.

| First eight distinct queries | Exact total | Submit → correct paint | Full fetch → JSON | Response → paint |
|---|---:|---:|---:|---:|
| 王星昊 | 504 | 815.5ms | 511.8ms | 279.8ms |
| 柯洁 | 1043 | 2715.5ms | 2585.0ms | 106.7ms |
| 申真谞 (first observed query) | 1150 | 996.5ms | 888.7ms | 95.4ms |
| 朴廷桓 (first observed query) | 1586 | 2859.1ms | 2765.8ms | 82.0ms |
| 辜梓豪 (first observed query) | 749 | 1088.9ms | 976.3ms | 98.9ms |
| 丁浩 (first observed query) | 635 | 1509.9ms | 1391.9ms | 104.9ms |
| 井山裕太 (first observed query) | 1326 | 1429.8ms | 1309.9ms | 108.9ms |
| 一力辽 (first observed query) | 1041 | 3782.6ms | 3673.4ms | 84.8ms |

Across retained 27 observations, median was 1429.8ms, minimum 563.1ms, maximum 3803.9ms. These bounded diagnostic observations are not a claim about production p99 or public-network conditions.

Remaining dominant cost: display/proof handling. For the first eight browser queries, display timing ranged from 395.818ms to 3106.179ms; candidate handling reached 641.558ms for another first-seen player. Queue waiting remained about 0.1–0.3ms, and count/page were generally single-digit to low tens of milliseconds. Warm response-to-paint still cost about 82–109ms after the first board's 279.8ms initialization; it remains a separate end-to-end budget component.

Explicit identity lookup was 561.13ms (display still applies). Separately, 围甲 was 2330.96ms / 22660 results and 王 was 2105.05ms / 23252 results. Zero-result and error requests are excluded from fast player successes.

Raw evidence: `test-after.jsonl`; one verified 1280×720 screenshot: `test-after-1280x720.png`. No PROD request, DDL, import or runtime configuration mutation was made by this validation agent.
