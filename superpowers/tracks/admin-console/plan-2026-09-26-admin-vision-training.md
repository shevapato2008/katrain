# 视觉实验室 · 训练与模型 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development or superpowers:executing-plans in the existing worktree. Steps use checkbox (`- [ ]`) syntax. Fan 指定顺序旅程；独立 GPT-6 Astra max 可代设计/方案裁定，不能代远程授权。

**Goal:** 对已冻结校验数据集，显式在测试机的预留单 GPU 运行 YOLO11，观察真实日志/指标并保存不可变模型版本；无授权时只做本地设计、Fixture 与可注入执行测试。

**Architecture:** 独立 Astra 已选择现有 admin 内的单一协调器管理独立训练子进程/进程组，一次最多一个 run，第二次请求直接 busy；不引入通用队列，不在 ASGI 请求进程内加载 CUDA 或 monkeypatch。默认关闭训练能力；路径由服务器固定根和 allowlist ID 解析，不收 shell、任意参数或客户端路径。每次远端连接/写入/真实训练均另经 Fan 当场授权。

**Tech Stack:** React/Vite/Vitest、FastAPI、现有 `katrain/vision/tools/train_model.py`、受控 subprocess、pytest。

---

规格：[视觉实验室 B 段](./spec-2026-09-26-admin-vision-lab.md)。依赖：采集冻结契约与真实测试机上传完成后，才有可训练输入。性能 Grafana 的外部阻塞不允许绕过，但不阻塞本模块本地工作。

## 文件职责

- `slice4/design/admin-vision-training.html`：claude-design 静态 HTML，unknown/running/failed/completed 设计状态与深浅主题。
- `src/admin/vision/training/{TrainingPage.tsx,TrainingPage.css,TrainingFixture.tsx,fixture.tsx}`、`admin-vision-training-fixture.html`：隔离可视演示；正式入口不包含样例数据。
- `slice4/vision-training-contract.md`：运行状态/权限/字段/日志预算与外部启用条件，四图通过后冻结。
- `katrain/web/admin/vision_training.py`：单运行协调、UUID 目录、状态持久化及取消；不混入相机 runtime。
- `katrain/web/admin/vision_training_worker.py`：独立 worker，allowlist 输入、真实 epoch/metrics/日志及产物校验。
- `katrain/vision/tools/train_model.py`：最小可选 `project`/固定输出适配；保持既有 CLI 默认兼容。不沿用 autobatch/MPS，也不信完成打印。
- `katrain/web/admin/routers/vision_training.py`、`app.py`、`settings.py`：受保护、默认禁用的真实接口；无 GET 隐式启动。
- `src/admin/vision/training/TrainingDashboard.tsx`、`api/client.ts`、`VisionDashboard.tsx`：真实整合、同 run 响应代际与 Fixture 删除。
- `tests/web_ui/test_admin_vision_training.py`、`tests/test_vision/test_train_model.py`、`src/admin/vision/training/TrainingPage.test.tsx`：本次行为与重要回归。

## Chunk 1: HTML → Fixture → 视觉

### Task 1: 训练操作 HTML

- [x] **Step 1:** 按已有后台字号/楷体/双主题，用 claude-design 落 `slice4/design/admin-vision-training.html`。主 Operate、次 Monitor：创建运行、当前 run 日志/指标/取消、模型版本；未知状态不出现假 GPU 名称、已上传数据或成功标记。
- [x] **Step 2:** 用 ui-ux-pro-max 检查表单标签、禁用说明、焦点、错误出口和状态不仅靠色。1440×900 查看 unknown/dark、running/dark、failed/dark、completed/light；示例运行均明确“设计示意”，不连网络。
- [x] **Step 3:** 独立 Astra max 看真实截图，修首屏 CTA/版本行和重要16–17px字号后，代表完成态最终 **APPROVE**。默认先单卡，不宣传 2×3090 DDP；三个计划 chunk 同时 Approved。当前只允许隔离 Fixture，不进入后端。

### Task 2: 隔离前端 Fixture

- [x] **Step 1:** unknown/running/failed/completed 页面与创建/取消确认测试；示例文案只在 designOnly 下出现。
- [x] **Step 2:** 页面和隔离 Fixture RED→GREEN，无真实训练/下载；控制器独立于正式入口。
- [x] **Step 3:** 5174真实 Chromium 四态1440×900，参考/实现/并排/叠加/差异见 [四图入口](./slice4/design/training-fourup.html)。独立 Astra max **APPROVE**，差异限免责声明/状态图标。
- [x] **Step 4:** 根代理与独立审核16测试通过，局部ESLint/build:admin通过、浏览器0error；正式只构建admin.html。代码本地提交 `f771a792`，独立SPEC+QUALITY APPROVE。

## Chunk 2: 本地真实契约与可注入执行

### Task 3: 固定训练输入与生命周期

- [x] **Step 1:** 四图 APPROVE 后冻结 [训练契约](./slice4/vision-training-contract.md)：默认禁用、test专用、固定输入/参数/预算、单运行生命周期/取消、best.pt与完整manifest发布；不授权外部操作。
- [ ] **Step 2:** 先写 fake worker 测试：默认禁用、未授权拒绝、不可信 ID/路径/参数拒绝、冻结 manifest/hash/schema 校验、实际解析后的可信本地权重缺失/哈希不匹配立即拒绝（禁止下载回退）、单 GPU allowlist、重复请求幂等、并发第二 run busy、启动失败保留状态。现有 `resolve_model` 会优先同名 `models/` 文件，必须验证最终真实文件，不能只验证请求路径。
- [ ] **Step 3:** `/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/web_ui/test_admin_vision_training.py` 先 RED；最小实现受控 roots 与可注入 worker 后 GREEN。无实际进程/网络/GPU 操作。
- [ ] **Step 4:** 增加同 run 指标与日志、取消/退出/重启 interrupted、失败保留旧模型、成功 best.pt/schema/hash/manifest 原子发布红测；不把 exit=0 或 stdout “complete”单独当成功。manifest 必须核对实际 imgsz/权重/类目/增强/seed/GPU/batch/代码版本/数据集哈希/best.pt 哈希，不只检查文件存在。取消只有确认本 run 进程组退出才能 `cancelled` 并释放运行占用；“已发取消但未退出”仍 busy。重启后旧进程退出状态未核实时不允许新 run，写对应 fake 测试。
- [ ] **Step 5:** 补独立 worker 与 `train_model.py` 固定 project/name、显式 batch/device、最终解析后的可信本地模型输入适配；在启动前校验该文件的实际哈希，缺失/不匹配拒绝且无隐式下载。测试启动 argv 无 shell，取消只针对本 run 进程组并确认退出才释放。不能影响 KataGo；本地仅 fake 子进程测试，不启动真实训练。
  - 已由独立 Astra 裁定的实际最小兼容边界：仅已核实 Ultralytics8.4.34 的 worker 内导入前设置受控 `YOLO_CONFIG_DIR`、OFFLINE/AUTOINSTALL；`amp=False/plots=False`（避免AMP检查额外下载）、跳过无图 dataset 字体下载入口、禁用外部 integration callbacks，保留默认回调。固定本地 YAML 拒绝 URL/download 脚本。真实版本不符停用待核对；不改ASGI/用户全局配置，不宣传系统级网络隔离，实际amp/plots写manifest；显存增加待真实Batch验证。
- [ ] **Step 6:** 聚焦训练/原有 CLI 回归转 GREEN；独立规格/质量复核高风险进程与完整性边界，精确提交。不能宣称测试机训练完成。

### Task 4: 正式接口和前端

- [ ] **Step 1:** 路由鉴权/禁用/轮询/有界错误/令牌失效红测，再接默认禁用训练服务；只有test环境＋显式开关＋经核实配置才能启用，Mac local始终disabled/unknown，无暗中SSH/RPC。操作者经独立授权隧道和不同origin/端口登录测试机后台。读操作不打开 GPU，隧道授权不等于训练授权。
- [ ] **Step 2:** 前端 fetch 同 run 真实数据，serialized poll ≤每2秒，旧 run 响应不覆盖新选中项。指标 null 显示“尚无验证指标”，不能填 0。启动/取消带明确确认与 disabled 原因。
- [ ] **Step 3:** 删除本模块 Fixture 入口、示例数据和控制器，保留纯页面；运行聚焦 Vitest、`npm run build:admin`、scoped ESLint、1440×900 未启用真实空态。数据/运行记录不进入公共 Galaxy 数据库。

## Chunk 3: 测试机真实启用与验收

### Task 5: 逐次外部授权

- [ ] **Step 1:** 🛑 Fan 当次只读 SSH 授权后核实 home-ubuntu 账号、固定根目录/同卷发布/磁盘、依赖、可信权重与输入数据集回执；核实 GPU 映射、KataGo 实际占用和预留单卡。不默认抢占，不能仅依据 GPU 内存当前空闲就视为可用。
- [ ] **Step 2:** 🛑 另经 Fan 当次部署/远端写入授权配置服务；保持启动训练仍需明确操作与授权。无可预留 GPU 则保持 unavailable，不绕过资源闸。
- [ ] **Step 3:** 🛑 Fan 单次真实 GPU 训练授权后，验证 epoch/日志/指标来自同 run，取消只停本 run，模型哈希/schema 与训练 manifest 一致；记录实测而非 fake 证据。
- [ ] **Step 4:** 用户视觉/设备验收后才完成切片。push 另经当场批准；未授权则写 codex-report 并顺序进入模型部署/诊断的本地设计，不代授权。
