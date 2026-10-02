# Chinese National Go Individual Championship source memo (read-only, 2026-10-02)

This memo advances the unresolved `中国围棋全国个人赛` label from the event source matrix. It is research evidence only: no canonical ID, alias, translation, candidate bundle, or production edit is approved here.

## Why this is the next family

The production Top 100 snapshot ranks the exact raw label `中国围棋全国个人赛` 21st: **279 games**, dates `1976-06-01` through `1995-09-16`, one source group (`19x19`). The original source-matrix notes listed it as an identity candidate requiring archive research. It is the largest unresearched exact event-like label after the already-covered English ordinal series, Japanese Ryusei, and Korean league family. These are observed counts from the controlled Top 100/family reports, not an estimate of event size.

A read-only scan of `families.jsonl` for either `中国围棋全国个人赛` or `全国围棋个人赛` found **168 raw strings / 756 games**. This is only a lexical scope estimate: it includes separately sponsored modern events, group and round annotations, other years, and inconsistent event/date metadata. It is not a proposed merge count.

## Raw name observations and tentative decomposition

| Raw field example | Games | Dates in report | Observation |
|---|---:|---|---|
| `中国围棋全国个人赛` | 279 | 1976–1995 | Legacy/import label with no explicit year; it spans 118 distinct `date_played` values. |
| `1977年中国围棋全国个人赛` | 1 | 1977-09-05 | Year-prefixed variant. |
| `1977年中国围棋全国个人赛决赛` | 1 | 1977-09-07 | Year plus a `决赛` (final) annotation; the historical 1977 event source also calls the competition `全国围棋比赛`, so the corpus label may be an editor normalization. |
| `1977年全国围棋个人赛（小组赛）` | 1 | 1977-08-26 | Year plus `小组赛` (group stage). The source history describes this as an open competition with separate groups; preserve stage text pending game-level source validation. |
| `全国围棋个人赛` | 10 | 1978–2000 | Bare native name, with date span covering multiple editions. |
| `2016年中国全国围棋个人赛男子组第6轮` | 15 | 2016-09-21–22 | Year, country qualifier, individual event, men’s group, and round are all fused. |
| `2024年恒丰基业杯全国围棋个人赛男子组第6轮` | 5 | 2024-12-10 | Sponsor, year, event, group, and round coexist; retain sponsor/group/stage as separate source fields. |

The tentative decomposition is `year` + `全国围棋个人赛` (series/name) + optional sponsor + group/division + round/stage. Keep `中国`/`全国` wording as source text until an editorial form is approved. Do not equate the 1977 label to a numbered edition from a different tournament chronology, and do not assume the modern formal title `全国围棋锦标赛（个人）` proves that all historical labels are the same format. The 1976 source year is a special case: the historical result table says the final was not held, while the imported raw label has games dated in June; the identity of those games needs source/book-level confirmation.

## Source evidence

| Language / source | Direct claim relevant to identity or boundary | Evidence weight and limits |
|---|---|---|
| Chinese, State General Administration of Sport, [“中国围棋运动发展研究”](https://www.sport.gov.cn/n322/n3407/n3413/c564649/content.html) | Lists `全国围棋个人赛` among the annual national professional Go competitions, alongside the national team championship, dan/rank event, and other named competitions. | Strong institutional evidence that this name denotes a distinct national individual competition category. It does not establish historical continuity, edition numbering, or every imported label’s scope. |
| Chinese, [狐围棋 / Foxwq retrospective on sixty years of national Go championships](https://foxwq.com/news/listid/id/12648.html) | Describes the 1977 national Go competition in Harbin (14 Aug–7 Sep), cites the 1977 competition order booklet, and reports male/female participants and distinct stages. | Valuable historical reconstruction with named primary references. It notes the event was then titled `全国围棋比赛`; this cautions against assuming the corpus wording is a contemporaneous official name. |
| Chinese, [Sohu Go chronology](https://sports.sohu.com/2004/03/17/43/news219464383.shtml) | States that the national Go competition resumed in 1974, Chen Zude won the individual title, and the 1975 national finals gave Nie Weiping his first national individual title. It distinguishes individual and team results in its annual chronology. | Secondary retrospective support for a recurring individual competition; its short chronology is not a complete edition register. |
| Chinese, [101围棋网 Jiang Mingjiu game index](https://www.101weiqi.com/chessbook/player/628/) | Shows game rows labeled `中国围棋全国个人赛`, including Kong Xiangming vs. Jiang Mingjiu dated 1976-06-01 in Hefei and Wu Songsheng vs. Jiang dated 1977-08-22 in Harbin. | Direct support for the imported wording and sample date/place interpretation, but a game database is not the event organizer’s authority. This index also labels distinct China–Japan games separately. |
| Japanese, [Pandanet Chinese Go news archive (2016)](https://www.pandanet.co.jp/event/chinaevent/backnumber2016.htm) | Calls the Chinese individual competition a unique/only individual event in the Chinese professional calendar and says it had undergone reforms; its article contextualizes contemporary individual competition with the team and dan events. | Independent Japanese-language evidence for a recurring Chinese individual competition and a changing format. It concerns the modern era, so it cannot establish the 1970s–1990s continuity by itself. |
| Japanese, [Pandanet Chinese Go news archive (2019)](https://www.pandanet.co.jp/event/chinaevent/backnumber2019.htm) | Reports a player’s win in `全国個人戦女子組` (national individual, women’s group), and mentions the individual men’s group in separate contemporary results. | Supports Japanese usage of the event concept and group distinction, not a fixed official Japanese display name or historical identity. |
| Korean, [Korean Baduk Association official player record: Qiu Jun](https://www.baduk.or.kr/record/player_view.asp?pkey=20000015) | Lists `1998년 전국 개인전 우승` (“1998 national individual event winner”) in the career record for Chinese player Qiu Jun. | Official Korean-source terminology corroborates a Korean rendering of the Chinese national individual competition. This record abbreviates the name and gives no tournament organizer/format details. |
| English, [Fuseki Info game database, National Individual Championship event list](https://fuseki.info/games_list.php?bs=ev&id=1Q39RX40&sb=full) | Uses the event label `National Individual Championship (Men), 1977` for a dated 1977 game. | Direct English-language database terminology and a stage/group clue; secondary game index only. |
| English, [“Chinese Go Championship” historical table](https://en.wikipedia.org/wiki/Chinese_Go_Championship) | Uses “Chinese Go Championship” and lists annual titleholders, including 1977. | Useful evidence that English sources use a broad championship name, but this page is tertiary and can conflate national individual competition with a championship title. Do not adopt this display name solely from this page. |

The sources support a named recurring Chinese national individual competition in both historical and modern eras, and show that sponsors, year labels, groups, and rounds appear in source records. The material reviewed does **not** prove that every historical and modern competition shares one uninterrupted ruleset or canonical entity. The best-supported Chinese form is `全国围棋个人赛`; the exact corpus spelling `中国围棋全国个人赛` appears to be a source/database label. Japanese and Korean claims above are language evidence, not translation approvals. English usage is inconsistent (`National Individual Championship`, `Chinese Go Championship`), so retain both as observed source forms only.

## Ambiguities to resolve in a bounded next pass

1. Compare 1976 raw games and 1977 source games against a primary game collection / competition booklet; especially reconcile the imported 1976 dates with the report that no final was held.
2. Trace whether `全国围棋比赛` (1977 contemporaneous event title), `全国围棋个人赛`, and current `全国围棋锦标赛（个人）` are historical names or distinct formats. Use official Chinese Go Association or sports-history records by year.
3. Review only high-count distinct raw strings from the 168-string lexical scan. Retain sponsor, men’s/women’s group, other divisions, and round/stage in separate fields; do not collapse the newer sponsored events into the legacy raw label based on substring alone.
4. For English, Japanese, and Korean display names, seek organizer/association terminology or publisher style sources before making any locale form a candidate.

## Reproduction references

Counts and raw strings were read from `/Users/fan/.local/share/kifu-event-inventory/2026-10-02/top100.jsonl` and `families.jsonl`; the latter scan selected strings containing `中国围棋全国个人赛` or `全国围棋个人赛`. No production database query or write was run for this memo. The source URLs above were reviewed read-only.
