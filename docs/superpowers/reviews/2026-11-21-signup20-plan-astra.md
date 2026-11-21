# Signup 20 / retire weekly free — independent Astra Max plan review

Reviewer: independent `gpt-6.2-astra`, reasoning max, `/root/astra_max_signup20_plan`.

1. Round 1 reviewed plan/spec at 287dc2764. Requested two linked fixes: report insufficient balance must be 402 rather than free-verification 403; ReportAccessDialog and shared ConsumptionQuoteDialog also require retired-free handling and 11-language updates.
2. Root checked the actual call sites and amended the plan/spec at 12e159d7a. Nonmember low-balance reports use existing `insufficient_credits`; stale free quotes cannot confirm or silently switch to a paid source; the two extra dialogs and focused tests are in scope.
3. Round 2 result: **Approved**. No remaining blocking plan issues. User's maximum of two review rounds was observed.

The user explicitly confirmed the policy and authorized implementation and the traditional four-step release. Existing balances/claims and old task settlement stay authoritative; membership weekly budgets are not the removed weekly gift. The work is a small policy/copy change with representative previews, not a new visual redesign.
