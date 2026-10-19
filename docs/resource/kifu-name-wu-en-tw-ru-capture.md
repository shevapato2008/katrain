# Wu Qingyuan en/tw/ru controlled capture

Producer: `/root/lee_sources_luna` (`gpt-6-luna`), 2026-10-01 UTC. This memo records evidence capture only. The three candidates are `pending`; an independent agent must review them. No database was written.

| Language | Candidate | Target-language evidence (captured response SHA-256) | Identity match |
|---|---|---|---|
| `en` | `Go Seigen` | Registered CWI Go games index, [Go collection listing](https://homepages.cwi.nl/~aeb/go/games/): exact body passage “A Go Seigen collection (800+ games).” `94aeee554b7febf817478224e8dea105bd58990b65b91f36bac5fa67c3b491b6`. | Official Nihon Ki-in profile identifies 呉清源 with reading ゴ セイゲン / WU, Qing Yuan, and 9-dan professional career. |
| `tw` | `吳清源` | Registered Haifong Go Institute page for the professional world tournament, exact passage “「吳清源杯」世界女子圍棋賽總獎金120萬元人民幣”: `96129516105da3aaa815fea8ead6ded9eb5f255e27c276015ff4712287a8c69d`. Additional PTS Taiwan obituary calls him a Chinese Go master and recounts his career: `2e0cf533ed7bcb1d9b0b9657b9a1469f480f8b58788c2fdf019f00ab006c9aae`. | Official Nihon Ki-in profile identifies 呉清源 / WU, Qing Yuan as a 9-dan Go professional. |
| `ru` | `Го Сэйгэн` | Registered Russian Go Library dedicated profile, exact heading “Го Сэйгэн (Go Seigen)”: `7cfff0ef48ae83fd5791880b42989531bd823956cfd77f7447458de4dcd080a7`. | The profile itself supplies Chinese name У Цинюань, 9p and Nihon Ki-in affiliation; official Nihon Ki-in profile independently matches. |

Original-name identity source for all three is the official [Nihon Ki-in profile](https://www.nihonkiin.or.jp/player/htm/ki001001.htm), body SHA-256 `2abec7ca3d6814e94ba6b1dd48e7952c3dfdec7ec210de90dd4520eb9e4a0e94`. Birth dates conflict among sources and were not used as the identity key.

Each candidate was passed through `validate_candidate` with its exact stored research record, current `docs/resource/kifu-name-source-registry.json`, and pinned production v2 inventory `kifu-name-inventory-prod-v2-20261002.json.gz` (SHA-256 `518748084105398b4faeadc090d54f4a033b282a9402db20d2b0564fab465bd9`). All three returned valid and remain pending. Candidate research hashes: en `af1f1f758fd7e477069770159f5b69c0ad239e4a30d198f7112a5b0078fc374a`; tw `0fbbb219fd0ac321788576814acf0830e68b2e9cedfbafcbe92bafa3e82d1e4c`; ru `dd09111702affd783b72129faae570ac1cccccb0fa45c4a510d110832b7d63de`.

Final controlled-file SHA-256 values (files remain outside Git, mode `0600`):

- `wu-pending-evidence.jsonl`: `4449ceafa42f508c77c96bddb75386e225daa5af0ed76099490fd02358d0f6d9`
- `wu-pending-candidates.jsonl`: `4ddcd23ad408bc22a807c6e32d6d66f219651a791c1ba096620e208d45b8795a`

The prior approved `cn/jp/ko/tr` candidate objects were retained unchanged. The incomplete prior `en/tw/ru` research objects were replaced by the three complete positive captures above, preventing duplicate research records for the same owner/language. The registry’s additional Wikipedia and Wikidata checks remain open; this capture does not assert complete source-scope research or a negative conclusion.
