# Honinbo Ukrainian name follow-up (2026-10-02)

Producer evidence for product language `ua` (`uk` sources), Japanese professional Honinbo title series 本因坊戦. The event cohort and its identity are separately reviewed in [the edition review](kifu-name-honinbo-edition-independent-review-2026-10-02.md). This note records source evidence and a bounded search; it does not sign an independent decision, approve a candidate, or approve a negative closure.

## Result

A Ukrainian Wikipedia article contains the exact event description **`Турнір на звання Хон'імбо`** and explains the annual Japanese title tournament. The article is revision `41093637` (page footer: last edited 8 December 2023). However, it carries the explicit banner that it has no citations. Its only footnote is a spelling note, not a source for the professional series passage. A Ukrainian Go Federation search also surfaced **`Киевский Хонинбо 2005`**, but that result is Russian prose about the Kyiv local tournament. It is excluded from evidence for the Japanese professional series.

This is a concrete Ukrainian-language lead, but the producer does not classify it as a reliable conventional name. The lead needs independent review against the runbook's Wikipedia-use criteria and the captured source text. If the reviewer finds the article adequate as a name-use witness after the identity cross-check below, the exact candidate to consider is `Турнір на звання Хон'імбо` (`conventional`). If the reviewer rejects the uncited passage, the same exact phrase can be evaluated as a **generated descriptive form**, using the rule and source anchors below; that would still require a distinct generated-name review. Neither route is approved here.

## Identity and reading anchors

| Source | Verified content | Use and limit |
|---|---|---|
| [Nihon Ki-in, 80th Honinbo edition](https://www.nihonkiin.or.jp/match/honinbo/080.html) | Japanese page; captured 2026-10-02. The page labels the event `第80期 本因坊戦`; its table says `棋戦名称 | 本因坊戦` and names the Mainichi Shimbun, Nihon Ki-in, and Kansai Ki-in as organizers. | Independently anchors the exact Japanese professional series and its event identity. It does not establish a Ukrainian convention. |
| [Shogakukan Digital Daijisen entry via Kotobank, 本因坊戦](https://kotobank.jp/word/%E6%9C%AC%E5%9B%A0%E5%9D%8A%E6%88%A6-134972) | Japanese dictionary entry gives the reading **ほんいんぼうせん** and defines it as a Go title competition; it describes the Mainichi/Nihon Ki-in/Kansai Ki-in sponsorship and its first Honinbo term. | Independent reading and event-type basis for 本因坊戦. The reading is source-language evidence, not a Ukrainian transcription decision. |
| [Ukrainian Wikipedia, Хон'імбо, permanent revision](https://uk.wikipedia.org/w/index.php?title=%D0%A5%D0%BE%D0%BD%27%D1%96%D0%BC%D0%B1%D0%BE&oldid=41093637) | Ukrainian body says `Турнір на звання Хон'імбо відбувається щороку`; distinguishes the yearly Japanese title tournament and has a separate `Київський Хон'імбо` section. The page also gives Japanese `本因坊` and kana `ほんいんぼう`. Its banner says the article lacks sources; the sole footnote concerns alternate spellings. | Exact Ukrainian-language phrase and context, but the page's own warning and uncited event passage make reliability a review question. It also avoids conflating the Japanese professional series with the Kyiv local event. |
| [Wikidata Q1197931 entity data](https://www.wikidata.org/wiki/Special:EntityData/Q1197931.json) | The item is described in English as `Japanese Go competition`, has Japanese label `本因坊`, Ukrainian label `Хон'імбо`, Ukrainian aliases `Хонімбо` and `Хонінбо`, and an `ukwiki` sitelink to the article above. | Discovery and spelling leads only. The label does not say `戦`, and the item label is not independent corroboration of Ukrainian usage; it appears linked to the same encyclopedia lead. |

The current Nihon Ki-in page's format is later than that described in the older Ukrainian article. Only the Japanese event identity and the Ukrainian wording are used here, not the older page's format or historical details.

### Possible generated route (unapproved)

If the uncited Wikipedia event phrase is not accepted as conventional-name evidence, an editorial rule could form `Турнір на звання Хон'імбо` as a plain Ukrainian description: use the Ukrainian event noun/phrase already present in the target-language article, retain its observed Ukrainian spelling of the Honinbo stem, and identify the event as the Japanese title competition verified by Nihon Ki-in and Kotobank. The source reading is **ほんいんぼうせん**; it confirms the Japanese name but does not by itself determine the Ukrainian spelling. The Ukrainian spelling `Хон'імбо` is an observed spelling lead, not a formally established transcription rule. A reviewer should therefore check that spelling choice before approving a `generated` candidate. This note does not claim the composed phrase is a settled Ukrainian linguistic standard.

## Bounded search performed

The registry `.4` maps `ua` to `uk` and lists `ufgo`, `wikipedia-uk`, and `wikidata` for this language. The recorded scan was limited to those public surfaces and the following exact checks:

- **UFGO site search, four one-page queries:** `Хон'імбо`, `Хонинбо`, `本因坊戦`, and `турнір Хон'імбо`. All returned HTTP 200. Three showed “Нічого не знайдено.” The `Хонинбо` query returned one result, the 2005 Kyiv event. The result page is Russian (`Киевский Хонинбо 2005`), and its body concerns a local Kyiv tournament; it is retained as a rejected identity/language lead, not as a Japanese-series name.
- **Ukrainian Wikipedia API, six exact one-page searches:** `Хон'імбо`, `Хонинбо`, `Хонъимбо`, `本因坊戦`, `Honinbo`, and `Hon'inbō`. The first found the article and related name mentions; `Honinbo` returned two bibliographic/name references; the other four had zero hits. Each response returned fewer than the ten-result limit and no continuation token.
- **Ukrainian Wikipedia API, three one-page descriptive searches:** `японський професійний турнір ґо Хонімбо`, `турнір на звання Хон'імбо`, and `японський турнір ґо Хонінбо`. They returned 1, 3, and 2 results respectively, without continuation tokens. Results included the same article, other Go articles, and unrelated matches; no second independent Ukrainian specialist account of the Japanese series was found.
- **Wikidata:** exact entity Q1197931 was checked in the entity JSON. It has Ukrainian target-language fields, so this is a known lead rather than a no-hit. No attempt is made to treat those fields as independent evidence.

These are finite queries, not an exhaustive crawl of UFGO, Ukrainian Go clubs, books, forums, or the web. The reviewed checks returned HTTP 200; no network failure, rate limit, or truncated response was recorded. The registry remains `complete_for_negative_claims: false`. Because the Wikipedia/Wikidata leads are known and require reviewer disposition, this producer note is **not** an approved v2 `negative_closure` and must not be represented as one.

## Controlled captures

Raw HTTP bodies and the manifest are stored outside the repository at `/Users/fan/.local/share/kifu-name-audit/2026-10-02/honinbo-ua-followup/`; the directory is mode `0700` and files are mode `0600`. The manifest records request and final URLs, UTC capture times, status, content type, byte count, and SHA-256 for each response. Its SHA-256 is `57bc4bd2227bea58c4d43b4a17453e1e841a4eaedf5991ec7a43e2d1c02d6528`.

Key body hashes:

| Capture | HTTP SHA-256 |
|---|---|
| Ukrainian Wikipedia revision 41093637 | `e3e42c0cbc3f1584ac3459f9cb92f9548a3f4424ec59c08ace44b58c39282c2c` |
| Wikidata Q1197931 entity JSON | `18adfecc8f18ad4f429f6f2e7a7fc5308f17fc2e1c6eaa37158a1b72cee245b0` |
| Nihon Ki-in 80th edition page | `64c49fbc17a6d4bb9242c15023926642a0953df4439e34eaeebca6a7159ef018` |
| Kotobank 本因坊戦 entry | `c62ac74cf1cc369088239ae3f4b88c2e15a20aff3a1e2a1cb0aa046275af127a` |
| UFGO Kyiv local event page | `db43ea935324cf8ed41c181407732f700cbc9fabbea0f19374975818ea6cc1f1` |

This work changed only this new follow-up document and the controlled external capture directory. No code, database, SGF, existing document, or production state was changed. No commit was made.
