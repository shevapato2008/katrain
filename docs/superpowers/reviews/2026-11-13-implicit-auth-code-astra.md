# Implicit phone authentication — independent code review

Date: 2026-11-13. Reviewer: independent Astra Max auth reviewer.

**Result: Approved auth slice after I1 follow-up. No Critical or Important findings remain.** The initial finding and its verification are preserved below.

## Scope and review basis

Reviewed Tasks 1–3 against the approved requirements, implementation plan and round-2 plan review. Child production baseline: `6a847cd7b`; approved plan/spec HEAD: `4ec4ded953dce7b9c7739ac6d66b2eba76fd7b7d`. Parent baseline in `/Users/fan/Repositories/smartbox-software/.worktrees/freeplay-analysis-20261111`: published `19aa5487ba5619f5eada71d19c02c12fa0e7a64e`.

Scope is the working auth diff: child OTP service, phone endpoints, remote adapter, React API/context/auth forms and focused tests; published parent identity adapter, auth router, launcher template/JavaScript, five locale changes and focused tests. The original parent's unpublished daemon implementation was neither inspected nor used. Report/provenance/startup/catalog work and deployment are outside this review.

## Important finding

### I1 — Invalid or expired proof retains private credentials and, in the launcher, a stale verified state (closed)

- **Locations:** `katrain/web/ui/src/features/auth/PhoneOtpForm.tsx:75`–`87`; `katrain/web/ui/src/features/auth/PhonePasswordDialog.tsx:76`–`83`; parent `setup-wizard/app/static/js/launcher.js:663`–`708` (`makePhoneFlow.update` and `showFailure`).
- **Trigger:** verify an unbound phone, enter an existing account name, reveal and fill the original-password field, then let the five-minute proof expire. The React forms compute expiry and disable submission without clearing OTP/password state or retiring the pending request. The launcher likewise retains the password and the masked-phone “Verified” label. Its `challenge_invalid`/`challenge_expired`/`challenge_used` response handling clears only the proof/code, also leaving the old/new password and continuation's verified presentation intact.
- **Impact:** this misses the approved A3 requirement to clear OTP/passwords when verification becomes invalid. On a shared kiosk, a revealed original password can remain visible after expiry; the launcher still represents the phone as verified. The server correctly rejects expired proof, so this is a private-state and UI contract failure, not an account-takeover or grant-transaction failure.
- **Reproduction:** used the existing launcher JSDOM helper with synthetic phone/code/password values and advanced its clock past the proof TTL. Observed `submitDisabled=true`, `passwordRetained=true`, `verifiedShown=true`, `phoneResendPanelHidden=true`, with the expiry error displayed. No SMS, network account mutation or database test was used.
- **Minimal correction:** use one proof-retirement transition on local expiry and the invalid/expired/used challenge errors. Clear code and old/new password, retire pending form work, remove verified/password-required presentation, and expose the existing re-verification/back path. Preserve the ordinary username/conflict retry behavior while proof remains valid. Add focused expiry/invalid-proof assertions to the existing UI tests; no new auth infrastructure is needed.

## Specification and security review

The remaining reviewed contract is implemented coherently:

- The service checks flow, active login-purpose challenge, code and expiry before selecting a name branch. Existing eligible names use the established canonical/public-name lookup, and bound/unbound names both require the old password before a phone-binding conflict is disclosed.
- Old-account reauthentication spends the existing independently committed per-account budget. Slow password work occurs outside phone/account locks; finalization reacquires locks and rechecks the proof, current password hash, name, eligibility and latest binding.
- Fresh signup creates the canonical user, phone identity, permanent claim, at-most-5000 credit ledger adjustment and consumed proof in one transaction. Existing claims suppress repeat grants. Binding/completion keep the same UUID and assets with zero grant; legacy completion does not select or merge a colliding account and preserves its password.
- New implicit accounts receive an unguessable per-account bcrypt password. Existing password login and the legacy registration API remain available. Optional password setting requires an authenticated eligible actor and a fresh proof for that actor's current phone, consumes it atomically and keeps the identity.
- Child board operations use the cloud authority and existing candidate verification/generation guards. Parent continuation uses candidate-token `/auth/me` verification and the existing box identity CAS. Password adapters accept an empty 204 without parsing JSON or replacing identity. Private validation and upstream errors retain safe, no-store envelopes.
- Progressive fields, same-proof name/password retries, username-change clearing, explicit back/tab/identity cancellation, grant-only success notice and separate optional password settings are present. The initial expiry cleanup exception I1 is closed in the follow-up below.

## Validation and limits

Independently read the new PG/API race, rollback, persistent-budget, asset-preservation and password tests, plus the relevant remote/React/launcher tests. Focused `git diff --check` passed in both worktrees. The synthetic JSDOM expiry reproduction above confirmed I1.

The coordinator reported 159 unique auth backend cases, 81 React cases with 6 expected mode skips, and parent launcher checks in progress. Those suite counts are reported evidence, not reruns by this reviewer. I did not run PG tests, real SMS, device operations, deployments or commits. No additional minor findings are requested.

This auth-slice review does not replace the required independent review of the final integrated child/parent release, representative actual UI, final test evidence and exact published commits.

## I1 follow-up — Approved

Re-reviewed the frozen auth slice after the owners' fix. **I1 is closed. Auth Tasks 1–3 are approved; no Critical or Important findings remain in this scope.**

React continuation and password settings now use a single proof-retirement path for deadline expiry and invalid/expired/used challenge responses. It clears code/password, removes continuation verification and old-password requirements, aborts pending work and advances the request revision. The submit guard prevents a retired proof from being sent again; the existing same-form re-verification remains available. The launcher applies the same transition, resets the password input type, removes its verified label, returns continuation to phone entry and rejects a late response when its captured proof has expired. Ordinary wrong-password failures retain a still-valid proof.

Independent focused reruns:

- `npm run test -- src/features/auth/NamedSignup.test.tsx src/features/auth/PhonePasswordDialog.test.tsx src/features/auth/PhoneOtpForm.test.tsx`: **29 passed** across three files.
- `node setup-wizard/tests/ui/launcher.phone.test.js`: **passed, 0 failed**, including expiry, invalid proof, late replies, wrong-password proof reuse and password 204 success.
- Auth-scoped `git diff --check`: clean in both worktrees.

No PG, SMS, device, deployment or commit actions were performed. The planned fresh final review of the complete integrated release remains required; this approval covers the auth slice only.

SHA-256 of the frozen reviewed production auth files and focused I1 regression files (paths relative to each repository):

```text
child:
367bbc48497d7ed5d28960bd54cad1e4dcf01a434bfe0822974e678d3d9ba685  katrain/web/core/phone_otp.py
0a6d0200429f05f21cda747bb79d140c25c6e129a5241d44299d28bec707488f  katrain/web/api/v1/endpoints/phone_auth.py
2d8a507621d1bacb6113ae70e52263650cf77c117bf97732b6d9ab78d02de332  katrain/web/core/remote_client.py
87d36f70fce7104e4dc33e5b59fccd586889fa537a6ebe6a465b77a32d340e95  katrain/web/ui/src/api.ts
86b87a8ed4f1a9b45f9bb51eb4d7d680d3378247d2855b14f4e732d70f03f221  katrain/web/ui/src/context/AuthContext.tsx
be34e78baf483a1b9361b47e6749219f26575e109202c5f290a76085103560b9  katrain/web/ui/src/features/auth/LoginMethods.tsx
738fa618cf685faae791176642059ac890de0f573e8464de564911b08599ba20  katrain/web/ui/src/features/auth/PhoneBindingEntry.tsx
0bcc34b4cdd3e2db897775ffd43636ca55e71ec5a7a1e864f01ebfb2d0d96ad0  katrain/web/ui/src/features/auth/PhoneOtpForm.tsx
86b60430fc808235a94da71ec2415c038c62ca0a4b5291b0451d393d3dab85aa  katrain/web/ui/src/features/auth/PhonePasswordDialog.tsx
4cb1edd1c75977d4810b661c5611aaa807e05e13b386f5a382bc4bf7213127b8  katrain/web/ui/src/features/auth/namedAuth.css
79df976ae14eb27432f1ed71f543ea13d727022f1e50ac89cc5e8816b03df2c1  katrain/web/ui/src/features/auth/NamedSignup.test.tsx
40e9abd6393cdd6330ce3276e87aa0f8b0fbf18451d1bb1358c97d3b717ce207  katrain/web/ui/src/features/auth/PhonePasswordDialog.test.tsx
804255b70d527540a23bfd342c075c54faf9ba5fb6c92313f3b5a13e0e744713  katrain/web/ui/src/features/auth/PhoneOtpForm.test.tsx
parent:
0d88490b893c30889318b435382f71ce85c0483648b15fb97644d29117f4bd32  setup-wizard/app/services/identity.py
fa41b77281446d7b3f34ad7fa4d9e8613ae5427890d5e48292f9b5ec1054f019  setup-wizard/app/routers/auth.py
1017164d069e2d27492fc693657281518216799eb378786791caf1fa294bfea0  setup-wizard/app/static/js/launcher.js
47b11fd797569f64b4b426e5ab2be21a5a17460e3c51bf66e934ff5e8a8f6e4a  setup-wizard/app/templates/launcher.html
53650ab38f5adf6832b0cf3a4826c41a7083f015222959852826ecc3d4f4ab29  setup-wizard/app/locales/en.json
d0a496228fbf6253acef4486dd259823594ab9f341fd816bc33c5fe422606172  setup-wizard/app/locales/ja.json
1a3377d8e832d2ba278c19be42f6bb6a766b157566316162f8c4d80202f04a5c  setup-wizard/app/locales/ko.json
f0dabd89094b5e7004638fe862e23a4a885e34cf4debb2ed355116469b786cda  setup-wizard/app/locales/zh-TW.json
18c4453dbd63af1e5dd5f9dae750d3ac3c9082ed66d089d8886269113082ee0d  setup-wizard/app/locales/zh.json
07569af648eaa78e96c331bdb22f1b34e9f542a55464e3c116f2d4d283f7575b  setup-wizard/tests/ui/launcher.phone.test.js
```

