# Lee Chang-ho player 143: Spanish/French source follow-up

Source-only work, 2026-10-02. Producer: `/root/lee_es_fr_gap_luna` (`gpt-6.1-sol`). Scope is limited to product languages `es` and `fr`. Registry `2026-10-02.3` canonical SHA-256: `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61`.

## Captures

Both matrix-listed revision IDs were recaptured from MediaWiki's revision-specific `action=parse` API. The hashes below are SHA-256 of the exact raw HTTP response bytes; parsed article text was separately inspected. The API response includes the pinned revision ID and an article body declaring its language. An independently published Hanguk Kiwon profile was freshly fetched for identity corroboration.

| Product language | Article revision and capture URL | HTTP / actual language | Raw response SHA-256 | Observed name and identity facts |
|---|---|---|---|---|
| `es` | `166117165`; https://es.wikipedia.org/w/api.php?action=parse&oldid=166117165&prop=text%7Crevid%7Cdisplaytitle&format=json | 200 / `es` (`html_lang`) | `1ef44422fa8992fbc27c8e031d626b0c7fc6d7cfea81673abd3d6f8e9da1d1ca` | `Lee Chang-ho`; biography gives Korean name `이창호`, Jeonju, birth date 29 July 1975, professional Go occupation and Cho Hunhyun as teacher. |
| `fr` | `221272547`; https://fr.wikipedia.org/w/api.php?action=parse&oldid=221272547&prop=text%7Crevid%7Cdisplaytitle&format=json | 200 / `fr` (`html_lang`) | `681f1759e1155c22ecd650e6655932bb29736c4ff3a7b76cf0cdae244950f730` | `Lee Chang-ho`; biography gives Korean name `이창호`, Korean nationality, professional Go activity, 9-dan and Cho Hunhyun as teacher. |

Identity corroboration for each article used the official Korean Baduk Association / Hanguk Kiwon profile at https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000001. Fresh HTTP 200 body SHA-256: `ad0fb2eedf8fbcebca17581ba3752a3ee40726a819e102217dbc9950367ce3c6`. The Korean body identifies `9단 이창호 (李昌鎬)`, gives birth date 1975-07-29, Korean affiliation and extensive professional records. This matches the Spanish biography's birth date and the French biography's Korean professional identity; the romanized name is directly present in each target-language article.

## Controlled pending artifacts

- Evidence JSONL: `/Users/fan/.local/share/kifu-name-audit/2026-10-02/lee-player-143-es-fr-source-followup.jsonl`, mode `0600`.
- Pending conventional candidates: `/Users/fan/.local/share/kifu-name-audit/2026-10-02/lee-player-143-es-fr-candidates.jsonl`, mode `0600`. Both display `Lee Chang-ho`; each `research_sha256` binds its corresponding evidence row.
- Both evidence records pass `validate_research_record` against registry `2026-10-02.3`. Status remains `pending`; no reviewer signature, preimage, or binding is included.

The records retain the other registered checks as incomplete: `es` still needs `aego`, `godokoro-es`, and Wikidata review; `fr` still needs `ffg` and Wikidata review. This bounded pass makes no completeness or negative-closure claim. No database or inventory was read or changed, and no database write was attempted.
