# Honinbo controlled 11-language research (2026-10-02)

Prepared controlled, unsigned research for event reference `honinbo-series-2026-10-02`, the Japanese professional 本因坊戦 series. The exact requested forms are recorded as positive source evidence; they remain pending independent candidate review and do not establish a catalog identity, edition membership, production write, or display coverage.

## Controlled artifacts

Raw HTTP response bodies, the capture manifest, the JSONL, and the Russian text review are under `/Users/fan/.local/share/kifu-name-audit/2026-10-02/honinbo-controlled-research/`. The directory is mode `0700`; files are mode `0600`.

- Research JSONL `honinbo-series-2026-10-02-research.pending.jsonl`, 11 rows: SHA-256 `21b96c75b47036781a03c14f3240345eba65898514d84535bb64b9955be30aa1`.
- Capture manifest `capture-manifest.json`: SHA-256 `8aef8aaa0b85bf0fcfd0fb24d400bad8e7c8c7f3ec0f9ac799b368e2b4a2b667`.
- Russian manual extraction `ru-page-141-reviewed-text.txt`: SHA-256 `6ce618b3af9d148fa5308e996f707611de4d01e8ac60e417539b9255c70ab0c4`.
- Immutable registry `2026-10-02.5`, canonical SHA-256 `d64180400bfdd95fa558e04dada00a7b4e0a31a6b361b2a8845ebd49e43bb88f`.

Validation completed with:

```sh
python scripts/kifu_name_research.py \
  --registry docs/resource/kifu-name-source-registry-2026-10-02.5.json \
  validate \
  --input /Users/fan/.local/share/kifu-name-audit/2026-10-02/honinbo-controlled-research/honinbo-series-2026-10-02-research.pending.jsonl \
  --output /tmp/honinbo-validated.jsonl
```

All 11 records validate as `scope_status: found`; every row remains `review_status: pending` and contains no reviewer signature. No negative search closure is asserted. Validation output SHA-256: `8bcef6da34354349d898f24aee59844bfbb6e5a3c312edf8741a56029e93b96c`.

## Evidence by product language

`body SHA-256` is over the saved HTTP response bytes. Wikipedia evidence is pinned to the listed revision and paired in the research row with the separately published Nihon Ki-in event identity page at <https://www.nihonkiin.or.jp/match/honinbo/070.html> (captured bytes SHA-256 `d96c496abca1c292ad0814200cf4d66adb7a7ed233347934a1a4bce11eda6f26`). The identity page labels `本因坊戦` as `棋戦名称` and names Mainichi Shimbun as organizer; the current contents of that page are used only to corroborate the original series identity.

| Product language | Pending exact form | Captured source and provenance | Body SHA-256 |
|---|---|---|---|
| `en` | `Honinbo` | CWI Honinbo title games, English: <https://homepages.cwi.nl/~aeb/go/games/games/Honinbo/> | `e04b9168fba2f1b6f06a032ca3afd1b36181c4ce7aeddd5ed970137e3265aac2` |
| `cn` | `本因坊战` | Chinese Wikipedia, `zh-Hans-CN`, revision `93277475`, Simplified variant: <https://zh.wikipedia.org/w/index.php?title=%E6%9C%AC%E5%9B%A0%E5%9D%8A%E6%88%98&oldid=93277475&variant=zh-cn> | `168337947ee7f1da468dcad82587c577539cbfd93b4f8a8cc24b0387cd955892` |
| `tw` | `本因坊戰` | Chinese Wikipedia, `zh-Hant-TW`, same revision `93277475`, Taiwan Traditional variant: <https://zh.wikipedia.org/w/index.php?title=%E6%9C%AC%E5%9B%A0%E5%9D%8A%E6%88%98&oldid=93277475&variant=zh-tw> | `7f191654462740c9564f1939aefe4ebf1711d8f5752aab019ab9eecbd7543663` |
| `jp` | `本因坊戦` | Nihon Ki-in official event page, Japanese: <https://www.nihonkiin.or.jp/match/honinbo/070.html> | `d96c496abca1c292ad0814200cf4d66adb7a7ed233347934a1a4bce11eda6f26` |
| `ko` | `본인방전` | Korea Baduk Association player record, Korean: <https://www.baduk.or.kr/record/player_view.asp?pkey=20000106> | `d788a5fdca0e5154f776796069e8d985146a7714bbc2bf823e79274bf6d30dcf` |
| `de` | `Hon’inbō` | German Wikipedia, revision `260688295`: <https://de.wikipedia.org/w/index.php?title=Hon%E2%80%99inb%C5%8D_(Turnier)&oldid=260688295> | `2c615169828fa627b20f3dbe9dab6ad943633b8ee23268e97ab49802dbf18301` |
| `es` | `Torneo Hon'inbō` | Spanish Wikipedia, revision `171879930`: <https://es.wikipedia.org/w/index.php?title=Torneo_Hon%27inb%C5%8D&oldid=171879930> | `e4cef2f0028141b4b33deeb8a78f19fba84848bfee2b0033f4e656b53476ca3b` |
| `fr` | `Tournoi Hon'inbō` | French Wikipedia, revision `239830918`, section `Tournoi Hon'inbō`: <https://fr.wikipedia.org/w/index.php?title=Hon%27inb%C5%8D&oldid=239830918> | `c56b22c762a820c0b110faa9c87803b2684a45b78e2603721cdebbefd9df4b85` |
| `ru` | `Турнир Хонинбо` | Russian Go book *Мыслить и побеждать: игра Го для начинающих*, PDF p. 141, heading `Самые престижные титульные турниры Японии`: <https://nikoraido.ru/files/Grishin-Emelyanov-Myslit-i-pobezhdat-igra-Go-dlya-nachinayushhih.pdf> | `169955c5064c0119b0f1a1d692e902a35267b793f13257fbb1867e1ebf0f972b` |
| `tr` | `Honinbo Turnuvası` | Turkish Wikipedia, revision `24969706`: <https://tr.wikipedia.org/w/index.php?title=Honinbo&oldid=24969706> | `80f2a3fe0b1041410a44b48cebd8d4fe04ed46bc69653f48b3e6d50c49f47737` |
| `ua` | `Турнір на звання Хон'імбо` | Ukrainian Wikipedia, revision `41093637`: <https://uk.wikipedia.org/w/index.php?title=%D0%A5%D0%BE%D0%BD%27%D1%96%D0%BC%D0%B1%D0%BE&oldid=41093637> | `e3e42c0cbc3f1584ac3459f9cb92f9548a3f4424ec59c08ace44b58c39282c2c` |

The Russian PDF was manually inspected after layout-preserving text extraction. On page 141, under `Самые престижные титульные турниры Японии`, the book lists `Турнир Хонинбо` alongside the Kisei and Meijin tournaments and names Mainichi as sponsor. The exact extracted page and PDF response hash are retained in the private capture directory.

## Review state and limits

No source-level HOLD is carried into this capture batch. The Ukrainian phrase has a separate qualified source-level decision in `kifu-name-honinbo-ua-independent-decision-2026-10-02.md`; that article warns it lacks citations, so its wording is observed usage rather than evidence of official Ukrainian endorsement or dominant spelling. Turkish evidence is the pinned article accepted in registry decision `.5`; it does not establish an independent Turkish federation convention. The Russian phrase follows the `.5` registry decision's admitted Russian Go-library evidence. These qualifications do not change the requested candidate strings.

All eleven JSONL rows are unsigned and pending another reviewer. This batch does not resolve the separate 1,617-row identity/link audit, assign a database event ID, or authorize production changes.
