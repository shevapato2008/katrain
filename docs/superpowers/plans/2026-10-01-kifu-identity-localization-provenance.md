# 棋谱实体、十一语言译名与多来源 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让棋谱库以独立棋手和赛事 ID 管理身份，按设置中的十一种语言展示卡片、跨语言检索同一批棋谱，并在合并重复谱时保留所有数据来源。

**Architecture:** `kifu_albums` 保留原始 SGF 和原始字段，新增可空的黑白棋手及赛事实体引用；实体的别名与逐语言展示名分开存储。来源使用带唯一约束的关联表，API 对外返回 `sources: string[]`。先迁移和回填、再让读接口及前端消费，最后在测试库核对并以相同制品发布生产。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, PostgreSQL/SQLite, React/TypeScript, pytest, Vitest, Docker Compose.

---

## 已确认的要求与边界

- 用户已批准独立棋手/赛事 ID；不确定的译名查证维基百科、棋院网站等资料，保留链接、语言、审核状态，不猜测译名。
- 十一种设置语言：`en cn tw jp ko de es fr ru tr ua`。原始 SGF、原始姓名、原始赛事、`source_path` 不覆盖；未核实译名回退原文，并在翻译数据中记录缺口。
- 搜索完整别名“吴清源”与“Go Seigen”解析到同一棋手实体，得到相同棋谱 ID、总数和稳定排序；“吴清源杯”仍是赛事。切换显示语言不改变查询语义。
- 来源是**多值**。数据库以规范化关系维护，响应为数组；原有 `source` SGF 属性仍保留，不把它冒充数据集来源。`19x19`、`golaxy`、`CWI` 等来源须按可核实的路径/元数据分类，未能核实的标成 unknown 而非臆测为星阵。
- 精确内容去重可自动归并来源；同棋盘与全主线只生成疑似项，涉及日期、双方、摆子/让子、结果冲突时不得自动合并。存量重复不物理删行：以 `duplicate_of_id` 标记确定的主记录，旧详情仍可访问，列表/COUNT 排除副本。按批次记录变更前关系和内容校验值，支持只撤销本批棋谱改动。
- 生产库已达 173,025 条，迁移必须非破坏、可重复运行、批量提交；不能在 Web 启动时全表扫描或生成全部十一语言译文。不得枚举/读取 `data/kifu-album/`，只让既有导入脚本处理该目录。
- 这轮交付“十一语言展示能力＋可核实译名集＋可靠原文回退”，不得把尚未覆盖的译名宣称全部翻译完成。以现有棋谱中不同的棋手/赛事原始名称全集为分母，分别报告身份关联率、十一种语言的已核实译名率、原文回退和歧义数量。
- 用户已授权测试和正式云端部署；测试 `home-ubuntu` / `go.sailorvoyage.top`，正式 `ucloud-v100` / `modelstella.com`。先备份和演练迁移，测试通过再生产；不重启无关服务。

## 文件与职责

| 文件 | 职责 |
|---|---|
| `katrain/web/core/models_db.py` | 实体、别名、逐语言译名、来源与棋谱关联模型及重复指针 |
| `katrain/web/core/migrations.py`、`katrain/web/core/auth.py` | 带真实 FK/唯一约束的幂等非破坏 schema 升级；初始化顺序和漂移保护 |
| `katrain/web/kifu/identity.py`（新） | 名称规范化、实体/别名解析、批量展示名读取 |
| `katrain/web/kifu/provenance.py`（新） | 来源分类与关联、重复谱关联判据 |
| `scripts/backfill_kifu_catalog.py`（新） | 批量回填身份及来源，dry-run、断点续跑、覆盖率报告 |
| `scripts/import_kifu.py` | 新入库时维护实体和来源；重复时补来源，不静默丢弃 |
| `katrain/web/api/v1/endpoints/kifu.py` | `lang` 参数、多语言展示字段、来源数组、身份搜索 |
| `katrain/web/core/repository.py`、`katrain/web/core/remote_client.py` | board mode 的列表及详情 `lang` 透传；保留旧调用和 404/503 语义 |
| `katrain/web/ui/src/{types/kifu.ts,api/kifuApi.ts}` | 契约与请求语言 |
| `katrain/web/ui/src/{galaxy/pages/KifuLibraryPage.tsx,kiosk/pages/KifuPage.tsx}` | 卡片改用展示字段，语言变化时重取当前页 |
| `tests/web_ui/test_kifu_*.py`、相关 `*.test.ts(x)` | 聚焦身份、搜索、来源、语言切换、迁移与卡片回归 |
| `docs/resource/go-kifu-resources.md` | 数据口径、来源和译名覆盖率、运行手册 |

## Chunk 1：数据契约与迁移

### Task 1：实体和来源 schema（后端代理 A）

- [ ] 测试先行：空库建表、旧库无损加可空列、重复迁移幂等、SQLite/PG 方言差异。运行 `pytest tests/web_ui/test_kifu_catalog_schema.py -q`，先看到缺表/缺列失败。
- [ ] 棋手与赛事分别建实体、别名、逐语言译名表，均用真实 FK；译名各以 `(player_id, lang)` / `(event_id, lang)` 唯一，保存 `display_name`、`status`、`reference_url`、`reference_kind`、`verified_at`。同一规范化别名若对应不同实体，允许记录歧义但不得任取首项自动回填。旧表无逐语言证据的译名只能标 review。
- [ ] 为 `kifu_albums` 加 `black_player_id`、`white_player_id`、`event_id`、`duplicate_of_id` 可空 FK/索引；保留原始字段。建来源类型表、`kifu_album_sources`（`album_id/source_id/origin_path` 唯一）和按批次记录变更前关系/校验值的去重日志表；接口 `sources` 由 `DISTINCT source_key` 生成。
- [ ] 专门迁移必须在旧 PostgreSQL 库建立实际 FK 和唯一约束，而非只靠现有 `add_missing_columns`（它不会生成 REFERENCES）。SQLite 旧库要显式处理加 FK 的限制；若无法无损升级则拒绝启动，绝不重建丢数据。`kifu_albums` 及新增实体/关联/日志表一并加入 schema drift 的禁止重建集合。测试需验证真实约束和孤儿写入拒绝，重复执行幂等。运行聚焦测试、提交。

### Task 2：身份/来源回填和导入（后端代理 A，Task 1 后）

- [ ] 测试先行：`Go Seigen/吴清源` 关联、同名不同人冲突留待审、`CWI` 与原来源同时存在、重复导入幂等；相同主线但不同摆子或元数据矛盾不得自动合并；存量精确重复的旧 ID/详情继续有效且默认列表不重复。
- [ ] 迁移现有 `player_translations`、`tournament_translations` 五语言记录与 aliases，先区分其中的赛事、轮次、规则；轮次采用静态十一语言词条和数字模板，未知值回退原文，规则不建赛事实体。保留直播调用兼容；旧表整行 `source` 不等于每种语言都已核实，没有逐语言证据的值标 review。只给有可靠映射的棋谱设置实体 ID。导入/回填按固定批次提交并输出 inserted/linked/conflicts/unknown 数量，可 dry-run、可续跑。
- [ ] 对现有来源路径和 SGF 来源标签建立规则，区分数据集来源与 SGF 原文 `SO/US`；重复谱精确内容匹配时追加来源关联，同主线匹配只写候选报告，**废止旧导入器的主线重复静默跳过**。已导入的 CWI 单独包、完整包及旧的 Go_Seigen 均纳入回填；跳过重复的历史源文件需要重跑导入器/清单才能恢复第二来源，缺原文件时明确报告尚未补齐。
- [ ] 存量库精确内容重复时选定稳定主 ID，把副本 `duplicate_of_id` 指向主 ID，不删除副本；记录批次、双方原 ID、哈希、来源路径和改动前关联。列表和 COUNT 排除副本，旧详情仍可访问。支持按批次撤销且不触碰无关数据。
- [ ] 运行 `pytest tests/web_ui/test_kifu_identity.py tests/web_ui/test_kifu_provenance.py -q`，检查 dry-run 和重复执行，提交。

## Chunk 2：译名、检索与页面

### Task 3：十一语言译名种子与校验（独立代理 B，可与 Task 1 并行）

- [ ] 从 `kifu_albums` 中全部不同棋手/赛事原始名称建立统计清单，核对身份关联、歧义与原文回退；从现有数据库译名表和已知历史棋手建优先审核队列，不按棋谱行数乘十一。优先吴清源、道策、丈和、秀策、木谷实及列表高频赛事。
- [ ] 用维基百科对应语言条目、棋院官方人物/赛事页交叉校验不确定名称；每条非原文译名记录来源 URL、核实状态。姓名作为专有名优先采用已有约定写法，不能可靠核实时原文回退。静态卡片词条沿用现有 i18n，不在实体表重复存手数、胜负、日期等模板。
- [ ] 生成可重复导入的译名种子和覆盖率报告（每语言已核实/待审/原文回退，棋手与赛事分开）；测试：十一语言逐一验证语义、同一实体各语言回退、核实来源证据不空、未核实值不得标 verified。提交。

### Task 4：列表 API 与跨语言搜索（后端代理 A，Tasks 1–2 后）

- [ ] 测试先行：`q=吴清源` 与 `q=Go Seigen` 返回相同 ID/total/order；`吴清源杯` 按赛事查；切换 `lang` 只改展示不改集合；来源多值去重且稳定排序；分页 COUNT 不带 ORDER BY，20 条页不 N+1。
- [ ] `GET /api/v1/kifu/albums?lang=...` 及详情返回原字段和 `display_player_black/white`、`display_event`、`display_round_name`、`sources`。lang 限定十一种且缺译名回退原文；结果、段位仍由前端 formatter 本地化。完整且无歧义的实体别名优先用 ID 过滤，片段/歧义查询用多语言别名/原始搜索；查询与界面语言解耦。board mode 的 endpoint、dispatcher、`RemoteKifuRepository`、`RemoteAPIClient` 两条路径均传 lang，旧调用仍可不传且 404/503 语义不变。
- [ ] 批量查询当页所需译名与来源，保持既有日期倒序索引和快速 COUNT；运行 `pytest tests/web_ui/test_kifu_list.py tests/web_ui/test_kifu_localization.py -q`，提交。

### Task 5：Galaxy 与 RK3562 前端（独立代理 C，可在 API 契约冻结后并行）

- [ ] 测试先行：同一页 `cn→en→jp` 后姓名、赛事、轮次、结果/段位单位同步变化且搜索词、页码、选中卡不丢；并发旧语言响应不能覆盖新语言。来源展示为紧凑多标签，有多个来源时均可见，窄屏卡片不溢出。
- [ ] `KifuAPI.getAlbums/getAlbum` 传 `lang`；卡片显示 `display_*`，原始值只用于 SGF/编辑语义；监听 `useTranslation().lang` 重取并取消/忽略旧请求。Galaxy 与 kiosk 都接入；Galaxy 按选中 ID 更新 `selectedAlbum` 展示字段，页头不得残留旧语言。来源标签用本地 UI i18n 翻译。只做当前卡片必要视觉改动，目标视口各做一次真实运行时预览。
- [ ] 运行相关 Vitest 与 `npm run build`（UI 目录），提交。

## Chunk 3：集成、审核与发布

### Task 6：集成与数据核对（主代理）

- [ ] 合并独立代理改动后运行聚焦后端/前端测试；核对旧 API 消费者与 board mode 转发，核对详情与摆谱 SGF 原文未改变。
- [ ] 测试环境数据库备份；迁移前后行数、来源关联数、孤儿引用数；回填 dry-run 再实际执行，重复运行计数不变。抽查吴清源/Go Seigen 等价、十一种语言语义和回退、已核实的 CWI/另一来源多来源、赛事精确搜索。备份先在隔离库演练恢复。
- [ ] 按 `superpowers:requesting-code-review` 发独立整体代码审核；Critical/Important 必修复并复审。记录剩余待审计译名/疑似重复谱，不谎报全量完成。

### Task 7：测试与正式环境发布（主代理）

- [ ] 明确测试 `home-ubuntu` 和正式 `ucloud-v100` 当前提交、工作树、容器、数据库连接、可用备份/回滚点。先发布测试代码/迁移/回填，再验证 API、十一语言、搜索等价、页面；不触碰 RK3562 或无关 KataGo/Postgres 服务。
- [ ] 生产库做数据库备份及 schema/行数快照；只发布测试通过的同一 Git SHA 和静态资源，按生产 runbook 重建 Web（需数据批处理时单独运行），核对健康、行数、来源、语言与搜索。故障优先退旧 Web 镜像并保留向后兼容的新增 schema；数据错误只按本批次日志撤销棋谱改动。不得把在线整库恢复当作常规回滚，以免覆盖发布后正常用户写入。
- [ ] 输出测试/正式的提交 SHA、部署时间、健康检查、数据迁移计数、译名覆盖率、剩余疑似重复与核实缺口，供用户次日验收。

## 并行与审核约束

- Task 1 与 Task 3 可并行；Task 5 在 Task 4 API 契约写定后与后端实现并行。代理不得同时编辑同一文件；每项先写会失败的聚焦测试，再最小实现。主代理负责合并。
- 实施计划由独立 `gpt-6-astra`、`max` 推理代理审核**至多两轮**；对未给定取舍由该代理依据用户目标和当前代码给建议，主代理记录决定并执行。最终代码审核另行进行，审查问题修到通过。
- 写入生产数据前，先证明迁移可幂等、可回滚，且不把不确定的来源或译名标为已核实。
