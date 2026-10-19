# Ranks 101–150 primary-five identity record correction (v2 pending)

2026-10-03. Following the [independent packet review](kifu-name-player-ranks101-150-primary-five-independent-review-sol-2026-10-03.md), I issued a new protected pending packet at `~/.local/share/kifu-name-audit/2026-10-03/player-ranks101-150-primary-five-pending-codex-v2/` (directory `0700`, files `0400`). The original packet remains byte unchanged. V2 changes exactly one field, `official_identity_name_as_recorded`, in each of four identity records. The values below are the saved Nihon Ki-in page's exact nonempty `h1` text, including the ideographic spaces and no added space before `（`.

| Rank / raw value | Corrected exact `h1` | Saved source SHA-256 | DOB visible in saved page |
| --- | --- | --- | --- |
| 128 伊田笃史 | `伊田　篤史（イダ　アツシ / IDA, Atsushi）` | `cfefe68b61e629a981b09783917c5b551fb4e5916df307625a641bc438a6ca75` | 1994-03-15 |
| 134 Hane Yasumasa | `羽根　泰正（ハネ　ヤスマサ / HANE, Yasumasa）` | `c4db2042b952e09d176a7796cb2b490a57fe83cebeda0ecf35caf21e9468c96e` | 1944-06-25 |
| 139 淡路修三 | `淡路　修三（アワジ　シュウゾウ / AWAJI, Shuzo）` | `72249bdad55f84a4926624e0708623df539a9b0e6e231f042a29cca001399c1d` | 1949-08-13 |
| 144 三村智保 | `三村　智保（ミムラ　トモヤス / MIMURA, Tomoyasu）` | `8250f54b21ffc44da471b4fe97bae1aae98d923082be09fca4695c817a8d4c2f` | 1969-07-04 |

V2 manifest SHA-256: `a15c44c1b258f1255541a57bb46e3847682b6bfc4606d0e36e28973781094b9f`. Corrected `identity-proposals.pending.jsonl` SHA-256: `822556916de7ede94919aafb961fa806c70708dae913c101121a70ac564d4e14`. The 109-display candidate file and complete 250-cell status file are byte identical to v1, SHA-256 `d7d4a58729d05da779bf58301738542791cdc2c4987baad88c0f111f05ab3623` and `a6c62e53fb8e7ec4084d7a4ee03ad5d7074da1c763d94292f64efcdacb7ba037`. The manifest records the v1 manifest and independent-review hashes plus all four field changes.

Validation confirmed each saved source body hash and DOB, the exact H1 text, exactly four one-field identity diffs, 26 unchanged identity records, byte-identical candidate/status files, all v2 manifest hashes, and protected permissions. **V2 remains pending independent review.** The 15 display cells associated with these four records remain held at the combined identity-and-display gate until that review. No raw owner/slot, FK, preimage, final candidate, database write, application code edit, deployment, self-approval, or git commit was made.
