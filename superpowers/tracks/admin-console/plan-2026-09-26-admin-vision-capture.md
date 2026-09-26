# 视觉实验室 · Mac 采集 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans in this same worktree. Steps use checkbox (`- [ ]`) syntax for tracking. Fan 指定一个模块一个模块推进；独立 GPT-6 Astra max 代做睡前视觉裁定，不代做远程操作授权。

**Goal:** Mac 本机后台可真实连接相机、标定棋盘、按 SGF 逐手采帧、复核并冻结数据集；测试机上传只在另行授权后执行。

**Architecture:** 复用独立 admin Bearer、CameraHub/CaptureService、SGF 回放与几何锁；按需启动的本机 `AdminVisionRuntime` 持有相机和受控采集目录，公共 CameraHub 以进程间租约避免与 kiosk 抢占。先做隔离的 React Fixture 和同视口四图，通过视觉关卡后才接后台真实状态。LED 模式与无 LED 双类模式必须在 manifest 中分开，不混充四类标注。

**Tech Stack:** React/Vite/Vitest、FastAPI/Pydantic、OpenCV、现有 KaTrain vision/baipu 模块、pytest、Chromium。

---

## 文件与责任

- `superpowers/tracks/admin-console/slice3/design/admin-vision-capture.html` 与本目录截图/记录：静态设计基准，已独立视觉通过。
- `katrain/web/ui/admin-vision-fixture.html`、`src/admin/vision/fixture.tsx`、`VisionFixture.tsx`、`VisionCapturePage.tsx`、`VisionCapturePage.css`：隔离的双主题/多状态可视 Fixture；真实集成后删除 Fixture 入口、样例数据和控制器，保留纯页面。
- `src/admin/vision/VisionCapturePage.test.tsx`：加载、未连接、可采集、错误与禁用操作的聚焦前端测试。
- `katrain/web/core/device_lease.py`、`camera_hub.py`、`led_service.py`、`katrain/web/server.py`：按设备标识共享的同机进程间相机/LED 租约，start 失败时不留锁，stop 释放；kiosk/admin 复用，kiosk 对专门的占用异常做现有降级而非整体启动失败。
- `katrain/web/admin/vision_runtime.py`：本机相机、几何、SGF 与采集目录生命周期及真实状态；不借用整个 kiosk lifespan。
- `katrain/web/admin/vision_sgf.py`：有界原始 SGF 输入、19×19 宽高校验及不可变逐手真值；持久化仍由采集事务负责。
- `katrain/web/admin/vision_capture_txn.py`：后台独立采集事务；LED 旧管线只在一次性暂存目录运行，两种模式共用不可变图片与原子 manifest 发布。
- `katrain/web/admin/routers/vision.py`：admin 受保护状态/预览/标定/导谱/逐手拍摄/样本检查与冻结 API；图像只读 Bearer fetch，不在 URL 带 token。
- `katrain/web/admin/vision_dataset.py`、`vision_transfer.py`：不可变双类/四类数据集及受控测试机上传状态；不混入硬件生命周期。
- `katrain/web/admin/app.py`、`__main__.py`、`settings.py`：仅本机显式启用的 runtime、路由与 127.0.0.1 绑定。测试/生产默认禁用相机能力。
- `tests/web_ui/test_admin_vision.py`、`tests/web_ui/test_admin_vision_dataset.py`、现有 `tests/test_camera_hub.py` 和 LED 服务测试：无硬件 fake 测鉴权、本机开关、租约冲突、标定/逐手写入/恢复/错误；不以 fake 声称真实相机验收。
- `src/admin/AdminApp.tsx`、`src/admin/api/client.ts`：四图通过后把真实页面挂进后台导航与 API；不得打包 Fixture 样例数据。

## Chunk 1: 设计、Fixture 与视觉关卡

### Task 1: HTML 设计基准

- [x] 按 `claude-design` 产出 [本地 HTML](./slice3/design/admin-vision-capture.html)，用 `ui-ux-pro-max` 检查后台主题/字号和空态；1440×900 查看夜间未连接、夜间采集中示意、白天采集中示意。
- [x] 独立 GPT-6 Astra max 修正三项状态问题后裁定 APPROVE；该裁定不代表相机在线或接口已实现。

### Task 2: 隔离 React Fixture（@superpowers:test-driven-development）

**Files:** `katrain/web/ui/admin-vision-fixture.html`、`src/admin/vision/{fixture,VisionFixture,VisionCapturePage,VisionCapturePage.css,VisionCapturePage.test}.tsx`（CSS 扩展名除外）。

- [x] **Step 1:** 写 `VisionCapturePage.test.tsx`：`unconnected` 只显示“尚未读取本机设备列表”、空图、采集按钮禁用；`ready` 标成“设计示意”且禁用真实采集/上传；错误状态有重试出口。`npx vitest run src/admin/vision/VisionCapturePage.test.tsx` 先 RED。
- [x] **Step 2:** 按 HTML 实现纯展示 `VisionCapturePage` + CSS，Fixture 壳层只切 `state/theme`，所有示意数据仅在 Fixture 控制器内。相同命令转 GREEN；`npm run build:admin` 必须不包含 Fixture 入口。
- [x] **Step 3:** 在 `katrain/web/ui` 运行 `npm run dev:admin`，Vite 5174 真正渲染 `unconnected/dark`、`ready/dark`、`ready/light` 三态 1440×900；保存参考、实现、并排、叠加/差异与差异记录。独立 GPT-6 Astra max 复核四图。若 REVISE，只修可见差异并复核。
- [x] **Step 3a:** 运行已有 `npx vitest run src/admin/admin-entry.config.test.ts`，确认正式构建入口仍只有 `admin.html`；不另建审计层。
- [x] **Step 4:** 🛑 四图视觉由 Fan 睡前委托的独立代理裁定 **APPROVE**。通过后才冻结下面的 API 契约或编写本模块后端；Fan 早晨可再修改外观。

## Chunk 2: 本机契约与基础硬件边界

### Task 3: 真实状态契约和相机租约

- [x] **Step 1:** 在 [本地契约](./slice3/vision-capture-contract.md) 中冻结 `GET /api/admin/vision/status`：`enabled/local_only/camera={unknown|disconnected|connecting|connected|occupied|error}/geometry={required|ready|stale}/sgf={loaded|none}/dataset={draft|frozen|none}`；每个状态带实际来源/更新时间，未知不变成“正常”。`GET /api/admin/vision/preview` 在同一次 `grab_fresh()` 新鲜取帧后编码原图/warped，返回同一个 `frame_id`、UTC 观测时间、相机序号/单调时间戳、`geometry_revision` 和两个有界尺寸的 JPEG base64；无缓存，未连接回 409、未标定时只返回原图且 warped 为 null。前端每次只接收同一个响应，不分别请求相机帧。
- [x] **Step 2:** 先扩展现有 `tests/test_camera_hub.py`、`tests/test_led_service.py` 与 `tests/web_ui/test_board_lifespan_camera_degraded.py`：同进程及跨进程同设备冲突、不同设备互不阻塞、open 异常、stop 后重获、kiosk camera/LED 占用降级；再在 `device_lease.py` 实现以相机设备 ID 或 LED 串口路径为同一租约键的非阻塞租约，`CameraHub`/`LedService` 生命周期共同使用，失败和 stop 必释放。`server.py` 对新增占用路径只 catch 专门的 `DeviceBusy`：相机占用降为 `camera_hub=None`，LED 占用降为 `app.state.led=None` 且不启动 LED 后续任务；原有摄像头普通启动失败降级保留，意外异常不被新增逻辑吞掉。独立规格与质量复核 APPROVE；修复提交为 `af0d3fe7`、`e66b8add`、`9ea0d478`、`c3518230`；聚焦及邻近测试 **110 passed**。
- [x] **Step 3:** 先写未授权、非 local、未设置 `KATRAIN_ADMIN_VISION_LOCAL=1` 时所有相机路由拒绝、启动不触硬件的测试；再加仅本机可用的 `AdminVisionRuntime` 和 admin 受保护 `POST /connect`、`POST /disconnect`。status/preview/app 创建绝不隐式打开设备；disconnect 与 ASGI shutdown 释放相机/LED 租约。`__main__.py` 在 local vision 模式绑定 `127.0.0.1`，容器环境仍沿用原绑定；聚焦 Python 测试转 GREEN。提交 `54f5be06`＋状态时间修复 `0c5b8205`，独立规格与质量评审均 APPROVE；本机真硬件仍待验收。

### Task 4: 标定、SGF 与真实逐手采集

- [x] **Step 1:** 测试相机断开/占用、非空盘或低置信度不锁定几何。实现读取真实 burst，复用 `lock_geometry_from_frames` 并保存来源；LED 可用时明确其状态，缺 LED 只能选择无 LED 路径。提交 `429cdaaa`；独立复核发现稳定棋子会被 burst 基线吸收，已用真实合成图红测并复用绝对 HSV 检测修复 `2ae78606`。几何/相机聚焦 **94 passed**，规格和质量复核 APPROVE；不代表真实光照/相机验收。
- [x] **Step 2:** 测试导入 SGF 的步数、提子、pass、19×19 宽高限制和错误反馈；纯准备层 `c8969af0`、采集会话独立 ID/CRLF 原始字节修复 `5e4a3f15` 与保护路由/原子草稿持久化 `b8c1cf9f` 已实现。受控目录写入、不写公共用户库；重启只恢复数据，不打开设备。
- [x] **Step 3:** 先测逐手确认、严格顺序、幂等、显式重拍、超时旧帧及断开并发；在 `vision_capture_txn.py` 串行验证 SGF 哈希、模式、几何版本和相机序号/单调时间戳。`Camera.grab_fresh()` 超时时会返回旧帧，非空不代表新鲜；旧帧不得发布。`stones2` 直接采新帧，LED 模式只在一次性同卷暂存目录以 `fiducial_mode="off"` 调用 `run_capture`，不得直接作用于持久会话。两种模式共用发布器；返回真实帧 ID、SHA-256、采集时间、序号、几何版本与条件。核心 `d65fa3f3`＋`5e4a3f15` 已独立双项复核 APPROVE；接口集成见 `b8c1cf9f`。
- [x] **Step 3a:** 先测重启恢复、坏 manifest 报 503、磁盘/图像写入失败时原状态逐字节不变、重拍较早一手仍保留之后所有帧；图片使用唯一不可变文件名，成功校验后构建新 manifest 并原子替换，旧引用文件不得提前覆盖/删除。首帧的 SGF、几何文件及 sidecar 同样先暂存后发布。manifest 记录 schema、模式/类目、SGF 哈希、几何修订/文件哈希，帧记录 board hash、真实时间与序号；`stones2` 初始空盘为独立 frame kind、`led_point=null`，下一步进度不混作 LED 标签。`b8c1cf9f` 增加实际相机编号 pin、保存几何 stale/最近同帧 30 秒确认；聚焦四套 **172 passed**。
- [x] **Step 4:** 运行 `pytest -q tests/web_ui/test_admin_vision.py tests/test_camera_hub.py tests/test_led_service.py tests/test_baipu_capture.py tests/test_geometry_api.py`：根代理 **182 passed**。接口独立规格 APPROVE；质量复核发现断开后成功帧重试错误，`19b43509` 经 RED→GREEN 修复，只读幂等响应不依赖硬件，新采集/显式重拍的准备闸仍保留；质量复核最终 APPROVE。真实 Mac 摄像头/LED 尚未验收。

## Chunk 3: 数据集闭环与正式集成

### Task 5: 样本复核和不可变版本

- [x] **Step 1:** 先在 `tests/web_ui/test_admin_vision_dataset.py` 写无 LED `stones2` 的类目顺序固定为 `black=0, white=1`，LED 四类沿用 `katrain/vision/classes.py`；标签 ID、冻结 manifest 的类目和 `data.yaml` 必须完全一致。`70b4b823` 实现显式 schema 选择，不调用硬编码四类的 `write_data_yaml`。
- [x] **Step 1a:** 对受控目录中的原图、SGF、几何和逐帧 manifest 做完整性及 SHA-256 检查；用现有 `baipu_autolabel.frame_boxes` 生成可视叠图，`stones2` 的 `led_point=null` 只产生棋子类。LED 四类用 `detect_led_centroid` 验证真实亮点。拒绝空集、缺帧、不可读图、非有限/非归一化标注、无效类别、任一 split 为空和按文件名或随机切分连续帧；聚焦 RED→GREEN，独立规格和质量 APPROVE。
- [x] **Step 2:** `70b4b823` 在临时同卷目录生成图像、标签、`data.yaml` 和版本 manifest，记录固定 ID、生成时间、实际参数、类目、标定来源、代码/生成器版本与全部产物逐文件 SHA-256；全部验证通过后原子发布为只读目录。失败/取消保留既有状态，重复请求幂等。`15aa2b64` 根据 Ultralytics 官方路径解析去掉 cwd 相关 `path`，确保版本可搬移；数据集＋采集＋SGF **81 passed**。`b8c1cf9f` 增加受保护复核/冻结路由；冻结在生命周期锁内同步执行，此阶段未实现大任务取消 UI。
- [ ] **Step 3:** 前端改为真实状态、同帧预览、逐手确认与复核/冻结。真实 API 错误与令牌失效沿用后台处理。删除 Fixture 入口及纯示意数据，在正式 `AdminApp` 导航接入；运行 `npx vitest run src/admin/vision/VisionCapturePage.test.tsx src/admin/admin-entry.config.test.ts`、`npm run build:admin` 与 1440×900 本地预览。
- [ ] **Step 4:** 完成可用的本机相机+棋盘手动走查；若硬件不可用，只报告 fake 验证及未验收项，不能宣称切片已完成。

### Task 6: 测试机上传（外部授权关卡）

- [ ] **Step 1:** 在 `vision_transfer.py` 建立只允许指定测试机/目录的本地上传配置与手动确认流程，写 fake 传输测试覆盖容量不足、中断/断点恢复、取消、大小上限、逐文件 SHA-256 回执不一致及幂等；此步不得连接远端。只有远端回执逐文件全部等于冻结 manifest 才能标“已上传”，取消/中断的暂存目录不可视为完整版本。
- [ ] **Step 2:** 🛑 Fan 当场授权单次只读 SSH 后才核实测试机目标空间、账户与部署能力；另经当场授权才运行实际上传/写远端，并核对全部 SHA-256 后原子发布。不得复用过去 SSH 或部署的批准；未授权保持“待上传”。
- [ ] **Step 3:** 真实测试机验收和 Fan 视觉验收后才记完成；push/部署另请当场批准。无授权时更新 `codex-report.md` 并顺序做下一切片的本地 HTML/Fixture，不越权。
