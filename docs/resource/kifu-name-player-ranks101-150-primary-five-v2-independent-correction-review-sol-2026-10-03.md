# Independent correction review: ranks 101–150 primary-five v2

Reviewed 2026-10-03. This is a narrow follow-up to the [v1 independent packet review](kifu-name-player-ranks101-150-primary-five-independent-review-sol-2026-10-03.md). It assesses only the four corrected identity-name fields and whether their 15 attached cells can pass the **combined external-identity and exact-display evidence** gate. It does not approve raw ownership, category applicability, album slots, person FK, name preimage, final candidates, or any database write.

## Bound artifacts

- [V2 producer memo](kifu-name-player-ranks101-150-primary-five-producer-v2-pending-codex-2026-10-03.md): SHA-256 `df38105a66a4d16d0baada3600d54afa47c88dfd261fdd0730e807584a103e21`.
- Protected v2 directory: `~/.local/share/kifu-name-audit/2026-10-03/player-ranks101-150-primary-five-pending-codex-v2/` (mode `0700`; four files mode `0400`).
- V2 `manifest.pending.json`: SHA-256 `a15c44c1b258f1255541a57bb46e3847682b6bfc4606d0e36e28973781094b9f`.
- V2 `identity-proposals.pending.jsonl`: SHA-256 `822556916de7ede94919aafb961fa806c70708dae913c101121a70ac564d4e14`.
- Unchanged `primary-five-candidates.pending.jsonl`: SHA-256 `d7d4a58729d05da779bf58301738542791cdc2c4987baad88c0f111f05ab3623`.
- Unchanged `all250-status.pending.jsonl`: SHA-256 `a6c62e53fb8e7ec4084d7a4ee03ad5d7074da1c763d94292f64efcdacb7ba037`.

## V1-to-v2 comparison and source check

I compared all 30 identity records field by field. **26 are unchanged**. The only differences in the other four are their `official_identity_name_as_recorded` values. The 109-candidate file and 250-status file are byte-for-byte identical to v1. All hashes in the v2 manifest match their files; the v2 manifest points to the v1 manifest and prior independent review hashes. The four new values equal the exact nonempty `h1` text obtained from the saved Nihon Ki-in HTML with `get_text(strip=True)`, preserving ideographic spaces and omitting an HTML formatting space before `（`. Each source body matches its recorded SHA-256 and visibly states the proposed full DOB.

| Rank / raw value | Exact saved official `h1` | Source SHA-256 | DOB |
| --- | --- | --- | --- |
| 128 伊田笃史 | `伊田　篤史（イダ　アツシ / IDA, Atsushi）` | `cfefe68b61e629a981b09783917c5b551fb4e5916df307625a641bc438a6ca75` | 1994-03-15 |
| 134 Hane Yasumasa | `羽根　泰正（ハネ　ヤスマサ / HANE, Yasumasa）` | `c4db2042b952e09d176a7796cb2b490a57fe83cebeda0ecf35caf21e9468c96e` | 1944-06-25 |
| 139 淡路修三 | `淡路　修三（アワジ　シュウゾウ / AWAJI, Shuzo）` | `72249bdad55f84a4926624e0708623df539a9b0e6e231f042a29cca001399c1d` | 1949-08-13 |
| 144 三村智保 | `三村　智保（ミムラ　トモヤス / MIMURA, Tomoyasu）` | `8250f54b21ffc44da471b4fe97bae1aae98d923082be09fca4695c817a8d4c2f` | 1969-07-04 |

The previous review's other checks remain bound to unchanged candidate/status bytes. The four corrected identity records now **PASS as external identity correspondence evidence**. Their 15 attached candidate cells now **PASS combined identity-and-display evidence**. Thus v2 has **30/30 identity evidence PASS** and **109/109 combined evidence PASS**, with **0 HOLD at those two bounded gates**. The complete status matrix remains **109 source PASS / 136 HOLD / 5 EXCLUDED_APPROVED**; no source HOLD was promoted. The source values and counts have not changed.

**Final candidate approval remains 0/109.** V2 still has no approved raw owner/category determination, current raw-slot applicability, FK binding, or name preimage. Evidence PASS here is not final candidate approval or write authorization. No database, application code, or commit change was made in this review.
