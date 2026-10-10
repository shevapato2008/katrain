# 棋盘音效、末手标记与实体连接状态修复计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to implement this plan. Steps use checkbox syntax for tracking.

**Goal:** Galaxy 与 kiosk 可交互棋盘统一落子音及反色末手圆圈；未接 Board A 时不显示 LED 已连接；对弈首页每小时更新问候；审核通过后发布至两台服务器和 RK3562。

**Architecture:** 复用现有 `useSound`、`useReplayStoneSound` 和棋盘渲染器，不把音效放入所有渲染组件。LED 在现有唯一串口 worker 内消费生产 ESP32-S3 固件的只读 LINK，分开串口连通与 Board A 供电确认。问候在原页增加有清理的小时定时器。

**Tech Stack:** React/Vite/TypeScript、Vitest、FastAPI/Python/pytest、现有 LED 串口 worker、Docker/systemd。

---

## 依据与范围

- 起点及最新远端 develop：`28325ebb`。专用 feature/admin-console worktree 干净，已 fetch 并 merge develop（Already up to date）。
- 用户直接指定末手视觉：黑子白色空心圆圈，白子黑色空心圆圈；沿用现有正确的自由对弈视觉，不改布局或字体。
- 排查：未分析棋谱的 Galaxy KifuLibraryPage / kiosk KifuDetailPage 无声音；SVG `.mark` 使用 accent；研究、教程存在缺音效或绕过静音开关；共享 LiveBoard 的试下末手仍指原谱；手数模式下 TsumegoBoard 无圈。
- 现有正确的服务端落子 sound 与 PvP/星阵实时观战声音必须保留，不能每步双响。静态缩略图、设置预览、识别镜像不发声，不为无最后一步的数据发明 last。
- Board A 是棋盘侧接口、供电和 LED 输出板；Board B v7 ESP32-S3 是盒内控制板。依据 hardware repo AGENTS、v7 交接及 software `firmware/led-esp32s3/src/main.cpp`，GPIO5=CC、GPIO6=Board A 电源 ACK。v8/CH32X035 是历史材料，禁止部署。
- 当前 RK LED API connected=true 只代表 Board B 回 BRIGHT OK；没有 Board A 查询。设置取 geometry capabilities，首页取 vision，两个来源必须一并修复。
- 本轮不修改或烧录固件，不改变 Board A/B 电路；LINK 不证明每颗灯正常。

## Chunk 1：计划审核

- [x] 独立 gpt-6-astra / max 检查以下需求、声音边界、串口仲裁、发布风险。最多两轮计划审核；如需决策由该 agent 提供意见，root 修订。
- [x] 审核通过再开始生产代码修改。用户已授权实施和发布，无需重复确认。

## Chunk 2：可交互棋盘统一

### Task 1：棋谱回放、观战边界、共享标记

**Files:**
- Modify: `katrain/web/ui/src/galaxy/pages/KifuLibraryPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/KifuDetailPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/ReportDetailPage.tsx`
- Modify: `katrain/web/ui/src/galaxy/pages/live/LiveMatchPage.tsx`
- Modify: `katrain/web/ui/src/galaxy/pages/live/LivePage.tsx`
- Modify: `katrain/web/ui/src/galaxy/pages/report/ReportsPage.tsx`
- Modify: `katrain/web/ui/src/galaxy/pages/report/ReportDetailPage.tsx`
- Modify: `katrain/web/ui/src/galaxy/pages/KifuReportDetailPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/KifuReportDetailPage.tsx`
- Modify: `katrain/web/ui/src/components/Board.tsx`、`components/Board3D/Overlays/LastMove.tsx`（空点不画圈）
- Modify: `katrain/web/ui/src/kiosk/shell/GoBoardSvg.tsx`
- Modify: `katrain/web/ui/src/kiosk-shell/go-screens.css`
- Modify: `katrain/web/ui/src/components/live/LiveBoard.tsx`
- Modify: `katrain/web/ui/src/components/tsumego/TsumegoBoard.tsx`
- Test: existing page tests, `GoBoardSvg.test.tsx`, `LiveBoard.test.tsx`, focused Tsumego board test.

- [x] 在现有测试中添加症状复现，先运行验证失败：未分析谱翻手无音效、SVG 黑白末手未反色、试下圈停旧点。
- [x] 回放复用 `useReplayStoneSound`：初始异步载入/切谱/重复 cursor/回开局/pass 静音；用户上一手、下一手、跳手、显式自动播放每次最多一声。identity 绑定谱/比赛，必要时将现有 hook 的 identity 类型扩为 string|number|null，无第二套音频对象。
- [x] kiosk 报告和 Galaxy 直播回放补真实坐标和身份过滤，保留实时声音原有首快照/恢复语义。声音读取共享 SFX 设置。
- [x] LivePage、ReportsPage 的显式PlaybackBar回放同样接音效；Galaxy LiveMatch/ReportDetail/KifuReportDetail、kiosk ReportDetail/KifuReportDetail 试下仅接受并显示棋子后通过useSound响一声。共享LiveBoard在回调前拒绝占用和重复试下点，3D同样核对真实接受路径。保留现有试下提子语义，不扩规则实现。
- [x] SVG 根据真实 last 所在棋子画反色空心圈（黑子白圈/白子黑圈），不存在棋子或 pass 不画；明确样式避免 CSS accent 覆盖。
- [x] 共享 LiveBoard 试下最后一颗实际画出的棋子更新 marker 位置和颜色，拒绝/空点不画圈；保留 PV/AI 候选标注语义。
- [x] Tsumego 数字模式仍画可读反色圆圈，圈尺寸避开中心数字；不新增第二个音效。
- [x] 基础Board和3D LastMove在lastStone不存在时不画空点圈。
- [x] 逐一核对基础 Board、3D LastMove、SVG、LiveBoard、Tsumego、教程 renderer 的调用点，记录已正确/修复/静态例外；无运行时 import 的旧 Galaxy 副本不重构。
- [x] 聚焦测试通过，提交本任务文件，报告红绿测试及剩余差异。

### Task 2：研究与教程动作音效、末手

**Files:**
- Modify: `katrain/web/ui/src/galaxy/pages/ResearchPage.tsx`
- Modify: `katrain/web/ui/src/galaxy/components/research/ResearchAnalysisPanel.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/ResearchPage.tsx`
- Modify: `katrain/web/ui/src/galaxy/pages/tutorials/TutorialFigurePage.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/TutorialSectionPage.tsx`
- Modify: `katrain/web/ui/src/components/tutorials/SGFBoard.tsx`
- Test: owning page/hook tests，教程逐步控制相关测试。

- [x] 测试复现直接 Audio 绕静音、研究无音效/导入误响、教程翻步无声与无圈。
- [x] 研究移除直接 new Audio，复用 useSound；只对接受的实际摆子及显式回放动作发声，初载/导入/删除/pass/自动分析 frontier 静音。拥有服务端音效的路径不重复发声。
- [x] Galaxy研究真实会话落子继续由useSessionBase服务端sound负责，本地Audio撤去；显式导航另走动作音效。L1本地研究实际摆子也按接受动作发声。
- [x] 教程只对有明确编号且存在对应棋子的用户翻步发声，并把该步棋子传为 last；初始静态书图、换图、讲解播放及没有编号的图静音。保留数字/字母/三角书图语义。
- [x] 同尺寸真实浏览器预览 Galaxy 与 kiosk 黑白两颗末手，检查空心圈和数字可读，不能用测试绿色替代视觉观察。
- [x] 聚焦测试通过，提交本任务文件。

## Chunk 3：真实 Board A 状态与首页问候

### Task 3：LINK 状态消费与两处 UI

**Files:**
- Modify: `katrain/web/core/led_service.py`
- Modify: `katrain/web/api/v1/endpoints/led.py`
- Modify: `katrain/web/api/v1/endpoints/geometry.py`（无capture服务的status分支）
- Modify: `katrain/web/api/v1/endpoints/vision.py`
- Modify: `katrain/web/core/geometry_calibration_service.py`
- Modify: `katrain/web/ui/src/api.ts`、`katrain/web/ui/src/api/ledApi.ts`、`katrain/web/ui/src/api/geometryApi.ts`
- Modify: `katrain/web/ui/src/kiosk/context/VisionContext.tsx`
- Modify: `katrain/web/ui/src/kiosk/context/GeometryContext.tsx`（错误/旧值失效）
- Modify: `katrain/web/ui/src/kiosk/components/layout/GoConsoleRail.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/SettingsPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/vision/GeometryCalibrationScreen.tsx`
- Test: existing LED fake serial、vision/geometry status tests，Settings/rail tests。

- [x] FakeSerial 先红：Board B transport true + LINK DOWN/CABLE_ONLY 不得 physical connected true；UP+ACK OK 才true；不支持/畸形/timeout/过期/串口断开为null或false并不绿色。
- [x] 保留 `is_connected()` 原串口语义，新增只读缓存的 Board A 查询。`LINK` 没有 OK：用独立有界读取，恢复 serial timeout，不通过 `_send_and_ack`；所有串口 I/O 仍唯一 worker，HTTP 只读缓存。
- [x] 空闲/任务间约2秒查询，strict batch 优先，不把 LINK 插入 CLEAR/SETI/SHOW 事务。查询预算短（如200ms），旧固件失败适当降频，状态新鲜度不超过约6秒。time.monotonic，断开/重新打开先失效旧Board A缓存。不得无限阻塞。
- [x] 校验完整 link/ack/CC 枚举和相容性；新鲜 UP + ack=OK → true，DOWN/CABLE_ONLY → false，缺数据/非法/陈旧 → null。状态可提供 transport_connected 与 board_link/cc/ack 诊断，但不暴露无关硬件实现到用户流程。
- [x] 固件ACK优先，UP+ack=OK+cc=OPEN也是有效UP；不以CC抵消供电ACK。LINK超时后迟到的LINK/ERR cmd不可当下一条CLEAR/SHOW的响应，补聚焦串口测试，不重做事务框架。
- [x] LED、vision、geometry API 的用户LED字段都取Board A 状态；nullable不强转true/false。已有需要transport的内部capture仍原语义，不扩大事务改造。
- [x] geometry/status没有capture服务的分支也返回从LED缓存读取的nullable capabilities.led_ready，前端不再将它写死false；保持既有phase/locked兼容字段。
- [x] 首页、设置、标定一致：true已连接；false未连接；null未确认。设置LED独立于摄像头是否存在；状态刷新失败不能持续绿色旧LED，恢复后自动更新。
- [x] 测试证明 LINK 不吞 SHOW ACK/strict batch 不被插入、旧固件不影响LED既有事务。提交本任务。

### Task 4：首页每小时问候更新

**Files:** `katrain/web/ui/src/kiosk/pages/PlayPage.tsx`、`PlayPage.test.tsx`。

- [x] Fake timer 从05:30→06:30 复现挂着首页仍夜深了，验证失败。
- [x] `const [hour,setHour]=useState(()=>new Date().getHours())`；useEffect `setInterval(()=>setHour(new Date().getHours()),60*60*1000)`，卸载清理。窗口focus/页面重新可见时立即更新，避免休眠后台 timer 被节流后过时。
- [x] 不触发每小时平台请求/账号动作；使用当前用户名、语言和已有时间分段，时区依设备当地时间。
- [x] 测试夜→早、焦点恢复、卸载无遗留定时器；聚焦运行原首页测试，提交。

## Chunk 4：整体验证、独立审查与发布

- [x] root检查规格完成度和 diff；独立 gpt-6-astra / max 先规格、再代码质量和代表性视觉，修复实质问题直至通过。不要因低风险样式扩展全站重复审核。
- [x] 运行各任务相关 Vitest/pytest，正常、admin、strict kiosk 三种构建；保留严格SSO manifest。截图同尺寸展示一份真实未分析谱（Galaxy/kiosk）黑白末手。
- [ ] 发布前 fetch 最新develop→merge当前分支→必要聚焦检查→commit/push feature→merge/push develop。
- [ ] 更新 smartbox-software/vendor/katrain 到发布 develop，commit/push main，保留 unrelated dirt；记录两个SHA。
- [ ] 用 server-deploy 技能按实际运行容器/挂载准备可回滚增量镜像，保留账号、对象存储、数据库、KataGo引擎和现有棋谱/摄像头覆盖；部署 test→production→RK3562。新添 Python helper 必须纳入 runtime 文件清单，覆盖挂载文件须核查实际生效，不能仅ENV改SHA。
- [ ] 验证 cloud web/cron/admin SHA+health+实际静态文件哈希；RK严格SSO、health、源文件哈希、页面运行状态，不中断正在绑定的实体盘对局。
- [ ] 当前 Board A 缺席 RK 的真实 LINK 判定与首页/设置截图：不得已连接；不要求未连接摄像头变为ready。既有 Board B transport 可仍true。
- [ ] RK进入真实未分析谱，点击下一手验证石子音播放与speaker monitor输出（不录麦克风）；刷新/初载静音；恢复用户原入口。网页真实谱检查对应反色圈。
- [ ] 最终报告修复清单、审核和聚焦验证、发布SHA/三目标状态及无法物理验证的Board A接入条件。

## 执行记录

- 计划审核两轮：第一轮补齐LivePage/ReportsPage与试下音效、无capture的geometry状态分支；修订后独立gpt-6-astra max Approved。
- Task4问候：新测试先红（挂页/焦点恢复仍夜深了），最小小时timer和focus/visibility恢复实现后两个首页测试文件26通过。

- Task1：35785730 + c4bda94f + 4aa7faee；18组181测试及星阵/大厅观战63测试通过，追加网页直播visibility边界21测试通过。
- Task2：f3b7a46f + d1d5c475；79测试通过；max发现L2面板Audio遗漏后真实Panel先红、修复后相关44测试通过。
- UI/greeting独立gpt-6-astra max代码与视觉审核Approved；查看8张1280×800黑白圈截图。真实未分析谱24054（211手）通过本地浏览器初载0声、第1/2手各一声、无JS错误。截图与临时网络拦截仅在/tmp/output，未进入生产业务数据。
- 组合验证：27个本次改变的前端测试文件369通过；normal/admin/strict kiosk三构建通过，严格Box SSO和无three.js/galaxy/live API边界通过。

### 棋盘覆盖记录

| 类别 | 处理与声音边界 |
|---|---|
| 自由对弈、升降级、人类对弈，2D/3D | 既有服务端落子音保留，补空点不画圈 |
| 未分析棋谱、分析报告、专业棋谱详情 | 补共享SFX回放音，初载/换谱/pass静音 |
| 直播列表与详情、星阵历史回放 | 显式翻手单声；实时连续新子单声，首次/跳跃恢复/隐藏静音 |
| PvP与星阵实时观战 | 保留既有实时动作音；PvP没有历史翻手控件，不发明新功能 |
| 试下与本地/会话研究 | 接受并实际显示棋子才响；拒绝/删除/导入/分析同步不响，撤重复Audio |
| 教程逐步书图 | 只对明确编号的真实棋子翻步响，末手反色圈不遮数字/字母/三角 |
| 死活题 | 既有动作音保留；数字显示时也画反色圈 |
| 摆谱 | 既有实体确认音保留，SVG末手反色统一 |
| 列表缩略盘、设置预览、识别镜像 | 静态不响；无真实末手数据不画圈 |

无运行时引用的旧Galaxy LiveBoard/TsumegoBoard副本未改，所有实际入口使用共享渲染器。

- Task3：d6ff35b5 + fe85376b；独立max抓到LINK半行ACK移位，红绿修复后227后端测试通过。max重新运行原复现确认SHOW无ACK必失败、有ACK不遗留，下一查询不采旧UP，最终Approved。
- 发布前再次fetch origin/develop为28325ebb，merge Already up to date；无冲突。三目标部署及现场验收结果保存在本次release manifest与deployed/device-verified记录，执行后最终答复发布SHA。
