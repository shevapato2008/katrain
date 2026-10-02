# Next high-impact event five-language source matrix (2026-10-03)

## Scope and decision state

Read-only research for one reusable series candidate, selected from the frozen production v4 event-group inventory. This memo and the controlled response-body captures are evidence leads only. They do not approve an event identity, canonical ID, display string, raw-value link, grammar rule, candidate row, or production write. All five display forms and the complete production scope remain **pending independent review**.

The selected candidate is the historic professional Fujitsu Cup. Its production v4 group has an exact core of `富士通杯`, grammar `explicit_components`, **306 affected games**, and **54 exact raw-value members**. The parser currently splits edition and (where present) round components. This is one of the larger reusable event-pattern opportunities not covered by the event-series source matrix or the explicitly excluded Honinbo, Judan, Oza, Old Meijin, Oteai, Pro Best Ten, Nihon Ki-in Championship, and Ryusei projects. The current documents mention Fujitsu Cup in player and individual-game context, but do not contain a series-level five-language event matrix.

No second candidate is included: this series alone has substantial impact and a reusable two-component structure, while the direct five-language source check already leaves scope and naming questions for independent review.

## Frozen inventory and scope limits

Inventory: `~/.local/share/kifu-name-audit/2026-10-02/kifu-event-groups-prod-v4-20261002.json.gz`.

- File SHA-256: `ae483b833c73879cf9b5544060d3857f1898806fddb76c93c2e6e0bda6716d05`
- Embedded `sha256`: `2cad3eb47908cc585c1090cd79e9209e8815b7025fef9724b0cedf2ca8b0b8d9`
- `inventory_sha256`: `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a4`
- `inventory_format=2`, `rule_version=event-components-v4`, `group_count=27119`
- Exact group: `core=富士通杯`, `grammar=explicit_components`, 306 affected games, 54 members; all 54 member structures have `status=pending_review`.

The raw labels are Simplified Chinese and encode ordinal edition plus round, for example `第10届富士通杯第一轮`, `第23届富士通杯第二轮`, and `第13届富士通杯第1轮`. Variants include Arabic and Chinese-number ordinals, abbreviated `13届`, and two edition-only labels using `期` rather than `届` (`第五期富士通杯`, `第九期富士通杯`). Those variants need explicit review before any parser rule or alias is adopted. The group has member labels for editions 1–23; this inventory does not show an edition-24 raw member. Official history places the 24 editions in 1988–2011, but the group file has no per-game date, row ID, source provenance, or timestamp fields. I therefore cannot flag pre-entry games, sentinel dates, or date mismatches from this artifact. Their absence here is not evidence those issues do not occur in the underlying rows.

The source-language identity is Japanese: the Nihon Ki-in calls the event `世界囲碁選手権・富士通杯`, says it ended after the 24th edition, and identifies the organizers and Fujitsu as sponsor. The imported Simplified Chinese core `富士通杯` is consistent with that identity, but identical stems also occur in unrelated events (including the BUPT–Fujitsu student event and other amateur/pro-am competitions). A stem match alone is not a safe membership test. Review must validate the full raw-label pattern and finite row scope; this memo does not blanket-map other Fujitsu-named events.

## Five-language source matrix

Capture root: `~/.local/share/kifu-name-audit/2026-10-03/fujitsu-cup-five-strict-captures/`. The response bodies were fetched directly over HTTPS and saved with mode `0600`; the directory has mode `0700`. UTC times below are the capture times recorded in `manifest.json`. A language tag absent from page markup is described from the actual body language, not inferred from the site domain.

| Language | Direct body and identity signal | Exact witnessed phrase; pending display candidate | Capture evidence |
|---|---|---|---|
| `cn` | [Sohu Sports, 23rd Fujitsu Cup topic page](https://sports.sohu.com/fujitsucup23/). Its title is a Chinese event-topic heading for the 23rd cup; this is the professional event, not a generic Fujitsu-sponsored competition. Simplified Chinese; HTML has no `lang` attribute. | `第23届富士通杯世界围棋锦标赛`; pending compact display: `富士通杯世界围棋锦标赛`. | HTTP 200; captured `2026-10-02T17:14:21.681926Z`; SHA-256 `7513082d388884aa4f0d24d088fb5819614a5c5d8867aa56999e467ef6bb91a6`; `cn_sohu_23rd.body`. Excerpt: page title `第23届富士通杯世界围棋锦标赛-搜狐体育`. |
| `tw` | [Haifong Go Institute, Taiwan Go history feature](https://www.haifong.org/news/content/157A1D983409CB2FFAFF70140B175A51). It says the 8th Japanese Fujitsu Cup opened in Tokyo in 1995 and that Taiwan’s Zhou Junxun represented Taiwan and met Lee Chang-ho in round one. Body declares `lang="zh-tw"`. | `第八屆日本富士通盃`; pending compact display: `日本富士通盃` (retaining the source’s Japan qualifier until scope review). | HTTP 200; captured `2026-10-02T17:14:34.918635Z`; SHA-256 `a8b5ff005743cd177cf46fbe75a701d5461b6ccfdb83dc3c47c9c04045951cd7`; `tw_haifong_article.body`. Excerpt: `1995年，第八屆日本富士通盃在東京開賽` and `代表台灣出賽`. |
| `jp` | [Nihon Ki-in official series archive](https://archive.nihonkiin.or.jp/match/fujitsu/). It identifies the tournament name, organizer, sponsor, format and end after the 24th edition. Japanese body; HTML has no `lang` attribute. | `世界囲碁選手権・富士通杯`; pending display candidate uses the exact official name. | HTTP 200; captured `2026-10-02T17:14:20.183700Z`; SHA-256 `3d4076af3cd255ac886d5775402fbf71346e5f6226cacf8ddf3e77a773f54058`; `jp_nihonkiin_archive.body`. Excerpt: `棋戦名称 世界囲碁選手権・富士通杯 （第24回で終了）`; organizers Yomiuri Shimbun, Nihon Ki-in, Kansai Ki-in; sponsor Fujitsu. |
| `ko` | [Korea Baduk Archive, professional-history record](https://archives.baduk.or.kr/archives/talk/view.asp?no=7). Its Korean career chronology names the 1994 tournament; the exact phrase is in a list of international Go results. Korean body; HTML has no `lang` attribute. | `후지쓰배 세계 바둑 선수권 대회`; pending display candidate preserves the directly witnessed spelling. | HTTP 200; captured `2026-10-02T17:14:37.365811Z`; SHA-256 `7a323b192d45bcbd5441041fbffdbb07c4c1ee403edc94dfccfb399028be3ce6`; `ko_kbaduk_archive.body`. Excerpt: `1994년 후지쓰배 세계 바둑 선수권 대회, 동양증권배 우승`. |
| `en` | [Nihon Ki-in English official archive](https://archive.nihonkiin.or.jp/match/fujitsu/index-e.html). It lists the formal tournament name, cooperating national/regional Go organizations, 24 editions, and 1988–2011 winners. HTML declares `lang="en"`. | `The World Go Championship The Fujitsu Cup`; pending display candidate preserves the exact official tournament-name field. | HTTP 200; captured `2026-10-02T17:14:18.409212Z`; SHA-256 `bb13e7f47015e76e649a2c851cba6a93fafe5859edd8c4147128fbda10eb8b66`; `en_nihonkiin_archive.body`. Excerpt: `Tournament name | The World Go Championship The Fujitsu Cup`; the archive lists terms 1–24 and years 1988–2011. |

The five rows demonstrate direct body wording in each requested language and identify the professional series with varying degrees of specificity. They are **not** independent final approvals: the cn and ko sources use a tournament topic/career record rather than an official series archive, and the tw feature uses the eighth-edition local history context. A reviewer should check the captured bytes, exact heading/body boundaries and each candidate’s fit for a compact event display before approving any language.

## Pending review items

1. Verify the 306-game scope against frozen production rows and a provenance-aware sample; determine whether all 54 member values refer to the same professional event and whether any homonymous Fujitsu event was included.
2. Inspect underlying game dates and source records for pre-1988 records, sentinel/malformed dates, late or non-event rows, and edition 24 coverage. The event-group inventory cannot answer those questions.
3. Decide whether exact `届`/`期`, Arabic/Han numeral, missing-round and edition-only variants can share one finite edition/round grammar. Do not accept all 54 raw values solely because the parser grouped them.
4. Review whether to retain the longer native source forms as display names, especially `日本富士通盃` in Traditional Chinese and the formal English tournament-name field.
5. Obtain an independent reviewer; no self-approval or production change is recorded here.

No code or database was changed, no production/identity approval was made, and no other languages were researched for this candidate.
