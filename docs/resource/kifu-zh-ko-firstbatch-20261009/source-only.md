# Chinese-to-Korean first batch: source research only

Captured U-Go source responses at 2026-10-08T21:50:15Z. No generated candidate has been approved.

This short list excludes every owner in the 592 completed set and the ready16 conventional batch. Existing qualified `cn` and `en` anchors are re-used from the saved PROD pre-592 snapshot and need fresh post-592 binding before any candidate record is created.

| Owner | Han / published Latin | Split | Source disposition | Proposed profile output (review only) |
|---:|---|---|---|---|
| 5890 | 许俭颖 / Xu Jianying | `['xu']` + `['jian', 'ying']` | `zh_ko_candidate_source_ready_pending_contrary_checks` | 쉬젠잉 |
| 5101 | 李青海 / Li Qinghai | `['li']` + `['qing', 'hai']` | `hold_diaspora_language_basis` | 리칭하이 |
| 5498 | 王宏伟 / Wang Hongwei | `['wang']` + `['hong', 'wei']` | `known_community_ko_usage_requires_contrary_review` | 왕훙웨이 |
| 5739 | 翁子瑜 / Weng Ziyu | `['weng']` + `['zi', 'yu']` | `known_community_ko_usage_requires_contrary_review` | 웡쯔위 |

## Reading and finite syllables

Every Latin/Han pair is an actual row in the captured U-Go search response. Its linked person page lists citizenship `CHN`. The rows use ordinary, unambiguous Hanyu Pinyin spellings; no reading was inferred from the characters. The saved approved snapshot has the same current CN and EN strings and no qualified KO for these owners. The outputs below are rule calculations, not approved player names.

| Pinyin | Hangul | NIKL Table 5 basis |
|---|---|---|
| `hai` | 하이 | Table5: h=ㅎ + ai=아이; composed |
| `hong` | 훙 | Table5: h=ㅎ + ong represented in weng(ong) row; composed |
| `jian` | 젠 | Table5: j=ㅈ + yan(ian)=옌; composed |
| `li` | 리 | Table5: l=ㄹ + yi(i)=이; composed |
| `qing` | 칭 | Table5: q=ㅊ + ying(ing)=잉; composed |
| `wang` | 왕 | Table5 explicit wang(uang)=왕 |
| `wei` | 웨이 | Table5 wei(ui)=웨이 |
| `weng` | 웡 | Table5 explicit weng(ong)=웡(웅) |
| `xu` | 쉬 | Table5 x=ㅅ + yu(u)=위; composed |
| `ying` | 잉 | Table5 ying(ing)=잉 |
| `yu` | 위 | Table5 yu(u)=위 |
| `zi` | 쯔 | Table5 z[zi]=ㅉ[쯔] |

## Source notes

### 5890 — 许俭颖 / Xu Jianying

U-Go same row publishes Latin and Han name, CHN citizenship; 2025 national individual championship source confirms contemporary active China pro identity. No matching name in saved Daum Korean-player list. This is not a negative Korean-usage closure.

Captured same-person row: [U-Go query](https://db.u-go.net/?q=Xu+Jianying) and [U-Go player profile](https://db.u-go.net/500/). Raw bodies, fetch times, HTTP status and hashes are indexed in `capture-index.json`.


### 5101 — 李青海 / Li Qinghai

U-Go row publishes Han and Latin form and CHN citizenship; official Chinese association list includes him. Separate sources say he moved to Japan / lived in Japan, so current language and actual pronunciation need explicit resolution before automatic Mandarin generation. No matching name in saved Daum Korean-player list.

Captured same-person row: [U-Go query](https://db.u-go.net/?q=Li+Qinghai) and [U-Go player profile](https://db.u-go.net/1816/). Raw bodies, fetch times, HTTP status and hashes are indexed in `capture-index.json`.


### 5498 — 王宏伟 / Wang Hongwei

U-Go same row publishes Han and Latin name, CHN citizenship. Saved Daum community roster has exact Hangul/Han pair at line 893. Record the known reference usage. It is not a qualifying official name source by itself; any later generated review must preserve this positive hit and resolve it explicitly.

Captured same-person row: [U-Go query](https://db.u-go.net/?q=Wang+Hongwei) and [U-Go player profile](https://db.u-go.net/1923/). Raw bodies, fetch times, HTTP status and hashes are indexed in `capture-index.json`.

Daum body excerpt: `왕훙웨이` with `王宏伟`. The captured community body is [saved here](../kifu-next-highfreq20-source-only-2026-10-09/sources/daum-korean-player-list.body) (line 893; SHA-256 `e699546d23c8d9cbd0794f0041a23a48328277754c3050589329243fd1478a41`). This is a positive published usage finding and must not be described as a negative search result.

### 5739 — 翁子瑜 / Weng Ziyu

U-Go same row publishes Han and Latin name, CHN citizenship. Saved Daum community roster has exact Hangul/Han pair at line 925. Record the known reference usage. It is not a qualifying official name source by itself; any later generated review must preserve this positive hit and resolve it explicitly.

Captured same-person row: [U-Go query](https://db.u-go.net/?q=Weng+Ziyu) and [U-Go player profile](https://db.u-go.net/1942/). Raw bodies, fetch times, HTTP status and hashes are indexed in `capture-index.json`.

Daum body excerpt: `웡쯔위` with `翁子瑜`. The captured community body is [saved here](../kifu-next-highfreq20-source-only-2026-10-09/sources/daum-korean-player-list.body) (line 925; SHA-256 `e699546d23c8d9cbd0794f0041a23a48328277754c3050589329243fd1478a41`). This is a positive published usage finding and must not be described as a negative search result.

## Limits and next source gate

- `5890` is the cleanest current generated-profile research lead. It still needs finite contrary-name searches and fresh owner binding.
- `5101` is held: sources identify a mainland Chinese player who lived in Japan. Resolve current language and pronunciation before applying an automatic Mandarin profile.
- `5498` and `5739` have known community Korean/Han pairs. Keep those hits visible in finite contrary-name review; community-only evidence does not automatically qualify the conventional source gate.
- There are no candidate approvals, generated proof records, signatures, batch files, SQL changes, cloud operations, Git changes or deployment in this packet.
