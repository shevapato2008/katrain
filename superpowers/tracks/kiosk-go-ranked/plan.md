# RK3562 围棋升降级对弈修复实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking. 本计划先由独立 gpt-6-astra（max）审核，最多两遍；领地判断开发须等用户确认 HTML 稿。

**Goal:** RK3562 升降级对弈可以在正式环境正常数子、提交完整结果，并清楚显示已结束但未送达的状态。

**Architecture:** 保持云端为段位、预约和结算权威。盒端仅在用户请求终局时获取私有裁判分数，并以同一局面原子写入终局；盒端产生自洽 SGF 和结构化成绩，耐久 outbox 发给正式 API。测试/正式切换同时处理认证地址、本机旧队列和旧预约，UCloud 保留专用 release/Compose 发布路径。

**Tech Stack:** Python/FastAPI、KataGo HTTP、SQLAlchemy/PostgreSQL/SQLite、React/TypeScript/Vitest、Docker Compose、systemd。

**当前状态（2026-09-25 16:35 CST）：** SGF、私有云端数子、待结算文案已开发并发布到 home、UCloud 和 RK3562；设备的围棋账号与结算地址已指向 UCloud。尚待用户在设备上重新登录并完成一盘**新局**，核对正式库实际落账。领地判断 HTML 已按现有星阵对弈图标调整，其余视觉修改和前后端开发仍等用户确认。

---

## Chunk 1: 部署与数据契约核查

### Task 1: 更新 home 测试部署到最新 develop

**Files/hosts:** `home-ubuntu:/home/fan/Repositories/katrain`, `docker-compose.yml`, `docker-compose.override.yml`。

- [ ] 记录当前 Git HEAD、容器镜像 ID、健康状态；确认无 tracked 修改且 untracked 文件不会被覆盖。
- [ ] 备份 `katrain_db`，核对备份能读取；记录磁盘余量。
- [ ] `git fetch origin develop` 后 `git merge --ff-only origin/develop`；确认 HEAD 包含 `fdf7fa39` 或更新的 `origin/develop`。
- [ ] 按 home 当前 Compose 构建并仅重建需要更新的 web/cron；保留测试环境的 `docker-compose.override.yml`，检查健康和 `/health`。

### Task 2: 更新 UCloud 正式发布到同一 develop 基线

**Files/hosts:** `release/ucloud-20260805`, `ucloud-v100:/opt/katrain/current`, `/etc/katrain/ucloud.env`（绝不输出密钥）。

- [ ] 核对 `/opt/katrain/current` 对应提交、release 分支独有文件、已有镜像与回滚目录。测量构建/发布峰值，若 16 GB 可用空间不足先停止生产构建。
- [ ] 备份正式 PostgreSQL 并确认备份有效；核查自动启动的 schema 迁移差异与两端六张表、约束、索引。
- [ ] 在独立工作树将最新 `origin/develop` 合入 UCloud release 分支，解决冲突，保留 `deploy/ucloud` 文件；跑发布相关聚焦测试和 Compose 配置检查。
- [ ] 以新不可变镜像和 release 目录更新 web/cron，保持 Postgres/MinIO/数据卷不变；上线前核对旧镜像兼容自动迁移后的 schema，不能兼容时准备数据库恢复与写入隔离；健康检查失败按已验证路径回滚。
- [ ] 记录实际合并提交、镜像 ID、服务健康和 schema 对照结果。

## Chunk 2: 三个故障的最小修复

### Task 3: 结算 SGF 与结构字段一致

**Files:** `katrain/web/server.py`（`_record_ai_game_locked`）；`tests/web_ui/test_ladder_settlement_sync.py` 或现有 ranked 端到端测试。

- [ ] 先补真实 ranked 结算测试：SGF 根缺 `PB/PW` 时当前实现应复现 422；测试须检查最终提交的 `PB/PW/RE/RU/SZ/KM` 与结构字段、冻结规则一致，并保留云端原有严格校验。
- [ ] 运行 `pytest -q tests/web_ui/test_ladder_settlement_sync.py -k 'sgf or settlement'`，确认新增用例因缺字段失败。
- [ ] 在构造 `data` 前从冻结的 ranked snapshot/座位名写 SGF 根属性，再生成 SGF；不可通过替换 SGF 字符串或放宽云端验证修复。
- [ ] 跑上述测试与 `pytest -q tests/web_ui/test_ai_ladder_ranked.py -k 'record or settlement'`，确认缺字段不再 422、伪造名字仍被拒。

### Task 4: 数子终局的私有裁判计算

**Files:** `katrain/web/interface.py`、`katrain/web/server.py`、`katrain/web/api/v1/endpoints/ai_ladder.py`、`katrain/web/core/remote_client.py`；`tests/test_play_ai_endgame.py`、`tests/web_ui/test_play_ai_endgame_api.py`、`tests/web_ui/test_ai_ladder_api.py`（若现有文件名不同，选最接近的既有 API 用例）。

- [ ] 用户已确认云端 AI 按中国规则判定、满 100 手可主动结束。UCloud 增加只接受当前预约、合法终局触发的专用裁判 API：主动数子须达到手数门槛；双 pass 则由服务端核对最后两手及待裁判状态，允许低于手数门槛。它用服务端 KataGo 分析上传局面，只返回目差/结果，不返回候选着、胜率、领地。盒端远端客户端调用它；网络/引擎失败返回可重试错误，不静默退回本机 1 visit 引擎。先实测 RK→正式 API 延迟与超时预算。
- [ ] 先写失败测试：ranked 101+ 手无缓存分数时仅数子动作可发云端裁判；主动数子未达到门槛、普通局中分析、换局/换手、并发终局仍被挡。双 pass 低于门槛时也走同一私有裁判并恰好结算一次；云端失败保留待裁判状态，不写“无结论”棋谱/账本，随后能重试。运行 `pytest -q tests/test_play_ai_endgame.py tests/web_ui/test_play_ai_endgame_api.py` 确认预期失败。
- [ ] 增加延迟裁判测试：计算在途、超时、局面变化后，HTTP `get_state` 和 WebSocket `game_update` 均不包含 score、winrate、候选着、ownership；只有成功原子终局后才出现最终结果。裁判计算使用引擎的私有回调/局面快照，不能在提交前写共享 `GameNode.analysis`。
- [ ] 实现数子与双 pass 的共同私有裁判入口：先捕获局、手、规则、预约，解锁等待云端返回，再用 `_commit_end_state` 校验同一局面后一次提交；失败保留终局前/待裁判状态及可重试入口。测试红后实施最小代码，不放宽其他 ranked 分析闸。
- [ ] 跑上述聚焦测试和 `pytest -q tests/web_ui/test_ai_ladder_ranked.py -k 'settlement or replay'`，确认唯一结算、失败不记账、局中无泄露。KataGo 估计的裁判性质需在前端终局文案中如实说明；若用户选精确数子，替换本任务的算法和断言后再实现。

### Task 5: 已结束但待结算的出口语义

**Files:** `katrain/web/ui/src/features/aiLadder/blockingCopy.ts`、`katrain/web/ui/src/kiosk/components/aiLadder/KioskAiLadderBlockingPanel.tsx`、相关 `.test.ts(x)`；必要时 `katrain/web/api/v1/endpoints/ai_ladder.py`。

- [ ] 先写失败测试，复现已结束 `pending_settlement` 仍显示“认输”，确认可重试/永久 422/已结算三态各有诚实反馈；运行 `cd katrain/web/ui && npm test -- --run src/features/aiLadder/blockingCopy.test.ts src/kiosk/pages/AiSetupPage.test.tsx`，确认预期失败。
- [ ] 维持一个价钱和唯一云端账本：正常状态先重试真实成绩；选择放弃时明确写“放弃未送达成绩，按一场负局了结”，二次确认说明云端可能以合成负局覆盖真实棋谱。沿用 `/end` 的唯一账本墓碑语义（技术字段 `remote_resign`），但 UI 不把已结束棋局说成再次认输。永久 422 时给出修复/放弃的实际出口。
- [ ] 先补 API/仓库并发测试：重试与放弃竞争，再重放旧 payload，只有一个该 game_id 的终局和一次计分；确认先成功结算时放弃返回既有收据，先放弃时重试被吸收，不产生第二局。
- [ ] 跑上述 UI 测试和 `pytest -q tests/web_ui/test_ai_ladder_ranked.py -k 'pending_settlement or remote_resign or replay'`，在 1024×600 真页面核对按钮文案、错误和触控。

## Chunk 3: 切换正式环境与验证

### Task 6: 将修复版发布到三端

**Files/hosts:** home `develop` 发布源、UCloud `release/ucloud-20260805` 发布源、RK `/opt/smartbox` 的 KaTrain 安装与 systemd 环境。

- [ ] Task 3–5 聚焦测试通过后记录修复提交；将修复合入 `develop`，确认 home fast-forward 到该提交并重建 web/cron，核对运行镜像包含该提交。
- [ ] 再将包含修复的 `develop` 合入 UCloud release，构建不可变 web 镜像，按 Task 2 的备份/兼容/健康/回滚门槛发布；核对正式运行版本包含同一修复提交。
- [ ] 在设备上备份原安装包和配置，安装同一修复版 KaTrain；暂不启动向正式地址的 worker，直到 Task 7 旧状态隔离完成。
- [ ] 按 home、UCloud、RK 三端记录 Git 提交/包版本、服务健康和两个关键 API 的合同测试结果，再进行 Task 7 的新局验收。

### Task 7: RK 身份与升降级权威同址切换

**Files/hosts:** RK3562 的服务环境配置、`KATRAIN_REMOTE_URL`、`BOX_IDENTITY_REMOTE_URL`；如配置模板确实需要修正，记录于本仓，不修改 `smartbox-software`。

- [ ] 只读检查实际设备服务环境、正式域名/路由、认证 token 的发行方和正式 API 可达性。确认 UCloud 账号对应同一主体。
- [ ] 在切换前停止 RK 的 KaTrain 会话、同步 worker 和 pending 恢复入口；做 SQLite 一致性备份。清点旧测试目标的 `pending`、`in_progress`、`waiting`、`failed` 队列和本地预约、终局会话；按环境归档或隔离所有旧记录，避免 `_recover_pending()` 再生旧结算。home 旧局和 7 条历史不迁移。
- [ ] 将设备身份 API 与 KaTrain 远端 API 一起指向 `https://modelstella.com`；只在 Task 6 修复版 RK 代码已经发布、旧队列隔离后重启服务，验证 token、`/api/v1/ai-ladder` 状态和新预约。重启后检查旧 game_id 不再新建同步项，旧相对路径也未向正式 API 发送。
- [ ] 新建一盘可控测试局并结束，确认正式 `ai_ladder_active_games` 释放、`user_games` 与 `ai_ladder_game_ledger` 有相同 game_id、`ai_ladder_profiles` 更新符合 counted 规则、本机队列为 synced。不得以旧局重新结算来验收。
- [ ] 检查测试域名的旧局仍保留且正式库未出现旧 game_id；回滚时也先停止服务、隔离正式目标的新队列和预约，防止正式 payload 发回测试库；记录最终 URL（不包含密钥）。

### Task 8: 其他棋类只读检查

**Files:** `smartbox-software/{chess,xiangqi,gomoku,setup-wizard,provisioning}/...`。

- [ ] 分别追踪国象、中国象棋、五子棋的盒端目标地址、身份服务、结算 outbox、云端权威库和部署配置；注明代码默认值与实际设备环境的区别。
- [ ] 只读查询可用的运行配置和关键请求日志，输出每种棋的目标环境、潜在混用和证据；不提交 smartbox 代码改动。

## Chunk 4: 领地判断设计，用户确认后才开发

### Task 9: 1024×600 HTML 设计稿

**Files:** `superpowers/tracks/kiosk-go-ranked/territory-preview.html`。

- [ ] 先用 `ui-ux-pro-max` 读取现有 RK 设计约束和 7 英寸触控原则，再用 `claude-design` 结合现有游戏页结构做独立 HTML 预览：入口、请求中、领地结果、每局 3 次余量、用尽/失败状态。
- [ ] 用 `ui-ux-pro-max` 再核对触控尺寸、层级、字体和对比度；在 1024×600 真实浏览器截图检查。
- [ ] 交付 HTML 和预览图，等待用户明确确认。确认前不做领地判断前后端代码。

### Task 10: 领地判断实现（待批准）

- [ ] 用户确认设计后再细化接口、服务端原子计数、每局最多 3 次、云端资源预算和前端状态测试。
- [ ] 按确认稿开发、集成、移除 Fixture，并在 RK 验收。

## 实施记录

| 日期 | 阶段 | 证据与结果 |
|---|---|---|
| 2026-09-25 | 现场排查 | 测试库 422、数子分析闸、已结束仍显示认输；两库六张升降级相关表列结构一致。 |
| 2026-09-25 | 计划审核 | 独立 gpt-6-astra max 审核两遍；修订旧 outbox/预约隔离、三端修复发布、双 pass 例外和并发验收。 |
| 2026-09-25 | home 更新 | `/home/fan/Repositories/katrain` fast-forward 到 `fdf7fa39`；备份 `katrain_db-20260925-pre-develop.dump` 190064110 字节并验证；web、cron 重建，`/api/v1/health` 200。 |
| 2026-09-25 | UCloud 更新 | 将 develop 合入专用 release，发布提交 `dfbea181`；先备份 `prod-20260925-pre-develop.dump` 189194374 字节，修复管理后台构建缺失 Logo 后生成不可变镜像 `sha256:d1cc3589…`。生产 web 健康，`KATRAIN_PREVIEW_MODE=0`；cron 源码无差异，原容器健康；Postgres、MinIO、KataGo 未重建。容量预检的 38.5 GB 是整机迁移门槛，本次仅替换 web，构建后仍有约 12 GB 空间。 |
| 2026-09-25 | 数据库 | home `katrain_db` 与 UCloud `katrain_prod_20260725` 的 `ai_ladder_profiles`、`ai_ladder_pending_games`、`ai_ladder_active_games`、`ai_ladder_game_ledger`、`user_games`、`sync_queue` 列名及类型逐项一致；本次未迁移任何历史成绩。 |
| 2026-09-25 | SGF 修复 | ranked 终局导出前按冻结座位和规则写入 `PB/PW/RE/RU/SZ/KM`；真实 box→cloud 测试先复现缺字段 422，修复后有效载荷 200、伪造名仍 422；最终 287 条聚焦 API 测试通过。已发布三端。 |
| 2026-09-25 | 待结算文案 | 已结束未送达时按钮和二次确认改为“放弃未送达成绩”，明确记负和真实棋谱无法补交；最终 97 条聚焦 UI 测试及 TypeScript 构建通过。已发布三端。 |
| 2026-09-25 | RK 备份 | 设备 KaTrain 服务保持停止；`/mnt/data/weiqi/backups/weiqi-web-20260925-pre-prod.db` 通过 SQLite integrity_check。旧队列 14 条（含永久 422），尚未隔离或切换。 |
| 2026-09-25 | 其他棋类只读检查 | RK 实际配置的 `lobby.sailorvoyage.top`、`ranked.sailorvoyage.top` 都指测试环境；国象经 setup-wizard ranked bridge，中国象棋默认使用同一 ranked origin，五子棋服务显式配置测试域名；`smartbox-software` 未修改。 |
| 2026-09-25 | 领地判断设计 | `territory-preview.html` 已含对弈中、请求中、结果、失败、三次用尽状态；在 1024×600 浏览器生成默认和结果截图。前后端仍待用户确认设计稿。 |
| 2026-09-25 | 裁判口径 | 用户确认云端 AI 中国规则判定，满 100 手可主动结束；不再等待算法选择。 |
| 2026-09-25 | 图标对齐 | 自由对弈及跨平台星阵对弈共用 `grid-nine` 领地、`squares-four` 数子、`hand-pointing` 停一手、`flag` 认输；HTML 预览已内联相同 SVG，并重新截取 1024×600 图。设计其余调整待用户说明。 |
| 2026-09-25 | 私有数子裁判 | 已接入冻结预约校验、中国规则 19 路云端 KataGo 500 visits 估分；主动数子满 100 实际手，双停可提前裁判，失败保留重试，终局前不写共享分析。287 条 API 测试、97 条聚焦 UI 测试及本机 Vite 构建通过；正式 KataGo 500 visits 实测 1.15 秒。Kivy 真窗口测试受本机窗口环境限制未能收集。已发布三端，待真实新局验收。 |
| 2026-09-25 | 最终发布 | 修复提交 `0a533a3eea6365aef3b2d8784fcc6ddb57b54134` 已推送 `origin/develop`。home fast-forward 至该提交并重建 web，健康 200。UCloud release 合并提交 `99c03cc9` 包含该提交；新镜像 `sha256:f60862fd…` 已发布，正式/本机健康 200，受保护数子接口未登录返回 401；保留旧 release `dfbea181` 与镜像用于回滚。发布核查 21 条测试通过，Postgres、MinIO、KataGo、cron 未重启。 |
| 2026-09-25 | RK 切换 | 设备原安装和 SQLite 已备份；从 `95999cb7` 安装至完整修复提交，73 个变更 Python 文件语法检查通过；严格 Box SSO 的 2D kiosk 构建验证通过，设备实际 `index.html` 与本地 SHA-256 一致。旧测试 outbox 14 条在备份后清空，本地预约/云端占位为 0。通过 systemd 专用 `go-prod-identity.env` 同时覆盖围棋与账号 API 为 `https://modelstella.com`，原始 `identity.env` 保留以通过装机校验。wizard、KaTrain、KataGo 均 active，设备健康 200、正式站可达 200。其他三棋的 `SMARTBOX_RANKED_ORIGIN` 仍为测试域名。 |
