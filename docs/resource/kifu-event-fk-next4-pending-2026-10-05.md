# 四类赛事有限 FK 关联待审包（2026-10-05）

Producer：`/root/hide250_review_astra`（配置 `gpt-6-astra`）。全部 **pending**；未独立签署、未 dry/apply，数据库写入 0。

| 现有赛事 ID | 赛事 | 候选 | 提议关联 | 本轮排除 |
|---|---|---:|---:|---:|
| 40 | 日本龙星战 | 424 | 424 | 0 |
| 53 | 台湾棋王赛 | 328 | 328 | 0 |
| 34 | 日本女子名人战 | 254 | 253 | 1 |
| 49 | 韩国名人战 | 159 | 112 | 47 |
| 合计 | | 1165 | **1117** | **48** |

包根目录：`/tmp/kifu-event-fk-next4-20261005/`，每个 ID 各一目录。各包独立提供 `README.md`、`manifest.json`、`scope.json`、`excluded.json`、官方原始正文、两库 `plan.json`、完整 `expected-after.json.gz`、只读检查及回滚 dry 的 payload、有限执行器。

## 身份依据与边界

- **日本龙星战**：424 局 raw 和 SGF GN 均明确日本龙星战；[日本棋院竜星戦官方档案](https://www.nihonkiin.or.jp/match/ryusei/022.html)证明同一日本赛事类型。13 局 GN 的届次、轮次或用词差异保持原样，例如 raw 第22期与另一 GN 第33期。
- **台湾棋王赛**：328 局均明确台湾棋王赛/台湾棋王战，日期在2008年以后。[海峰棋院历届棋王赛记录](https://www.haifong.org/news/content/5F8593D9A30A1F7EC7DD05EFF299C791)确认2008年首届现代系列。51 局 GN 字差主要为繁简、赛/战、回/轮；108762 缺届次的 raw 保持不动。
- **日本女子名人战**：[日本棋院女流名人戦历代记录](https://www.nihonkiin.or.jp/match/fmeijin/archive.html)为身份锚点。**80407 排除**：第二 GN/GC 明确写日本女子本因坊战，与第一 GN/album.event 实质冲突。
- **韩国名人战**：[韩国棋院官方档案](https://www.baduk.or.kr/game/game_view.asp?cmpt_code=1105)确认赛事及1968年首届。112 局中105局 raw 明确韩国名人，另7局 `7thMyeonginLeague` 为1972–1975年韩国棋手对局，6局第二 GN 直接写韩国名人；沿用已批准英文 `Myeongin` 名称与既有 alias。148043 的第7/第5届差异不改写。

韩国候选排除47局：42局 `Women/Female Myeongin` 为不同女子赛事；39168 第二 GN/GC 为日本1971春季大手合；172930 为1960年日本棋手对局，早于韩国名人首届；39241/39293/98256 三局特别对局暂留待定，本包未证明它们应作为常规名人赛事关联。未把排除项改归其他赛事。

官方正文均复用已批准赛事五语名称的 retained HTTP200 原始 bytes；逐份重核 SHA，与当前数据库 evidence 正证一致，不重复研究已批准名称。这里复用既有 type-only 政策，不声称已逐局核对外部对阵表。

## 最低充分验证

1. TEST/PROD 各一次只读捕获限定1165候选，未重抓全库；四个 ID/canonical 绑定及各五个当前 verified 名称、独立 approved evidence 均成立。
2. 1117 拟关联记录分别与两库 post123 冻结 inventory 的 association 和 source-link 前像相符；当前 event/edition FK、duplicate 和隐藏标记均为空。两库的棋手 FK 原本有差别，分别完整冻结保留；目标 SGF 内容两库一致。
3. 旧 HOLD 联集4768全部排除，隐藏250及韩国未来之星旧 HOLD 均未解除。SGF 全根属性已解析并检查赛事冲突，逐局 hash 与原始 SGF 在包内保留。
4. 四个单赛事包 × 两环境共8次真实数据库 **read-only check 全通过**。执行器只替换已用 type123 工具的固定 scope、计数与格式名；原有完整前像 CAS、表锁、后像比较和独立批准 plan SHA 的 apply 要求保持。

## 下一步

Root 独立审阅各包原 SGF、官方身份和排除原因，按每包 TEST dry/apply/verify 后 PROD dry/apply/verify 执行。每个 plan 的完整 SHA 在对应 `manifest.json`；生产者未填写批准字段。

本轮唯一提议写入是 `kifu_albums.event_id`；届次、轮次、原文、SGF、棋手 FK、staging 和隐藏状态保持。FK 写入会改变名称 importer 的全库快照 hash，宜在当前名称包入库完成后集中执行，再按既有方式捕获一次新基线；不得放松 snapshot gate。
