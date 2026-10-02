# Park Junghwan and Kobayashi Koichi: Ukrainian source follow-up

Research date: 2026-10-02. This memo records two positive Ukrainian-language name uses on the UFGO forum for existing player IDs 54 and 82. It does not approve either display name or establish any album/SGF link.

## Source capture

The exact permalink [UFGO post 88633](https://forum.ufgo.org/viewtopic.php?p=88633) returned HTTP 200 on 2026-10-02 at 04:30:53.600481 UTC. The raw response was 84,507 bytes, SHA-256 `64668631b1c5da55d8bcdf85423050b57eb7b5e3aa18238fc510426634e8e5cf`. Its final URL matched the permalink. The forum belongs to the registered `ufgo` source in registry `2026-10-02.3`; that registration permits subdomains. The registry canonical SHA-256 is `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61`.

The HTML document declares `lang="uk"`. In the substantive Ukrainian interview answers, question 6 asks which professional players the respondent likes; the answer says: “Park Junghwan (Корея) сильний у всьому але у нього немає якоїсь однієї риси, яку можна було б назвати надпотужною.” Question 5 asks for Go books to recommend; the answer says: “В основному це книги японських майстрів 80-х років - Рін Кайхо, Ісіда Йосіо, Кобаясі Коічі, Чо Чікун.” These are authored answer passages, not Russian interface text or a Russian quotation. The Russian forum heading/chrome is not used to establish language.

## Pending findings

| Player | Exact source form | Identity cross-check and limitation |
|---|---|---|
| Park Junghwan, ID 54 | `Park Junghwan` | The post calls him Korean and places him among contemporary professional Go players. The Korea Baduk Association profile independently identifies `박정환 (朴廷桓)`, Korean affiliation, 9-dan and birth date 1993-01-11; its saved-body SHA-256 is `0d1024775bcb8a8109dc5049aa0c90d9c52d648c36591de0278a6aff608f300e`. The forum does not provide kanji or a birth date, so the player match relies on the exact Latin name plus Korean professional context and the independent profile. |
| Kobayashi Koichi, ID 82 | `Кобаясі Коічі` | The Ukrainian answer lists him among Japanese Go masters whose 1980s books the respondent read. The Nihon Ki-in profile independently pairs `小林 光一` with `コバヤシ コウイチ / KOBAYASHI, Koichi`, and identifies a Japanese 9-dan born 1952-09-10; saved HTML SHA-256 is `c8fc10a734da7143d0c9bf5225f32a241556ca936a8e59311dc49ee90afa6e7d`. The forum gives no kanji or biography, so identity linkage rests on the specific Japanese Go-author context and the official profile. This is one community use, not an official Ukrainian naming standard. |

The spelling `Кобаясі Коічі` is retained exactly as printed. No generated transliteration was used. Both names remain pending independent review.

## Controlled records and limits

Raw capture and JSONL artifacts are in `/Users/fan/.local/share/kifu-name-audit/2026-10-02/park-kobayashi-ua-followup-20261002/`, with directory mode `0700` and files mode `0600`:

- `ufgo-post-88633.html`: the raw response above.
- `manifest.json`: request/fetch timestamps, final URL, status, byte count and raw-body hash.
- `research.jsonl`: two `.3` registry-bound pending research records; SHA-256 `e4774b868d5cdc7467ee2ab697e76cb0370a14535a3d2a4bfff7c19e976bb881`. Both pass `validate_research_record` against the pinned registry.
- `candidates.jsonl`: two pending `conventional` candidate rows; SHA-256 `9532518bdb16073eda0f72b7d1a53a1ddfca98a1243af5008249fb54ae802080`. Candidate decision checks pass using an explicit local allowlist for player IDs 54 and 82. This validates the row contract only; it is not the production album inventory.
- `registry-2026-10-02.3.json`: exact registry snapshot; raw-file SHA-256 `9e2016ac9675c44aa0bbdb304f8c5e1134a4a020d4d577c1c37890a813e0821b`.

The production inventory has no album foreign-key links for these player IDs. No production inventory binding, approved link declaration, name preimage, independent review signature, import bundle, database write or display-name approval is included. These findings supply positive `ua` source evidence only; they do not close the Ukrainian source scope or resolve any of the other ten product languages.
