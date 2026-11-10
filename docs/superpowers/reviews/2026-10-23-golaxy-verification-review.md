# Golaxy Task 2 verification review

Reviewed range: `321e8cc09..9d8f36f29d91d58baa4808338d1e31f617a30f65`. Initial review was against `6a5b4cec4495faf63e0c4ef6439a728e875313f3`; the focused correction is `9d8f36f29d91d58baa4808338d1e31f617a30f65`.
Scope: `katrain/kifu_ingest/sync.py`, new `verification.py`, and `tests/test_kifu_api_verification.py`, against Chunk 2 Task 2 of the approved plan and the production verification diagnosis. Task 3 cron integration is outside this review and is not counted as missing.

## Spec review: approved after correction

No remaining spec must-fix was found in Task 2. The original timeout-retry finding below was reproduced independently, fixed in `9d8f36f29d91d58baa4808338d1e31f617a30f65`, and rechecked before starting the quality review.

The current implementation preserves all five language detail requests, canonical SGF hashes, original player/event values, source membership, reviewed display values, and each album's Chinese public-card comparison. List reuse is scoped to the current call and its target/query/language/page/page-size key. Checkpoints bind the complete provided manifest, complete receipt, normalized target, algorithm, and language set; only complete per-album evidence is saved. Partial albums restart, binding changes trigger fresh verification, corruption and symlinks fail closed, and final returned checks cover all games. Existing receipt-based resume and failure state coverage remains passing. Task 3's cron wiring is not part of this approval.

### Resolved P2 — Per-request wall-clock timeout bypassed the allowed transient retry

In initial commit `6a5b4cec4495faf63e0c4ef6439a728e875313f3`, `katrain/kifu_ingest/verification.py:68–76` immediately raised from `except TimeoutError` when `asyncio.wait_for` reached the per-request wall-clock cap before the overall verification deadline. It did not enter the two-attempt transient retry path even when sufficient absolute budget remained.

The approved requirement is: “one retry only for timeout/transport transient errors; every attempt wrapped by the absolute monotonic verification deadline using `asyncio.wait_for`, with httpx inactivity timeout also clamped.” A slow or trickling response can hit the whole-request cap without triggering an httpx inactivity timeout. Such a first-attempt timeout therefore needs the same bounded retry behavior; exhausting the overall verification deadline must still stop immediately. The initial `test_per_attempt_timeout_is_a_wall_cap_without_caller_deadline` expected one attempt and fixed the implementation's narrower behavior in place.

Minimal reproduction, run in the worktree with the project Python and only an in-process HTTP transport:

```python
import asyncio
import time
import httpx
from katrain.kifu_ingest.verification import VerificationGET

async def main():
    calls = []
    async def handler(request):
        calls.append(request.url.path)
        if len(calls) == 1:
            await asyncio.sleep(0.1)
        return httpx.Response(200, json={"ok": True})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        getter = VerificationGET(
            client, timeout=0.02, deadline=time.monotonic() + 1,
            clock=time.monotonic, sleep=asyncio.sleep,
        )
        try:
            result = await getter.get("https://example/list", {})
            print("status", result.status_code, "attempts", len(calls))
        except Exception as exc:
            print(type(exc).__name__, str(exc), "attempts", len(calls),
                  "remaining", round(getter.remaining(), 2))

asyncio.run(main())
```

Initial actual result: `TimeoutError album API request wall-clock timeout attempts 1 remaining 0.98`.
Expected: first request is cancelled at its cap, a single retry succeeds, and total verification remains inside the absolute deadline. Repeated request-cap timeouts must stop after two attempts; an exhausted absolute deadline must never retry.

Correction verified: current `verification.py:69–79` routes attempt wall-clock timeouts and transient httpx failures through the same two-attempt bound. It checks the absolute deadline before retry and after retry waiting. New focused cases prove first-cap-timeout recovery, two-cap-timeout failure, and deadline exhaustion during the retry delay without a second request; the existing deadline cancellation case remains passing.

## Independent quality review: approved within scope

Started only after the corrected spec review passed. No remaining correctness, data-integrity, or budget must-fix was found in the scoped implementation. The review checked the actual checkpoint load/save/reuse paths, exact bindings and evidence validation, unchanged per-album completion timestamps, finite two-attempt HTTP behavior, per-invocation cache ownership, and final check coverage. No change to publication, translation, or batch-state transitions is hidden in the reviewed diff.

TTL has the usual consumption-time boundary: an album is reusable only while its age is below 24 hours at `AlbumCheckpoint.get()`. A focused fake-clock case starts with age 86,399 seconds, then advances six seconds while checking another album: return is `verified` with 10 checks, the first proof is then 86,405 seconds old, and its stored `completed_at` is unchanged. This is not classified as a must-fix: the approved requirement rejects expired checkpoints on reuse and does not require a simultaneous final-return snapshot across sequential checks. This approval does not claim every reused proof remains younger than 24 hours at the exact final return instant. An exact-age-86,400-second lookup was also checked and performs all six requests again.

## Verification performed

Read the actual implementation diff, full new verification tests, existing verification coverage in the cron test file, Stage's atomic write primitive, the approved Task 2 requirements, and the bounded production diagnosis.

Command:

```text
/Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest tests/test_kifu_api_verification.py tests/test_kifu_incremental_state.py tests/cron/test_kifu_ingest.py -q
```

Initial result: **100 passed in 0.47s**. The initial suite did not establish the missing attempt-timeout retry requirement; the historical reproduction above demonstrated its failure.

After the correction, independently reran the same command: **102 passed in 0.58s**. Also ran:

```text
git diff --check 321e8cc09..9d8f36f29d91d58baa4808338d1e31f617a30f65 -- katrain/kifu_ingest/sync.py katrain/kifu_ingest/verification.py tests/test_kifu_api_verification.py
```

Result: exit 0, no whitespace errors.

Additional short in-process checks, using `AlbumAPI`/`Clock` from the focused test module and `TemporaryDirectory`, passed:

- Exact 24-hour expiry performs all five details and the public-card request again.
- A different target path or nondefault port cannot reuse a prior target's checkpoint.
- A synthetic `Stage._atomic` disk failure propagates and cannot return `verified` or leave a completed checkpoint file.
- The TTL-crossing case above preserves the original completion timestamp when another album is saved.

All checks used local temporary data or mocked HTTP. No production SSH, model calls, database writes, deployment, or access to `data/kifu-album` was performed. No implementation file was modified and this report was not committed.
