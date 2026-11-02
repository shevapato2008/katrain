# Both-surface metadata runtime acceptance

Used genuine candidate API routers, actual production SGF copies and an isolated disposable SQLite database (`/tmp/baipu-feature-runtime/acceptance.db`). This is an acceptance fixture, not production data repair or a deployed release.

Applied the real combined prepare/apply helpers to three reported preview fixtures and four additional real records (25055,140858,24658,24621), with trusted source links and relevant approved canonical player IDs. Result: five frozen rank overlays, one reviewed duplicate hidden, existing raw fields/SGFs retained. Source setup and writes were confined to this disposable database.

Shared actual API verification:

- Original25055 detail remains readable with raw7d/9d; normalized display7p/9p and journal-bound display_duplicate proof point to140858.
- Canonical140858 remains7p/9p, no duplicate pointer;1989-01-17 shared list contains one row.
- Raw B+24658 remains B+ in API; raw W+24621 remains W+. Display translation is client-side, not invented source data.

Actual production-build browser previews:

- Kiosk1024×600:1989 search shows one card with 依田纪基 职业七段 / 吴清源 职业九段.1947 search shows 黑胜 for bare B+, while explicit amateur Ida Isaburo remains 业余3段.
- Galaxy1440×900: same1989 record appears once with 职业七段/职业九段;1947 raw B+ renders 黑胜 in both selected header and card.
- Existing board previews still render; no layout/style redesign. Isolated header lacked its production logo/hardware/engine services, as recorded in physical-history runtime evidence.

Screenshots: `evidence/2026-11-03-kifu-standardization/`. No production writes, code deployment, restart, integration merge or SGF deletion occurred.
