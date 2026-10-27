# One-off controlled TEST probe

`test-public-before.jsonl`: old official TEST port 8001, revision e9b4d3ecc; 11 measured public GETs plus one preliminary contract GET. Five-language Wang Xinghao results are all 504 records and the same 20 ordered IDs; page 2 starts at 174240. Only public result fields and preview SGF SHA-256 are stored.

`test-after-probe.cjs` is prepared but has not been run. It must run only after the release owner confirms TEST release and indexes ready. No deployment, DDL, database mutation, import or LLM is performed by this probe. Do not run it against production without separate authorization.

The probe uses existing TEST Node/Playwright/TypeScript and Chromium 1208 at 1280×720. From `/home/fan/Repositories/katrain/katrain/web/ui`, with the three input files copied to an isolated temporary probe directory:

```sh
NODE_PATH="$PWD/node_modules" node /tmp/kifu-search-validation-20261027/test-after-probe.cjs /tmp/kifu-search-validation-20261027/test-public-before.jsonl /tmp/kifu-search-validation-20261027/sgfSerializer.ts /tmp/kifu-search-validation-20261027/test-after-1280x720.png
```

API: the 11 baseline contracts are compared across every public summary/detail field, IDs/order, exact total, and preview SGF hash. Three explicit identity/error contracts and event/fuzzy slow paths are separate. Full HTTP includes reading the response body and JSON decoding; Server-Timing is preserved separately because its handler/worker values exclude FastAPI serialization.

Browser: 32 searches per group for server loopback and loopback plus CDP `Network.emulateNetworkConditions latency=40ms`, each with 1 and 4 independent clients, at most 1 submission per second per client. The emulation is a controlled latency setting, not a measurement or claim of real public RTT. Throughput is unlimited and packet loss is zero. Startup/assets and initial no-result requests occur before timed searches, so results describe established, loaded sessions. Distinct players' first search is labelled. Each group includes actual page-2 form submission.

Enter is captured before React handling. Actual fetch headers and JSON completion are timed. Completion requires a new-response-following canvas clear/draw and two animation frames, exact actual LiveBoard moves/colors/currentMove/size matching `sgfToMoves` compiled from the actual source, first-card ID/selected state, correct title/total, and nontransparent canvas pixels. A single screenshot is taken. Errors/timeouts never become successful zero-result or fast samples. Event/fuzzy paths do not enter player-search percentile aggregates. Small-sample tail values must be reported as empirical values, not a general p99 guarantee.

Context7 documentation lookup failed with a transport error; current official Playwright [initialization-script](https://playwright.dev/docs/api/class-browsercontext#browser-context-add-init-script) and [CDP session](https://playwright.dev/docs/api/class-cdpsession) documentation was consulted as fallback. Probe source is uncommitted until the release owner permits inclusion.
