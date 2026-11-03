# Membership and recharge — 11-language i18n implementation plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to implement this plan. Steps use checkbox syntax for tracking.

**Goal:** Complete the existing membership, usage, API recharge and related order/consumption journeys in all 11 supported languages, then integrate and deploy TEST → new PROD for the user's next-day acceptance.

**Architecture:** Keep the existing gettext PO/MO catalogs, `/api/translations` and React `useTranslation` subscription. Extract whole sentences with named placeholders; translate only presentation, never identifiers, SKU/profile/source/status codes, amounts, quota arithmetic or authorization. Keep commercial flags and the existing layout. The user explicitly authorizes autonomous implementation/release and will accept tomorrow; no new product-design approval gate is needed for this localization repair.

**Tech Stack:** React/TypeScript, existing gettext/polib scripts, Vitest, Playwright, existing selective Web release process.

## Scope and acceptance

- `en`, `cn`, `tw`, `jp`, `ko`, `de`, `es`, `fr`, `ru`, `tr`, `ua`, including Spanish even though legacy `i18n.py` marks it inactive for synchronization (it must still compile).
- Galaxy/Kiosk membership usage, plans, API top-up, quota/pricing help, account status, checkout, receipts/history, disabled/loading/error/retry states, accessibility labels, navigation/settings entries and analysis/report payment confirmations/errors added by this feature. Localize the membership-related admin billing presentation if it contains feature-specific untranslated copy; do not translate unrelated admin/legacy modules.
- Use complete translated templates; preserve placeholder names. Keep Plus/Pro/Max, TEST, API and CNY denomination as appropriate product identifiers. Do not translate arbitrary backend exception text: map known billing reasons/statuses to local messages with a translated safe fallback.
- Open dialogs and already-present errors update after a language change without reload. No language dependency may reset a purchase, recreate orders, restart paid work, re-scope identity or reset server-clock quotas.
- Dates/numbers follow the selected display locale where appropriate; map `cn→zh-CN`, `tw→zh-TW`, `jp→ja-JP`, `ua→uk-UA`, with standard locale equivalents for the other seven codes. Dates/reset rules remain explicitly Beijing time (`Asia/Shanghai`), prices remain CNY. Percentages and points retain arithmetic and precision.
- Keep current approved visual hierarchy; allow wrapping/minimal sizing fixes where longer translations require it. This is not a visual redesign. Representative real-browser checks: Galaxy1440×900, mobile375px, Kiosk1024×600; Chinese baseline plus English and a long translation (German/Russian), CJK spot check.
- Runtime catalogs must actually contain the new messages (PO-only/source-only completion is insufficient). Test missing/fuzzy values, duplicate keys and placeholder parity for the feature's keys, with gettext MO round-trip.

## Chunk 1: Plan and stable presentation contract

### Task 1: Inventory and review

- [x] Read AGENTS.md, `katrain-i18n-expert` skill and previous release receipt. Reuse prepared worktree; no worktree recreation.
- [x] Fetch/merge published develop before edits (fast-forward baseline `8cc4b6dcdd236bd8339643043f176708ff499503`). Do not enter Elasticsearch worktree.
- [x] Complete exact feature-copy inventory, including remaining `membership:*` keys and hardcoded copy/reason strings. Read-only independent audit found no existing membership catalog entries; estimated220–260 keys after sharing. The existing membership UI baseline is45 passing tests.
- [x] Independent Astra Max reviews this plan, at most two rounds; fix material gaps before implementation. Scope review proportionately to localization and release risks.

### Task 2: Shared copy and consumption journey (one implementer)

**Files:** `katrain/web/ui/src/features/membership/{presentation.ts,ConsumptionQuoteDialog.tsx}`; a small `useMembershipI18n.ts` if it removes duplicate formatting; `katrain/web/ui/src/features/analysis/usePaidPosition.ts`; `katrain/web/ui/src/features/report/useReportTasks.ts`; the membership-specific rendered messages in `galaxy/pages/{ResearchPage.tsx,report/ReportsPage.tsx}` and `kiosk/pages/{ResearchPage.tsx,ReportsPage.tsx}`; `components/auth/{AccessPrompt.tsx,ProtectedOutline.tsx}`. Tests adjacent to changed files. `useMembership.ts` diagnostics are internal and need no translation; inspect but do not change unnecessarily.

- [x] Keep `useTranslation()` subscriptions in every affected rendered component/hook. Frozen shared helper contract: `{t, lang, locale, date(value, full?), countdown(seconds), money(fen), number(value, options?)}` from `useMembershipI18n.ts`. `t(key, defaultText, values?)` performs named interpolation without unsafe HTML; helpers use Beijing timezone. `number` is display-only. Keep `usagePercent()` as the existing ASCII machine value; never parse a localized display string. Galaxy progress values and Kiosk CSS width/ARIA take the raw bounded numeric `period.percent`. Render localized percentages separately from that number. Add a German comma-decimal regression asserting display localization while CSS width and `aria-valuenow` remain numeric and correct. No hook or UI callback may depend on unstable `t` identity.
- [x] Replace shared feature copy with `membership:*` keys and whole templates; store message codes instead of frozen translated error strings, translate at return/render time. Preserve raw diagnostics only in existing developer channels.
- [x] Add focused switching/error/formatting coverage, preserve existing consumption and account-switch tests. No billing backend behavior changes.

## Chunk 2: Parallel UI extraction, then translations

### Task 3: Galaxy (one implementer)

**Files:** `katrain/web/ui/src/galaxy/pages/membership/{MembershipPage.tsx,useMembershipCheckout.ts}` and adjacent tests; `galaxy/components/layout/galaxyNavigation.tsx`. Audit confirmed billing admin is a separate legacy credits/redeem module and is excluded.

- [x] Extract visible/accessible copy, including helpers/subcomponents/status maps/selection summaries and history; subscribe all rendered subcomponents. Reuse shared `membership:*` keys for identical semantics; otherwise use `membership:galaxy_*`.
- [x] Open checkout and error language switching must not create/refresh an order or alter account/environment boundaries. Render translated selections from frozen data/keys, not a frozen translated sentence.
- [x] Run focused Galaxy tests; report new keys/default texts and changed files. No catalog edits in this parallel task.

### Task 4: Kiosk (one implementer, disjoint files)

**Files:** `katrain/web/ui/src/kiosk/pages/membership/{MembershipPage.tsx,useKioskMembershipOrder.ts,membership.css}` and tests; `kiosk/components/settings/AccountSection.tsx`; membership-related aria label in `kiosk/shell/KioskTopbar.tsx`.

- [x] Extract visible/accessible copy with complete templates, dynamic units, statuses and modal/history copy. Use shared helpers and subscription; `membership:kiosk_*` only where semantics differ.
- [x] Preserve scaled-canvas dialogs, scroll zones/focus/touch targets, status guards, identity cleanup and async cancellation. Wrap longer copy without hiding warnings or controls.
- [x] Run focused Kiosk tests and a translated language-switch check; report keys/defaults. No catalog edits in this parallel task.

### Task 5: All 11 catalogs (parallel disjoint language groups)

**Files:** `scripts/batch_translate_galaxy.py`; optionally `scripts/membership_translations.json` loaded/merged into `GALAXY_TRANSLATIONS` to keep this large data set maintainable without module import-path changes; `katrain/i18n/locales/*/LC_MESSAGES/katrain.po` and compiled `.mo`; focused translation tests under `tests/`.

- [x] Freeze the extracted key/default/placeholder inventory after Tasks2–4. Translators own disjoint language sets or temporary output files; only one integrator edits the common batch dictionary/POs. Avoid conflicting file rewrites.
- [x] Human-quality whole-sentence translations for every feature key, including existing membership keys. Keep weekly/30-day caps, full-use savings conditions, membership-first whole-request API fallback, no automatic RMB recharge, expiry, pending-versus-paid and TEST-only simulation meanings accurate.
- [x] Merge data into the existing batch workflow. Apply only the membership subset while developing so unrelated existing translations are not overwritten; run `python i18n.py` as required by skill, inspect and retain only changes needed by this task (record unrelated legacy warnings). Compile/verify all11 MO catalogs, including Spanish.
- [x] Verify all extracted keys exist and are nonempty/nonfuzzy, placeholders match English, no duplicate feature keys, and real gettext loading returns the translated values. Use one focused durable test, not a second translation platform.

## Chunk 3: Verification, independent review and release

### Task 6: Focused validation and independent Astra Max

- [x] Run affected UI/API presentation tests plus feature catalog tests, ordinary frontend build and strict Kiosk build. Billing backend regression only if touched; no GPU/payment/capacity request required for copy changes.
- [x] Reuse existing Playwright membership fixtures for representative populated usage/checkout/receipt/error states. Load actual PO-derived catalogs; check all11 resolve the module's messages, actual language changes and representative geometry/screenshots. Do not add fixture data to product code.
- [x] Independently review spec compliance then code/translation/representative visual quality with Astra Max, fix material feedback via implementers until Approved. Independent review must actually occur; save concise report/evidence.

### Task 7: Four-step integration and selective deployment

- [ ] Fetch latest develop again; merge into feature, resolve conflicts, verify combined relevant checks/build, commit and push feature.
- [ ] Merge feature into develop and push. Work with the existing develop worktree safely or an isolated integration ref if dirty; never overwrite unrelated work.
- [ ] Update `smartbox-software/vendor/katrain` to published develop commit, preserve unrelated parent changes, commit/push main.
- [ ] Use current `server-deploy` skill and fresh runtime/config snapshots. Deploy only Web/static and compiled catalogs needed here, first TEST `home-ubuntu`, then new PROD `ucloud-v100` (`117.50.177.254`). Never retired PROD `117.50.183.169`; do not restart Cron/GPU/DB/MinIO for copy work.
- [ ] Preserve all current runtime configuration, especially paused membership, disabled payments, billing enforcement, Free0 and Max gate. No schema migration, merchant credentials or real charge.
- [ ] Verify actual source/static/catalog version, all11 `/api/translations` responses, service health, representative authenticated Galaxy/Kiosk pages and unchanged unrelated containers. Report physical box state separately; publishing Kiosk assets/parent pointer is not a physical-device update.
- [ ] Write release receipt with feature/develop/parent commits, actual deployed image/software identity, review/test results, URLs and a short next-day acceptance checklist. Clean up only task-owned temporary processes/tunnels.

## Progress communication

Report stage start/completion and at least every30 minutes: current step, completed work, blockers and remaining estimate. Continue work autonomously; user will review tomorrow. Routine commentary stays concise during ongoing tools.
