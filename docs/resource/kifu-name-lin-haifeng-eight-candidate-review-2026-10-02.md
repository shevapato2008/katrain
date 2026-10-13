# Lin Haifeng: independent review of eight language candidates

Review date: 2026-10-02. Reviewer: `/root/lin_eight_review`; actual model: GPT-6. Scope: positive name evidence and candidate-to-evidence binding for `cn`, `tw`, `jp`, `ko`, `en`, `de`, `es`, and `ru` in the controlled Lin Haifeng capture set. This review does not bind any of the reported 1,669 raw `林海峰` game slots to this person and does not authorize a player, alias, album, or database write.

## Review basis

I reviewed the complete archived response files in `/Users/fan/.local/share/kifu-name-audit/2026-10-02/lin-haifeng-source-captures/`, checked their byte counts and SHA-256 values against `capture-manifest.json` and the corresponding `source_check` records, and inspected the source-language context around each proposed form. All eight page captures report HTTP 200; the Korean response was decoded as EUC-KR as declared in its HTML metadata and its Korean text was inspected after decoding.

The research records validate against the archived registry snapshot `2026-10-02.3`, canonical SHA-256 `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61`. Each candidate's `research_sha256` equals the canonical hash of its corresponding research record. The archived snapshot registers all eight cited source IDs for the appropriate language: `china-sport` (`zh-Hans`), `haifong` (`zh-Hant`), `nihon-kiin` (`ja`), `cyberoro` (`ko`), and the revisioned Wikipedia sources (`en`, `de`, `es`, `ru`). The repository's default registry currently loads as `.2`; this review explicitly used the archived `.3` snapshot named in the research artifacts.

The official Nihon Ki-in profile directly identifies `林　海峯（リン　カイホウ / LIN, Hai Fong）`, professional 9-dan, born 1942-05-06 in Shanghai, affiliated with Nihon Ki-in Tokyo, and a Go Seigen pupil. This is a strong independent identity anchor for the professional discussed in the target-language Go sources. It also exposes orthographic variation: the profile uses `峯`, while several Chinese-language sources use `峰`. The sources and article context concern a Go professional; they do not establish that every raw `林海峰` occurrence is that professional. Chinese-language disambiguation includes a Hong Kong DJ/host/singer named 林海峰, so slot-level dates/opponents remain necessary before identity linkage.

## Language decisions

These are PASS/FAIL decisions on the proposed conventional display form's positive source support and research binding only. PASS does not mean the registry's full language search is closed.

| Language | Candidate | Decision | Review finding |
|---|---|---|---|
| `cn` | `林海峰` | **PASS** | The full China Sports Administration article is Simplified Chinese and its surrounding passage identifies `林海峰九段` as the Go Seigen pupil commemorated by a youth Go event. The Nihon Ki-in profile independently anchors that identity. Manifest/body hash and research binding match. |
| `tw` | `林海峰` | **PASS** | The full Haifong Go Institute feature is Traditional Chinese; its headline, opening paragraphs, and profile discuss 林海峰 as a Taiwanese Go prodigy and Japanese Go professional, with Shanghai birth, Go Seigen, titles, and career context. The candidate exactly matches the source's form. Hash and research binding match. |
| `jp` | `林　海峯` | **PASS** | The official Nihon Ki-in profile uses the exact proposed ideographs and ideographic space, with kana reading `リン　カイホウ` and romanization `LIN, Hai Fong`. It directly identifies the Go professional. Hash and research binding match. |
| `ko` | `린하이펑` | **PASS** | The complete Korean Cyberoro report names `린하이펑(林海峰 42년생) 9단` as a Japanese-team player in the 2003 Nongshim Cup and recalls his 2001 Meijin challenge. Those details align with the official profile. Korean text was reviewed after EUC-KR decoding. Hash and research binding match. |
| `en` | `Rin Kaiho` | **PASS** | English Wikipedia revision `1360979080` uses this article title and the captured English lead uses `Rin Kaihō or Lin Haifeng`; the biography identifies a Go professional born May 6, 1942 and connects him to Go Seigen and Japan. The official profile independently corroborates identity. The proposed unaccented form matches the target-language title. Hash and research binding match. |
| `de` | `Rin Kaiho` | **PASS** | German Wikipedia revision `255312114` begins `Rin Kaiho oder Lin Haifeng` and identifies the subject as a professional Go player born in Shanghai in 1942; the article body supplies Go Seigen and career context. `Rin Kaiho` is the page title and is an attested target-language form despite the stated alternate. Hash and research binding match. |
| `es` | `Rin Kaiho` | **PASS** | Spanish Wikipedia revision `173469376` uses `Rin Kaiho` in its title and lead, identifies him as a professional Go player, and provides `林海峰`, pinyin, birth date, Shanghai, and Go Seigen context. The official profile independently corroborates. Hash and research binding match. |
| `ru` | `Рин Кайхо` | **PASS** | Russian Wikipedia revision `149933322` uses `Рин Кайхо` as title and lead, identifies a Go player born in 1942, and explicitly gives `Линь Хайфэн` as another name while explaining that `Рин Кайхо` is the Japanese-adopted pronunciation of the Chinese name. The official profile corroborates the Japanese Go identity. The proposed title form is directly attested; retaining the article's alternate as a variant is appropriate. Hash and research binding match. |

## Limits and disposition

All eight rows pass this positive-evidence review. The producer's `review_status` remains `pending` and the producer files remain unchanged; this memo records the independent conclusions without editing their candidate JSONL. The `.3` registry requires other sources in each language (for example, association/federation sources and Wikidata) and marks every scope incomplete for negative claims. This review makes no absence, uniqueness, or full-scope claim.

French is intentionally excluded: its `Rin Kaiho` title/prose conflicts with `Lin Hai Fong` infobox usage and `Lin Hai Feng` in the French federation PDF. It remains unresolved for Sol as directed. Turkish and Ukrainian are also outside this review. No conclusion here decides whether any raw game slot belongs to this professional; exact game metadata and the separate identity/link review remain open.
