# Four primary names: source precheck (pending)

Date: 2026-10-03. Reviewer model: GPT-6 Luna. Read-only; no names, identity links, FK, or database changes approved.

Candidate input SHA-256: `7b6b592aeb59afa8a2243b542e93eb2e105e15b6beb9631d33c38d105c7518c0` (manifest count 153). Checked each row against the raw official roster response, retained Wikidata entity JSON, exact GoRatings ranking response for each language, and GoRatings profile HTML/profile summary. Verified payload hashes against candidate references and GoRatings index.

## Result

- **149 strict source-pass candidates / 13,525 slots**: source ID, official roster name/DOB, GoRatings ID/name in cn/en/jp/ko, profile name/DOB, Wikidata QID, en/ja/ko labels and DOB agree. The exact subset is machine-readable in `source-pass.pending.jsonl` (149 rows; GoRatings ID included), SHA-256 `4c67ac8c499cb911debf8425d86ef359bbc01645b04945e7157303727430a28c`.
- **4 label exceptions / 1,395 slots**: 周鹤洋 (135), 叶桂 (307), 杨士海 (86), 黎春华 (2). Each official name/DOB, QID, all four GoRatings ranking names, GoRatings profile name/DOB, Wikidata DOB and en/ja/ko labels match. Wikidata `zh` label is traditional orthography while candidate is simplified; exact simplified candidate is present as a Chinese alias. These are source identity/name matches with a Chinese-label variance, kept out of strict-pass subset pending label handling.
- No other missing IDs, name mismatches, DOB mismatches, or payload hash mismatches found in the four exceptions or strict-pass records.

Machine-readable exceptions: `exceptions.pending.jsonl`, SHA-256 `4dc0c594eb9a2c8e0a3149b7fc43048526c2dde98c4876546e5a10e7991ace55`. Strict pass rows: `source-pass.pending.jsonl`, SHA-256 `4c67ac8c499cb911debf8425d86ef359bbc01645b04945e7157303727430a28c`. File modes are 0600; containing directory 0700.

## Source and identity limits

The ranking names show a GoRatings listing for the same site ID; profile name/DOB provides an additional source cross-check. Wikidata labels and DOB plus the official roster record support person-record correspondence. This does **not** establish that same-name SGFs in this repository depict those people, and it does not approve any translation or FK. As recorded in `kifu-name-four-primary-context-triage-2026-10-03.md`, 63/153 players have at least one slot below age 15 or a `1900-01-01` sentinel; ages are triage context, not proof of identity. The site's list is bounded by its rating/history coverage; absence elsewhere would not mean a player does not exist.

## Input hashes

- `candidate_jsonl`: `7b6b592aeb59afa8a2243b542e93eb2e105e15b6beb9631d33c38d105c7518c0`
- `batch_manifest`: `569a0dddff16f0bc336848c9e70de9f442254f9f465db13fd09717931d7bce61`
- `official_roster_body`: `18ba2a04efdca69d47528cbe703d9c54e1005b7f986af782434cbc3f1dd316f9`
- `goratings_index`: `d687c9c64b382851aa53fa6d4b569e0c863af5cbffce1a3de0557712b397b18c`
- `goratings_profile_summary`: `9e262be3e4338438c52a2fa04f9e62ef462d4cc7e3b9afb84c8cf95d2f09526a`
- `wikidata_all678_summary`: `9979c7ffe29b1cb0032fab7e2ac523c76960234126496540d3cc709cab272090`
