# Hardware hotplug — verification and independent review

Product range: `6cdd62b5b..49b7cf79c052591bcc5532bea4dbee36e521bf87`, following develop `954a374bdd0cf5661a9e7e556af7f699928edfbe`.

The independent spec reviewer returned **APPROVED**, with no material gaps or extra scope. A new isolated `gpt-6-astra` / `max` reviewer inspected the complete product diff, tests, locked builds and bounded release operators. Final verdict: **APPROVED**, no unresolved blocking or important findings.

## Verification

- TDD failures were observed before implementation: camera arrival/removal/identity handling, LED deadlines/stale batches/handshake ordering, and preview stale-frame/retry/bitmap cleanup.
- Controller integrated Python slice: **453 passed**; upstream preferences and SPA boundary checks: **67 passed**.
- Locked frontend integration: **91 passed**, covering preview, calibration, device preferences and root bootstrap.
- Independent reviewer: **161 product Python** and **61 UI** tests passed. The final operator suite independently passed **60 tests**.
- Clean candidate checkout full and strict Kiosk builds passed TypeScript/Vite and strict SSO/Galaxy/three/live guards. Lockfile SHA256 `e77b869cc7a6cc729a98d79e2176e97635a3d128d54bfdd7ba0db64cae85282f` matches the existing isolated `npm ci` installation; release Vitest is 4.1.8.
- Full output: 494 files, index SHA256 `9467996d28111cca677a63b84684fc7a9b90c8a3a95ed893b99ea2118b621a02`; strict: 387 files, index `70f3269f0f3f72988bd5e7a5d545ed27954e13d01ace6f5b498896b954857c4e`. Module report has no Galaxy modules and strict manifest is true.
- `git diff --check` passed. Existing chunk-size advisories remain.

The isolated board-lifespan suite is blocked by 17 fixture import failures: its unchanged fixture replaces `katrain.web.core.__path__` with an empty path and omits a `baipu_history_sync` stub, failing at unchanged `server.py:639`. The tracked source exists. No unrelated fixture/package restructuring was added; this is not a claim that full pytest passed.

## Reviewed release corrections

The reviewer found that an initial CDP blank-navigation failure could reach cleanup before original Go was proven safe to stop. The operator now tracks positive blank proof and original-stop authority separately. Initial navigation/page-ID/blank-proof failures retain the lock and do not stop/start/restore the original mode. Three new regression cases cover these failures; the already-safe apply-before-start rollback remains valid.

Actual read-only device preflight then correctly refused the installed `chromium-bin` name. The revised helper verifies the kernel `/proc/PID/exe` exact path `/usr/lib/chromium/chromium-bin` together with the kiosk cgroup; argv spoofing, wrong/copied/deleted executables and wrong/prefix-spoofed cgroups fail. Sole-CDP, network, original blank proof and rollback gates remain. Independent Astra re-review approved these exact bytes:

| Operator | Final approved SHA256 |
| --- | --- |
| RK | `089122e5cea71b8236698086642c4bd79f9681de737f142e002deebf5ff9da39` |
| Cloud preparation | `a747415f77e197f1d365bb0839e797131a55c49d47543cf0673b00d0fc5f5b23` |
| Existing native helper | `98e816acbe780baf95e8f8168073ba2894efe852bb0bd3c0b454264e89027108` |

Operator code/tests, exact hashes, prior versions and offline results remain under `output/releases/hardware-hotplug-20261108/`. Physical USB enumeration and unplug/replug acceptance are separate from this approval and remain subject to actual device observations.

## Auth-gate recovery and handoff

Actual candidate startup succeeded, but the calibration route rendered its explicit anonymous AccessPrompt. The safety guard refused automatic stop/restoration. A finish-only helper `c3177dec243861bc347d0f8eda8f90a981cabbcf7e6a30c1a9cd291e01193c13` and exact resume plan `341126d7c5d03707c7662ffc9c0819252c5416f3abe5a733de87082e35044d5c` were independently approved; all69 combined operator/recovery tests passed. It allows only fresh CAS, same-page restoration and owned-lock release, with no service/source/auth changes and no false authenticated-preview claim.

Its read-only preflight then refused because the user/external page had moved to the launcher login flow. No recovery apply or manual unlock occurred. After the user's explicit pause and resume, fresh read-only evidence showed a new idle launcher page and no maintenance lock; all887 installed files and the hardware marker still matched the published candidate. Current user state was preserved, and RK was handed off to the separate coordinated release session. See [the release receipt](../../operations/hardware-hotplug-release-2026-11-08.md). This handoff does not claim that the original pre-pause URL or authenticated camera preview was restored.
