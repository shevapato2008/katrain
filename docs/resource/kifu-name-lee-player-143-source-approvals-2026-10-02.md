# Lee Chang-ho, player 143: independent source approvals

Reviewer: `/root/lee_candidate_closure_luna` (`gpt-6-luna`), reviewed `2026-10-02T04:09:17Z`. Producer IDs and producer models remain unchanged in each candidate. Scope: source-only review and approval of the exact pending conventional candidates in `en`, `cn`, `tw`, `jp`, `ko`, `de`, `es`, `fr`, `tr`, and `ua`. No production preimages, slot links, database writes, or deployment were performed.

## Decisions

| Language | Approved display | Target-language source and identity check |
|---|---|---|
| `en` | `Lee Chang-ho` | English Wikipedia revision 1373361912; Hanguk Kiwon profile identifies `이창호` / `李昌鎬`, birth date, and Go career. |
| `cn` | `李昌镐` | National Sports Administration Chinese Go report; Hanguk Kiwon identity profile. Exact Simplified Chinese string appears in the report body. |
| `tw` | `李昌鎬` | Haifong Go Institute Traditional Chinese Go report; Hanguk Kiwon identity profile. |
| `jp` | `李昌鎬` | Nihon Ki-in Fujitsu Cup page; Hanguk Kiwon identity profile. The Japanese Ki-in archive independently supplies reading and birth-date corroboration. |
| `ko` | `이창호` | Cyberoro Korean Go report; Hanguk Kiwon identity profile. |
| `de` | `Lee Chang-ho` | Deutsche Go-Zeitung 3/2018, page 14; Hanguk Kiwon identity profile. |
| `es` | `Lee Chang-ho` | Spanish Wikipedia revision 166117165; Hanguk Kiwon identity profile. |
| `fr` | `Lee Chang-ho` | French Wikipedia revision 221272547; Hanguk Kiwon identity profile. |
| `tr` | `Lee Chang-ho` | Turkish Wikipedia revision 28972733 and Turkish Go School's `Go oyuncuları ve akış`; Hanguk Kiwon identity profile. |
| `ua` | `Лі Чхан Хо` | Ukrainian Wikipedia revision 47335190 Go-article caption and Ukrainian Kinorium Go-film prose; Hanguk Kiwon identity profile. |

These are positive-source approvals only. In particular, `ua` is supported by an article caption and secondary film prose, not a dedicated player biography. The candidates contain only the person's name; surrounding rank text is not included. The cited prior language-specific source reviews and producer memos remain the detailed source notes; the controlled evidence rows were rechecked for exact research-hash linkage and valid `found` records under registry `2026-10-02.3` (canonical SHA-256 `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61`).

## Direct capture checks in this review

For `cn` and `jp`, the controlled raw response bodies were checked directly: the Chinese article contains `李昌镐`; the Japanese Fujitsu Cup page contains `李昌鎬九段（韓国）`. Their raw body hashes match the evidence: `cn` `b955994190dfc2aca6e9a9d42d444c159ec6ddf0c2f68a5b2b4160be91904674`, `jp` `1e99d71bbc5f73f80c92785257d7ab8808d90a33f4bef56b5e44c430a1fddc47`. The supplemental Japanese reading body hash is `979f6a73c71647b47d8461ec581e35848659f9823f2a0c420cf58f9a868617a6`; the shared Korean identity profile hash is `ad0fb2eedf8fbcebca17581ba3752a3ee40726a819e102217dbc9950367ce3c6`.

For `tr`, the target-language passages in the research row exactly contain `Lee Chang-ho`; the pinned Turkish Wikipedia response hash is `a5c3d6ef4e64bf070ca70c7b5bfd4c39797c1b9774b36125c206c7e1eb1e8ca8`, and the Turkish Go School response hash is `b0447606605c3097445e3c7fca580645d1eb91e695540ab6eb4abb5fdbecf2ae`. For `ua`, the saved revisioned Ukrainian Wikipedia `rawHtml` field re-encoded as UTF-8 has SHA-256 `aeab1b2eb9461dd1c26922478113a66e3b7ca48cfb4075795a1808f6d083024f`; its article caption contains `Корейський гравець Лі Чхан Хо`. The Ukrainian Kinorium capture hash is `bbaeef3f7667f57d47118a121edc9ccf2da87a856ec0544e512606ba86281c99` and contains `Лі Чхан Хо (이창호)` in Go-related prose. The Ukrainian Wikipedia hash is over Firecrawl's `rawHtml` value, not original HTTP bytes.

The `en`, `tw`, `ko`, `de`, `es`, and `fr` source passages, body hashes, and identity checks were previously independently fetched and documented in the linked language review memos: [East review](kifu-name-lee-east-review-memo-2026-10-02.md), [German review](kifu-name-lee-player-143-de-review-2026-10-02.md), and [Spanish/French review](kifu-name-lee-player-143-es-fr-review-2026-10-02.md). This reviewer checked those memos and their exact pending candidate/evidence row linkage. The candidate research hashes equal the canonical SHA-256 of their matching evidence records; every approved language research row validated against the pinned registry.

## Candidate signatures

Each source candidate JSONL remains unchanged. Separate mode-`0600` reviewed copies were written to `/Users/fan/.local/share/kifu-name-audit/2026-10-02/`. The exact original candidate row hash, signed row hash, and reviewed-copy file hash are recorded below. The signature fields are `reviewer_id: /root/lee_candidate_closure_luna`, `reviewer_model: gpt-6-luna`, `reviewed_at: 2026-10-02T04:09:17Z`, and `review_conclusion: approved_conventional_name` with a language-specific description of the target-language and identity sources.

| Lang | Original row SHA-256 | Signed row SHA-256 |
|---|---|---|
| `en` | `76c9971a22acf3d4d89e9eddadfbb7bc000eed6360865b912677f80386cbe089` | `f4411b6f425b1656adfa7d764aaadfe46863cdb48bedaf5aee55bc01becd6cfb` |
| `cn` | `f4ed4fce8a497bb887a5bf06f3aae0bfa6073f56a58acbff7bfc13f56933a715` | `bedcc38b6cce47651daebe2800080cf0a422493afc617346a1d4f3ef58ba5055` |
| `tw` | `a60af195d5eb704e0ac475cd9d8f10d1686dcd8ad3ba978711af1d6b58614e76` | `31a241b7f9e7a0602b82939728ffb5a272ae84f96cbc00ffb4cc66e7aad8e39c` |
| `jp` | `a86f226bd45ea3f5ae9a00146a0d1677aca8ba99315549975b1ebe5c97c675e6` | `8a6435b825820fa37d9540e2d98fbd46430dd2be23b6c2e6fd8ef744211f41bd` |
| `ko` | `451d4d5aab4e10ed22f0d8fd2bc1601708d48b9d8bbc95f237d76ddc07de8415` | `1807ff9fa965eefffd5756ba702dc80d947cf912035b7becfbedead918df4ddd` |
| `de` | `c5e59a074fd34608ae6b20c101497d8ca906ab93c2dd6f2c331427bd268cbd3b` | `77545bbc9d621e7abc26e60f47689f0412f23e664bcdbd76d30463c3037ff817` |
| `es` | `9945f14b060b14c52fc6c2494148c6f45147aa1a571b45a705edf52cc4e63288` | `648004677ea93f8e60168639cd2bdfb613fe5a401ba436e224f39926defa9d84` |
| `fr` | `d99773ad7dcfd96aee1aa214504c21cb288d5dace951dc12d62f82b630f35b03` | `828a3b9727c1f70a35f8e971adc9bf70b87310b85795bffa4ab6092fa3cb17ba` |
| `tr` | `38d0623c4287e2d5f7846aa064b9e548375041f14a3e9f8174d1585fb6d5d16e` | `da8caa8d80e34fb241b15730c72ebc7532a12244b2cb1b722a861a4b4c8d10d6` |
| `ua` | `b0dae51d91bce94157f90c66d103295b3e3f87347d2fcde261dd7cb511b8c00a` | `9ab8b3d78d3070303da315972d124f60bf882fa4daab7de55dfe61d0dd9fb681` |

Reviewed-copy files and SHA-256:

| Controlled file | SHA-256 |
|---|---|
| `lee-chang-ho-en-tw-ko-reviewed-candidates.jsonl` | `7436243375f931b67ddea90b4a3c560b681d05278c344ccc6e23f339ec2c6e19` |
| `lee-player-143-cn-jp-reviewed-candidates.jsonl` | `c74672f3dca1224f2a44629ee1b58df8564e26ffddbdc98398c0cfbeb874f5bd` |
| `lee-player-143-de-reviewed-candidate.jsonl` | `c9693da2b3fd36939019acbf240d6bedec03c874bb8b45f96e89ea99b179af5d` |
| `lee-player-143-es-fr-reviewed-candidates.jsonl` | `f783648affda08137d445de81ed9bd7e6b84e77895d4dddec8236a888b3838ec` |
| `lee-player-143-ru-tr-reviewed-candidates.jsonl` | `5d49decbdf14d2d2a790815526bb27825a291d8bcd996dbcd6e142f4d3438e50` |
| `lee-player-143-ua-reviewed-candidate.jsonl` | `ee3b6149f81b61f4522b19a5b350400ea3f4279587dbc70438a9b83f961adac8` |

All six reviewed copies are mode `0600`. The mixed Russian/Turkish copy preserves the Russian row as `pending`; no signature was made for `Ли Чхан Хо` in Russian. The source-level Sol adjudication prefers `Ли Чханхо` and retains `Ли Чхан Хо` as an attested alias lead. The exact next producer task is to prepare a new Russian conventional candidate for `Ли Чханхо`, binding it to the already recorded Russian research only if its excerpt and provenance support that exact unspaced form; otherwise capture target-language body text directly attesting `Ли Чханхо`, update the research and candidate hash, and submit that new row for independent review. Preserve `Ли Чхан Хо` as an alias lead, not as the display candidate.

## Explicit validation and scope limits

The reviewed copies are source-only signatures and are **not import-ready**. `validate_candidate` against the available pinned production, clone, sequence, and test inventory snapshots rejects `player:143` because none of those album-association inventories contains player ID 143 (they contain linked player IDs 1–5 and null). No synthetic inventory membership was added. Later, a v2 link bundle can bring `player:143` into scope with its actual scoped album links, complete eleven-language names, current inventory/catalog and SGF hashes; independent raw-slot identity review remains separate.

The `de`, `es`, `fr`, `tr`, and `ua` scope checks remain explicitly incomplete, as do any uncompleted encyclopedia/Wikidata searches in the other languages. These approvals make no negative-closure claim. Existing raw SGF slot identity and album associations have not been reviewed here.
