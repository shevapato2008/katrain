# 全国围棋个人赛／团体赛：离线 exact 赛事计划

状态：**TEST / PROD 均已按修正冻结计划写入并直接复查**。两环境均通过最新共享 importer 的锁表 live dry-run，再依次写入个人赛 670 盘和团体赛 419 盘。脚本：[plan_kifu_china_national_events.py](../../scripts/plan_kifu_china_national_events.py)。每条计划固定 `[album_id, 原始 EV, 统一赛事类型, 年份届期键或 null, date_played]`。

| 类型 | raw | 棋局 | 年份届期 | 只连类型 | TEST 计划 SHA-256 | PROD 计划 SHA-256 |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| 中国全国围棋个人赛 | 87 | 670 | 359 | 311 | `9169afe627e0ce2cead75ecaa2e5d8d7c49027c707852b058b315eb570728691` | `bf0dd3e8458e0ff8e1bf6e2750257aac1921d021694d28636a2118306294d314` |
| 中国全国围棋团体赛 | 21 | 419 | 92 | 327 | `f1b5e3e5209cb512b38a31b10b95b8cf179d2f96f4498f7f7b506d1ac794fb9a` | `2b777c9a8078aad869c540c0b18f5dcc2406dd5197d78a43a7c92a4ea02b0e35` |

计划：[个人赛 TEST](kifu-china-national-individual-test-plan-2026-10-04.json.gz)、[个人赛 PROD](kifu-china-national-individual-prod-plan-2026-10-04.json.gz)、[团体赛 TEST](kifu-china-national-team-test-plan-2026-10-04.json.gz)、[团体赛 PROD](kifu-china-national-team-prod-plan-2026-10-04.json.gz)。两个类型的 album ID 集互不重叠；原始 EV 中的男子／女子组、轮次和冠名均原样保留，年份才作为届期键。裸 `个人赛`、`团体赛`、城市联赛与中国围甲均不在 exact raw 集合。

中国围棋协会[比赛规则第 25 条](https://wqwh.weiqi.org.cn/rules/)分列个人赛与团体赛；[国家体育赛事目录](https://www.sport.gov.cn/jts/n4998/c28363453/part/28363543.pdf)也将全国个人锦标赛和全国团体锦标赛分别列项。[野狐围棋历史资料](https://foxwq.com/news/listid/id/9931.html)记载 1998 年全国团体赛男子甲组赛制与此后的围甲联赛赛制不同，因此 `1996中国围棋团体赛男子甲组第10轮` 仍归团体赛。[Go4Go 1985 年棋谱页](https://www.go4go.net/go/games/tournament/133/240)将英文 `Chinese National Team Championships` 标为中国团体锦标赛，支持英文原值归组。

无年份的聚合 raw 只连类型：个人赛 `中国围棋全国个人赛` 279 盘跨 1976–1995 年；团体赛 `中国围棋团体赛` 243 盘及 `ChineseNationalTeamTournament` 69 盘跨多年。英文 raw 的 `(Women)`／`{Women}` 等女子组写法仍属团体赛，保留原文，不另建赛事类型。

带 2022 年的个人赛 raw 共 30 盘，日期在 2023 年 9 月。[2022 年竞赛规程及补充通知](https://www.foxwq.com/news/mlist/id/14602.html)确认这届比赛因疫情延期至 2023 年举办；本批遵循审慎届期规则，**30 盘只连个人赛类型**，不建立 2022 或 2023 年届期关联。其他年份仅在 raw 含唯一明确年份且日期同年时连 `year` 键。没有命中比赛说明类 raw；脚本显式排除此类标签。

聚焦离线测试 `tests/web_ui/test_plan_kifu_china_national_events.py`：4 passed。两环境 live exact raw 计数、逐 album 原文/日期/既有 FK 及类型/alias 冲突检查均通过。写后逐条核对 1,089 盘的原始 EV、日期、类型和届期，并确认两个 held album 的赛事 FK 均仍为空。

审查后团体赛冻结范围修正：整条 raw `2000年中国围棋团体赛`（album `68822`）暂不归组；聚合 raw `中国围棋团体赛` 仅排除 exact album `75789`。该 raw 的数据库全量计数仍固定为 `243`，实际计划纳入 `242` 盘，确保 live raw 计数检查不会误报。旧团体赛计划 SHA 已作废，未执行。

写入结果：两库个人赛类型 ID `72`，团体赛类型 ID `73`；新增 19 个年份届期键、5 条别名。本批增加 1,089 盘类型关联、451 盘届期关联。各库总盘数均 `173025`；TEST 类型关联 `81926`、PROD `82408`，届期关联均 `78650`，赛事类型均 `73`。这些是直接 FK 覆盖率，未将本批新增类型计作五语名称已完成。[执行及逐条验收记录](kifu-china-national-apply-record-2026-10-04.json)。
