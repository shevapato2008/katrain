# Wu Qingyuan de/fr PDF evidence capture

Producer: `/root/lee_sources_luna` (`gpt-6-luna`), 2026-10-01 UTC. Both candidates remain pending for independent review. No database writes.

| Language / candidate | Registered PDF source; original response SHA-256 | Reviewed passage and pages | Identity check |
|---|---|---|---|
| `de` / `Go Seigen` | Deutscher Go-Bund, [DGoZ 6/2014](https://www.dgob.de/wp-content/uploads/dgoz/pdf/2014/dgoz2014_6_low.pdf); `e7f87664142ef85cf8aa34784667515b5254c2d269637def2d379a562f3f1422` | PDF p.27 / printed p.27: “Obwohl die meisten Go-Spieler ihn als „Go Seigen“ kennen, ist sein chinesischer Name eigentlich „Wu Qingyuan“ (was ungefähr „Uh Tching jüen“ ausgesprochen wird).” Extracted text splits “chinesischer” across a line break; I normalized the line-wrap after visually reviewing the PDF page. German text continues with his Japan career and invitation by Kensaku Segoe. | Official Nihon Ki-in profile identifies 呉清源（ゴ セイゲン / WU, Qing Yuan）, 9 dan, Fujian origin and career. |
| `fr` / `Go Seigen` | Belgian Go Federation, [Belgo 46 (April 1997)](https://www.gofed.be/files/belgo%2046.pdf); `d93cd7e250d2dc85ce1e50b31d737acd6bf828246fa857be1ec3cd59ceea659d` | PDF p.11 / printed pp.18–19; visually reviewed scan: “Lin Hai Feng n’est autre que Rin Kai Ho et Wu Ch’ing Yuan est mieux connu sous le nom de Go Seigen. Ce dernier, âgé de 38 ans au moment de la partie (1952), était au sommet de son art. Incontesté meilleur joueur mondial…” The article continues with his recommendation that Lin pursue a professional career in Japan. | Official Nihon Ki-in profile independently matches the Chinese master and Japanese reading 呉清源 / ゴ セイゲン, with 9 dan and professional career. |

Each record uses `observed_lang` `de` / `fr` and `language_basis: "reviewed_text"`; `body_sha256` is the original downloaded PDF bytes, not OCR text. Records and candidates validated after writing through `validate_research_record` and `validate_candidate`, using immutable registry `2026-10-02.2` and pinned production v2 inventory SHA-256 `518748084105398b4faeadc090d54f4a033b282a9402db20d2b0564fab465bd9`.

Research hashes: `de` `791007fc33245e825aa2edfceadea3c66786c1cd64d295995cd8af45b14062a4`; `fr` `b7206febc1c704b945aa96c1b13d2dd70f4cd9a046236337b574946875cb8555`. The seven existing approved candidate lines remain byte-identical. Controlled files are mode `0600`:

- `wu-pending-evidence.jsonl` SHA-256 `bf9d210de012a63c3a7312d9f8983189320bbc7933a3d6d7c848ed7c7c147382`
- `wu-pending-candidates.jsonl` SHA-256 `f79ecc6c2628682f1026016f942e3a18832c05ac08d28a5efa4fb3ed99559959`
