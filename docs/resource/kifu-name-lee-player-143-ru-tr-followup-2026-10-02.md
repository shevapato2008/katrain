# Lee Chang-ho player 143: Russian/Turkish source follow-up

Source-only pass, 2026-10-02. Producer: `/root/lee_ru_tr_sources_luna` (`gpt-6-luna`). Scope is product languages `ru` and `tr`. Registry `2026-10-02.3` canonical SHA-256: `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61`.

## Captured positive evidence

All hashes below are SHA-256 of the exact captured HTTP response bytes. The revisioned Wikipedia API response includes the pinned revision, and the parsed article body was checked for the quoted target-language text. The Korean Baduk Association (Hanguk Kiwon) profile independently corroborates identity.

| Product language | Source and capture | Body SHA-256 | Exact evidence |
|---|---|---|---|
| `ru` | [Russian Wikipedia, revision 149787621](https://ru.wikipedia.org/w/api.php?action=parse&oldid=149787621&prop=text%7Crevid%7Cdisplaytitle&format=json); observed `ru`, HTTP 200 | `2487e11bef2a70ec778f3a99bdeb9154f255ce144b2322f7b8efaecc69906e50` | `Ли Чхан Хо ( кор. 이창호 ? , 李昌鎬 ? , род. 29 июля 1975 года ) — корейский го -профессионал 9 дана` |
| `ru` | [RusGoLib individual profile](https://rusgolib.gofederation.ru/LeeChangho.html); observed `ru` by reviewed body, HTTP 200 | `1a2f67fab9cbee409551d0882223cf128978d2ed8fa76a5a2cbaa72e477b9921` | `Ли Чханхо (Lee Changho) (29.07.1975) Страна Южная Корея ... Уровень: 9 p ... Учитель ЧоХунхён` |
| `tr` | [Turkish Wikipedia, revision 28972733](https://tr.wikipedia.org/w/api.php?action=parse&oldid=28972733&prop=text%7Crevid%7Cdisplaytitle&format=json); observed `tr`, HTTP 200 | `a5c3d6ef4e64bf070ca70c7b5bfd4c39797c1b9774b36125c206c7e1eb1e8ca8` | `Lee Chang-ho (d. 29 Temmuz 1975, Jeonju, Güney Kore), Güney Koreli 9-dan profesyonel go oyuncusudur.` The passage further identifies Cho Hun-hyeon as his teacher. |
| `tr` | [Turkish Go School, Go players and flows](https://www.gookulu.com/go_oyunculari_ve_akis/); observed `tr`, HTTP 200 | `b0447606605c3097445e3c7fca580645d1eb91e695540ab6eb4abb5fdbecf2ae` | `1990’lı yıllarda Cho Hun-hyun ve Lee Chang-ho tarafından bulunan Kore akışı` |

The two Russian sources use different spellings: Wikipedia `Ли Чхан Хо`; RusGoLib `Ли Чханхо`. The user also supplied the registered RusGoLib world-directory page [KtoEst%27Kto/Mir.html](https://rusgolib.gofederation.ru/KtoEst%27Kto/Mir.html), reported to list `Ли Чханхо (Lee Changho)`. Direct fetch of that directory timed out, so its listing is recorded as a lead rather than captured evidence. The individual profile was captured directly and independently identifies the subject by Latin name, 1975 birth date, South Korea, 9p rank, Korean Baduk Association and Cho Hun-hyeon as teacher. The Russian candidate remains pending for independent Sol adjudication of the spelling conflict.

Independent identity source for both language rows: [Hanguk Kiwon profile](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000001), HTTP 200, body SHA-256 `ad0fb2eedf8fbcebca17581ba3752a3ee40726a819e102217dbc9950367ce3c6`. It identifies `9단 이창호 (李昌鎬)`, birth date 1975-07-29, Korean affiliation, Cho Hun-hyeon as teacher, and professional Go records. This matches the Russian article's Korean name, date, 9-dan rank and teacher, and the Turkish article's birth date, 9-dan rank and teacher.

## Pending controlled artifacts

- Evidence JSONL: `/Users/fan/.local/share/kifu-name-audit/2026-10-02/lee-player-143-ru-tr-source-followup.jsonl`, mode `0600`, raw file SHA-256 `db5a780d9b878777d9b89e0cf6932323fe137271c6fd59657f3a5140a6f6b777`.
- Candidate JSONL: `/Users/fan/.local/share/kifu-name-audit/2026-10-02/lee-player-143-ru-tr-candidates.jsonl`, mode `0600`, raw file SHA-256 `c3d3935098cbfd0c353a21b8ff271a1dd2cc49ecb484275046382b8b21189f6d`.
- Candidate `ru`: `Ли Чхан Хо`; `research_sha256` `d140cacad34dca76ae55c27176939aa1e04e65446473452d06f770d6ad922e16`.
- Candidate `tr`: `Lee Chang-ho`; `research_sha256` `195e695dd6e339b62478f03b6219cc8a4523ea733d736c1f884defd184265279`.

Both research rows validate against registry `2026-10-02.3`; status remains `pending`. No reviewer signature, preimage, negative closure, or database write is included.

## Remaining source gaps

`ru`: The registry home page redirected to `/Vxod` login (response SHA-256 `798e8ee3cd4c10adb6c7d64aa71d09b9c3c2583e3e2fc8d65977ac95b7a3ffde`); the specific individual page is accessible and captured above. Direct fetch of the world-directory page timed out. Wikidata target-language labels/aliases were not checked.

`tr`: TGOD homepage was fetched (response SHA-256 `68ec7c843881d9c6f9c95cfbaccba205dbf456259712a907c21c79d58ea180b2`) and had no exact name passage, but the registered source was not searched comprehensively. Wikidata target-language labels/aliases were not checked. These limitations do not establish absence or close either language's source scope.

No player table, name preimage, inventory, or database was read or modified.
