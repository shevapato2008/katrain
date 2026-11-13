# Implicit auth and report release — independent plan review, round 1

Date: 2026-11-13. Reviewer: independent Astra Max plan reviewer.

**Result: Blocking findings — one parent-baseline dependency must be made explicit before approval.**

Reviewed the complete implementation plan and requirements, `CURRENT-STATUS.md`, `auth.html` / `auth.js`, and the current Kiosk v5 / Galaxy v4 preview sources. Checked only the owning authentication, report/provenance, launcher identity and native deployment code needed to verify the proposed work. Child baseline: `6a847cd7b3e6ec45473b6e6d3dff762655c3dff7`. No production implementation, tests, device operations, commits or deployments were performed.

## Blocking finding

### B1 — Task 3 depends on a parent identity refactor absent from its published baseline

**Plan sections:** authority/baseline paragraph; Chunk 2, Task 3 (lines 77–83); Chunk 5, Task 8 (parent integration).

Task 3 instructs the implementer to integrate published parent main `19aa5487` and then extend `identity_phone.py`, `device_identity_client.py`, `device_identity_mutation_protocol.py` and the identity daemon. None of those modules exists in that published tree. A read-only `git ls-remote origin refs/heads/main` during this review confirmed the remote still points to `19aa5487ba5619f5eada71d19c02c12fa0e7a64e`; the designated parent worktree remains at `6ce5cad9`.

The modules do exist in the original parent's **local** main at `168b1b06`; the relevant phone authority and wire commits are `e07fc21b99092f6665bc6f33f1074442f8197ef4` and `652e4d8d9bb72ddbad287449897d3cfd90c2c798`. The published implementation instead owns the phone flow in `setup-wizard/app/services/identity.py` and `setup-wizard/app/routers/auth.py`. The plan therefore mixes two implementation baselines and leaves an implementer to import another session's unpublished work, recreate it, or silently omit the planned daemon path. This is also a release-scope issue, because the final parent publication must not inadvertently include an unreviewed architecture migration.

**Minimal correction:** state which parent baseline this release will use. Either make publication and integration of the existing identity-authority commits by their owning work an explicit prerequisite for Task 3, with an exact fetched commit/ancestry check before work starts, or target the currently published legacy owner and defer the unavailable daemon additions. Do not copy unmerged files or reproduce that refactor. Preserve the original worktree's unrelated edits. This needs a short dependency gate, not new infrastructure or a review of the entire parent history.

## Nonblocking implementation notes

1. **Task 9 — distinguish the actual launcher authority at deployment.** In the newer local parent, the identity service file is explicitly an inactive template (`provisioning/systemd/smartbox-device-identity.service:1`). The current native app deployer copies `setup-wizard/app`, but `scripts/rk3562_deploy.py:1113` and `Transaction.run` restart only `smartbox-setup-wizard.service`. Strict Go SSO alone does not establish that the daemon is active. Record the actual runtime in preflight. If a daemon is active by release time, ensure its actual code location, restart, readiness and rollback are covered in the same maintenance transaction before exposing the new client methods; otherwise fail the compatibility gate. Do not enable or migrate an inactive daemon as part of this feature.

2. **Tasks 1–3 — honor the new password endpoint's empty 204 response.** Existing child `RemoteAPIClient._identity_bound_request`, React `privatePhoneRequest`, and parent `identity.phone_request` all parse every successful response as JSON. The new endpoint needs explicit empty-success handling through each applicable adapter and a focused success-path assertion in the already planned tests. Otherwise the password can change successfully while the UI reports a failure. No response envelope redesign is needed.

## Scope and contract assessment

No additional blocking change is needed in the frozen account contract. It requires OTP proof before name branching, privacy-preserving old-password prompting, independently committed reauthentication limits, final transactional rechecks, preservation of canonical UUID/assets, permanent once-only phone grants and same-row legacy completion. The optional password setting/reset flow is proportionate to passwordless first entry and must retain the current actor while verifying a fresh proof for that actor's bound phone.

The report plan correctly separates both tiers, uses real persisted task progress, keeps reconnect GET-only, and explicitly defers paid-worker crash resume without promising free continuation. The nullable platform chain covers the POST receiver and offline replay; imported records retain their classification, and old rows are not guessed or backfilled. Kiosk v5 / Galaxy v4 dimensions, 11 child locales, five launcher locales, minimal visible error containment, and guarded device coordination remain in scope. The unknown black-screen root cause is not presented as diagnosed or fixed. The focused verification plan is proportionate; no broader test matrix or billing/queue redesign is requested.
