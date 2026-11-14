# Restore report card deletion and repair legacy platform origin

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 两端每张可删除复盘卡恢复删除按钮；修正已确认的旧星阵对局platform空值，不改变棋谱或分析计费记录。

**Architecture:** 沿用现有确认弹窗与UserGamesAPI.delete，不新增删除接口。旧数据用有界、默认只读、可回滚的一次性脚本修正平台分类，继续既有云端权威列表路径，不在前端按名字猜来源。

**Tech Stack:** React/MUI/Kiosk CSS、Vitest、Python/SQLAlchemy、既有双云/RK发布工具。

## Chunk 1: 成因及边界

- 基线origin/develop 1bf7ba580，独立分支fix/report-delete-origin-20261115。
- 删除：a1be35252在紧凑卡片改造时删除卡片onDelete及按钮，把入口移到左侧选中预览。接口/确认逻辑仍在。4861c6200本轮排版沿用该状态。应恢复每卡可操作入口。
- 来源：a1be35252加入新局KTP+UserGame.platform，只给已有表加可空列；未实现旧计划Task3 scripts/backfill_user_game_platform.py。旧SGF无KTP，platform_games表也无关联证据。
- 实际只读DB：正式9局、测试2局，对弈source=play_ai/free且对手有[golaxy]，platform均NULL；不能把其它普通play_ai空值批量改成星阵。用户已要求旧星阵记录修正，本轮正核实这11局具体身份，确认前不写这些名称线索候选。
- 不变：充电进度只显示running、未运行卡全宽、左右棋手中间结果/手数、报价/计费/删除后端保护。导入/棋谱库/研究不可按星阵名字改类。

## Chunk 2: 两个实施任务

### Task A: 恢复两端卡片删除（独占UI）
Files: Galaxy ReportGameCard.tsx及test、Galaxy ReportsPage.tsx及test；Kiosk ReportsPage.tsx及test、personalGamesReviewed.css。
- [ ] 先加红测：每张可删除卡显示删除，点未选中卡删除传该卡id、不选中卡；弹窗取消不发DELETE，确认只删除目标；kifu_library保持保护隐藏。
- [ ] Galaxy恢复onDelete prop并接现有setDeleteTarget；IconButton放在卡内、选择点击区域之外，不嵌套button，至少44px触控。Kiosk用包裹选择button与同级删除button，卡内右侧预留空间；不恢复常驻进度空列。删除按钮别盖住棋手/结果。
- [ ] 移除左预览重复删除入口，保留原确认弹窗、后端拒绝提示及删除后选择/刷新逻辑。现有state/API权限不改。
- [ ] 聚焦测试与diffcheck，单独提交本人文件。沿用现有垃圾桶图标和危险操作样式，不进行新视觉设计或全状态截图矩阵。

### Task B: 有界历史修正工具（独占Python）
Files: scripts/backfill_user_game_platform.py、tests/web_ui/test_user_game_platform_backfill.py。
- [ ] 默认只读dry-run，必须指定user-id/明确game-id范围，产出manifest；仅played来源且platform空为候选；有明确KTP可确认，[golaxy]名字仅列待确认。无凭据/完整SGF导出。
- [ ] manifest含目标数据库/schema身份摘要、id/owner/source/game_type、旧platform、原updated_at、存储SGFhash和实际内容hash。apply接受已审manifest和明确确认ID；不从名字自动决定，不改其它未知记录。
- [ ] apply前把目标原值写0600备份且拒绝覆盖；事务锁行并比较快照，冲突则拒绝/回滚。只更新platform为golaxy，不重新POST、不改SGF/手数/结果/报告/账务，保留updated_at以免重排历史。重复应用不得重复改写。
- [ ] 明确rollback入口只恢复本批元数据；比对目标库、owner、SGFhash、来源、写后platform/updated_at，拒绝覆盖后续编辑。不要新增服务/表/通用审计框架。
- [ ] 最低充分测试：dryrun零写、确认范围apply/幂等、名字候选未确认拒绝、导入/非NULL不改、错误owner/跨库/陈旧行拒绝、rollback与编辑后拒绝。先红后绿，只提交本人文件。

## Chunk 3: 审核与发布

- [ ] 新计划独立Astra Max一轮审核，收敛必要修订；主代理规格核对后独立Astra Max代码审核至通过。保持本次范围。
- [ ] 两端聚焦测试/构建、一个代表性实际尺寸卡片预览；不为了验收删除用户真实对局。数据先dryrun，确认身份清单后备份apply，核验修改数/不变字段。
- [ ] fetch/合最新develop→pushfeature→合并pushdevelop→隔离parent更新vendor/katrain并pushmain；保留其它会话WIP。
- [ ] 先云端发布（沿用server-deploy完整配置保护），再无活动对局/无其它部署时标准app发布RK；不回滚另一会话的新代码。
- [ ] 核对两云及RK实际版本/入口。在线RK复盘直接读云端；另检查离线本机是否同一批历史记录，只在相同明确证据/确认范围修正，不改syncqueue或凭据。输出实际修正/未知/冲突数。
