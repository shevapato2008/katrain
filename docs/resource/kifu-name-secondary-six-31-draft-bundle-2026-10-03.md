# Six-language draft bundle for 31 Chinese professionals

**Status: pending, unsigned draft.** The approved anchor packet contains 33 source anchors. The exact intersection of the Russian and Ukrainian rule passes with the 33/33 Latin four-language review is 31 owners: 33 minus the two language-specific holds. This packet proposes 186 outputs (31 × 6). It does not approve names, identity bindings, database writes, or imports.

## Dependencies and counts

- Approved anchor JSONL SHA-256: `dff6c196c3353666ecff1d0f59b4f692d1a27fa4522d18fb59042484fad3ab96`; 33 approved source anchors.
- Cyrillic review packets: Russian `ru.reviewed.json` SHA-256 `1e3c39e6f75159b75464170d7a4fc88a3e3ce97ccb5978dbc97f3b4e7d60d27b`; Ukrainian `uk.reviewed.json` SHA-256 `fca30154b873a2010b9634051748aae9a7f5a76178aa78cea36c833546b991a1`. Rule/display decisions are 32/33 pass for each; the reviewed proposed displays have zero within-batch collisions.
- Latin four-language reviewed packet SHA-256: `3b64192bd6d693da23737e663329e0d6b49f113c5431b9da3b4040e0eb6ce8c9`; 132/132 displays passed at rule/display layer.
- The six content rule hashes are recorded in `bundle.pending.json`; each output row carries its rule hash and canonical approved source-anchor hash. Frozen catalog dependency: `420ed4a10445a8d50c49d1132cd47ee8eee893b871dce2a968e8593775fa6105`.
- This 31-row draft has zero normalized same-language collisions in each of ru, ua, de, es, fr, tr. Latin review also reports no collision against its frozen snapshot; the Cyrillic reviews establish finite batch uniqueness only.

## Output samples

| Han | Source reading | ru | ua | de / es / fr / tr |
|---|---|---|---|---|
| 彭荃 | Peng Quan | Пэн Цюань | Пен Цюань | Peng Quan |
| 牛雨田 | Niu Yutian | Ню Юйтянь | Ню Юйтянь | Niu Yutian |
| 王群 | Wang Qun | Ван Цюнь | Ван Цюнь | Wang Qun |
| 吴肇毅 | Wu Zhaoyi | У Чжаои | У Чжаої | Wu Zhaoyi |

The Latin output shown once applies identically to `de`, `es`, `fr`, and `tr`. The complete 186-row output is `outputs.pending.jsonl`. Each record carries owner ref, language, display, source-anchor hash, rule hash, and reviewed reading.

## HOLDs and remaining blockers

- `宋容慧` (`cwa_cwa000216`): Russian held because `hui` has two Palladius forms (`хуэй` / `хой`); the RU review approves no display.
- `邱峻` (`cwa_cwa000027`): Ukrainian held because `jun` differs between the selected 2019 academic table (`цзюнь`) and an alternate table (`дзюнь`); the UA review approves no display.
- Database player entity/QID resolution and FK, exact source preimage/owner mapping, SGF or album ownership, and import authorization remain unresolved. The anchors approve source correspondence only.
- The combined batch has no independent batch signature. It is not import-ready and cannot pass the current approval-gated transliteration validator.

## Protected packet

Directory: `/Users/fan/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/secondary-six-31-draft-bundle` (mode 0700); files mode 0600. `bundle.pending.json` SHA-256 `00b6fcf60949b928a2191a4dd33dbe9dfc3bf4c6bbe183d3291acc06e6f8696e`; `outputs.pending.jsonl` SHA-256 `ace4fd4d280a66603f827229bbcaba9d473d6dfa5a8d1c025fe90019be1e2d2f`.
