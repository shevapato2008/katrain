# One-off controlled TEST probe

`test-public-before.jsonl`: old official TEST port 8001, revision e9b4d3ecc; 11 measured public GETs plus one preliminary contract GET. Five-language Wang Xinghao results are all 504 records and the same 20 ordered IDs; page 2 starts at 174240. Only public result fields and preview SGF SHA-256 are stored.

`test-after-probe.cjs` was used for the first TEST release, which failed the latency gate; the run was stopped early (see `test-after-summary.md`). It is now restricted to the second-round quick plan below and has **not** been run in that form. Wait for an explicit new-release-ready instruction. No deployment, DDL, database mutation, import or LLM is performed by this probe. Do not run it against production without separate authorization.

The probe uses existing TEST Node/Playwright/TypeScript and Chromium 1208 at 1280×720. From `/home/fan/Repositories/katrain/katrain/web/ui`, with the three input files copied to an isolated temporary probe directory:

```sh
PROBE_RELEASE_REVISION=CONFIRMED_REVISION PROBE_FRESH_PROCESS=1 NODE_PATH="$PWD/node_modules" node /tmp/kifu-search-validation-20261027/test-after-probe.cjs /tmp/kifu-search-validation-20261027/test-public-before.jsonl /tmp/kifu-search-validation-20261027/sgfSerializer.ts
```

API: exactly the existing 11 baseline contracts are compared across every public summary/detail field, IDs/order, exact total, and preview SGF hash. No extra identity/event/fuzzy matrix is repeated in round 2. Full HTTP includes reading the response body and JSON decoding; Server-Timing is preserved separately because its handler/worker values exclude FastAPI serialization. First observed list request and reused-connection status are recorded. Set `PROBE_FRESH_PROCESS=1` only if the release owner confirms a fresh process. The first observation must be reported separately; it is not described as warm.

Browser: one client, server loopback, **at most 6** real paints: Wang, Ke, first-observed Ichiriki query, Wang repeat, actual page-2 form submission, and first-observed Shin query. If any of the first five exceeds 200ms, the probe records `budget_stop` and stops after the five required samples; it never automatically starts 32/128 samples, 4 clients, or 40ms emulation. Additional network/concurrency groups require a new explicit instruction after this gate passes. At most one submission per second; assets and an initial no-result page load precede timed searches. A third screenshot path is optional; omit it to avoid repeating the existing representative screenshot.

`first_observed_q_in_probe` describes only whether that exact query string has been observed in this probe. It does **not** imply a first-pass compiled-cache miss: another name, translation, alias or prior owner request may share the same artifact. Cache hit/miss is explicitly recorded as `not_observed`; no debug endpoint or cache inspection is added.

Enter is captured before React handling. Actual fetch headers and JSON completion are timed. Completion requires a new-response-following canvas clear/draw and two animation frames, exact actual LiveBoard moves/colors/currentMove/size matching `sgfToMoves` compiled from the actual source, first-card ID/selected state, correct title/total, and nontransparent canvas pixels. A single screenshot is taken. Errors/timeouts never become successful zero-result or fast samples. Event/fuzzy paths do not enter player-search percentile aggregates. Small-sample tail values must be reported as empirical values, not a general p99 guarantee.

Context7 documentation lookup failed with a transport error; current official Playwright [initialization-script](https://playwright.dev/docs/api/class-browsercontext#browser-context-add-init-script) and [CDP session](https://playwright.dev/docs/api/class-cdpsession) documentation was consulted as fallback. Probe source is uncommitted until the release owner permits inclusion.
