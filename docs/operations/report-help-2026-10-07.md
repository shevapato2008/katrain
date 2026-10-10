# Shared report help update — 2026-10-07

- Personal review and professional library reports share the help icon, definitions and translated copy. Galaxy uses `TrendChart`; kiosk uses `MoveGradePanel` and the same `AnalysisChartHelp`.
- Help icons use `InfoOutlined`, matching game details. Galaxy label/icon gaps measure 6–10px; kiosk measures 12px. Help targets remain 44×44px.
- Explain `top_prior` as AI initial selection probability before search, distinct from win rate and human-model probability. Remove `prior` jargon and misleading intuition language. Grading is unchanged.
- Update four help keys in all 11 catalogs, including kiosk selected-move details. MO round trips and placeholders verified for all 44 entries.

## Verification and deployment

- Existing help/chart tests: 9 passed. Personal/professional Galaxy/kiosk page tests: 73 passed.
- Desktop and kiosk builds passed; kiosk 2D boundary verification passed.
- Real Galaxy reports visually checked on both environments at 2048×1080; kiosk checked at 1024×600. Screenshots are in ignored `output/playwright/report-help-*`.
- Web translation overlay preserves each environment's current `normative-ja-ko` image and restores its runtime user. Only web is recreated; static indexes are published after assets. Deployment helper and rollback records are under `kifu-help-20261007` on each host.
- Desktop index SHA256: `a467c94b5f6c16d5ec580a6cb20fc9251afa339d5e4a6b15f9cabd877c7f01c3`.
- Kiosk index SHA256: `28f0cd9db0a68d6b4c4d0db92512f7f5bc84e83928bc1e703c5e53bbfbde0ef7`.
