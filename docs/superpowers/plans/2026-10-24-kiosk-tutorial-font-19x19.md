# Kiosk 教程字体与 19 路内容实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 教程沿用围棋已有字体/字号设置；为语义与答案可保持的小盘训练和 OGS 教程提供可追溯的 19 路派生内容，原数据库与 Galaxy 默认读取保持原样，并将审核后的 published develop 部署 RK3562。

**Architecture:** 一个纯 Python 读取时派生模块承接两种坐标载荷，采用来源语义许可与全分支棋规/边界等价双重资格检查。显式 `board_variant=kiosk19` 只影响 Kiosk 请求，板端在代理返回后派生，因此这次 RK 交付不依赖云端部署。前端继续使用既有判题和实体盘状态机，派生完成后它们只接收一致的 19 路初始局面、全部答案与标记；原题保留明确的屏幕练习理由。

**Tech Stack:** Python/FastAPI，既有 SGFNode，React/TypeScript，现有 CSS 字体变量/DOM 字号扫描，pytest/Vitest，1024×600 浏览器与 RK3562。

---

## Chunk 1: 基线、契约及范围

- [x] 已 fetch `origin/develop`、`origin/fix/kiosk-ui-debug`；主树 debug 安全 fast-forward 到 `faacf2597c0904edfbb56c016b7f7d496abaf03d`。远端 debug 为祖先。本次隔离树 `fix/kiosk-tutorial-font-19x19-20261024` 同 base。不移动别人 checkout 的 develop。
- [x] 用户未跟踪报告保留：hourly 报告与新 develop 受跟踪文件字节完全相同，personal review 报告原样未跟踪。不包含未批准的 play-home-icon 功能分支或复盘原型。
- [x] 后端基线：`./.venv/bin/python -m pytest -q tests/web_ui/test_ogs_public_course.py tests/web_ui/test_board_tutorial_proxy.py` → 20 passed。
- [x] RK 真实偏好 `kaiti/large`，当前 1024×600 OGS 章节页的文字 computed font 却为固定 SmartBox Kai。文字已有 `data-kiosk-base-size`，字号公共机制已覆盖新增 HTML；需真实核对切换，不造新机制。
- [x] 来源只读盘点：训练题 21072（19路20193，小盘879：4路190、5路2、7路12、8路25、9路534、11路12、12路2、13路102）；OGS3551（19路2860、9路689、13路2）。本次新课程指 pinned OGS；不扩大到 TEST 的其他未发布教材。源数据只读导出 `/tmp/kiosk-small-content-20261024.json`，不可覆盖源库。

### 对外契约（实现前固定）

原始请求默认响应不变。训练题 detail 和 OGS step 接受可选 `board_variant=kiosk19`。派生成功时返回现有字段的完整19路版本，ID/课程页/进度身份仍为原ID；增加 `board_variant` 元信息：`status`（original/adapted/unavailable）、`source_size`、`target_size`、`policy_version`、`source_sha256`、`offset:[dx,dy]`、中文 `reason`。unavailable 返回完整原题和明确原因，不冒充19路。未知来源/校验失败不能以500破坏原题。

板端 proxy 在远端原始响应之后执行相同函数，不要求云端支持新参数。完整部署的 server endpoint 支持参数；Galaxy省略参数不会派生。Kiosk训练hook新增可选读取variant选项，由Kiosk页传入，Galaxy调用保持默认。OGS只读API提供Kiosk专用variant参数，不能让管理端导出/源码路径变成派生。

### 资格与转换权威

1. 先识别原生19路并原样返回。小盘派生不写数据库、不增加重复进度、不修改源码下载/SGF导出。
2. 仅**平移**（不旋转/镜像）到19路：每轴固定选择保留原左/右、上/下某一侧边，offset为0或19-N；每个源点、所有分支落子/节点setup/移除、标记/视窗均同一变换。依赖相对方向的文字因此不被翻转。所有未知坐标性质/矩形/越界数据明确拒绝，不能静默漏转。若支持压缩SGF点必须展开再变换。
3. 几何资格：所有初始、节点设置、答案分支、标记和目标点必须在被移走边界内有空白缓冲；同时需要相对两边或四边的内容拒绝。每条答案分支逐步回放原版和派生版，比较占用、提子集合、每个棋块气集合、合法性、轮次及劫重复关系；分支终点也检查。几何只能证明已给定局面/答案的棋规等价，不能单独证明题面语义。
4. 语义资格另有**固定来源摘要的可审核清单**：OGS逐课审查中英instruction/choices/目标，允许局部气、提吃、连接、断、做眼等有几何证明的局部题；全盘数目/胜负/终局、盘宽教学、征子/引征、劫/劫材、依赖自然语言绝对坐标等保留原题。训练题按实际SGF题面和变化审查候选，官子/全盘计分/征子/劫/无法确认局部目标的题不得只凭类别或关键词认证。清单记录 source ID、源摘要、允许或原因；未知/摘要变化默认保留。关键词只能用于发现复核风险，不能作为安全的正向依据。
5. 不以不能全局证明为由全跳过。至少实际纳入有可复核局部目标的中央、角、边与多分支题；例如92643、129993、218387、124386应调查是否满足全分支证明。108018四边眼形、122131/123086/213404官子计目保持原样。所有实际结果由审计脚本输出ID/路数/理由/派生摘要/分支计数，交付精确计数与清单。
6. OGS派生显示完整19路 `viewport=null`（屏幕和实体坐标同一权威）；原始 viewport/截图保留在原读取，不把源截图当19路派生。训练页已有完整盘渲染。派生标记、正确/错误分支、先手、说明和对应原始来源不丢失。

## Chunk 2: 独立实现切片

### R1 修订：以下具体约束优先于上面的宽泛草案

- **可见来源摘要**：OGS用公开代理能看到的source_id/lesson_id/step/page/source_url/size/initial_player/stones/letters/shapes/viewport/exercise规范JSON摘要，不含环境不同的book_id/figure_id；另独立校验当前effective locale的title/instruction/choices摘要。不可拿DB完整payload hash在RK比对。训练题摘要覆盖SGF及detail ID/size/setup/hint/category。Galaxy默认响应不能新增null metadata字段。
- **实际格式边界**：879源SGF实际根属性只有GM/FF/CA/AP/SZ/GN/AN/SO/GC/C/AB/AW/PL，非根只有B/W/C，无pass、压缩点或节点setup。首版只支持这个实际集合；未知属性、压缩点、pass、节点setup、矩形、越界数据保留原题并明确原因，不建通用SGF转换平台。OGS覆盖实际puzzle/choice；现有pass/remove/finish属于整盘终局课程，保留。
- **正向局部证书**：category/关键词仅辅助审查，不能作允许依据。直接提吃需固定初始对方目标棋块，所有正确叶完整提掉目标、失败叶未达同目标，记录每叶及全程邻接/气；先覆盖一步提吃，再覆盖已审核短序列。解除打吃需固定初始己方一气棋块，正确叶存活且至少两气、失败叶仍一气或被提；仅证明解除当前打吃，不宣称活棋或征子成立。计气/棋块/打吃选择题需固定问题目标并独立重算结果与choice键；不能拿choice默认initial_player推断正文指定的行棋方。连接需固定两个源分量并验证正确叶同组；切断需固定所问两块/连接点。两眼、封闭角空、对杀、枷等必须额外局部目标证书，否则写“本次未能确认局部目标”，与“边界无法保持/全盘必须原盘”区别。中英轮到方冲突的OGS内容保留原文，当前中文不派生。每个接受source记hash、目标、证书族、逐叶统计和共享审查说明；有限树证书不宣称穷尽全局所有可行下法。至少检查调查报告的中央/边角/多分支代表，不能用四个手选样例替代实际候选覆盖。
- **训练预览一致**：Task3还修改`katrain/web/ui/src/kiosk/pages/TsumegoUnitListPage.tsx`，选中题preview也显式请求同一variant，不能缓存原小盘而做题却显示19。
- **撤回与延迟应手**：Task3修复普通undo对stones.slice的错误，改由原始初始局面+剩余moveHistory重放捕获，恢复被提棋子；撤回、重试、换题取消尚未执行的300ms自动应手。聚焦测试捕获后撤回与延迟期间撤回，不泛化重写hook。
- **前端先可审后接API**：Task3先在隔离测试/临时preview fixture展示同题原盘、19派生以及明确留原的一题，含标记、分支、复位和理由；1024×600参考/实现/并排/叠加/差异交主session。沿现有版式无新视觉选择时，按用户已授权方向推进；确有视觉选择才需用户确认。完成具体可审预览后再接真实API，不把fixture放进生产。
- **RK资源清单**：Task6除了完整受控Python和同源full/strict static，显式打包`katrain/web/content/kiosk19_policy.json`，全部同一published SHA与哈希校验；不能复用仅.py旧打包而漏policy。启动前后核实policy加载及真实代表API。

### Task 1: 教程字体与字号（可与内容纯函数并行）

**Files:** Modify `katrain/web/ui/src/kiosk/tutorial/ogs-course.css`，必要时 `katrain/web/ui/src/kiosk/tutorial/OgsCourseBoard.tsx`；focused test in `katrain/web/ui/src/kiosk/pages/OgsCoursePages.test.tsx` 或现有字体浏览器检查。使用 @ui-ux-pro-max 与既有 `tokens.css`/`theme.ts`，无新页面设计系统。

- [ ] 以现有1024×600真实截图/新OGS已批准参考为基准，记录固定字体覆盖点，正文/标题/按钮/错误加载/来源弹层改走 `var(--font-sans)` / `var(--font-mono)`；品牌与棋盘坐标保留既有专用字体及几何。
- [ ] 沿用字号扫描；若实测已支持无需改公共扫描。SVG中文标记继承正确CJK，但棋盘坐标、图形、字母的固定显示依既有规则。
- [ ] 以真实React运行时的楷体large与另一字体small核查主页/章节代表页、长题干、来源弹层；核对字体实际渲染face、22/18/28基准和2/4px减量、触控几何与文字滚动不溢出。各代表画面保存before/after/side-by-side/overlay。
- [ ] 将具体预览交总负责人，沿用用户已确认的现有设计；无布局改造时不引入冗余许可。若产生新布局选择需主session给用户审阅后进入对应后端切片。
- [ ] focused Vitest与一次实际预览，提交该slice。

### Task 2: 共享派生纯函数与资格清单

**Files:** Create `katrain/web/content/board_variants.py`（及package init），Create `katrain/web/content/kiosk19_policy.json`，Create `scripts/audit_kiosk_board_variants.py`，Test `tests/web_ui/test_board_variants.py`。

- [ ] 先写并运行失败测试：不改源对象；中央/四角/边/多分支映射；全部SGF点属性/压缩点/节点setup；all-branches提子与气等价；被移动边上的石/答案/标记、四边/非法树/未知语义/摘要变更拒绝；原生19不变。
- [ ] 实现最小纯函数 `adapt_tsumego_detail(detail)` / `adapt_ogs_step(step)`，共享验证、摘要与metadata；原始响应不受副作用。任何失败均原题+原因。
- [ ] 在实际导出源上运行只读审计，审查候选语义并写版本化allowlist；输出全体小盘接受/排除机器清单（UTF-8 JSON/CSV，包含摘要）。审计不联网、不调LLM、不改数据。
- [ ] 以已有Go规则实现/独立预期局面验证所选代表答案的正确与错误路径，而非仅比对实现自身。提交pure foundation。

### Task 3: Kiosk读取契约与完整旅程

**Files:** Modify `katrain/web/api/v1/endpoints/{tsumego,board,tutorials}.py`，Modify `katrain/web/ui/src/hooks/useTsumegoProblem.ts`，Modify `katrain/web/ui/src/kiosk/pages/{TsumegoProblemPage,OgsCourseExercisePage}.tsx`，Modify `katrain/web/ui/src/api/tutorialApi.ts`，Modify `katrain/web/ui/src/types/ogsCourse.ts`。Test existing board proxy/OGS API/tsumego hook/page tests，add only relevant cases。

- [ ] 在已固定的契约下先写失败API测试：原始读取/源码导出不变，云server显式variant可用，盒端代理不把参数转发给旧云、在原始结果后适配；无资格原题诚实呈现。
- [ ] 接入纯函数及metadata，Pydantic响应不得过滤metadata。Kiosk明确请求variant，统一选可用19路；错误/取消/下一题不泄漏旧状态。非适配题保留屏幕操作并显示“原N路题：原因”，实体按钮继续不可用。
- [ ] 按真实完整19路载荷核对source top-left → training bottom-left → vision row/col转换；初始摆局、所有应手/提子、错子恢复、撤回、重试/直接复位、终局等待最终实体一致均复用已有机器。
- [ ] focused tests覆盖至少一个转换后题完整判题/复位以及一个不可转换题；OGS多步自动应手与提子最终收敛。不得为验收重新采集或改动实体盘。
- [ ] 实际本机1024×600显示19路与原始小盘并排、叠加/差异对照，确认提示、标记、按钮、长文可读；fixture只存在测试/preview，不残留业务生产数据。

## Chunk 3: 独立审核、发布与验收

### Task 4: 独立审核与聚焦验证

- [ ] 实施前由独立 `gpt-6-astra` / `max` 审查本计划与调查报告（fork none，完整上下文），最多两轮修改。
- [ ] 实现后独立 Astra Max 先按spec核对，再代码质量/真实视觉审核，可一次任务依次两阶段报告；修正所有must-fix再复核至通过。
- [ ] 后端聚焦：`./.venv/bin/python -m pytest -q tests/web_ui/test_board_variants.py tests/web_ui/test_ogs_public_course.py tests/web_ui/test_board_tutorial_proxy.py`（加实际tsumego现有相关文件）。前端 `npm test -- --run` 指定OGS/tsumego/physical相关test文件；source audit应无“批准但验证失败”。
- [ ] `npm run build` 与 `npm run build:smartbox-kiosk-2d` 同源构建并通过strict边界，不跑无关全量回归。

### Task 5: 安全集成和推送

- [ ] fetch最新origin/develop，合入feature、解冲突、重跑受影响测试；commit/push feature。远端develop竞态需再次fetch/retry，禁止force。
- [ ] 用独立integration worktree将feature合入远端develop并push，不移动他人checkout的本地develop。核对远端published SHA。
- [ ] 父仓 `/Users/fan/Repositories/smartbox-software` 在隔离工作树从最新origin/main更新唯一 `vendor/katrain` gitlink到published develop，commit/push并核对；保留用户父树其他变化。

### Task 6: RK3562定向发布

**Reference:** @server-deploy 的范围约束；实际采用上一发布 `/mnt/data/smartbox-deployments/20261024-kiosk-player-cards-db32efe06/` 的受控runtime+full/strict static办法，不能调用provision所有棋类脚本。

- [ ] 发布前只读核实当前页面、进程 `KATRAIN_BUILD_SHA`、真实源码与静态哈希、service/env、磁盘与旧marker；与最近发布竞态核对。根仅约2G，备份与候选放 `/mnt/data`。
- [ ] 从干净published develop导出完整受控运行Python和同源full/strict static，清单逐项SHA256。在线SQLite快照、旧源码/static/markers/service环境备份与保护配置/身份/模型/标定哈希。
- [ ] 只停起 `smartbox-katrain.service`；保留用户数据库/配置、标定、识别、其他棋类和当前实体盘。完整更新教程所需源代码而不回退已有新OGS/旧chunk恢复等更新。
- [ ] 核对manifest全部文件、实际PID环境版本、health/API 200、served入口/chunk，API请求真实小盘原始与19派生及排除例。原数据库数据哈希/统计不变；保护文件哈希一致。
- [ ] 重载原页面并恢复原URL；若SSO失效仅真实“盒子主页→围棋tile”恢复既有身份，不读/注入cookies、不伪造generation。不新开对局、不摆盘/重新标定/调用付费报告。
- [ ] 本机完整实体状态机自动化与设备真实API/当前页面可视验证分别如实报告；不把未实际摆盘称为物理端到端通过。保存RK1024×600 after和同尺寸before/after。
- [ ] 写发布回执：原因/修复范围、允许与排除精确计数/ID清单、Astra结论、聚焦验证、图片、published develop/Smartboxmain、RK实际进程/资源版本及任何物理未执行边界。五节点主动回传主session。
