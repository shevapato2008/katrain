# Raw-player ranks 89–100: bounded primary-source candidates (pending)

**Date:** 2026-10-03. Scope is the twelve supplied raw names and counts: 彭立尧 713, 吴侑珍 706, 辜梓豪 698, 林书阳 691, 刘小光 690, 余正麒 689, 李钦诚 683, 刘星 679, 赵善津 679, 古灵益 678, 李赫 675, 睦镇硕 675. These are raw-value album-occurrence counts; they are not GoRatings ranks, player IDs, identity-to-game links, or approved write scope.

## Language cells

Each non-HOLD entry is an exact form observed on an official association/professional site in that language. It is a **candidate pending independent review**, not an approved display value. A source in one language is not reused to infer another language. GoRatings is used for DOB/profile crosswalk only; its localized strings do not count as primary use evidence here.

| Raw name | cn | tw | jp | ko | en |
|---|---|---|---|---|---|
| 彭立尧 | 彭立尧 | HOLD | HOLD | 펑리야오 | HOLD |
| 吴侑珍 | HOLD | HOLD | HOLD | 오유진 | HOLD |
| 辜梓豪 | 辜梓豪 | HOLD | HOLD | 구쯔하오 | HOLD |
| 林书阳 | HOLD | 林書陽 | HOLD | 린수양 | HOLD |
| 刘小光 | 刘小光 | HOLD | HOLD | HOLD | HOLD |
| 余正麒 | HOLD | HOLD | 余　正麒 | 위정치 | HOLD |
| 李钦诚 | 李钦诚 | HOLD | HOLD | 리친청 | HOLD |
| 刘星 | 刘星 | HOLD | HOLD | 류싱 | HOLD |
| 赵善津 | HOLD | HOLD | 趙　善津 | 조선진 | HOLD |
| 古灵益 | 古灵益 | HOLD | HOLD | 구링이 | HOLD |
| 李赫 | 李赫 | HOLD | HOLD | 리허 | HOLD |
| 睦镇硕 | HOLD | HOLD | HOLD | 목진석 | HOLD |

**Coverage:** 21/60 cells have primary/professional-source candidates, 39/60 remain HOLD. This covers all 12 names with an identity crosswalk. Candidates: cn 7, tw 1, jp 2, ko 11, en 0. All 21 remain unsigned. `TW` appears only for 林書陽 because Haifong has a direct Traditional Chinese professional profile. No zh→tw character conversion was applied. English roman letters on Japanese/Korean pages are recorded only as a clue, not English-language usage evidence.

## Primary capture set

All fetched HTML/API response bodies are in the protected packet `~/.local/share/kifu-name-audit/2026-10-03/raw-player-ranks89-100-primary-luna/` (directory 0700; captures and evidence JSON 0400). The per-cell artifact [primary-language-cells.pending.json](~/.local/share/kifu-name-audit/2026-10-03/raw-player-ranks89-100-primary-luna/primary-language-cells.pending.json) gives, for every sourced cell, the exact name/identity span, source URL, UTC capture time, body filename and SHA-256. [capture-manifest.json](~/.local/share/kifu-name-audit/2026-10-03/raw-player-ranks89-100-primary-luna/capture-manifest.json) inventories **35 captures**, including immutable byte lengths and hashes. Manifest SHA-256 `92c6bba3aa5f781bd3f94508caff5513409d1de4835db1b94a04fb73c6fb7c1d`; cell-set SHA-256 `6974f385bbca5b52e43f0980f5fd5ad83303c2de1f7c9a2bf894a20beb697634`; identity crosswalk SHA-256 `f786806ff22076314f7ba4b4179276cbba8487a2c2b1206901a8c41fa836bd8f`.

### Chinese Weiqi Association

The official CWA page bundle loaded the endpoint `https://wqapi.cwql.org.cn/playerInfo/professional/list`; the captured official bundle records that route. The live API body was captured at `2026-10-03T01:25:03.669152+00:00` (body SHA-256 `18ba2a04efdca69d47528cbe703d9c54e1005b7f986af782434cbc3f1dd316f9`). Its exact `playerName` fields support these Simplified Chinese candidate spellings:

| Exact CWA playerName | CWA roster ID | CWA date of birth |
|---|---|---|
| 辜梓豪 | `CWA000386` | `1998-03-13` |
| 刘小光 | `CWA000011` | `1960-03-20` |
| 李钦诚 | `CWA000259` | `1998-10-20` |
| 彭立尧 | `CWA000037` | `1992-01-14` |
| 古灵益 | `CWA000029` | `1991-07-03` |
| 刘星 | `CWA000033` | `1984-12-10` |
| 李赫 | `CWA000124` | `1992-01-01` |

### Korea Baduk Association

Each row is the Korean site’s native-language player record. Its Hangul display, Hanja cross-label, birth date, and nationality/organization line are preserved in the corresponding immutable page body; each capture’s exact span is in the per-cell file.

| Raw name | KBA pkey | Exact profile heading and identity span | Captured UTC | Body SHA-256 |
|---|---:|---|---|---|
| 彭立尧 | `20000354` | `펑리야오( 彭立堯 ) 9단` | `2026-10-03T01:25:03.669442+00:00` | `62e02712dd762104eb23464063d2b80da30bd1ec5d4b5b6b939020362a64c9fd` |
| 吴侑珍 | `10000736` | `오유진( 吳侑珍 ) 9단` | `2026-10-03T01:21:54.749289+00:00` | `df1868552e1f825106241b491cf4d7c19d7927c8c4a428f681581d10b440d31d` |
| 辜梓豪 | `20000629` | `구쯔하오( 辜梓豪 ) 9단` | `2026-10-03T01:21:54.751963+00:00` | `00d35ae8dba2ee0143be3b48ab1d86af2ee128d0643bb9e521c1286f3b9bfd6f` |
| 林书阳 | `20000248` | `린수양( 林書陽 ) 9단` | `2026-10-03T01:25:03.669756+00:00` | `5747e646e15271af617fe876ab571165b437f1f607cb48d7344f051509e5887e` |
| 余正麒 | `20000353` | `위정치( 余正麒 ) 9단` | `2026-10-03T01:25:03.669973+00:00` | `eab2e8f7d2c6e9eab068b68197b05684b9a5e87c991734e31bde2b5549d568da` |
| 李钦诚 | `20000526` | `리친청( 李欽誠 ) 9단` | `2026-10-03T01:25:03.670383+00:00` | `f839434f420a30cf42cbcf4960d611bab063ea1d8503e927eb5f4d4758f992f7` |
| 刘星 | `10000353` | `류싱( 劉星 ) 7단` | `2026-10-03T01:25:03.670561+00:00` | `26c1a5c8295ea780a6c39c8a6b6c0c3213ebc6368385a700cf6ee42dd1b3626a` |
| 赵善津 | `20000056` | `조선진( 趙善津 ) 9단` | `2026-10-03T01:21:54.749712+00:00` | `99f1dfba61704942c6ea11f33eeebb84721217d6f76ba30db2555d504ac1f8d2` |
| 古灵益 | `20000312` | `구링이( 古靈益 ) 9단` | `2026-10-03T01:25:03.670736+00:00` | `3545900419d73d9189e65849d5165470dc076722bf24c1efc249cf52efc47e3a` |
| 李赫 | `20000359` | `리허( 李赫 ) 6단` | `2026-10-03T01:25:03.670889+00:00` | `ea3579cce60e7e4c4d9f86d58398f5f69859a0388e818a343dba64c68b583d3d` |
| 睦镇硕 | `10000093` | `목진석( 睦鎭碩 ) 9단` | `2026-10-03T01:21:54.752279+00:00` | `02a5ccf84c1e697405a5a4183fdea4003a496bbb8343e20a7adabcb2322a526c` |

This includes the requested anchor resolution: KBA profile pkey `10000736` identifies `오유진(吳侑珍)`, DOB `1998-06-11`; GoRatings profile ID 1315 has the same DOB. KBA pkey `20000056` identifies `조선진(趙善津)`, DOB `1970-04-18`; GoRatings ID 95 has the same DOB. These are DOB crosswalks, not assumptions based on similar spelling.

### Taiwan and Japanese professional sources

| Source / player | URL | Captured UTC | Body SHA-256 | Exact displayed span |
|---|---|---|---|---|
| Haifong Lin Shuyang | https://www.haifong.org/venue/115967099A3190B9705F17A83DFF23C5 | `2026-10-03T01:21:54.751025+00:00` | `75ad37cfe6b71b91c98fd266268337749abbfff249e194d66e23ae405a45dea9` | `林書陽 九段 歷史成績 冠軍數: 5冠 (含非公式戰1) 2026年度成績 (9/1更新) 台灣職業賽 8勝7負　勝率53.3% 世界賽 0勝0負　勝率0% 去年度總成績 17勝13負　勝率56.7% 簡介 1989年9月19日生，出生於臺灣臺中市。 2003年入段，2004年二段，2005年三段，2006年四段，2008年五段` |
| Kansai Kiin Yu Zhengqi | https://kansaikiin.jp/kisi_prof/yoseiki.html | `2026-10-03T01:25:03.671142+00:00` | `36c69755e0fafba5e3a018b9c81ff07e23236c90ab58d7e9ecc5982550e44f6a` | `余正麒｜プロ棋士｜一般財団法人関西棋院 ﻿ 施設・催事 大会・イベント 囲碁サロン 囲碁教室・さーくる こども囲碁道場 棋士・棋戦 プロ棋士 プロ棋戦 対局履歴検索 昇段基準 指導碁・棋力検定 棋士派遣 ネット利用 まいど！ 囲碁ネット中継 囲碁入門ゲーム 販売・各制度 通信販売 会員 支部 公認インストラクター 院生 囲碁文化継承基金 囲碁免状 関西棋院と` |
| Nihon Ki-in Cho Sunjin | https://www.nihonkiin.or.jp/player/htm/ki000187.html | `2026-10-03T01:21:54.749772+00:00` | `834f204384ebde9f89a234bcef15d6fae52dd995d9ee29dba4e5e2dd0d2ae245` | `趙　善津 | 棋士 | 囲碁の日本棋院 English(Information) MENU Language 検索 PCサイト ようこそ ゲスト さん 日本棋院IDマイページ ログイン 棋士コメント用ログイン 新規ID登録 (日本棋院IDマイページ) ホームページに設定する お知らせ 棋戦 棋士 大会・イベント 施設案 1970年（昭和45年）4月18日` |

Haifong supports the Taiwan candidate 林書陽 and gives a matching birth date with KBA’s Taiwan affiliation and GoRatings ID 569. Kansai Kiin supports the exact Japanese form and kana reading for 余正麒. Nihon Ki-in supports the Japanese kanji, kana reading, and Roman-letter field for 趙善津; KBA’s Japanese affiliation, DOB, and GoRatings ID 95 crosswalk to it.

## Identity crosswalk and gaps

[identity-crosswalk.pending.json](~/.local/share/kifu-name-audit/2026-10-03/raw-player-ranks89-100-primary-luna/identity-crosswalk.pending.json) binds each of the 12 supplied raw values to a GoRatings profile ID using matching birth dates and, where available, KBA and CWA IDs. GoRatings is a secondary index; it does not supply any of the 21 language-use decisions above.

The packet does not establish primary `tw` usage for the other eleven, primary `jp` usage for the other ten, or English-language names for any player. It does not establish primary `cn` usage for five rows or KBA Korean display for 刘小光. Those exact cells remain HOLD rather than inheriting a transliteration or a related language’s glyphs.

Research only: no live database read or write, no app-code change, no raw-value/game-scope approval, and no self-approval. Independent review remains outstanding.
