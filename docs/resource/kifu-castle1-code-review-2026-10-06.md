# Castle1 独立代码与字面译法审查 — 2026-10-06

**结论：APPROVE。无阻塞项，五语候选保持现状。**

审查者：独立 GPT-6 Astra。范围为 main 工作树相对 `864c4964636ec15417cda2b78fdff7a4dce8493f` 的 castle1 profile、对应参数化测试及计划 Continuation 4，并核对 `/tmp/kifu-event-title-castle-game-20261006/` 的冻结研究材料。本报告不修改或签署研究、owner plan、候选或数据库批准记录。

## 代码与范围

- 生产差异仅新增固定 `castle1` profile：1 个 exact raw `Castle Game`、539 局。独立重算 raw-set canonical SHA-256，确为 `85b73b82847777deefd627ce637ee3870725385cdfd76916202b4c23574f5f7c`。
- 两库捕获均指向既有 pending raw owner **69273**；完整 occurrence 为 539，ID 与 manifest 一致，canonical ID SHA 均为 `e4f9ce173d8db4f242905ad16dda2d991bbfac5dcd7d1e3bfe9237cf1bc9af93`。捕获使用既有 `_scope_rows`，要求所有 direct albums 公开、非重复、NULL event FK、无 selected scope。五语名称前像为空，所捕获的身份名称/别名碰撞项为空。
- 既有固定集合/数量门禁、完整 owner 前像、scope、inventory/catalog、独立签署、外部哈希、锁、ledger 和 undo 均未改动；first24 默认与其他 profiles 未变。没有 reader、grammar、schema、FK 或身份创建改动。
- 新测试复用现有成功、错误 profile/raw/数量、scope CAS、apply 和 undo 参数化路径。root 已确认 **RED unknown profile → GREEN，12 项 owner 测试通过**。本次未重复运行该套件；指定代码 diff 的 `git diff --check` 通过。

## 五语字面译法

| 语言 | 结论 |
|---|---|
| cn | 保留 `御城棋` |
| tw | 保留 `御城棋` |
| jp | 保留 `御城碁` |
| ko | 保留 `오시로고` |
| en | 保留原文 `Castle Game` |

已渲染并目视核对 [British Go Journal 134](https://www.britgo.org/files/bgj/bgj134.pdf) 的 PDF 第 9 页／印刷第 8 页。T. Mark Hall 的《Styles of Play》正文在 GoGoD 历史围棋语境中明确使用 `Castle Game series`，可支持 exact core `Castle Game`。本地 PDF 字节 SHA `4224461b653af7d34ab6346c75666383b1dc04652a4bbc5a28f65e0eb5815438` 与研究记录一致。

已读 [日本棋院历史页](https://www.nihonkiin.or.jp/teach/gakkouigo/history.html) 的保存正文，实际出现 `御城碁`，并以江户城内举行的正式围棋对局解释其含义。保存 HTML SHA `b86bdac2365de81c489d149492fddb0ba1ee4d8a473b11c71284e896266ceb52` 已独立核实。中文用“棋”表达同一围棋概念，简繁两语保持 `御城棋` 合理。

韩文 `오시로고` 可直接保留。[TYGEM 韩文专栏](https://www.tygem.com/column/pastcolumn/viewpage.php?gubun=C006&pagec=2&seq=492) 实际使用 `오시로고(御城棋)` 并解释其围棋含义，为此次有限词义复核提供直接佐证。无需替换为新造的韩文描述，也无需把这次补充词义核对扩张为新的研究流程。

以上结论适用于这个 raw 字符串的历史围棋显示语义。材料没有把 539 局绑定为同一届、同一具体赛事身份；继续采用 `translated_from_original` / `literal_event_title`，不增加 identity link，也不将这些译法标成五语官方专名。

## 最小充分验证

独立纯读取检查通过：两库 539 IDs、scope/owner 状态及哈希与 manifest 一致；两份实际来源文件 SHA 正确；五条 pending research 均通过现有纯字面标题 validator；完整 `name-registry.json` 可由 `load_registry` 加载。既有正式 prepare/dry-run/apply 的当前状态与碰撞门禁继续适用。

本轮未连接数据库、SSH、改动代码或签署数据审批；仅写本独立审查报告。
