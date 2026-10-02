# Korean Baduk League event identity and naming source memo

Researcher model: **`gpt-6-luna`**. Reviewed 2026-10-02. Confidence is stated per identity partition below. This memo records sources and safe candidate boundaries for later independent review; it does not approve event IDs, aliases, eleven-language names, or database writes.

## Finding

Treat division and season as separate identity dimensions. The 2011 `KB국민은행 한국바둑리그` was the single principal Korean Baduk League competition before the separately named second-tier league appeared in 2012. The 2012–2014 main league and its lower-tier companion must not be merged. The 2022–2023 top league is well identified, but the inventory label `2023年度韩国围乙联赛` is not yet tied to a Korean organizer-defined event and remains unresolved.

| Inventory label | Frozen games | Safe identity finding | Confidence |
|---|---:|---|---|
| `KB国民银行杯2011韩国联赛` (2011-05-12–2011-12-18) | 267 | Map as the 2011 main/top Korean Baduk League season, with season `2011`; do not add a division token to the source display. The Korean Baduk Association player records call it `2011 KB국민은행 한국바둑리그`. The contemporary introduction of the 2012 `락스타리그` as the second-tier league supports that 2011's unqualified league label is the principal/top competition. | **High** for main league; **medium-high** for explicit “top division” wording, since that is a retrospective structural inference. |
| `KB国民银行杯2012韩国围甲联赛` | 471 | 2012 principal `한국바둑리그` / KB Korean Baduk League, division A/top. | **High** |
| `KB国民银行杯2012韩国围乙联赛` | 339 | 2012 companion `락스타리그` (Rockstar League), described contemporaneously as a second-tier/futures league; map to division B only if product semantics require the A/B normalization. | **High** for separate lower-tier event; **medium-high** for equivalence to the Chinese `围乙` label. |
| `KB国民银行杯2013韩国围甲联赛` | 166 | 2013 principal Korean Baduk League, division A/top. | **High** |
| `KB国民银行杯2013韩国围乙联赛` | 65 | 2013 lower-tier companion. Specialist sources call it `락스타리그`; keep a distinct identity from main league. | **High** for separate tier; **medium** for exact Chinese-label correspondence pending a season-specific organizer record. |
| `2014韩国围甲联赛` | 281 | 2014 principal KB Korean Baduk League, division A/top. | **High** |
| `2014韩国围乙联赛` | 166 | Lower-tier companion; 2014 reporting describes changes to the second-team league, while later sources call the successor the Future League. Preserve a separate tier identity, but do not silently rename it `Future League` without an exact 2014 organizer record. | **High** for lower tier; **medium** for its season-specific proper name. |
| `2022-2023年度KB银行杯韩国围甲联赛` | 112 | 2022–2023 KB main Korean Baduk League season, division A/top. Organizer material uses `2022-2023 KB국민은행 바둑리그`; season runs across two calendar years. | **High** |
| `2023年度韩国围乙联赛` | 120 | **Unresolved.** Do not map to the 2022–2023 KB top league or its playoff, and do not yet map to a KB second-tier/Futures league. The inventory dates alone (2023-01-17–2023-05-24) are suggestive but not identifying. | **Low / hold** |

The counts and date bounds above come from the frozen 2026-10-02 Top 100 inventory, not a live database query. Each row is one source group (`19x19`). The broader Korean-marker scan has 12,529 games across 2,980 distinct raw strings, but it is a regex family scan and must not be interpreted as a deduplicated event total. In particular, it contains stage/round/postseason labels that require structural parsing and season review.

## Evidence and source hierarchy

**Organizer / Korea Baduk Association (Hanguk Kiwon):**

- The [Korea Baduk Association player record](https://www.baduk.or.kr/record/player_view.asp?pkey=10000545) explicitly lists the professional's participation in `2011 KB국민은행 한국바둑리그`, `2012 KB국민은행 한국바둑리그`, `2013 KB국민은행 한국바둑리그`, and `2014 KB국민은행 한국바둑리그`. This directly supports the Korean title form and consecutive main-league seasons.
- The association's [2012 season final report](https://m.baduk.or.kr/news/B01_view.asp?news_no=620) calls the main event `KB국민은행 2012 한국바둑리그`, separately names `락스타리그`, calls it the Korean Baduk League's “퓨처스리그격” (Futures-League-like companion), and reports the two winning teams together. This is strong evidence that 2012 lower tier and main league are distinct competition identities.
- The [2012 season media-day report](https://m.baduk.or.kr/news/B01_view.asp?news_no=589) describes the principal league's playoff and names its four main-league teams. It also distinguishes `락스타리거` from main-league players.
- The official league site's [2014 season announcement](https://kbleague.baduk.or.kr/media/news_view.asp?db_div=2&news_no=518983) uses `2014 KB국민은행 바둑리그`, specifies the eight-team principal league, and says its second-team league format changed. The article establishes the main event and continuing separate lower-tier structure, but not a precise lower-tier proper title in its body.
- The official site identifies the later cross-year tournament in the [2022–2023 championship report](https://kbleague.baduk.or.kr/m/media/news_view.asp?db_div=1&news_no=632): it calls it `2022-2023 KB국민은행 바둑리그`, describes the regular season, two-league competition, playoffs, and championship series. This supports the top-tier identity and season span; it does not identify the inventory's generic 2023 B-division string.

**Independent and target-language evidence:**

- Contemporary Korean coverage of the 2012 draft describes the newly presented `KB국민은행 2012 락스타리그` as “2부 리그격” (second-tier league-like): [Sports Kyunghyang](https://sports.khan.co.kr/article/201203192021083). This independently corroborates the association's separation.
- A 2012 [CCTV Chinese-language report](https://news.cntv.cn/20120415/118438.shtml) says a Korean league second division was added that year and distinguishes it from the main Korean league. The source does not prove every database row marked `围乙` is a lower-tier game, but supports the Chinese distinction in the 2012 context.
- A Chinese-language SGF catalogue entry directly uses `KB国民银行杯2012韩国围甲联赛` for an August 2012 game: [101围棋](https://www.101weiqi.com/chessbook/player/53/65612/). Treat this as evidence of target-language usage, not authoritative event identity.
- English specialist season schedules use the normalized series title “Korea Baduk League” for 2010–2014: [Go to Everyone 2010](https://gotoeveryone.k2ss.info/news/kr/kl/8/), [2011](https://gotoeveryone.k2ss.info/news/kr/kl/9/), [2012](https://gotoeveryone.k2ss.info/news/kr/kl/10/), [2013](https://gotoeveryone.k2ss.info/news/kr/kl/11/), [2014](https://gotoeveryone.k2ss.info/news/kr/kl/12/). These schedules are useful independent game evidence but are not organizer records.
- A Japanese Go channel described and streamed a game under `2022~2023 KB国民銀行囲碁リーグ`: [IGOPRO stream](https://www.youtube.com/watch?v=rTQTlVClhPo). This supports a Japanese target-language form for the top-level series, not an official Japanese event title.
- The official contemporary 2013 press coverage from the league site also records KB as title sponsor since 2006 and calls the series `KB국민은행 바둑리그`: [2013 KB league closing coverage](https://kbleague.baduk.or.kr/media/news_view.asp?db_div=2&news_no=518864). In 2014, the league's title form is shortened in headlines, while body text retains the sponsor and event name; sponsor string differences are not identity differences by themselves.

Sources establish that `KB국민은행` is a sponsor/title element and `한국바둑리그` is the principal series name. Preserve sponsor and season as display components if desired, but model division and season separately from series identity. Do not infer the exact official season branding for 2011 from the database's Chinese `杯` suffix.

## Eleven-language candidate policy

The directly supported strongest-language forms below are **research candidates only**, not approved display names:

| Language | Candidate basis |
|---|---|
| `ko` | Organizer name `KB국민은행 한국바둑리그` for 2011–2014; `2022-2023 KB국민은행 바둑리그` for 2022–2023. Prefer exact season source title. |
| `en` | “Korea Baduk League” in independent season schedules. “KB” may be retained as a sponsor qualifier only where the product wants sponsor branding. |
| `cn` | The raw source forms `韩国围甲联赛` / `韩国围乙联赛` are common in Chinese coverage; 2012 example `KB国民银行杯2012韩国围甲联赛` is directly visible in 101围棋. Use `韩国围棋联赛` as the broader series term; preserve 甲/乙 only where tier is proven. |
| `tw` | No sufficiently direct Taiwan-localized source was found in this pass. `韓國圍棋聯賽` and `韓國圍棋甲級聯賽` / `乙級聯賽` are script-conversion/editorial candidates from `cn`, not attested Taiwan names. Keep pending. |
| `jp` | A Japanese broadcaster uses `KB国民銀行囲碁リーグ` for the 2022–2023 main event. Older seasons lack a direct Japanese source in this pass; do not present the same string as an officially attested historical title. |
| `de`, `es`, `fr`, `ru`, `tr`, `ua` | No target-language usage was verified in this source pass. A future editorial transliteration can be based on Korean `한국바둑리그` / romanized “Korea Baduk League,” and the language-specific word for Go, but mark each as an editorial rendering with explicit basis and seek review. Do not claim source-attested names or fill all six by machine transliteration. |

Useful low-risk naming strategy after identity review: use the stable series-level equivalent of “Korean Baduk League” in each language, with the season as a separate qualifier and A/B division only on rows whose source and event context establish tier. Preserve `KB국민은행` as optional sponsor metadata rather than forcing the bank name into every language's canonical event name. Keep source labels intact for display provenance.

## Open questions and recommended review cohort

1. Obtain the official 2013 and 2014 season pages or regulations that identify the lower-tier league's exact Korean name (`락스타리그` vs later `퓨처스리그`) and its team/game schedule. Do not normalize historical season names by successor naming.
2. For `2023年度韩国围乙联赛`, inspect representative source SGF roots (`EV`, all `GN` values, `GC`), source folders, participants, and dates against official 2023 KB/other league schedules. The available evidence does not distinguish KB Futures, an unrelated league, or a generic upstream label.
3. **Small review cohort:** independently review the two 2012 top/lower-tier labels (471 + 339 games) and the isolated 2011 unqualified label (267 games). These make the key boundary testable with direct Korean organizer terminology plus the contemporaneous 2012 second-tier source. Hold the two 2013 labels, both 2014 labels, and 2023 lower-tier label out of any finite registration until season-specific lower-tier naming/rosters or game schedules are captured. The 2022–2023 main event may be reviewed as a separate cross-year top-tier candidate, not coalesced with 2023 B-tier.

The adjacent Lee Chang-ho research files in this directory establish selected 2010–2014 individual game matches against specialist English schedules; they do not establish the event taxonomy or approve event naming. Their album IDs therefore are not part of this event cohort. All identity, display-name, and game-link decisions remain separate gates.
