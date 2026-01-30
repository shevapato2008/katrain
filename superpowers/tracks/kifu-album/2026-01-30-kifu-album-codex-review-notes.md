# Kifu Album Module Plan Review

Date: 2026-01-30
Reviewer: Codex (Go/web full-stack, Go pro)

## Must Fix (runtime correctness)
- Research page guard: `kifuLoaded` stays `true`; a new `kifu_id` or session reset won’t reload SGF. Reset the flag when `kifuId`/`sessionId` changes or key the component on `kifu_id` (`ResearchPage.tsx`).
- Date sorting uses string `date_played`; lexicographic order makes "1930" sort after "1975-01-01". Add a sortable field (`date_sort` int or ISO string) while keeping raw SGF date for display (model + import + list query).

## Security & Robustness
- SGF decoding: `read_text(..., errors="ignore")` can drop bytes from legacy encodings. Decode using parser-detected encoding or fallback chain; log failures (import script).
- Case-insensitive search: SQLite `ilike` may be case-sensitive under collations. Normalize with `lower(search_text) LIKE %lower(q)%` and consider a dedicated CI column/index (kifu API + model).
- Large SGF payloads: detail endpoint ships full SGF; enable gzip/deflate or provide a head/summary endpoint for navigation pages.

## Performance / Scalability
- `%...%` LIKE will full-scan; fine for ~900 rows but not for growth. Plan FTS5 (SQLite) or trigram GIN (Postgres) on `search_text`/`search_vector`.
- Offset/limit + count: acceptable now; add keyset/cursor pagination option if table grows to avoid large offset scans.

## Data Integrity
- Duplicate detection only by `source_path`; file renames bypass it. Add content hash (MD5/SHA1) with a unique constraint.
- `count_moves` traverses only the main line and skips root; handicap branches/variations are omitted. Traverse all move nodes or at least include root move when present.

## API & Schema Design
- Use Pydantic ORM mode (`model_config = ConfigDict(from_attributes=True)`) to avoid manual mapping drift.
- Add secondary sort (e.g., `id.desc()`) for deterministic pagination when dates are equal/null.
- Consider a `lang`/`translit` param for player names to match live module behavior.

## Frontend UX / Accessibility
- URL ↔ state sync: state writes to `searchParams` but doesn’t respond to changes. React to `searchParams` or derive state from them so back/forward navigation updates results.
- List rows need keyboard affordances: add `role="button"`, `tabIndex`, and Enter/Space activation.
- Error handling: fetch failures are only logged; surface a user-visible error (snackbar/toast).
- Mobile: long player/event strings can overflow; allow wrapping or ellipsis with tooltip.

## Platform Parity
- New module is web-only; confirm desktop behavior. If desktop should hide it, gate sidebar entry on `ui === "web"` or document the scope.

## Testing & Ops
- Add fixtures and API tests for list/search/detail and date ordering edge cases (partial dates, ranges). Frontend: Playwright flow from library → research load.
- Add dry-run test for import script covering dedupe and move counting.

## i18n
- Register `kifu:*` translation keys in locale files instead of relying on defaults.

## Nice to Have
- Show event/place/round as chips for quicker scanning; add common year filters.
- Cache SGF detail with `ETag`/`Last-Modified` since data is immutable.
