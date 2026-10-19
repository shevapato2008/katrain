# OGS 教程书 TEST 接入实施计划

> **For agentic workers:** Use `superpowers:subagent-driven-development`. 用户明确授权独立任务并行开发；共享契约先冻结，修改文件互不重叠。Astra Max 计划审核／修改最多两轮，最终代码审核修复至通过。

**Goal:** 在现有 TEST 教程管理书籍列表中永久找到并打开一本「OGS 围棋入门与基础练习」，浏览全部已注册课程、来源截图和文字，并操作真实练习。

**Architecture:** 复用现有 TutorialBook → Chapter → Section → Figure 身份，以及后台登录、代理、棋盘与围棋规则。在 Go provider 中增加两张 OGS 专用表和只读管理接口，保存源版本、互动规则及语言；不把答案树硬塞入单线回放字段。前端用现有书籍下拉框进入专用课程视图，沿用已确认的三栏预览。

**Tech Stack:** 现有 FastAPI / SQLAlchemy / PostgreSQL / S3；React / Vite / TypeScript；本地固定版本 OGS TypeScript 导出与 Playwright 截图。

## 已确认范围和授权

- 用户已看过前端预览，明确要求开始正式接入，无需再次审批实施方案。沿用已确认主题、导航及三栏，保持右栏讲解／音频／视频空白。
- 本阶段只发布 TEST，入口仍为 `http://127.0.0.1:18012/admin`。不合并到生产 develop，不操作 ucloud-v100，不联系 OGS 或其他人。
- 固定官方源码 `1c1c2b82d027f7c307ab25886112cf0a6baf680a`、语言包版本 `5304fd731af8856a16d198d506111d61`。注册范围 7 章、248 课、3,551 步；未注册课程排除。
- 已清点 3,028 答案树题、520 单选题、3 个终局操作。2,131 题含多手分支，不能复用四样例的单手判题假装全量可用。
- 本次存全部32种语言文字。来源截图首先完整采集简体中文；语言切换时明确显示截图实际语言，其他语言截图没有采集就不声称已存在。所有截图必须实际从原站渲染采集。
- 保留 AGPL 原作者、许可证、源代码版本、修改说明及源文件获取方式；测试库标注商用授权范围待确认。没有取得额外商业许可，不把 TEST 接入登记为可对外商用发行。
- 答题尝试是本地临时状态，不增加终端学习记录体系；刷新清空，切换语言保留当前尝试，切换题目重置。

## 工作区与文件所有权

1. Go provider：`/Users/fan/.config/superpowers/worktrees/katrain-tutorial-module/ogs-tutorial-import-2026-10-19`，基于运行 TEST 的 `0bcc1d65f7c5f5ea7131e869b56718258b66b737`。
2. 管理前端：`/Users/fan/.config/superpowers/worktrees/smartbox-software/ogs-learning-preview-2026-10-19`，预览提交 `99bb6e06` 之后继续。
3. 计划、研究和交付报告：当前 `katrain-admin-console/superpowers/tracks/tutorial-database/`。
4. 大体积来源包／截图和含配置的运行证据保存在私有 `~/.local/share/smartbox-admin/ogs-integration-20261019/`，不提交凭据和用户会话。

## 冻结契约 v1

导出 bundle 为纯 JSON，不在服务器执行抓取的 JavaScript：

```text
schema_version: 1
source: {repository, commit, locale_version, license, license_text}
languages: [32 language codes]
chapters: [{id, number, title, translations:{locale:{title}}}]
lessons: [{id, chapter_id, order, course_code, route, title, step_count, first_page,
           translations:{locale:{title,subtext}}}]
steps: [{
  source_id: "ogs-learning:<original-route>:<1-based-step>", lesson_id, step,
  page: 1-based global source-step ordinal, source_url,
  size, initial_player: B|W, stones:{B:[[x,y]],W:[[x,y]]},
  letters:{"x,y":label}, shapes:{"x,y":shape}, viewport:null|{col,row,cols,rows},
  exercise:{kind:puzzle|choice|pass|remove|finish|unsupported,
    tree?:{point:null|[x,y],correct:bool,wrong:bool,children:[same node]},
    choices?:[{value,label_key}],correct_choice?:string,remove_targets?:[[x,y]]},
  translations:{locale:{title,instruction,choices?:{value:label},fallback?:bool}},
  raw_source:object, issues:[string],
  screenshot?:{path:relative-path,sha256,width,height,language}
}]
```

- 所有坐标为原始左上原点，不叠加 viewport 偏移。9/13/19路照实保留。
- 同色重复坐标在规范局面去重，原始坐标串仍保留（`bp-ko` 六题均存在此情况）；异色占点冲突拒绝，不静默选择颜色。
- 原站URL步号从0开始：`source_step_index=step-1`；内部 `step/page` 从1开始，截图核对实际步骤和初始局面。
- 原始路线保留，包括上游 `bl;3-skills-5` 的分号；内部 URL 参数用编码传递。标签、翻译和标题不作为主键。
- `tree.point=null` 用于根或 pass；根与 pass 的区分由节点位置决定。保留任意节点的正确／错误标志及原分支顺序。根 wrong 异常等记 issues，不能误报成功。
- 未识别到的配置／题型报 unsupported，来源数据仍可查看，操作关闭并说明原因；报告逐项列出，不能静默丢题。

接口均在现有鉴权下，通过原有 `/api/admin/providers/katrain` 代理：

```text
GET /api/admin/tutorials/books/{book_id}/ogs-course
  → {book_id,title,source,languages,chapters,lessons,counts,license_notice}
GET /api/admin/tutorials/books/{book_id}/ogs-steps/{page}?lang=zh-cn
  → {book_id,figure_id,...step fields,
     locale:{requested,effective,text},
     screenshot:null|{image_path,language,width,height}, screenshot_status}
GET /api/admin/tutorials/books/{book_id}/ogs-export
  → ZIP: per-step SGFs with branches, source index, source JSON and LICENSE
```

- 目录响应不携带全部题面／32词库；一步响应只含所选语言和原始证据，避免一次加载整本大 JSON。
- 媒体路径仅可为受控 `tutorial_assets/ogs-learn-to-play-go/...` 对象键，通过现有 assets 接口访问。无 Mac 本地路径／任意远程 URL。
- source `book_id` 与数据库 figure_id 严格分离，导出索引包含两者。

## Chunk 1：共享基础与全量来源导出

### Task 1 — 固定版本导出器与覆盖检查（来源 agent）

**Files (Go provider repo):**
- Create `scripts/ogs/export_course.mjs`, `scripts/ogs/README.md`
- Create `tests/web_ui/test_ogs_course_bundle.py` (Python consumer validation;与后端 agent 协调避免覆盖)
- Private output `~/.local/share/smartbox-admin/ogs-integration-20261019/course.json`

- [x] AST／受控本地转译固定源码，枚举 sections 注册列表及 pages 顺序。只允许已识别的配置、gettext/pgettext、JSX文本、选择题及三个已知终局行为；不在生产或带凭据的服务进程运行下载代码。
- [x] 导出全部棋子、符号、初始轮次、viewport、分支树、选项值及全部32语言。缺译保留英文回退及标记；不要把译文错误静默修正。
- [x] 原 config、正确／错误着手字符串、源文件／类名保留。记录 `bl3-joseki-1/Page04` 根 wrong、中文黑先／白先翻译疑点等来源异常。
- [x] 聚焦检查四个已知样例、3,028/520/3实际题型计数、完整多分支、默认9路和黑先、特殊分号路由。输出真实总数／哈希／unsupported 清单。
- [x] 导出时不下载或重新识别棋盘，不调用生成模型，不写数据库。

### Task 2 — DB身份、增量导入和受保护读取（后端 agent）

**Files (Go provider repo):**
- Create `katrain/web/tutorials/ogs_models.py`, `ogs_course.py`, `ogs_import.py`
- Create `katrain/web/admin/routers/tutorial_ogs.py`
- Modify `katrain/web/admin/app.py`（仅注册路由）
- Create `scripts/import_ogs_course.py`
- Create `tests/web_ui/test_ogs_course_import.py`, `test_admin_ogs_course.py`

- [x] 两张专用表：`tutorial_ogs_courses`（unique book_id、来源版本与目录）、`tutorial_ogs_steps`（unique course_id/source_id、course_id/page、figure_id）。只显式创建这两张新表；不运行全库 create_all 或替换同步。
- [x] 导入一本 `slug=ogs-learn-to-play-go`、category入门、subcategory网页交互教程；建立7章248节3551图和稳定来源映射。明确既有同slug但无OGS身份时拒绝接管。
- [x] 初始局面写现有严格 board_payload（序列无数据时标 needs_calibration，不自动人工审核）。互动树、翻译、原始证据留专表。讲解、音视频为空。
- [x] 默认 dry-run，只读零DDL。`--apply` 必须校验 TEST环境、显式数据库system ID／名称、S3 endpoint／bucket／publicbase。复用既有 `verify_apply_target`，不打印凭据。
- [x] 按来源ID幂等；重复同版本内容跳过，独立允许补齐缺失截图。已有人工编辑、审核、讲解、媒体绝不覆盖；来源内容变化单列冲突；截图变化不算课程内容冲突，只填缺失或同哈希，不替换已有不同哈希媒体。
- [x] 导入事务与唯一约束防并发重复；进程级／数据库事务锁限同一课程。输出来源→book/chapter/section/figure映射、所有步骤状态和异常。
- [x] 三个只读 API 校验book归属、页号、语言，401/404/503明确；英文回退透明；截图缺失显示 pending 而不是伪造图片。SGF逐步独立，保留各变化及正确／错误注释，不串整书。
- [x] 聚焦测试：新导入→重复零新增、来源冲突、人工成果保留、错误目标拒绝、无权限拒绝、外书页拒绝、语言回退、导出分支及pass。

## Chunk 2：真实书目入口和交互（前端 agent，与 Task2 并行）

### Task 3 — 从真实 API 浏览并作答

**Files (SmartBox repo):**
- Create `admin-console/ui/src/admin/tutorials/ogs-course/{types.ts,engine.ts,engine.test.ts,OgsCourse.tsx,OgsCourse.test.tsx}`
- Modify `admin-console/ui/src/admin/api/client.ts`（3接口）及聚焦测试
- Modify `admin-console/ui/src/admin/tutorials/workbench/WorkbenchContainer.tsx` 和聚焦测试
- Reuse 已确认 `ogs-preview.css`／来源放大、折叠和 `SGFBoard`，必要时把无业务数据的公共样式／组件移动到课程目录。

- [x] 先按冻结契约写测试。普通书不变；列表选中稳定OGS slug时加载课程 API，不调用旧 source-page/workbench 导致404。刷新／返回／再次选择书籍可重入，URL含 book/page/lang。
- [x] 7章节／课程／步骤选择、上一题／下一题、语言切换；错误／加载／重试与401沿现有路径。终局有明确 Pass／确认死子／Finish 操作。
- [x] 引擎保留完整历史，优先复用固定版本 OGS Goban/MoveTree 的规则和题目引擎，支持白先、多手、自动应手、pass和答案树终止标志；错误分支不能误成功。需要时现有 `buildTutorialReplay` 只承担已验证的局面计算。对未支持模式诚实禁用。
- [x] 原站自动应手从当前分支随机选择，并支持 strong isobranch 转置；叶节点按当前／祖先正确标志判断。先核对固定 Goban 契约后复用，不能简单固定第一分支而声称原站一致。静态marks属节点，新着手节点不自动继承。撤回／重试恢复全部状态，不污染已保存图面或人工审核。
- [x] 单选标签随语言变化，稳定value判题；移除死子保持来源局面，以选择覆盖显示，再按独立规则确认。源站静态初始局面不会因作答写回DB。
- [x] 左栏真实截图＋原文＋来源链接，截图语言显式显示；pending时保留原文和原站入口。右栏讲解／语音／视频空白，无生成按钮。退出课程可选普通书，二者不混用参数和请求。
- [x] 成品构建不依赖 VITE_OGS_PREVIEW，不包含四题Fixture作为课程数据。移除临时预览入口，保留旧文件仅作开发历史或删除不再使用Fixture。
- [x] 核对1920×1080和一个紧凑桌面、真实白先多手／提子／MCQ／终局／语言／再次进书；不重复大范围全站回归。

## Chunk 3：来源截图、TEST入库与交付（协调 agent）

### Task 4 — 可续跑来源截图

**Files:** Go provider `scripts/ogs/capture_pages.mjs`；私有截图及逐步manifest。

- [x] 使用固定清单逐步访问公开原站，浏览器语言zh-cn，截图棋盘及题卡实际渲染区域，保留图像尺寸、语言、原URL、SHA。含分号路线编码正确。
- [x] 有限并行、成功缓存、断点续跑和可读进度。只重试实际失败步骤；页面不是目标题面时不得保存成成功。
- [x] 上传现有S3受控哈希键。导入只写真实已上传对象，失败／未采集清单保留。不会把某题截图冒充其他题或其他语言。

### Task 5 — 有界独立审核、真实集成和发布

- [x] Astra Max 独立审计划，最多审核／修改两轮。独立文件所有权允许来源、后端、前端并行；共享契约变更先协调。
- [x] 开发后 Astra Max 先审核需求符合性，再代码质量，修复到通过。只审核本次接口、数据完整性、交互和TEST部署边界。
- [x] 先使用临时SQLite及少量真实源数据做后端完整流程；再全量dry-run。fresh核对 TEST env、DB system7596941912817897507 / katrain_db、S3 http://minio:9000 / tutorial-assets / https://go.sailorvoyage.top/media，目标不符停止写入。
- [x] 在测试服务进程配置中执行增量导入，复跑零新增；其他书籍与既有人工成果抽样指纹不变。记录counts而非以模型/导出成功替代UI验收。
- [x] 仅重建发布现有 `katrain-admin` 和 `smartbox-admin-admin-console-1`，保留环境、鉴权、端口、网络、卷和资源配置。沿用SSH隧道；不接生产，不重启DB／MinIO／引擎。记录原镜像供回滚。
- [x] 实际已部署 API 读取一本书、各题型、最后一页和含分号路线；资源可访问；后台书籍列表→OGS→普通书→OGS，刷新仍能打开。浏览器鉴权用现有用户会话，不伪造用户学习记录。
- [x] 输出真实覆盖报告（章节/课/步、题型、语言、截图、unsupported/源异常）、来源数据库映射、导出ZIP、源码提交、TEST直接链接。课程导入完成与截图／人工审核／商业发行授权分别报告。

## 当前状态

2026-10-19：已恢复并完成现有 TEST 后台接入、全量导入与真实页面验收。

- 计划 Astra Max 第一轮通过；来源／后端／截图采集、前端／发布脚本及最终截图签名组包修正均独立审核通过。
- 后端提交 `e8d31725f48a7f271d5509e171993623f9dee5dc`；前端提交 `aab2a4c7f51d383077d066ac3bb773038daad3de`。仅部署原有 TEST 两个服务，均 healthy；未合并 develop 或部署生产。
- 实际书籍 ID **80**，7章、248课、3,551步骤、32语言文字；全部3,551张简中原站截图严格校验并入现有S3。
- 全量 dry-run 无冲突；首次新增3,551图／截图；第二次 unchanged，图与截图均零新增。原有教材代表性内容指纹未变化。
- 真实后台现有教材列表可选择《OGS 围棋入门与基础练习》，支持返回普通书、再次进入及刷新；白先多手、自动应手、提子和撤回、选择题、停着／死子／终局、分号路由和末题均验收通过。
- 实际32语言 API、代表截图内容哈希及全书3,551份独立SGF导出通过；1920×1080和1440×900真实鉴权页面已留图。无业务接口mock。
- 人工审核0、讲解0、音频0、视频0；未将导入／模型结果记为人工审核。
- 直接入口：<http://127.0.0.1:18012/admin?book=80&page=1&lang=zh-cn>。沿用现有隧道与登录。
- 详情：[交付与视觉核对](ogs-integration-2026-10-19/README.md)、[验收报告](reports/ogs-test-integration-2026-10-19.json)、[来源映射](reports/ogs-source-db-mapping-2026-10-19.json)、[来源异常](reports/ogs-source-anomalies-2026-10-19.json)。
