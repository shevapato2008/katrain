# Complete Chinese kifu rank display consistency

Observed actual production Galaxy search still mixes “九段” and “职业九段”; the existing canonical API intentionally distinguishes professional `9p` from category-unspecified `9段`. Do not invent professional evidence to remove this wording difference.

Decision: in the shared **kifu-only** `formatKifuRank`, render professional Chinese/TW ranks as Chinese numerals plus 段 (“九段”). The existing unspecified form already renders identically. Keep database/provenance categories intact, explicit amateur `业余X段`/`業餘X段`, unknown handling, non-Chinese translations, and the generic strength/ladder `formatRank` unchanged. Both Galaxy and Kiosk already call this helper.

1. Independent Astra max plan review at most twice, then an independent implementer updates only `src/utils/rank.ts` and its focused tests, with RED→GREEN for equivalent pro/unspecified Chinese labels and explicit amateur/non-Chinese counterexamples.
2. Independent code review; run the existing rank utility tests and normal frontend type/build checks once. No backend tests or new visual infrastructure for this wording-only change.
3. Publish through feature → develop → parent gitlink. Build exact published UI; deploy only changed Web assets plus RK app bundle. Do not interrupt the active hourly Cron merely for a UI label update. Report its already deployed backend release separately when relevant.
4. Backend rank modules remain byte-identical, so the running read-only manifests keep their existing code-SHA authority and need no re-prepare. Rank apply may use the new Web runtime only after verifying the unchanged critical module hashes.
5. Verify one representative Galaxy view and the real RK Kiosk after data application, preserving the device's captured mode/page/session and avoiding synthetic account history.
