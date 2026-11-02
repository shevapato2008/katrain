# Kiosk SGF alignment verification

Implementation began only after independent astra/max plan review round 1 approved. Shared utility and Kiosk consumers were developed in parallel with separate file ownership. The independent spec compliance review passed before the final astra/max code quality review.

## Automated checks

- Baseline before implementation: KifuPage + LiveBoard, 19 tests passed.
- Task A RED: adapter behavior missing against original LiveBoard namespace, 15 assertions failed; existing Galaxy characterization remained valid. GREEN: shared utility + LiveBoard, 31 tests passed.
- Task B RED: occupied-point preview and detail both failed against the strict Baipu screen path. GREEN: KifuPage + detail + detail localization, 45 tests passed.
- Controller combined check: `npm test -- src/utils/goReplay.test.ts src/components/live/LiveBoard.test.tsx src/utils/sgfSerializer.test.ts src/galaxy/components/board/ReplayBoard3D.test.tsx src/galaxy/pages/KifuLibraryPage.test.tsx src/kiosk/pages/KifuPage.test.tsx src/kiosk/__tests__/KifuDetailPage.test.tsx src/kiosk/__tests__/KifuDetailPage.localization.test.tsx` — **8 files, 115 tests passed**.
- `npm run build:kiosk-2d` — passed TypeScript, production build, and the existing no-three.js / no-Galaxy / no-live-API boundary guard. Existing >500 kB bundle-size advisory remains; no new runtime package was added.
- `git diff --check` — passed.
- Independent spec reviewer separately verified 104 tests, TypeScript, exact extraction of all six original functions, and byte-identical real-record fixtures.

The implementation workers checked the known lint diagnostics against HEAD: KifuPage has three existing effect state errors plus one dependency warning; LiveBoard has an existing `Date.now()` purity error and two hook warnings. These were not introduced by this extraction. The final reviewer also examined the old `kiosk/__tests__/KifuPage.test.tsx` suite; its heading/navigation expectations and missing getAlbum mock predate this patch. The combined passing checks above do not claim the entire repository suite is green.

## Actual RK3562 runtime

The same physical Chromium displayed a temporary reverse-forwarded local Vite frontend at port 15175 with the real device API, in its actual 1024x600 viewport. No mocked API payloads, deployment file replacement, service restart, or SGF database changes were used. The successful Kiosk production build is a separate build check; this runtime smoke used the dev server.

All three originally failing records displayed `终局棋谱` and an enabled `查看棋谱`:

| Record | Actual final stones | Detail total | Initial stones at cursor 0 |
| --- | ---: | ---: | ---: |
| 140859 | 233 | 345 | 2 |
| 124442 | 259 | 488 | 0 |
| 118394 | 202 | 304 | 0 |

For each detail, tested the first overwrite's preceding and following cursor, start and end. Captured 17 actual SVG positions (all 15 detail frames plus two additional preview frames) and compared every stone coordinate/color against the **unmodified HEAD Galaxy matrix algorithm**, rather than only comparing stone counts. All 17 matched. Screen preview/detail issued zero `/api/v1/baipu/load` requests. All three buttons were enabled; a real library-to-detail navigation was exercised.

Screenshots, before/after evidence, and `device-parity-summary.json` are in `evidence/2026-11-02-kiosk-sgf-alignment/`. The original device URL `http://127.0.0.1:8081/kiosk/kifu` was restored after inspection. The installed production frontend still has the original behavior; this work has not been released.

## Data audit and remaining boundary

Read-only full-library audit details are in `2026-11-02-kiosk-kifu-preview-investigation.md`. Each environment has 718 strict rejections among 176,690 visible rows (0.406361%). All 718 can be interpreted by the shared screen replay in an offline content check. Independently detected 16 mainline format/coordinate/setup issues remain separately listed; neither list authorized deletion after the user revoked that request.

Physical board guidance continues to consume backend-authoritative steps. Opening the three reported records as physical-board sessions still encounters the existing strict 422; this screen-only compatibility fix does not alter capture/LED instructions. The separate recent-history persistence issue is investigated but not implemented here.

Final independent astra/max code review round 1: **APPROVED**, no material findings or required fixes. Reviewer separately ran 119 tests, TypeScript, extraction/fixture checks and reproduced the unrelated old list-suite failures on baseline. Review record: `2026-11-03-kiosk-sgf-alignment-code-astra-r1.md`. Temporary local Vite and SSH forwarding listeners were stopped after restoring the device URL. No code changes followed approval.
