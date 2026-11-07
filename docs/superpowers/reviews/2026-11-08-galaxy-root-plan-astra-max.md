# Galaxy root routing — independent plan review

Plan: [2026-11-08-galaxy-root-routing.md](../plans/2026-11-08-galaxy-root-routing.md).

User requires a maximum of two plan review/revision rounds, then parallel implementation and a new independent Astra Max code review. No production code was changed before this plan review.

## Round 1 — Issues Found

Independent reviewer: `gpt-6-astra`, reasoning `max`, isolated context (`fork_turns=none`). The reviewer inspected the plan and repository and reproduced route registration behavior using the installed FastAPI/Starlette.

1. Exact GET-only routes before the final root StaticFiles mount leave new trailing-slash URLs and HEAD requests unhandled or without the intended no-cache header. Required explicit GET+HEAD registration for both slash forms and negative retired-URL tests.
2. The rollout specified neither the executable cloud helper nor a bounded RK3562 replacement/restoration sequence. Parent app/full deployment is too broad. Required exact helper/hash/invocation, immutable build inputs, fresh identity checks, rollback, and original launcher mode/page restoration.

Runtime URL coverage, relative child routes, Kifu bootstrap/preload, Kiosk boundaries, and parallel ownership were otherwise considered appropriately scoped. No optional suggestions.

Controller revised the plan to address both findings, including the verified existing native cloud helper and a bounded RK operator reusing current Runtime and existing atomic replacement mechanisms. Submitted for the second and final permitted plan review.

## Round 2 — Approved

The same independent Astra Max reviewer checked the revised plan and verified the actual cloud helper source/hash/parameters. Result: **APPROVED**, no remaining blocking or important issues. GET/HEAD, trailing slashes, cache/404 behavior, bounded cloud/device publication, atomic replacement, failure recovery, original mode/page restoration, and review of the one-off RK operator are explicitly covered.

The two-round limit is satisfied. Parallel implementation may proceed; no third plan review is required.

Baseline before implementation: layout/guard UI 9 files / 42 tests passed; Galaxy page UI 19 files / 212 tests passed; `tests/test_ws_route_order.py` + `tests/web_ui/test_guest_bootstrap_route.py` 2 tests passed. These are baseline results, not post-change verification or deployment acceptance.
