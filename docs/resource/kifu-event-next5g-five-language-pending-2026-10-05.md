# 最后一项低频赛事名称（g，待独立审核）

2026-10-05；生产者 `/root/hide250_review_astra`，配置模型 `gpt-6-astra`。包 `/tmp/kifu-event-next5g-20261005`；无写库、无自签。剩余分配范围仅 ID 87，因此交付 1 个赛事、5 个语言单元。两环境各 5 pending，errors/write_errors/missing 均 0；4 conventional，1 translated。目标前像 PROD 10:40 UTC、TEST 10:42 UTC 均为空；复用不变 association/catalog，registry 沿用 `2026-10-02.5`。

| ID | cn | tw | jp | ko | en |
|---|---|---|---|---|---|
| 87 | 新体育杯 | 新體育杯 | 新体育杯戦 | 중국 신체육배† | New Sports Cup |

† 韩语为直接翻译，并加中国用于辨识；无当地惯用名断言。

- [国家体育总局／中国体育报回顾](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c22729544/content.html) 明示 2019 年时的四十年前首届新体育杯，首届冠军聂卫平，并说明这是中国最早的商业围棋杯赛，确认既有 ID 87 对应的旧赛事。
- [繁中围棋比赛页面](https://zh.wikipedia.org/zh-tw/围棋比赛) 的中国停办棋赛段实际使用新體育杯。
- [日文棋戦页面](https://ja.wikipedia.org/wiki/棋戦_(囲碁)) 中国一般棋战段实际使用新体育杯戦，列中国围棋协会、1979–1992 年。
- [英文职业围棋赛事列表](https://en.wikipedia.org/wiki/List_of_professional_Go_tournaments) 的中国停办赛事段实际使用 New Sports Cup。页面另有 New Physical Education Cup 文字；本包只采 New Sports Cup，不据此拆分或改变赛事身份。

正文、HTTP 200、SHA-256、摘录和 Wiki 修订版保存在 sources/ 与 research.pending.jsonl；国家体育总局原文为各 Wiki 用名的独立身份佐证。待主代理独立签署及目标库 dry-run。

PROD bundle file SHA-256: `36beb9cf2693fdc9d446c1b487ad8fb9c0038a4f042e271e35f8a7e1215bc8c6`。

TEST bundle file SHA-256: `2248e439f20960092b0e8fb109e31bc3e5695a03a61305c196ceeece98d3a811`。

