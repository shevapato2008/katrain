# 交接给 Claude：管理后台后续开发（2026-09-26）

以下正文可直接作为 Claude Code 的接手 prompt。本文是此次交接的最新状态快照；旧文档中“代码还没开始”“共用 Galaxy 管理员”“先做 cron”“后台用绿色”等历史描述不得覆盖本文。未完成的外部关卡仍有效。

---

你接手 KaTrain / 智星盒 StellaBox 管理后台的后续开发。请先读文档和真实源码，从当前断点继续，不重做已完成模块，不把本地测试当作真实设备或生产验收。

## 1. 工作位置、交接状态和文档优先级

- 工作目录：`/Users/fan/Repositories/katrain-admin-console`，现有 worktree，分支 `feature/admin-console`。主开发分支是 `develop`，不是 `master`。
- Fan 已决定保持在这个 worktree 中逐模块完成；不要另开三个窗口同时改共享源码、暂存区或 HEAD，也不要去主工作树 `/Users/fan/Repositories/katrain` 切分支或改文件。
- 功能代码基线 HEAD 是 `a831389e`。本次交接另提交本文件、最新报告、诊断 HTML 草稿/截图和忽略规则；接手时以 `git log -1` 为交接提交，以 `git status` 和分支实际 HEAD 为准。
- Fan 本次明确授权 Codex 将现有成果 commit & push 到 `origin/feature/admin-console`。**这不授权 Claude 后续 push、合入 develop、更新父仓 submodule、部署或远程操作。** 接手时可只读核对 Git 状态；再次推送须当场批准，不强推、不改写历史。
- `.playwright-cli/` 和 `output/` 是临时浏览器记录/本地 smoke 产物，忽略且不作为运行时输入；本次停止跟踪旧的六份浏览器缓存。正式 HTML、参考图、实现图、并排/叠加/差异图留在 `superpowers/tracks/admin-console/`，必须保留。不要把 `.katrain` 数据集、模型、真实凭据或运行目录提交进 Git。
- 原始计划部分勾选和“尚未部署”等结尾滞后于报告顶部修订。按**最新用户要求 → 本文 → codex-report 顶部更新 → 最新模块 spec/计划/契约 → 历史计划**理解现状；发现实际源码不同先只读核实，不照旧代码片段覆盖。

开始前完整阅读：

1. 仓库根目录 `CLAUDE.md`、`AGENTS.md`，以及会话提供的用户级 AGENTS 约束，特别是比例化交付、SBC 构建隔离、浏览器使用要求。
2. `superpowers/tracks/admin-console/codex-report.md`：顶部最新状态优先，下面是历史记录。
3. `superpowers/tracks/admin-console/spec-2026-09-24-admin-console.md` 和 `plan-2026-09-24-admin-tutorial-first.md`：后者覆盖旧的共用身份和开发顺序。
4. `plan-2026-09-25-admin-cron-rebase.md`、`slice1/cron-contract.md`、`tutorial-admin-contract.md`、`docs/operations/admin-console-access.md`。
5. `plan-2026-09-25-admin-performance-access.md`、`slice2/design/design-notes.md`。
6. `spec-2026-09-26-admin-vision-lab.md`，三份 `plan-2026-09-26-admin-vision-{capture,training,diagnostics}.md`，`slice3/vision-capture-contract.md`、`slice4/vision-training-contract.md`。
7. `slice5/recognition-observation-notes.md`、`slice5/design/design-notes.md` 和现有诊断 HTML。

`codex-handoff.md`、旧 `plan-2026-09-24-tutorial-admin-guard.md` / `plan-2026-09-24-admin-console-cron.md` 是历史安全/实现依据，涉及原安全修复、cron 记录器或生产发布时读对应全文；不能重新执行其中已被覆盖的身份、设计、引导账号或发布步骤。

## 2. 不可越过的权限边界

- **每次远程连接均需 Fan 当场授权**：home-ubuntu（测试）、ucloud-v100（生产）、盒子；包括只读 SSH、scp、rsync、隧道、自动探测。过去的“确认”“部署吧”只授权当时操作，不能复用。
- 每次真实环境数据库写入、上传/写测试机、配置变更、真实 GPU 训练、模型下载/登记/加载及设备验收、push、部署均要对应的明确批准。后台按钮或计划获批不等于代理可替用户执行外部操作。
- 先测试机，再生产；不停止/抢占 KataGo、校准服务或别人的本地服务。不得凭显存空闲认定 GPU 已预留。
- 密码、bcrypt 哈希、后台签名密钥、公共密钥、env/SSH 私密内容不能打印或写进仓库/聊天。只检查是否存在、长度或校验结果。测试后台口令由 Fan 从 Mac Keychain 的 `katrain-admin-test` 项取用。
- 不用共享 stash，不 reset/clean/强制 checkout，不覆盖其他 worktree 或用户改动；暂存具体路径，提交前检查 staged diff。
- 本地临时目录和注入 fake 可用于代码测试；不是目标库、真实摄像头、真实训练或生产证明。不要为了演示打开硬件、下载模型或访问外部 TTS。

## 3. 开发方式、设计和视觉要求

采用“共享基础优先、用户旅程垂直切片”，同一时间主要闭环一个模块：

`claude-design 本地高保真 HTML → ui-ux-pro-max 优化 → 隔离 React Fixture → 同尺寸视觉对照确认 → 契约冻结 → 后端 → 真接口集成 → 自动化/设备/用户验收 → 删除 Fixture`。

- 使用可用的 vertical-slice / Superpowers 技能落实上述顺序。**所有新设计步骤都要用 claude-design，落可本地打开的 HTML，再用 ui-ux-pro-max 优化**，不能只交一张生成图片或只写代码。
- Fan 已授权独立 **GPT-6 Astra、max effort** 代做本地方案决策与视觉判定；实现者不能自审。有工具则调用独立代理；没有该模型/跨模型工具就诚实报告，不假称已调用，也不把普通 Claude 评审冒充 Astra。Fan 保留最终网页复核权。代理不能代外部操作授权。
- 目标 viewport **1440×900**。新模块 Fixture 同时检查参考图、真实运行截图、并排图、叠加/差异图，记录构图、间距、层级、字体/色彩、图标、文案与状态语义。当前切片的视觉门没过，不能写后端。
- 后台独立风格：**B 石墨铜夜间 + C 雾白蓝白天，楷体**，不要恢复 Galaxy 绿色或黑体。品牌仍为“智星盒 StellaBox”。主题依系统深浅模式；复用现有 admin CSS 最终生效的 tokens，不照文件开头历史绿色规则抄。
- 以已实现的教程/cron 最终字号为基准。用户先要求放大，后又要求内容字号约减30%；不要再翻回任一旧版大字号。密集诊断/训练的关键文字约16–17px、说明13–14px，具体以实际 CSS/最终稿为准，不全页 `transform:scale`。
- 教程与 cron 最终参考稿为 `tutorial-admin-design-final.html`、`slice1/design/admin-cron-final.html`；旧 Galaxy 版、v2/v3 和旧四图仅历史，不重新批准或追齐它们。
- 不要每两分钟问问题。常规本地判断自主完成，必要时派独立 Astra；持续完成安全范围内的后续任务。遇权限关卡保留待办，可顺序转到不依赖外部状态的本地任务。
- 工作成本必须相称：聚焦测试、局部格式化/ESLint、代表性真实预览；不为小字号或文案变化全状态重拍，不新增重复审计/变异体系，不全仓 Black。鉴权、文件完整性、并发、进程退出等高风险边界才做对应审查。
- 实现按 TDD/现有计划执行，及时更新 checkbox 和 `codex-report.md`。每个本地任务提交；达到阶段验收即可推进，不为未来需求搭通用任务平台。

## 4. 已实现模块，以及仍须收尾的内容

### 4.1 安全基础与独立后台身份

- 后台是 katrain 仓内独立 FastAPI 进程，独立 `admin.html` / Vite 构建，宿主机仅 loopback，经 SSH 隧道访问；公开 Galaxy 不挂 `/api/admin`。
- **后台专用用户名为 `admin:fan`**，不是在 Galaxy 注册新用户。env 注入 `KATRAIN_ADMIN_USERNAME`、cost≥12 bcrypt `KATRAIN_ADMIN_PASSWORD_HASH`、独立且≥32字符 `KATRAIN_ADMIN_SESSION_SECRET`、`KATRAIN_ADMIN_ENV=local/test/prod`。
- 不使用公开 `users.is_admin`、公共口令或公共 JWT 密钥签后台会话。Bearer 放 localStorage，8小时，严格 sub/type/aud/env/exp；不用 cookie。换密码同时轮换后台签名密钥才能让已发令牌失效。
- 后台不 `init_db()`；必要表由公开 web schema 初始化，缺表不能伪装空数据或跳过审计。审计记专用 admin realm，不伪造公开用户 ID。
- 前置安全代码已合入过 develop，测试机旧公开 `admin` 已经另获批准撤权、随机化密码；**本机与生产旧管理员处置、生产安全发布/验收仍未完成**。不要重新创建公开默认 admin，也不要未经批准操作生产。
- 当前源码中公开教程四写路由、公开设备列表及两项计费管理路由已经退役；普通计费、公开教程/媒体 GET 和盒子 heartbeat 保留。旧计划未勾项不表示要恢复这些接口。

### 4.2 教程管理

- 已实现专用登录、教材/章/节/图选择、原书页、2D电子棋盘/逐手滑条、棋图编辑/撤销/保存、讲解编辑、语音生成入口、人工核对/审核、现有音视频读取。
- 真实 API 与正式前端已集成，Fixture已删；保存并发版本冲突409保留草稿，支持读取服务器版本后重试；401退出、书/章/图切换草稿隔离、变更导致旧视频失效已覆盖。
- 已部署测试机。真实外部 Edge TTS、目标媒体存储/更新与 Fan 完整端到端验收、生产发布仍有待办；不能用本地合成媒体的播放证明真实 TTS 成功。
- 用户公众教程页最终应为成品“2D电子棋盘 + 配语音视频”；**公开页面成品化由 Fan 另一个 session 负责**。本后台保持编辑工作台，不自行扩张去重做公众页面，合并时避免覆盖那条赛道。
- 三份 tutorial-data-sync 技能已停用旧全表 TRUNCATE/替换流程，防止覆盖在线编辑和历史；将来同步新教材须先另定范围核差、冲突拒绝、完整备份/恢复流程，不运行旧指令。

### 4.3 定时任务

- 已实现9项真实任务、cron心跳、健康判定、运行历史/完整错误、两条分析队列、15秒刷新及采样陈旧提示；**只读，不做立即运行/暂停**。表由web建，cron写，admin读。
- 概览已改彩色 icon + 简短状态标签，状态随采样更新；任务详情补模块、用途、调度和记录说明，不只是错误文本。
- 任务名必须“模块 - 功能”：直播 - 分析/赛事列表/赛事预告/落子轮询/Pandanet对局/棋手译名，复盘 - 分析，系统 - 数据清理，教程 - 备份；未知任务诚实显示原名。
- 已在测试机验证真实9项状态、心跳及队列。3秒 `poll_moves` 成功不逐次写历史，空历史可能符合契约；吞错/历史残留错误不可被简单“正常”标签掩盖。
- 测试机 cron SQLAlchemy 已约束 `>=2.0,<2.1`，避免新默认驱动缺 psycopg；不要随意删约束。生产发布和 Fan 最终复核仍另走授权。
- 教程最终字号调整已经推送过 develop，但当时未重新部署测试机；因此用户测试隧道与本地最新稿可能不同，接手不要声称线上已是最终字号。

### 4.4 性能监控（slice2）

- 明确要求**后台内嵌 Grafana**，不是只放 Netdata/Grafana 外跳链接。旧外跳提案已废弃。
- claude-design HTML、ui-ux-pro-max优化、隔离React Fixture及同尺寸四图已获独立Astra批准。正式后台还没有真实监控功能；演示没有真实 iframe 或伪造指标。
- 待办：单次只读 SSH 授权后核实 home-ubuntu 是否已有 Grafana、数据源/看板、绑定、鉴权、iframe策略/CSP和最小代理需求；之后冻结契约、正式集成、删除Fixture、真实测试机验收。若没有服务，先明确最小部署方案和权限，不能假称存在。
- 后台 Bearer 不给 Grafana；不能用匿名公网开放或宽放 CSP 绕过嵌入保护。

## 5. 紧急视觉实验室：全部用户需求及实现边界

这是核心算法快速迭代平台，优先于尚未详细计划的其他后台模块。用户完整目标是：

1. **MacBook摆谱采样**：连接摄像头、记录YOLO11训练棋谱画面、检查/管理训练数据、可视化上传至 home-ubuntu。
2. **测试机训练平台**：利用 home-ubuntu 的2×3090快速训练YOLO11，展示进度/日志/指标、存储不同迭代模型版本。
3. **MacBook模型与识别**：拉取已训练模型、部署/回滚，用OpenCV+YOLO11识别棋盘棋子，实时展示标定原图、warped、YOLO框、去重框、纠偏前电子盘、纠偏后电子盘、最终稳定电子盘。

按 A/B/C 三个顺序切片，不将不同运行/帧的数据拼成漂亮假图。2×3090是硬件背景，**首版只支持明确预留的单卡**，DDP尚未验证，不宣传双卡训练已可用。

### A / slice3：采集与不可变数据集（本地前后端已集成）

- 已完成连接/断开、同帧原图/warp、真实空盘标定、SGF导入/19×19回放含提子pass、独立采集会话、恢复、逐手确认、重拍、可视叠框复核、不可变数据集冻结。
- 代码主要在 `web/admin/vision_runtime.py`、`vision_sgf.py`、`vision_sessions.py`、`vision_capture_txn.py`、`vision_dataset.py`、`routers/vision.py`，前端 `src/admin/vision/VisionDashboard.tsx` / `VisionLivePage.tsx`。
- Mac能力仅 local + `KATRAIN_ADMIN_VISION_LOCAL=1` + 明确 `127.0.0.1` 绑定启用；默认不打开设备。受控目录为 `~/.katrain/admin-vision`，可选LED串口 env `KATRAIN_ADMIN_VISION_LED_PORT`。GET不能暗中连相机。
- CameraHub/LED 同机同用户跨进程租约避免与kiosk抢设备；不抢占、不自动重连。不同Unix用户的共享锁边界需另核实。
- 无LED `stones2` 类固定 black=0/white=1；LED四类沿用classes.py，不能混集/伪造LED标定。旧LED `run_capture` 仅在一次性暂存目录复用。
- 序号+单调时间保证帧晚于确认/指引；grab_fresh超时返回的旧帧不能发布。不可变图像先写/验证，最后原子发布manifest；重拍不删后续帧，失败保留旧引用。已成功采集的只读幂等重试不因相机断开而失败。
- 冻结验证可读图、有限归一标签、合法类目、非空两侧split、SGF/几何/文件SHA；按棋谱/顺序隔离，不随机拆连续帧，data.yaml可搬移。
- **未完成**：Task5 Step4真实相机/棋盘/LED走查；Task6完整上传能力。`vision_transfer.py` 只有默认禁用的可注入纯协议/容量/断点/取消/逐文件SHA回执验证，**无SSH适配器、真实上传API或已上传状态证明**。这不是已完成上传。
- 后续补受控目标/手动确认的适配器与前端流程；目录/账户先授权核实，实际远端写入另批准；所有回执匹配冻结清单并原子发布后才标成功。

### B / slice4：训练与模型（本地正式前后端已集成，真实服务未启用）

- HTML/Fixture四图/契约已批准。核心 `92879448`、真实API `7b4a0818`、正式React `2efca8e2`，训练Fixture入口/控制器/样例已删除。
- 代码 `vision_training.py`、`vision_training_config.py`、`vision_training_worker.py`、`vision_training_process.py`、`routers/vision_training.py`；正式API前缀 **`/api/admin/vision-training`**；前端 `vision/training/TrainingDashboard.tsx` / `TrainingPage.tsx`。
- 已做真实接口目录/预设/创建/取消/运行/指标/日志/模型版本。独立进程组、一次一个run、固定root flock、UUID幂等；取消必须确认原组退出才释放。重启遗留 interrupted/busy，不按持久化PID乱杀或删除锁绕过占用。
- 仅 test + Linux + 显式loopback + `KATRAIN_ADMIN_VISION_TRAINING=1` + 已核实绝对JSON配置 + 本地权重哈希 + Ultralytics **8.4.34** 才启用。Mac/local与prod禁用，不自动SSH/RPC；Mac通过另获授权的测试机隧道、不同origin/端口独立登录。
- 配置 env `KATRAIN_ADMIN_VISION_TRAINING_CONFIG`，格式看访问文档；不存在权重不得联网下载回退。输入冻结目录/类目/hash核实，单卡不抢KataGo。
- worker保持已核实8.4.34离线最小边界（本地权重，amp=False/plots=False，外部integrations禁用）；不是系统级网络隔离，不能照新YOLO型号下载示例改实现。
- 成功须可读best.pt + schema + 实际全部参数/类目顺序/模型与dataset哈希一致，原子只读版本；日志有界且最新尾部可见。
- 正式React≤2秒串行轮询、Abort/401/旧代际隔离、原UUID重试；选择历史不停止活动run观察，发布后更新模型目录，读取失败不反复扫描已缓存大目录。不要回退这三项修复。
- **未完成**：Task5全部，核实GPU映射/资源预留、上传真实数据、配置部署训练服务、实际GPU运行/取消/产物验收、用户验收。没有实际epoch/模型版本，不造样例填正式空页。

### C / slice5：模型部署与七阶段诊断（当前断点）

- 计划已独立Astra逐chunk批准，提交 `a831389e`。**只做了Task1 HTML草稿，未做最终独立视觉批准；React Fixture、契约、observer、模型管理/API均未实现。**
- 当前文件 `slice5/design/admin-vision-diagnostics.html`、`design-notes.md`、四态 `diagnostics-design-*-1440x900.png`；本次按Fan授权提交草稿，不代表视觉通过。四态为 unconnected-dark / ready-dark / running-dark / stale-light；`capture=true` 隐藏设计控制条。画布已压缩以便七格完整首屏，保持关键字号；过期态有观察时间和未更新时长，未知态不造时间。
- **第一步：复核这四态实际HTML截图/主要交互，派独立Astra max视觉判定，然后执行Task2隔离React Fixture与四图。未过门禁止Task3以后后端。** 不需要重画多个风格。
- 必须用 `AdminVisionRuntime` 持有的 CameraHub/GeometryLock → **VisionService/InProcessAdapter 的唯一真实链**。不能另用简化DetectionPipeline，不能七格各做推理/重复有状态赋值。
- “同帧”准确说**同一处理批次**：当前raw作锚点，实际最多8帧平均+CLAHE才是模型输入；记录真实贡献帧身份、相机seq/时间、模型hash/几何revision，整个快照原子替换。
- 七格准确语义：①本轮原图/标定叠图；②平均前带生产margin纯warp；③实际平均增强输入背景上的NMS后、业务去重前框；④同输入的业务去重+阴影剔除框，分清keep/sustain与赋值输入；⑤**原始定位投影·诊断派生**，最近点/越界丢弃/同格最高置信度，不做视差/历史/掩码，不回灌，绝不是现有生产中间矩阵；⑥本轮唯一一次detections_to_board返回；⑦两帧逐格vote→deny mask→reference之后实际发布的电子盘。
- 初版viewer不绑对局、不启monitor、不发棋步或驱动LED；参考检查/落子确认未参与就显示未参与，MoveDetector不产生第八盘。
- 一worker/一在途推理；观察发布≤2Hz，不改变原识别采样配置。只留最新完整和生成中各一份，最多三底图，长边≤960、JPEG各≤1MiB、每阶段≤4096框、总响应≤8MiB。运动/断线/错误保留整份旧快照+stale，超限报不可用，不裁掉部分冒称完整。
- 可信模型只接受服务端固定root/登记JSON的 model_id + **独立可信 manifest_sha256**；浏览器不能传任意路径/PT。列表不加载torch，≤100模型/每模型≤1GiB。远程拉取按钮保持待授权，最终真实拉取功能仍必须补完，不能以禁用占位宣称需求完成。
- 从训练 `_artifact_info` 抽共享纯产物校验；训练仍与冻结spec独立比对，Mac登记用可信摘要，不从manifest自造spec后自证。显式实际激活需核YOLO.names数量/顺序、实际imgsz，不只信旧checkpoint_readable字段。
- 旧线程实际退出才换模型/采集/标定/断开；当前通用VisionService.stop会丢join超时句柄，**仅加诊断专用stop_diagnostic()->bool**保留alive占用，不顺手重写生产subprocess生命周期。加载失败保留current/previous文件与状态，诊断停，手动可重启旧版，不自动启动。
- 修通 config→worker→StoneDetector→Ultralytics 的真实imgsz（当前三处未贯通），默认960不变；不扩改ONNX/RKNN固定输入规则。
- Task3可信产物/版本→Task4只读observer/等价性→Task5严格生命周期/API→Task6真实React/删除Fixture→Task7另授权模型拉取/设备验收，按已批准计划执行。

## 6. 其他后台需求：记录在案，尚未详细设计/批准

原spec §10还列了：金镜像制品库（镜像manifest/上传归smartbox provisioning，后台做通用制品库；存储/N100网络待定）、用户/计费与审计查看（计费管理接口迁入后台）、盒子设备页（须先接真实heartbeat调用方）、配置体检、报错追踪/告警。

这些**不在现有三份最初计划内，也没有本轮完整契约/验收标准**。YOLO数据集已纳入紧急A/B/C。先闭环性能与视觉实验室、已有模块外部验收；再逐模块澄清最小旅程、设计和计划，不能把“完成所有未完成slice”解释成自行实现上述全部未定平台。第一版也不擅自加入多角色、2FA、模拟用户登录、cron控制或通用队列/DDP。

## 7. 本地预览、验证和当前证据

- Python可用 `/opt/miniconda3/envs/py311_katago/bin/python`，含cv2/PIL/numpy/Ultralytics8.4.34；依赖已在本worktree安装，不默认重新安装全部。
- 前端在 `katrain/web/ui`：`npm run dev:admin`（5174）、`npm run build:admin`（含 `tsc -b`）；类型检查不是 `tsc --noEmit`。后台独立产物 `katrain/web/static-admin/` 不入库。
- 当前端口只读核对：8765为repo-root静态HTML预览；5174为admin Vite；8015为临时SQLite真实admin/API smoke、摄像头/训练开关均关闭；8010已有先前cron预览，**不要杀它或不查端口就占用**。进程可能退出，不能把本文当存活证明。
- 8015脚本为忽略的 `output/playwright/admin-training-local-smoke.py`，仅本机临时库/演示账号，不含目标环境业务数据；新clone不会有该脚本，必要时最小重建临时库预览，别当服务启动依赖。正式入口是 `python -m katrain.web.admin`，凭据用私有env；当前CLI不支持旧计划中的任意host/port参数。
- 设计HTML有相对CSS/字体依赖，优先repo-root本地HTTP打开，例如 `http://127.0.0.1:8765/superpowers/tracks/admin-console/slice5/design/admin-vision-diagnostics.html?state=running-dark&capture=true`；本地文件也保留。遵守CLAUDE.md浏览器规矩；Codex此前用真实Playwright Chromium做截图，不能把旧会话当Claude工具已连接。
- 测试机此前部署后台宿主机127.0.0.1:8012（容器8010）；8010被katago-calib占用。Fan此前用Mac8013隧道看测试后台；**本轮未检查远端当前存活，也未重开隧道**。映射命令在访问文档，执行仍另批。
- 本次交接前新鲜验证：视觉训练/采集/数据集/传输后端9文件 **215 passed**；前端采集/训练/入口/client/performance共8文件 **55 passed**；`build:admin`成功。仅既有passlib crypt弃用及Node localStorage环境警告。没有真实硬件/GPU/网络训练，也不代表全仓所有测试通过。
- 后端聚焦命令：`/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/web_ui/test_admin_vision_training.py tests/web_ui/test_admin_vision_training_api.py tests/web_ui/test_admin_vision_training_config.py tests/web_ui/test_admin_vision_training_entry.py tests/web_ui/test_admin_vision_training_worker.py tests/web_ui/test_admin_vision_training_process.py tests/web_ui/test_admin_vision.py tests/web_ui/test_admin_vision_dataset.py tests/web_ui/test_admin_vision_transfer.py`。
- 前端聚焦命令：在UI目录 `npx vitest run src/admin/vision/VisionDashboard.test.tsx src/admin/vision/training/TrainingDashboard.test.tsx src/admin/vision/training/TrainingPage.test.tsx src/admin/AdminApp.vision.test.tsx src/admin/api/client.test.ts src/admin/admin-entry.config.test.ts src/admin/AdminApp.test.tsx src/admin/performance/PerformancePage.test.tsx`。
- `tests/web_ui/conftest`会mock interface，不与platform/root测试混同一pytest进程。改共享web/vision边界要做对应邻近回归；改共享UI时按CLAUDE.md验证Galaxy与kiosk两构建，不能把admin引入公开/SBC包。不要重跑全部历史视觉或加无关流程。

## 8. 接手后的具体行动与交付标准

1. 读完上述文档，核Git/文件/服务边界；先简短报告真实断点，不询问已定字体、用户名和架构。
2. 当前C停在Task1视觉关卡，完成独立视觉确认→Task2 Fixture/四图→契约→Task3–6本地实现，保持A/B已有正式集成与行为修复。
3. 在需外部权限时明确列出目标、动作、是否写入及批准范围。未批准的Grafana、上传、GPU训练、模型拉取/加载/硬件验收保持待办，可继续独立的安全本地工作；不能用Agent替批准。
4. 获取相应批准后闭环真实链：采集冻结→逐文件验证上传→测试机预留单卡训练/取消/版本→Mac验证拉取/激活/诊断/回滚，补Grafana真实嵌入；先测试，后单独生产发布。公众教程成品页与smartbox父仓的变更另协调，不能擅自push。
5. 每个阶段都真实可预览、状态诚实、契约清楚；正式实现无模拟业务数据，Fixture在真实集成后删除。外部依赖未验收就写“本地实现完成、外部未验收”，不宣称整个slice完成。
6. 持续更新计划checkbox、当前commit/验证/偏离原因/授权缺口，并写 `codex-report.md` 或清晰链接的新Claude报告。会话结束/额度接近上限前留下下一安全起点，用户无需依赖本次聊天才能继续。

现在从**诊断HTML四态的独立视觉复核**开始接手；不提前写C后端，不重做A/B，不重用过去的远程批准。
