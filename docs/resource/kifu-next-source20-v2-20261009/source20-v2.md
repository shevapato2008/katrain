# Next 20 distinct players — source-only v2

Frozen post-590 inventory selection. 20 distinct owner pairs; no database query/write, signing, Git or deployment. Root owns current source binding and approval.

| PROD / TEST | Slots | Missing | Proposed name | Source type | Review note |
|---|---:|---|---|---|---|
| 3771 / 9569 | 111 | ko | 시모히라 아키오 | direct_korean_go_tournament_table |  |
| 6642 / 12411 | 105 | ko | 다이나카 신 | direct_korean_go_tournament_table |  |
| 6635 / 12404 | 84 | ko | 마에타니 신고 | generated_korean_from_complete_japanese_kana | generated; finite conflict searches |
| 4568 / 10358 | 78 | ko | 가와무라 마사미치 | generated_korean_from_complete_japanese_kana | generated; finite conflict searches |
| 5094 / 10876 | 12 | ko | 리강 | direct_korean_wikipedia_disambiguation |  |
| 368 / 369 | 18 | ko | 자오젠난 | direct_korean_professional_go_player_profile |  |
| 3820 / 9618 | 22 | ko | 차오스야오 | direct_korean_professional_go_player_profile | partial_hanzi_identity_review |
| 4634 / 10424 | 10 | ko | 장자야오 | direct_korean_professional_go_player_profile |  |
| 5133 / 10914 | 7 | ko | 양원카이 | direct_korean_professional_go_player_profile |  |
| 5473 / 11247 | 18 | ko | 왕보강 | direct_korean_professional_go_player_profile | partial_hanzi_identity_review |
| 5675 / 11448 | 14 | ko | 친쓰웨 | direct_korean_professional_go_player_profile |  |
| 5790 / 11559 | 14 | ko | 판시위 | direct_korean_professional_go_player_profile |  |
| 6296 / 12062 | 11 | ko | 천야펑 | direct_korean_professional_go_player_profile |  |
| 6378 / 12144 | 11 | ko | 천창칭 | direct_korean_professional_go_player_profile |  |
| 6547 / 12311 | 28 | ko | 황량위 | direct_korean_professional_go_player_profile | partial_hanzi_identity_review |
| 5351 / 11127 | 19 | en | Sha Xingyu | direct_english_organizer_roster |  |
| 4340 / 10134 | 15 | ko | 안도 히나타 | direct_korean_go_tournament_table |  |
| 4041 / 9837 | 6 | ko | 마에다 료 | direct_korean_go_tournament_table |  |
| 339 / 340 | 11 | ko | 진 하쿠쇼 | direct_korean_news_article |  |
| 3844 / 9642 | 6 | tw | 亞歷山大·迪那斯塔因 | direct_zh_hant_wikipedia_go_event_table | same_page_tw_spelling_variant_迪納 |

## Source-quality boundaries

Baduk TV is a Korea Baduk Association affiliated Go broadcaster. Its player index is GET; individual profiles were actually fetched by POST to `gisa_view.asp` with retained `prpl_code` and form fields. Cyberoro GET profile URLs use the same player code and data, so they are access links, not independent identity corroboration.

For 3820, 5473 and 6547, profile bracket Hanzi are partial or mixed Hangul/Hanzi. The whole Hangul name appears in the professional profile; retained Daum pairings are identity leads, not an upgrade of the incomplete bracket to full Hanzi. The root should adjudicate those three.

For 3844, the same Traditional Chinese Wikipedia Go event page contains both 迪那斯塔因 and 迪納斯塔因. The proposed 迪那 form is directly published and matches the existing CN base; retain the variant flag.

For 6635 and 4568, the proposed Hangul is generated from full Japanese kana and retained NIKL rules. The two additional actual search responses per owner are saved, and no global absence is claimed.

Frozen PROD SHA-256 `009ee2db0f7415ac8356461acc2a6d5f604f9f3207d5de9c96939abb09a4a521`; TEST SHA-256 `ab0ad9f8f839ce9451ec37d424c280aa2769abd4518282e958dd9385e36ce0fb`. Detailed URLs, methods, form data, content paths, timestamps and hashes are in `source20-v2.json`.
