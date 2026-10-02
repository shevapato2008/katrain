# Three generic event labels: 11-language source candidates

Research captured 2026-10-03 (Asia/Shanghai; 2026-10-02 22:11 UTC). Producer: Luna. Scope is exactly the three raw labels and 2,134 rows in the frozen inventory described by [high-volume triage](kifu-name-high-volume-event-triage-2026-10-02.md): `段位赛` (901), `个人赛` (638), and `Hoensha game` (595). These are display candidates only. No event entity, event ID, alias, row link, approval, or write is proposed. In particular, neither Chinese label establishes a national competition.

## Decision boundary and evidence

The triage evidence classifies `段位赛` as a generic dan-rank competition description and `个人赛` as a generic individual-format description. Both lack edition, round, and event ID evidence. `Hoensha game` is a historical archive/source-context label: CWI says Hoensha (方円社) was an organization of professional Go players, started in 1879, and that its monthly game records appeared in *Igo Shinpo*. Nihon Ki-in history independently says 方円社 recorded monthly games and published them in that magazine. Thus the Hoensha candidates explicitly retain an archive/history/organization cue; none calls it a tournament.

Observed source passages (short excerpts):

- CWI Hoensha archive: “The Hoensha (方円社; an organization of professional go players) started in 1879.” [Page](https://homepages.cwi.nl/~aeb/go/games/games/Hoensha/)
- Nihon Ki-in history: “方円社（ほうえんしゃ）を結成し、毎月の手合を収録して雑誌（＝囲碁新報）を発行” (formed Hoensha; recorded monthly games and published the magazine *Igo Shinpo*). [Page](https://archive.nihonkiin.or.jp/history/06.html)
- National Diet Library (English): “the Go study group Hoensha (方円社)”. [Page](https://www.ndl.go.jp/kaleido/e/entry/22/2.html)
- Kotobank, *Sekai Daihyakka*: 方円社 was an 囲碁の研究会 and its journal 囲棋新報 ran from 1879 to 1924. [Entry](https://kotobank.jp/word/%E6%96%B9%E5%86%86%E7%A4%BE-131797)
- For the rank/format distinction, the prior bounded terminology review records Nihon Ki-in use of `段級位`, Korea Baduk Association contrast `단체전` / `개인전`, and the Go rank system `단위`; see [review and citations](kifu-name-generic-event-11lang-review.md). The source labels themselves are the direct Chinese wording. Traditional Chinese below is a script-normalized editorial form.
- English “individual tournament” is attested in International Go Federation event text describing competition “as an individual tournament under an eight-round Swiss system.” [IGF](https://intergofed.org/46th-world-amateur-go-championship-to-be-held-in-mungyeong-korea/)

Page-body SHA-256 records were captured by direct HTTPS fetch with a browser user agent at 2026-10-02 22:11 UTC: CWI Hoensha `abeb516b8b69c606d1bf246191416aa6ef4a1db14b5b171aac505cafd22c417e` (8,698 bytes); Nihon Ki-in `813b6092377b2808f5dc91574fee2ea2c38673f84351ca72dd3c83fd9b74289f` (9,505 bytes); Kotobank `539bb6b9bfd9ec7e876483b0ba43ad3a4125b960153a51594336dcdc036aa80b` (214,223 bytes); National Diet Library `9aafda521f74ba8329464af2c0223bb694007844d2f8d0022ca86d6f37504435` (28,936 bytes). These hashes identify retrieved response bodies, not publisher signatures. Korean Baduk Association rules and the cited Japanese grade-event listing are cited in the prior review; this memo did not capture their response hashes.

## Candidate wording

“Source wording” means the proposed display reproduces the observed source language/label. “Script/orthographic normalization” preserves source meaning while adapting script or conventional spelling. “Editorial translation” is a descriptive translation based on the raw term and the evidence above; it is not claimed to be an established official tournament name. Candidate-ready means suitable for independent terminology review, not approval for product display.

### `段位赛` — generic dan-rank tournament (901 rows)

| Language | Candidate | Basis / kind | Assessment |
|---|---|---|---|
| cn | 段位赛 | Exact source label | Candidate-ready; generic only |
| tw | 段位賽 | Traditional-script normalization of source | Candidate-ready; generic only |
| jp | 段位戦 | Japanese Go grade terminology; editorial rendering of rank + competition | Candidate-ready; generic only |
| ko | 단위 대회 | `단위` is the Go dan/rank concept; `대회` competition; editorial rendering | Candidate-ready; generic only |
| en | Dan-rank tournament | Explicitly identifies Go rank grades, avoids “ranking contest”; editorial translation | Candidate-ready; generic only |
| de | Dan-Grad-Turnier | “dan grade” + tournament; editorial translation | Candidate-ready; generic only |
| es | Torneo de grados dan | Makes the Go dan-grade sense explicit; editorial translation | Candidate-ready; generic only |
| fr | Tournoi de grades dan | Makes the Go dan-grade sense explicit; editorial translation | Candidate-ready; generic only |
| ru | Турнир по данам | “Tournament by/in dan grades”; editorial translation | Candidate-ready; generic only |
| tr | Dan derecesi turnuvası | Dan grade + tournament; editorial translation | Candidate-ready; generic only |
| ua | Турнір за данами | Dan-grade tournament; editorial translation | Candidate-ready; generic only |

No candidate adds “national”, a country, year, organizer, championship status, or named series. “段位赛” can be ambiguous in isolation; these translations preserve only the rank-related category supported by the raw text.

### `个人赛` — individual tournament (638 rows)

| Language | Candidate | Basis / kind | Assessment |
|---|---|---|---|
| cn | 个人赛 | Exact source label | Candidate-ready; generic format |
| tw | 個人賽 | Traditional-script normalization of source | Candidate-ready; generic format |
| jp | 個人戦 | Conventional Japanese individual-division wording; editorial normalization | Candidate-ready; generic format |
| ko | 개인전 | Korea Baduk Association format term, contrasted with team competition | Candidate-ready; generic format |
| en | Individual tournament | Attested Go competition wording (IGF); generic format | Candidate-ready; generic format |
| de | Einzelturnier | Individual tournament; editorial translation | Candidate-ready; generic format |
| es | Torneo individual | Individual tournament; editorial translation | Candidate-ready; generic format |
| fr | Tournoi individuel | Individual tournament; editorial translation | Candidate-ready; generic format |
| ru | Индивидуальный турнир | Explicit “individual”, avoids “personal”; editorial translation | Candidate-ready; generic format |
| tr | Bireysel turnuva | Individual tournament; editorial translation | Candidate-ready; generic format |
| ua | Індивідуальний турнір | Explicit “individual”, avoids “personal”; editorial translation | Candidate-ready; generic format |

No candidate inserts “national championship” or implies a particular edition. `个人赛` describes format only.

### `Hoensha game` — historical Hoensha archive game (595 rows)

| Language | Candidate | Basis / kind | Assessment |
|---|---|---|---|
| cn | 方圆社史料棋局 | Editorial translation; retains organization + historical-source context | Candidate-ready; archive context, not event identity |
| tw | 方圓社史料棋局 | Traditional-script normalization of editorial translation | Candidate-ready; archive context, not event identity |
| jp | 方円社の史料棋譜 | Editorial Japanese description: Hoensha historical record game record | Candidate-ready; archive context, not event identity |
| ko | 호엔샤(方円社) 역사 자료 기보 | Editorial translation; romanized name plus original characters and historical record cue | Candidate-ready; archive context, not event identity |
| en | Hoensha archive game | Raw English name retained, with archive qualifier made explicit | Candidate-ready; archive context, not event identity |
| de | Historische Partie aus dem Hoensha-Archiv | Editorial translation: historical game from the Hoensha archive | Candidate-ready; archive context, not event identity |
| es | Partida histórica del archivo de Hoensha | Editorial translation: historical game from the Hoensha archive | Candidate-ready; archive context, not event identity |
| fr | Partie historique des archives de la Hoensha | Editorial translation: historical game from the Hoensha archives | Candidate-ready; archive context, not event identity |
| ru | Историческая партия из архива Хоэнся | Editorial translation; historical game from Hoensha archive | Candidate-ready; archive context, not event identity |
| tr | Hoensha arşivinden tarihî go partisi | Editorial translation; explicitly a Go game from the historical archive | Candidate-ready; archive context, not event identity |
| ua | Історична партія з архіву Хоенся | Editorial translation; historical game from Hoensha archive | Candidate-ready; archive context, not event identity |

The organization form 方円社 is preserved in Japanese and in the Korean candidate to reduce ambiguity; romanized Hoensha is retained in languages using Latin script. No candidate calls these games a Hoensha tournament, monthly tournament, or one event. The archive evidence establishes organizational context, not that each individual game was played at a particular meeting.

## Count and remaining review

This memo offers **33 candidate strings** (3 exact raw labels × 11 languages). All **33 are candidate-ready for independent review**, **0 are approved**, and **0 are event identities**. The six secondary-language strings per Chinese label are explicitly editorial translations; source evidence supports meaning and category, not official localized names. A reviewer may hold any wording found unnatural or inconsistent with product terminology. The frozen count is 2,134 rows; this research does not verify current database membership or authorize any write.
