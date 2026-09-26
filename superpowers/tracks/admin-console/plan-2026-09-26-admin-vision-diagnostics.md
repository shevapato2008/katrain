# 视觉实验室 · Mac 模型与七阶段诊断 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development or superpowers:executing-plans in this existing worktree. Steps use checkbox (`- [ ]`) syntax. 独立 GPT-6 Astra max 可代本地方案/视觉裁定，不能代真实设备、下载、远程连接、写库、push 或部署授权。

**Goal:** 选择本机可信登记模型、显式激活/回滚，观察现有真实识别链的七阶段同批次快照，快速定位棋盘/棋子识别问题。

**Architecture:** 复用 admin 的 CameraHub/GeometryLock 和 `VisionService/InProcessAdapter` 单一 viewer 实例；只加可选只读 observer，不复制算法、不重复推理或有状态赋值。纯模型校验复用训练产物规则，登记摘要独立固定可信来源；默认禁用、受控本机根、显式确认操作。远程拉取暂禁用，真实设备与模型验收仍外部关卡。

**Tech Stack:** React/Vite/Vitest、FastAPI、OpenCV、现有 StoneDetector/BoardStateExtractor/FrameAverager、pytest。

---

规格：[视觉实验室 C](./spec-2026-09-26-admin-vision-lab.md)，算法挂点与独立裁定：[勘察记录](./slice5/recognition-observation-notes.md)。前序训练本地集成已提交 `2efca8e2`；真实上传/训练未验收，不编造本机可用模型。使用 @claude-design → @ui-ux-pro-max → 隔离Fixture与四图 → 本地契约 → 后端 → 真接口 → 删除Fixture。

**计划复核：** 独立 GPT-6 Astra max 对三个chunk分别 Approved，无阻断项；当前只允许Task1 HTML，视觉门前不进入后端。比例化计划记录准确文件/行为/验证命令，不重复抄写整份未来生产代码。

## 文件职责

- `slice5/design/admin-vision-diagnostics.html`、`design-notes.md` 与同尺寸截图：Monitor/Inspect、七格观察和模型操作设计。
- `src/admin/vision/diagnostics/{DiagnosticsPage.tsx,DiagnosticsPage.css,DiagnosticsFixture.tsx,fixture.tsx,types.ts}`、`admin-vision-diagnostics-fixture.html`：纯页/隔离演示；正式入口不包含业务样例。
- `slice5/vision-diagnostics-contract.md`：状态、模型来源、同批次身份、资源预算、权限/失败与删除条件，四图通过后冻结。
- `katrain/web/admin/vision_model_artifact.py`、`vision_training.py`：从训练 `_artifact_info` 抽纯校验，共享固定文件集/SHA/schema/实际参数/model ID；训练继续提供冻结spec独立比对，本地登记用可信manifest摘要固定来源，不实例化训练协调器或复用“自证spec”。
- `katrain/web/admin/vision_models.py`：固定根与受控登记的版本目录、current/previous原子状态、显式激活/回滚；列表不导入torch，浏览器只传登记ID，不接受任意路径/PT上传。
- `katrain/vision/diagnostic_observation.py`：不可变有界快照、框/网格只读序列化及原始网格诊断投影，不控制设备/模型。
- `camera.py`、`web/core/camera_hub.py`：同一次锁内返回原帧/camera seq/单调时间，不暗中重连；只供观察的附加读取，原接口默认不变。
- `temporal.py`：可选贡献帧身份与实际平均一起推进/重置；未观察时原行为不变。
- `stone_detector.py`、`worker_inprocess.py`：可选NMS后只读出口、同轮局部结果打包，单次真实赋值/投票；observer错误不改变识别结果。只在诊断开启时复制/编码。
- `config_service.py`、`inference/ultralytics_backend.py`：修通配置→worker→detector→实际backend imgsz，旧默认960；不修改ONNX/RKNN固定输入规则。
- `service.py`：附加诊断专用 `stop_diagnostic() -> bool`，join超时保留alive句柄；通用生产stop不改。
- `web/admin/vision_diagnostics.py`、`vision_runtime.py`、`routers/vision_diagnostics.py`、`app.py`：本机显式开启、生命周期互斥、admin Bearer/no-store接口；不混进公共Galaxy/kiosk API。
- `src/admin/vision/diagnostics/DiagnosticsDashboard.tsx`、`api/client.ts`、`VisionDashboard.tsx`、流程导航：真实集成、2Hz串行单快照、代际/Abort/401与Fixture删除。
- 测试：`tests/test_vision/test_diagnostic_observation.py`、`test_shared_camera.py`、`test_temporal.py`、`test_stone_detector.py`；`tests/web_ui/test_admin_vision_models.py`、`test_admin_vision_diagnostics.py`；`diagnostics/DiagnosticsPage.test.tsx`、`DiagnosticsDashboard.test.tsx`。

## Chunk 1: HTML、Fixture与视觉

### Task 1: 真实语义的观察设计

- [ ] **Step 1:** 按claude-design落HTML，主Monitor次Inspect。沿用当前楷体/铜夜蓝日、关键16–17px与解释13–14px；模型/开始停止操作紧凑，七阶段首屏比较，点击放大。未连接/就绪/运行/过期四态，所有合成图明确设计示意，不连网络或设备。
- [ ] **Step 2:** ui-ux-pro-max检查状态不仅靠颜色、focus/禁用原因、批次公共身份、平均贡献帧说明；第五格标“诊断派生”，参考/落子确认未参与不冒称生效。模型激活/回滚/开始带确认，下载禁用待授权。
- [ ] **Step 3:** 1440×900 Chromium四态、0控制台错误；独立Astra实际看图裁定后才进入Fixture。

### Task 2: 隔离Fixture与四图

- [ ] **Step 1:** 先写纯页面状态、确认、放大、过期整份快照测试，运行 `npx vitest run src/admin/vision/diagnostics/DiagnosticsPage.test.tsx` 确认RED；实现HTML对应纯页＋独立控制器/入口后GREEN。样例只在Fixture，不触设备或模型。
- [ ] **Step 2:** Vite5174四态1440×900参考/实现/并排/叠加/差异，记录字段/语义/字体/间距差异。独立Astra视觉APPROVE后冻结契约；此前不做本切片后端。
- [ ] **Step 3:** 聚焦Vitest、局部ESLint、`npm run build:admin` GREEN；正式入口仍只有admin.html，本地提交设计/Fixture。

## Chunk 2: 可注入真实链与本机生命周期

### Task 3: 可信本机模型与真实尺寸

- [ ] **Step 1:** 写纯产物校验/登记摘要、坏hash/schema、越界路径/symlink、未登记ID、默认无torch、加载失败保留current/previous与持久化失败测试，先RED。登记配置来自本机服务端已核实JSON（固定root、model_id+manifest_sha256），不信浏览器路径/manifest自证。
- [ ] **Step 2:** 抽并复用纯产物校验；训练调用冻结spec，登记调用可信摘要＋内部一致性。登记只读列表和显式模型操作，固定根、每模型≤1GiB、列表≤100；当前/前一版本只原子变更状态，不删模型文件。
- [ ] **Step 3:** 激活一次实际加载核对YOLO.names/schema数量顺序和backend实际imgsz。修通imgsz配置，未指定仍960；停止旧诊断确认退出后才加载，失败不替换current/previous，明确诊断已停，手动可重启旧版。默认不加载/启动，无隐式下载。
- [ ] **Step 4:** `/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/web_ui/test_admin_vision_models.py tests/web_ui/test_admin_vision_training.py tests/test_vision/test_stone_detector.py` GREEN；新边界聚焦独立审查，本地提交。只注入fake，不加载真实权重。

### Task 4: 同批次七阶段只读出口

- [ ] **Step 1:** 先测原帧身份原子读取、平均贡献身份随reset同步、observer前后原识别结果相同/只推理赋值一次、raw框不被dedup修改、运动/断线不拼旧结果、预算超限、诊断投影原始坐标不回灌，RED。
- [ ] **Step 2:** 单一observer采同轮raw/纯warp/真实平均增强input、NMS后框/业务去重阴影剔除框、一次真实赋值/最终发布棋盘。保留keep/sustain/实际赋值输入语义，第五格仅最近点只读投影；缺参考/历史初始化明确标注。
- [ ] **Step 3:** 最新和生成中各一份，发布≤2Hz；三底图长边≤960、每JPEG≤1MiB、每阶段≤4096框、总≤8MiB。运动/错误保持整份旧快照＋stale，不拼接；不保存视频/原图历史，不改原推理采样配置。
- [ ] **Step 4:** `pytest -q tests/test_vision/test_diagnostic_observation.py tests/test_vision/test_shared_camera.py tests/test_vision/test_temporal.py tests/test_vision/test_stone_detector.py tests/test_vision/test_board_state_golden.py` GREEN；独立聚焦审核来源/结果等价后本地提交。

### Task 5: 严格诊断生命周期与API

- [ ] **Step 1:** 先写test/prod/默认禁用、Bearer/no-store、确认start/stop/activate/rollback、同camera/model/geometry代际、stop超时仍busy、capture/calibrate/disconnect互斥红测。GET只观察，不打开相机/模型/推理线程。
- [ ] **Step 2:** 附加诊断专用strict stop保留超时alive引用，确认退出才换版本/释放操作；runtime共享锁内串行协调。viewer不绑对局、不启monitor、不发送落子/LED。相机已连接且几何已验证、可信当前模型可用才显式start；thread失败/断线真实error，无自动重启。
- [ ] **Step 3:** admin独立路由 `GET /vision/diagnostics/status|models|snapshot`、`POST /start|stop|activate|rollback`，strict ID/confirmation、no-store与路径剔除。已登记文件哈希在激活核对，不随2Hz状态读取全量hash。
- [ ] **Step 4:** `pytest -q tests/web_ui/test_admin_vision_diagnostics.py tests/web_ui/test_admin_vision.py tests/web_ui/test_admin_auth.py` GREEN；局部Black/diffcheck、独立规格/质量审查，本地提交。绝不以fake替硬件验收。

## Chunk 3: 真接口整合与授权验收

### Task 6: 正式页面与Fixture删除

- [ ] **Step 1:** 写真实disabled/无模型/同批次原子替换、stale、确认操作、Abort/旧代际/401和≤2Hz不重叠测试RED；接真实API后GREEN。目录初次/手动读取，周期只status/snapshot；公开Galaxy不引入本模块。
- [ ] **Step 2:** 正式三段流程导航、纯页面真数据、模型/几何来源与各阶段说明；切页不暗中断开相机，诊断显式停止出口清晰。删除Fixture入口/控制器和样例，运行聚焦Vitest、scoped ESLint、build:admin；1440×900真实disabled代表预览与独立评审，本地提交。

### Task 7: 真实模型/设备与外部关卡

- [ ] **Step 1:** 🛑 Fan当次授权后核实训练真实版本、固定根/可信摘要/可搬移产物；另获下载/本机登记权限才执行模型拉取。当前不能标“已下载”。
- [ ] **Step 2:** 🛑 Fan明确设备/加载操作后在Mac手动连接标定、激活、七阶段实时识别/回滚；记录真实fps/设备/模型hash/贡献帧与失败保留，用户验收后才记切片完成。
- [ ] **Step 3:** push/部署仍当场独立批准。未授权时写codex-report明确本地完成项/外部未验收项；不得把“所有未完成slice”理解为越过授权或自行扩张未定的金镜像/盒子等模块。
