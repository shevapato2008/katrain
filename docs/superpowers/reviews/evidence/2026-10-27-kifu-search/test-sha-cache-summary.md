# TEST SHA-cache quick round: correctness passes, 200ms gate still fails

Official TEST `127.0.0.1:8001`, release `06d8e732f2c9cb956c76d9c9806f3f3584adcd43`, image `sha256:80be16d9e88e2d754c3d646944c0569ed4db9be82dd0c02226327be4eadf8987`, container `7266e0c60af67f13aca0f9c66d434967226aa8e77da4d9b12249269c0d48203b`. Release owner confirmed a fresh process with health/inspect only, no list request or warm-up before this probe. Indexes were unchanged and already confirmed valid by the owner.

All **11 public old/new contract comparisons passed**: all 20 ordered IDs, exact total, public display/rank/report fields, preview detail, and preview SGF SHA-256. Five language variants and the second page preserve Wang Xinghao's 504 records; Ke Jie remains 1043, Zhang Tao 488, alias 504, and both representative zero-result queries remain 0. No new all-artifact, event/fuzzy or debug/cache-inspection request was added.

First observed list request after the confirmed fresh deployment: **781.89ms full HTTP**, first connection, handler 761.563ms, display 624.493ms, candidate 103.570ms. This first observation is separate from later requests and is not called warm. Compiled-cache hit/miss was not directly observed and is not inferred from process freshness or query text.

Subsequent Wang first-page language HTTP observations were 248.61ms (tw), 224.36ms (jp), 166.00ms (ko), and 196.20ms (en), on the reused connection. Page 2 was 660.75ms (display 600.608ms). The first observed Ke Jie query was 1935.27ms (display 1874.776ms). HTTP includes full response-body receipt; handler/worker Server-Timing excludes FastAPI serialization.

The single-client loopback browser probe completed exactly **5 correct paints** and automatically stopped with `budget_stop`; process exit was 0 because this is an intentional gate stop, not an assertion of performance success. All five matched new first-card ID/selection/title/total, actual board moves/colors/currentMove/size against real `sgfToMoves`, post-response canvas draw, two animation frames and nontransparent pixels. No page errors occurred. Browser viewport remained 1280×720; no repeat screenshot was taken.

| Browser action | Exact total | Submit → correct paint | Fetch → JSON | Response → paint | Display | Candidate |
|---|---:|---:|---:|---:|---:|---:|
| 王星昊 first board in this browser | 504 | 507.3ms | 271.5ms | 210.7ms | 141.655ms | 92.204ms |
| 柯洁 | 1043 | 539.7ms | 402.7ms | 118.4ms | 278.897ms | 88.485ms |
| 一力辽 first query string observed in probe | 1041 | 3693.3ms | 3543.0ms | 133.0ms | 3062.830ms | 372.129ms |
| 王星昊 repeat | 504 | 349.0ms | 237.8ms | 96.7ms | 134.255ms | 79.530ms |
| 王星昊 actual form jump to page 2 | 504 | 530.3ms | 397.7ms | 108.3ms | 308.721ms | 64.642ms |

Every complete browser sample exceeded 200ms. Display/proof remains the main observed cost, with candidate work also material. Queue was only 0.188–0.243ms in these browser samples; count/page were low single digits to about 15ms. Response-to-paint is still a separate approximately 97–133ms warm budget component (first board 210.7ms).

No 4-client, 40ms-CDP, 32/128-sample, PROD, DDL, import or profile work was performed. Exact count: 11 API contract GETs + 1 initial browser setup list GET + 5 timed search GETs = **17 public list GETs**. Raw second-round evidence is `test-sha-cache-after.jsonl`; first-round `test-after*` evidence is retained unchanged.
