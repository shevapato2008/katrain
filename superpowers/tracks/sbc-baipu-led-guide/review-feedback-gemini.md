## 总评 (go-with-changes) + 整体架构清晰且逻辑严密，但在软硬件结合的时序（相机缓冲、防人手入镜）以及数据版本一致性上存在致命盲区。

## Top 3 必改（最高优先）
1. **[Critical] 问题：OpenCV 硬件帧缓冲导致的“照片状态滞后”** — 证据(plan.md §4.2) — 建议：`cv2.VideoCapture` 在 Mac/Linux 底层默认有 3~5 帧的环形缓冲。点亮 LED 后 `wait 150ms`，然后调用 `.read_frame()`，极大概率拿到的是 150ms **前**（LED 还没亮时）缓冲队列里的旧帧。**必须在抓帧前显式清空缓冲**：在 `capture_to` 中循环调用 `cap.grab()` 5 次后再调用 `cap.retrieve()`，或者在等待的 150ms 内保持抽帧丢弃，否则 YOLO 会拿到全黑的错位照片。

2. **[High] 问题：Manifest 与几何锁定的时间版本脱节** — 证据(plan.md §4.2 & §5) — 建议：`autoresearch` 依赖 `manifest.json` 加 `geometry_lock.npz` 生成包围盒。但 `geometry_lock.npz` 是全局覆写的。如果明天重新标定了相机（移动了设备），昨天采集的谱在今天生成标签时，就会全盘错位。**必须在 `POST /baipu/capture` 首帧时，把当时的 `geometry_lock.npz` 核心字段（特别是 361 points 数组）拷贝/固化进本次采集的 `manifest.json` 中**，或者拷贝一份 `geometry.npz` 到 `{out_dir}/{game_id}/` 下。

3. **[High] 问题：带灯拍 (方案 B) 的人手入镜风险** — 证据(plan.md §2.3 CAPTURE 状态) — 建议：时序是 `点亮 k+1 → 等 150ms → 拍照`。人眼看到灯亮（特别是快棋手），条件反射会立刻伸手落子。这 150ms 内手极易切入画面，污染训练数据。**必须在前端增加听觉/视觉屏障**：拍照完成前，屏幕显示“正在拍照请勿伸手”；拍照完成后（`/baipu/capture` 接口返回 200），播放一声清脆的**“咔嚓/滴”音效**（Shutter sound），提示用户可以落下一子。

## 详细发现
- **[Medium] 空盘带灯帧缺失风险**
  - 类型：遗漏 / correctness bug
  - 证据：plan.md §2.3 "首帧——可选在 GUIDING(0) 拍一张(配置开关，默认关)"
  - 建议：对于 YOLO 训练，空棋盘上只有一颗 LED 亮起的负样本（无黑白子干扰）至关重要。首帧 `k=0` 的状态 **绝不能是“默认关”**。必须强制在进入 `GUIDING(0)` 且用户第一次点击确认 **前**，抓拍第一张照片（`stones_through_move: 0`, `next_move: moves[0]`）。

- **[Medium] 队列线程安全的过度设计**
  - 类型：架构风险 / 更优方案
  - 证据：plan.md §3.1 "LedService... threading.Lock 保护入队"
  - 建议：Python 的 `queue.Queue` 本身就是线程安全的。额外加 `threading.Lock` 去保护 `put_nowait` 毫无意义，反而增加死锁面。直接删掉 Lock，用 `try: q.put_nowait() except queue.Full:` 即可。清空旧数据用 `try: q.get_nowait() except queue.Empty:` 配合 `put`。

- **[Low] 前端重建 Go 逻辑的隐患**
  - 类型：更优方案
  - 证据：plan.md §1.1 "前端共享 util goBoard.ts 算"
  - 建议：虽然复用了 `LiveBoard` 逻辑，但在 TS 中维护完整的围棋气/提子状态机始终有 Edge Case 风险（如打劫、特殊 SGF 异常）。更优且更稳的做法是：在进页时调用后端 `api/v1/baipu/load`，**由后端 Python (KataGo/SGF 引擎) 一次性计算好这盘棋每一步的 {row, col, color, removed_stones[]}**，生成一个完整的 JSON Array 发给前端。前端只做“哑渲染”，彻底消灭 TS 算错提子的可能。

## 对我们关键决策(§4)的判断
- 决策 1 (坐标系): **同意**。规范到 `row=0 顶部` 并统一入口是非常明智的防御性设计，消除了多模块对坐标系解释的歧义。
- 决策 2 (提子在前端算): **异议**。理由见上文详细发现。替代方案：改由后端解析 SGF 时顺带算好每步提子，前端退化为 JSON 播放器。不过为了复用现有的前端提子逻辑（打谱也在用），当前方案可接受，属于 Trade-off。
- 决策 3 (相机互斥独立): **同意**。`RuntimeError` 硬互斥可以防止 USB 带宽耗尽。
- 决策 4 (带灯拍时序): **异议**。虽然逻辑对，但物理世界中人的反应很快，必然导致手入镜。替代方案：加入明确的“拍照完成”声音反馈。
- 决策 5 (19x19/pass处理): **同意**。
- 决策 6 (Ko不校验): **同意**。Kiosk 模式下信任 SGF 是 MVP 的务实选择。
- 决策 7 (几何识别迁移): **同意**。只存 8 字段保证了与 `autoresearch` 仓库的二进制兼容性。
- 决策 8 (选谱复用): **同意**。

## 你认为我们漏掉的（§3/§10 之外的新问题）
1. **环境光鲁棒性（曝光问题）**：相机在看 LED 灯时，如果曝光时间(Exposure Time)由系统自动控制，LED 的强光可能导致相机自动下调全局曝光，使得棋盘上的黑子彻底融入阴影变成死黑。**需要确保在使用 `CameraManager` 采集时，相机的自动曝光(Auto Exposure)被锁定或手动指定了一个不会欠曝的值**。
2. **非法手动重置 (Reset/Abort)**：如果在摆谱中途用户直接点击“退出”离开，LED 必须被强制重置（`led.clear()`）。计划中前端有做 `退出→clear()`，但如果浏览器直接被关闭或刷新，后端需要一个机制检测 Session 断开并熄灭 LED，否则由于 Kiosk 是长运行设备，LED 可能会亮一整天直到下一人使用。可以在后端的 `/api/v1/led/clear` 之外，给 `_lifespan_board` 补充一个基于超时或 WebSocket disconnect 的兜底灭灯策略。