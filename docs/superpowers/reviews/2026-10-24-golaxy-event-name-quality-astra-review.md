# Event-name quality guard after real release audit

Base `662b6a25048ee2bb3752bdbf54fb3a927ab68084`. A new independent Astra Max post-deployment flow audit found five incorrect Japanese/Korean event displays in four raw titles affecting six newly published games. SGF/source/identity/date and frozen-package binding were correct; model approval did not establish translation semantics.

The minimal code change adds finite known-error checks before a candidate reaches its reviewer: a title-match series must not become a challenger-deciding stage; an unambiguous single 3/5/7-game series must not become first-to-the-same-N wins; the known Korean Wu Qingyuan Cup spelling and Li Weiqing substitution are guarded. Producer, repair and reviewer receive the same rules. The original budget reservations, two repair attempts and cached-decision revalidation remain unchanged.

Independent reviewer `gpt-6-astra` with reasoning `max`, task `astra_receiver_boundary_review`, first found two false positives: mixed series lengths/one-game matches, and an explicitly separate Korean-named person in an event containing Li Weiqing. Four regression examples were added and the rules narrowed. Its final verdict: **Approved; no remaining must-fix in the two-file difference**. Independent focused verification: **67 passed**, `git diff --check` clean. No production or model operation by the reviewer.

Implementation TDD: the original 12 added bad-form tests failed before the guard; the four review regressions failed before narrowing it. Final names tests 64 passed; names plus saved-decision resume tests 67 passed. The full ingestion regression suite including those files: **368 passed in 15.32s**.

This code guard does not rewrite old approved decisions. The five deployed display cells require separate independently reviewed native semantic-correction bundles, exact target preimages, normal dry-run/apply and new API verification. Original immutable game manifests and publication receipts must remain unchanged. That production correction and the subsequent independent flow re-review are separate release evidence.
