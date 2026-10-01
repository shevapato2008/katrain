# Generic event label review: 段位赛 and 个人赛

Scope: linguistic and classification review of two frequent raw event values, using the `classification-v1` template model in `katrain/web/kifu/name_candidates.py`. The supplied production counts are 901 games for `段位赛` and 638 for `个人赛`. These are labels, not confirmed event identities. This memo does not approve candidate decisions or assert coverage.

## Model under review

The current generic event model maps the rank label to `rank_event` and the individual label to `individual_event`, with these display strings:

| Language | `段位赛` (`rank_event`) | `个人赛` (`individual_event`) |
|---|---|---|
| en | Rank Tournament | Individual Tournament |
| cn | 段位赛 | 个人赛 |
| tw | 段位賽 | 個人賽 |
| jp | 段位戦 | 個人戦 |
| ko | 단위 대회 | 개인전 |
| de | Rangturnier | Einzelturnier |
| es | Torneo de grados | Torneo individual |
| fr | Tournoi de niveaux | Tournoi individuel |
| ru | Турнир разрядов | Личный турнир |
| tr | Seviye turnuvası | Bireysel turnuva |
| ua | Турнір розрядів | Особистий турнір |

## Terminology and accuracy

`段位赛` denotes a competition associated with dan/rank grades. The Chinese and Japanese forms are direct and natural. Korean `단위` is the established Go/Baduk word for rank grade; the Korea Baduk Association's rules distinguish `단체전` and `개인전` by competition format, while the Korean encyclopedia describes the Baduk `단위` system. These support the semantic components of `단위 대회` and `개인전` ([Korea Baduk Association rules](https://www.baduk.or.kr/story/gameRule.asp), [Encyclopedia of Korean Culture, 바둑](https://encykorea.aks.ac.kr/Article/E0020464)). Japanese Go institutions use `段位` as the player grade and publish grade-banded events, e.g. `段級位認定大会` ([Nihon Ki-in event listing](https://www.nihonkiin.or.jp/event/area/ichigaya/2026_10.html)).

The remaining `段位赛` renderings convey a rank/level-based event but vary in precision. English `Rank Tournament` can mean a tournament about standings rather than dan grades. German `Rangturnier`, Spanish `Torneo de grados`, French `Tournoi de niveaux`, Turkish `Seviye turnuvası`, and Russian/Ukrainian `Турнир разрядов` / `Турнір розрядів` are intelligible category labels, but the source material reviewed here does not establish them as conventional Go-specific event names. They may be mistaken for ranking contests, general skill levels, school grades, or sports classifications. They should be treated as understandable provisional wording, not verified idiomatic terminology.

`个人赛` means an individual competition format, commonly contrasted with a team event. Chinese and Japanese forms are direct. Korean `개인전` is standard sports/competition usage, explicitly contrasted with `단체전` in the Korea Baduk Association rules. German `Einzelturnier`, Spanish `Torneo individual`, French `Tournoi individuel`, and Turkish `Bireysel turnuva` communicate an individual tournament naturally. English `Individual Tournament` is clear though generic. Russian `Личный турнир` and Ukrainian `Особистий турнір` are understandable, but the reviewed evidence does not confirm that “personal” is the preferred sports terminology over an “individual” construction in those locales.

## Generic versus formal-event risk

These exact values are descriptive event types rather than names that uniquely identify a named championship: `段位赛` says the event concerns ranks/grades; `个人赛` says the format is individual. That makes generic display plausible and preferable to inventing a named event. However, a raw label can still be shorthand for a recurring formal event or a specific division in the source system. Replacing it globally with a generic template could erase that identity if the same label is used within a formal-event series. Counts alone do not distinguish those cases. The generic classification therefore needs source-context evidence for the affected raw values before approval; no such identity check is made in this memo.

## Sources and limits

- [Korea Baduk Association, competition rules](https://www.baduk.or.kr/story/gameRule.asp): uses `단체전` / `개인전` as competition-format distinctions.
- [Encyclopedia of Korean Culture, 바둑](https://encykorea.aks.ac.kr/Article/E0020464): describes the Baduk rank (`단위`) system.
- [Nihon Ki-in, grade certification event](https://www.nihonkiin.or.jp/event/area/ichigaya/2026_10.html): uses `段級位` for grade divisions/certification.
- [Nihon Ki-in high-school event outline (PDF)](https://www.nihonkiin.or.jp/event/amakisen/highschool-gochampionship/49/docs/outline.pdf): uses `男子個人戦・女子個人戦` for individual divisions.

This is a bounded terminology check, not a full native-speaker review across eleven languages. No authoritative multilingual Go lexicon was found for the European-language labels. Unresolved questions: whether `段位赛` is attached to named event series in the source records; preferred Go-specific equivalents for the rank label in en/de/es/fr/tr/ru/ua; and preferred sports-register wording for Russian/Ukrainian “individual tournament.”
