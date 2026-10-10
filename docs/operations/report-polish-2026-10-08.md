# Report display polish - 2026-10-08

## Changes

- Remove source metadata from Galaxy and kiosk professional library cards.
- Show plain rule names and komi labels; preserve original SGF metadata and parameter provenance.
- Rename report candidate score column to `report:score_difference` in all 11 locales.
- Reduce shared Galaxy report recommendation typography from 18px to 16px; kiosk recommendation typography from 16px to 14px. Row geometry and touch targets remain intact.
- Shared report components cover personal and professional reports. Live recommendations retain their existing typography.

## Verification

- Focused library/rules/recommendation tests: 49 passed.
- Shared report/page tests: 80 cases, all passing after updating display expectations; the final affected kiosk personal file passed its 57 cases on rerun.
- Desktop production build and kiosk-2d boundary/build passed.
- Actual 24171 report visually inspected on home-ubuntu and ucloud-v100: Galaxy 2048x1080, kiosk 1024x600. Plain rules/komi, score-difference header and computed 16px / 14px recommendation fonts verified.
- Actual library pages checked for absence of source metadata. Screenshots under `output/playwright/report-polish-*`.

## Deployment

Minimal catalog overlays built on each existing live web image; existing backend fixes, compose overrides and mounts preserved. New hashed frontend assets published with index last. Rollback image/config/index recorded remotely under `kifu-polish-20261008`.

- home-ubuntu: `katrain-web:report-polish-home-20261008`, running.
- ucloud-v100: `katrain-web:report-polish-prod-20261008`, healthy.
- Desktop index SHA256: `6299ad0afea4f1df1e65911ef38fd27d9dac9cf01e6a617a3fd58cef50514bc9`.
- Kiosk index SHA256: `45316c42c6d1464847a09d53d212770b7fde680687d8837f0307f8c555349bdf`.
- Both remote index hashes match the local release.

## Read-only data export

Album 24171 exported from production in a repeatable-read, read-only transaction. Full data and schema under `output/exports/kifu-24171` (not committed): JSON, standalone HTML viewer, three CSV files and ZIP.

- Canonical album 24171; job ID 2; completed; 2000 requested visits; Japanese preset, komi 6.5.
- `kifu_analysis_jobs`: 15 columns, 1 row.
- `kifu_analysis_moves`: 21 columns, 212 rows (position 0 through 211); minimum root visits 2002.
- Original values and nested candidate/ownership JSON retained. HTML embedded payload checked equal to original full JSON.
- Personal report tables remain `report_tasks` and `report_task_moves`.
