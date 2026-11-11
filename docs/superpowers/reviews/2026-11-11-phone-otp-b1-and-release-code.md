# Phone OTP B1 and release-helper code review

Date: 2026-11-11. Baseline: `60817167c`; reviewed current B1 frontend working tree and the isolated task-local release-helper delta.

| Review | Decision |
| --- | --- |
| B1 specification compliance | **Approved** — R1 fixed and independently rechecked |
| B1 code quality | **Approved** — no remaining blocking findings in this slice |
| Release-helper configuration delta | **Approved**, for the exact helper bytes recorded below |

The existing B1 visual approval remains valid. This code review does not cover the in-progress backend, B5 binding UI, the later whole-feature review, any real private manifest, credentials, SSH, Docker execution, or deployment.

## R1 — closed: retire password-form work on identity change and distinguish discarded candidates

**Original priority: P1; fixed.** Before correction, `katrain/web/ui/src/features/auth/LoginMethods.tsx:9,17,25` read `login` but not `identityKey`; its revision/abort cleanup ran only on tab change and unmount. `katrain/web/ui/src/context/AuthContext.tsx:154,163` resolved a stale password login with `undefined` after a generation mismatch. The form treated that resolution as success.

Reproduced with the real `AuthProvider` and `LoginMethods`, using fake fetch only:

1. Resolve the initial identity as technical guest and open the password tab.
2. Fill credentials and suspend the password-login response.
3. Call `logout()` while the same form remains mounted.
4. Release the old login response.

Expected: no success callback, empty private fields, no installed candidate token.

Originally observed: **one success callback, both username and password retained, token still null**. The canonical generation guard protected token installation, but the UI could falsely close/navigate as a successful login and retain the previous identity's credentials. This violated the requested identity-change cleanup and honest success boundary.

Minimum correction: reset/abort password-form state when the canonical identity changes, and make an aborted/superseded `AuthContext.login` reject or explicitly report that it did not install an identity. A generation change without an `identityKey` change must also not resolve as success. Keep successful password login functional; do not broaden this into a new auth subsystem.

Focused reproduction ran once and failed as expected:

```sh
npm test -- src/features/auth/LoginMethods.astra-review.test.tsx
```

The temporary test was moved out of `src` after reproduction to `output/playwright/phone-otp-2026-11-11/LoginMethods-identity-review.test.tsx` for the implementer to adopt. No product source was changed by this review.

**Closure verification:** `AuthContext.login` now asserts generation/signal before sending, after parsing the candidate token, after canonical `/me`, and in its error path. A retired candidate rejects with `ApiError(code="identity_changed")` rather than resolving as success. `LoginMethods` resets/aborts private password state on `identityKey` change; the classified rejection also clears it for a null-to-null logout. The reviewer read these exact changes and independently ran the adopted real-provider regression file:

```sh
npm test -- src/features/auth/LoginMethods.identity.test.tsx
# 1 file passed; 4 tests passed
```

The four tests cover guest-to-signed-out retirement, null-to-null logout retirement, normal password success and normal OTP success. Both normal paths install the canonical identity and invoke success exactly once. R1 is closed; no new blocking issue was found in this targeted re-review. No visual change or new screenshot was needed.

## B1 checks satisfied

- Request DTOs use `phone/purpose/flow_id` for challenge and `challenge_id/code/flow_id` for login; submit does not derive identity from the supplied phone. Flow entropy is 128 bits, OTP is a single six-ASCII-digit input, and 300-second expiry/cooldown/error semantics are covered by focused tests.
- `loginPhone` keeps the candidate token in memory, calls `/me` with that candidate, checks generation/abort and canonical username, and only then writes the existing allowed access-token storage and user state. Phone/code/password are not written to storage or URLs by the B1 changes. UI errors render known local messages rather than upstream body text.
- OTP form identity changes, phone edits, tab switches and close/unmount retire private challenge work with revision and abort guards. Existing real-browser `galaxy-canonical-confirmed.png` confirms that a normal OTP success still closes the actual modal after canonical confirmation; the identity-reset effect is not treated as a hypothetical failure.
- Strict Kiosk keeps its launcher redirect and no local login form; the phone API and auth methods also reject direct strict-mode login. Non-strict technical guests can use the shared login methods.
- Legacy `RegisterDialog` delegates to the shared login dialog. `ZenModeApp` now handles its success as login and no longer opens a second password dialog after OTP registration. Temporary Fixture entries remain intentionally limited to the B1 stage and are due for deletion in B4.
- All 11 PO catalogs add exactly the same 25 nonempty keys, preserve every existing translated entry, and retain the `{seconds}` placeholder. Signup-once/50-points, mainland +86, old-account binding guidance, 5-minute validity, unknown and rejected semantics were inspected across the languages. Each of the 11 compiled MO catalogs contains the 25 keys. This is code/catalog verification, not a claim of native-speaker or full multilingual visual acceptance.

After correction, root reported the focused frontend run as 36 passed / 5 mode skips, strict run as 13 passed / 15 mode skips, and `tsc -b` passing; both build modes had already passed in the preceding B1 check. This review independently ran only the four affected real-provider regression cases above; it did not repeat builds or a screenshot matrix.

## Release-helper delta approval

Reviewed `output/releases/phone-otp-20261111/tools/{native-release.py,cloud-release.py,baseline-diff.patch,README.md,test_release_tools.py}`. The recorded patch matches the complete actual delta from the named predecessor helpers. `SHA256SUMS` verifies all five files, and the cloud helper's internal native hash matches.

| Helper | Approved SHA-256 |
| --- | --- |
| `native-release.py` | `153b6f0538f67544c8ebc1cd04467a49fff5d16195cb6139898194bfe6d17a81` |
| `cloud-release.py` | `e8d5e34677b78f2db01b489ab5608600c91980a10f06cc262c9abfce5beac673` |

- The patch requires exactly `KATRAIN_BUILD_SHA` plus the six public SMS fields: enabled=`true`, credential target=`/run/secrets/aliyun-sms.env`, approved sign/template, daily limit TEST=`10` / PROD=`50`, and an empty trusted-proxy list. Alternative values, extra keys, existing SMS fields, wrong target/site/environment/User are rejected. No AK/SK is added to Env or image payload.
- Existing non-build Env entries retain their literal bytes and order; only the build SHA is replaced in place and six public fields appended. Existing enabled/live, billing=true, free reports=0 and Max sale state are preserved. The cloud boundary retains all eight WeChat keys and the existing exact read-only secret binding.
- The entire HostConfig is cloned with one exact site-bound single-file `:ro` bind appended. Existing target/ancestor/descendant overlap is refused. Config, runtime mounts, resources, networks, volumes, ports, Healthcheck and User are compared; runtime acceptance permits only the old mounts plus the specified new read-only file.
- Credential inspection uses `lstat` only: no opening, reading, hashing or printing credential contents. It rejects symlink components, non-regular/multilink files, non-0600 file mode and non-0700 parent mode; PROD owner is 10001:10001. The prepared file/directory metadata is compared again before apply, switch, create and verification. Host ancestors need not be traversable by the container UID because Docker daemon root resolves a single-file bind.
- Prepare writes the full before-image and payload privately, binds their hashes and immutable target/image/source identifiers, and does not switch services. Apply retains reviewed-manifest hash checks and live config CAS. The helper refuses rollback-compatibility opt-in; it does not add schema deletion, balance changes or a migration container. Public receipts expose permitted field names/hashes and accurately describe the SMS bind addition.
- The nine existing offline tests use synthetic inspect/metadata and cover the actual config delta and relevant refusals. Root independently reran them successfully; this review inspected their coverage without repeating the run.

This approval covers the helper code and its allowlist. A fresh private manifest and actual release remain separate planned evidence; none was read or executed during this review.
