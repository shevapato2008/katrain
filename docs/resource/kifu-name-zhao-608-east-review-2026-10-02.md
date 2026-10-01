# Zhao/Cho Chikun east-language independent review

Review date: 2026-10-02. Reviewer: `/root/zhao_east_review_luna`, model `gpt-6.1-sol`, independent of producer `/root/zhao_east_sources_luna` (`gpt-6-luna`). Scope: pending conventional candidates for existing player ID 608 in `jp`, `tw`, and `ko`; `cn` is excluded. No database, preimage, or write operation was used.

## Result: FAIL — do not approve these candidate rows yet

The name and identity evidence is substantively supported, but candidate validation against the pinned production inventory fails: player ID `608` is absent from every player ID in `kifu-name-inventory-prod-v2-20261002.json.gz` (SHA-256 `518748084105398b4faeadc090d54f4a033b282a9402db20d2b0564fab465bd9`). `validate_candidate` therefore rejects all three rows with `entity ID/ref absent from pinned inventory and approved links`. This review did not substitute another inventory or infer an identity link.

## Evidence checks

- Both controlled JSONL artifacts are mode `0600`. All three research records pass `validate_research_record` against immutable registry `2026-10-02.3`, canonical SHA-256 `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61`.
- Each candidate's `research_sha256` equals the canonical SHA-256 of its same-language research record: `jp` `9de5fb9d4ce528494bff6050f271933c11b95ae9b40d1bebfe356f787230c01d`; `tw` `000716027a0a8f922fe7701db705e3dfda3d1570d466a47febae3aa189346c42`; `ko` `2a2bcece7750ef937838c4ea992f3c3d8c89ec4f87fdbaaa1792adad839b6eed`.
- Independent HTTPS refetches returned HTTP 200 and exact recorded body hashes for Nihon Ki-in (`665d169cbf6c893654c238083e7e2a8003d5911bae727561594a291c4c04ac3c`), Korea Baduk Association (`7e84c0da51068e6cb0efdd1db4a6625980828092e96a7369d24f2a302c3fd130`), Haifong (`8e0d5fb3ae9116fee3bcce1ebe06defc27d52bee07616664901a7f397c65a5f8`), and revision-pinned Korean Wikipedia (`299358a9436f76310561d593aded816436184da612e713ecd8b4097d1ba0d5b8`). Their captured passages attest `趙　治勲`, `趙治勳` / `조치훈`, and `조치훈` respectively, with profile identity anchors matching the Japanese/Korean professional, Busan origin, 1956-06-20 birth date, and Japan affiliation.
- The current PTS Taiwan response is HTTP 200 and still contains both cited usages (`南韓旅日棋士趙治勳`, `日本職業棋士 趙治勳`), but its current body hash is `ee5ded80544f5d109b62c828ec7a1645f6c1435aefca051fea0022d9cdffdb28`, not the historical captured hash `10ef2e648ab1fc499229c46025f09d8d29694f04450f7d14e563d6aa5a44458e`. Haifong independently corroborates the Taiwan spelling with an exact matching body hash. The PTS response appears to vary; retain the mismatch for follow-up rather than treating the recapture as the original body.
- All three names use the target language's expected writing system and contain no rank suffix. The research scope remains `found`, not closed; Japanese/Korean/Taiwan registry source checks remain incomplete. This does not support any absence claim or `cn` candidate.

Pending source rows were not changed. Re-run candidate validation only after an authorized pinned inventory or approved link includes the exact existing owner ID 608; this memo does not establish that identity link.
