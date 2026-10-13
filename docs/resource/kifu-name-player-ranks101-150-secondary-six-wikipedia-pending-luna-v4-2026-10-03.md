# Ranks 101–150: secondary six locale name proposals (v4 pending)

2026-10-03. Source-only 180-cell packet using the updated lower-bar rule. It carries proposed names for 30 source-positive identities across German, Spanish, French, Russian, Turkish, and Ukrainian Wikipedia locales (`ua` maps to Wikipedia `uk`). Every candidate remains pending independent review; no database write, application edit, self-approval, or commit was made.

## Inputs and immutable packet

- Protected identity packet: `~/.local/share/kifu-name-audit/2026-10-03/player-ranks101-150-primary-five-pending-codex-v2/`; manifest SHA-256 `a15c44c1b258f1255541a57bb46e3847682b6bfc4606d0e36e28973781094b9f`; identity proposals SHA-256 `822556916de7ede94919aafb961fa806c70708dae913c101121a70ac564d4e14`.
- The 30 English display names come from `primary-five-candidates.pending.jsonl`; all 30 records have `source_status=PASS` and retain their source URL, body hash, source-record hash, and timestamp in each cell.
- New protected packet: `~/.local/share/kifu-name-audit/2026-10-03/secondary-six-wikipedia-pending-luna-v4-2026-10-03/` (directory `0700`; packet and manifest `0400`). Packet SHA-256 `106104103b6f91f1cc4ed59a4570ac72f5ca581e93650c5711e412fb91b59b5b`; manifest SHA-256 `b8ff40822a44e180debf7ae814f48f600aba6ab0c27832f80ddd4ca43428e863`.
- v1, v2, and v3 packets remain unchanged. V4 supersedes v3 for the current proposal set.

## Exact counts

| Locale | Wikipedia code | Cells | PASS proposals | HOLD | Basis |
| --- | --- | ---: | ---: | ---: | --- |
| de | de | 30 | 30 | 0 | SOURCE_BACKED_LATIN_NAME_REUSED 30 |
| es | es | 30 | 30 | 0 | SOURCE_BACKED_LATIN_NAME_REUSED 30 |
| fr | fr | 30 | 30 | 0 | SOURCE_BACKED_LATIN_NAME_REUSED 29, VERIFIED_TARGET_WIKIPEDIA_ARTICLE 1 |
| ru | ru | 30 | 30 | 0 | RULE_BASED_CYRILLIC_TRANSLITERATION 30 |
| tr | tr | 30 | 30 | 0 | SOURCE_BACKED_LATIN_NAME_REUSED 30 |
| ua | uk | 30 | 30 | 0 | RULE_BASED_UKRAINIAN_CYRILLIC_TRANSLITERATION 30 |
| **Total** |  | **180** | **180** | **0** | **1 verified Wikipedia name; 119 source-backed Latin names; 60 rule-based Cyrillic proposals** |

Here `PASS` means the cell is populated with a name candidate under the user-authorized source-backed/transliteration fallback. It does **not** mean independent approval, final candidate approval, or production readiness. `target_article_status=NOT_ESTABLISHED` means no target-language article match is asserted; it is not an absence claim.

## Evidence basis

- **1 verified Wikipedia article name:** rank 116 Ding Hao / French. `https://en.wikipedia.org/wiki/Ding_Hao` links to `https://fr.wikipedia.org/wiki/Ding_Hao` (`hreflang=fr`). Both pages map to Wikidata entity `Q25252394`; the entity page records 13 June 2000, matching the protected official DOB and GoRatings profile ID 1511. The French H1 is `Ding Hao`. The packet retains title, heading, URL, language, revision `233421195`, retrieval timestamp, article HTML SHA-256, linking-page evidence, and entity-body hash.
- **119 source-backed Latin names:** exact English display strings from the source-PASS GoRatings profile rows are used unchanged for `de`, `es`, `fr`, and `tr`, except rank 116 / `fr`, which uses the verified French article H1. No claim is made that these strings were observed on those locale Wikipedias.
- **60 Russian/Ukrainian script proposals:** the English profile name is the verified Latin input. Origin class comes from the official identity record (Chinese Pinyin, Korean Revised Romanization, or Japanese Hepburn). The exact conversion is recorded below; it is a proposed orthographic/transcription fallback, not an observed local Wikipedia spelling. It was not inferred from a search miss.

## Reproducible Russian and Ukrainian proposal mapping

Rule ID: `source-origin-aware-proposed-cyrillic-v1`. Keep source name component order and spaces; use the listed origin class and output pair as the deterministic transliteration proposal. Chinese Pinyin follows common Russian/Ukrainian transcriptions for these names, Korean names follow the official Korean name reading and revised-romanization source, and Japanese names follow Hepburn readings. The explicit per-name mapping is normative if a generic syllable boundary is ambiguous. These are pending proposals, not claims about current Wikipedia titles.

| Rank | Verified Latin input | Origin | ru proposal | ua proposal |
| ---: | --- | --- | --- | --- |
| 102 | Hikosaka Naoto | Japanese Hepburn | Хикосака Наото | Хікосака Наото |
| 103 | Tong Mengcheng | Chinese Pinyin | Тун Мэнчэн | Тун Менчен |
| 106 | Tao Xinran | Chinese Pinyin | Тао Синьжань | Тао Сіньжань |
| 108 | Cao Dayuan | Chinese Pinyin | Цао Даюань | Цао Даюань |
| 110 | Xie Erhao | Chinese Pinyin | Се Эрхао | Сє Ерхао |
| 113 | Zhao Chenyu | Chinese Pinyin | Чжао Чэньюй | Чжао Ченьюй |
| 115 | Imamura Toshiya | Japanese Hepburn | Имамура Тосия | Імамура Тосія |
| 116 | Ding Hao | Chinese Pinyin | Дин Хао | Дін Хао |
| 117 | Xu Jiayang | Chinese Pinyin | Сюй Цзяян | Сюй Цзяян |
| 118 | Kim Chaeyoung | Korean Revised Romanization | Ким Чэён | Кім Че-йон |
| 124 | Wang Chenxing | Chinese Pinyin | Ван Чэньсин | Ван Ченьсін |
| 126 | Xie Ke | Chinese Pinyin | Се Кэ | Сє Ке |
| 127 | Kim Myounghoon | Korean Revised Romanization | Ким Мёнхун | Кім Мьонхун |
| 128 | Ida Atsushi | Japanese Hepburn | Ида Ацуси | Іда Ацусі |
| 129 | Meng Tailing | Chinese Pinyin | Мэн Тайлин | Мен Тайлин |
| 131 | Liao Yuanhe | Chinese Pinyin | Ляо Юаньхэ | Ляо Юаньхе |
| 132 | Na Hyun | Korean Revised Romanization | На Хён | На Хьон |
| 133 | An Sungjoon | Korean Revised Romanization | Ан Сон Джун | Ан Сон Джун |
| 134 | Hane Yasumasa | Japanese Hepburn | Ханэ Ясумаса | Хане Ясумаса |
| 135 | An Joyeong | Korean Revised Romanization | Ан Чо Ён | Ан Чо-йон |
| 136 | Seto Taiki | Japanese Hepburn | Сэто Тайки | Сето Тайкі |
| 137 | Hong Seongji | Korean Revised Romanization | Хон Сон Джи | Хон Сон Джі |
| 138 | Xu Jingen | Chinese Pinyin | Сюй Цзинэнь | Сюй Цзінень |
| 139 | Awaji Shuzo | Japanese Hepburn | Авадзи Сюдзо | Аваджі Сюдзо |
| 141 | Li Weiqing | Chinese Pinyin | Ли Вэйцин | Лі Вейцін |
| 142 | Yang Zixuan | Chinese Pinyin | Ян Цзысюань | Ян Цзисюань |
| 144 | Mimura Tomoyasu | Japanese Hepburn | Мимура Томоясу | Мімура Томоясу |
| 145 | Wu Guangya | Chinese Pinyin | У Гуанъя | У Гуан’я |
| 149 | Seo Nungwuk | Korean Revised Romanization | Со Нын Ук | Со Нинук |
| 150 | Kim Hyemin | Korean Revised Romanization | Ким Хе Мин | Кім Хе Мін |

## Holds and review boundary

There are 0 HOLD cells because each identity has a source-PASS Latin name and the secondary Cyrillic cells have an explicit, deterministic proposal. The Korean discovery article for rank 118 remains recorded in its six rows, with no target-locale article claimed. Search misses and timeouts are not treated as evidence of absence. The set remains pending independent review; the protected source packet does not approve raw scope, candidate applicability, name preimage, or any database write.
