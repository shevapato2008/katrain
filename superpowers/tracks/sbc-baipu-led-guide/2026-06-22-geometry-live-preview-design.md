# 实体棋盘几何实时预览设计

## 1. 背景与目标

现有 P5 已经用单一 `CameraHub`、LED 四角加九星位扫描和 RANSAC 建立 `GeometryLock`，并能在摄像头位移后进入 `degraded`。当前缺口在 SBC 前端：用户只能看到未经标注的原始视频，无法直观看到系统最终采用的四角、19×19 网格和 361 个落子点，也无法在位移后通过同一界面完成重标定。

本功能把几何标定变成可视化的产品流程：短时间同时显示原始摄像头画面和俯视矫正画面，在原始画面上实时呈现 LED 锚点和最终几何，在矫正画面上呈现规则网格；位移后保留失效几何作为诊断参照，要求用户清空棋盘并确认后才重新闪灯。

## 2. 范围

### 2.1 包含

- 原始 HBV 摄像头 MJPEG 实时预览。
- 原始画面上的四角、网格线、361 点和人视角角点标签。
- 标定过程中逐个显示已发现的 LED 锚点。
- 使用当前 `GeometryLock.M` 的俯视矫正 MJPEG 实时预览。
- 矫正画面上的 19×19 网格和 361 点。
- `required`、标定中、`ready`、`degraded`、失败和摄像头断开状态。
- 实体功能入口自动展示标定工作区，设置页提供手动重标定入口。
- 摄像头位移后自动提示，但必须由用户确认空盘后才能重新闪灯标定。

### 2.2 不包含

- 新的棋盘检测算法、第二套摄像头读取或新的坐标系。
- WebRTC、WebSocket 视频传输或逐帧同步元数据。
- YOLO 棋子框可视化和模型训练。
- 长时间对局中的双视频常驻显示；该页面只用于短时安装、校准和诊断。

## 3. 复用边界

以下现有实现是唯一真值来源，不重复实现：

- `CameraHub`：原始帧唯一来源。
- `CaptureService.read_frame()`：两个预览流读取当前帧。
- `LedGeometryCalibrator`：四角、九星位、颜色回退、LED 时序和 RANSAC。
- `GeometryLock`：`corners`、`points[19][19]`、`M`、`Minv`、`out_size`。
- `GeometryCalibrationService`：会话状态、取消、原子保存、热更新和漂移监测。
- `geometry_drift.py`：位移阈值与连续帧判断。
- `board_qa.py` / `worker_inprocess.py`：`cv2.warpPerspective` 用法。
- `show_grid.py`：角点、网格和落子点可视化语义参考。
- `GeometryContext`、`PhysicalBoardGuard`、`VisionSetupPage`：现有前端入口和轮询机制。

前端只缩放后端给出的摄像头像素坐标，不推导新的单应矩阵。

## 4. 后端接口设计

### 4.1 标定状态扩展

`GET /api/v1/geometry/status` 在现有字段上增加：

```json
{
  "geometry_revision": 3,
  "detected_anchors": [
    {"row": 0, "col": 0, "x": 569.7, "y": 984.1, "color": "green"}
  ]
}
```

- 每次开始标定时清空 `detected_anchors`。
- `LedGeometryCalibrator` 每成功定位一个锚点，通过观察回调通知 `GeometryCalibrationService`。
- 回调只发布既有检测结果，不改变标定算法。
- `geometry_revision` 仅在新几何成功提升为当前锁时递增。
- 状态读取返回快照，避免标定线程与请求线程共享可变列表。

### 4.2 几何布局

新增 `GET /api/v1/geometry/layout`：

```json
{
  "revision": 3,
  "phase": "ready",
  "stale": false,
  "frame": {"width": 1920, "height": 1080},
  "out_size": 950,
  "corners": [
    {"row": 0, "col": 0, "label": "左上", "x": 569.5, "y": 983.3},
    {"row": 0, "col": 18, "label": "右上", "x": 306.1, "y": 216.0},
    {"row": 18, "col": 18, "label": "右下", "x": 1670.3, "y": 204.5},
    {"row": 18, "col": 0, "label": "左下", "x": 1397.0, "y": 979.9}
  ],
  "points": [[[569.5, 983.3]]]
}
```

- `points` 实际固定为 `[19][19][2]`，行从人视角上到下，列从人视角左到右。
- `frame` 来自当前 CameraHub 帧，而不是启动参数，确保叠加缩放准确。
- `stale=true` 表示 `degraded` 或当前会话尚未完成新标定，但仍有上一有效锁。
- 没有任何有效锁时返回 `409 geometry_not_available`。
- 布局只在 revision 或 phase 变化时重新获取，不跟随视频帧轮询。

### 4.3 俯视矫正流

新增 `GET /api/v1/geometry/warped-stream`：

- 从 `CaptureService.read_frame()` 获取共享帧。
- 用当前 `GeometryLock.M` 和 `out_size` 执行 `cv2.warpPerspective`。
- JPEG quality 65，目标 5 fps；只有浏览器连接时才进行变换和编码。
- `ready` 和 `degraded` 都可显示；后者用于观察旧几何偏移，但前端必须用红色失效状态覆盖。
- 没有有效锁时在建立流之前返回 `409`。
- 客户端断开时生成器立即结束，不保留后台编码线程。

原始流继续使用现有 `/geometry/stream`，不新增相机实例。

## 5. 前端组件设计

### 5.1 共享标定工作区

新增 `GeometryCalibrationWorkspace`，由以下两处复用：

- `PhysicalBoardGuard`：实体功能需要标定或检测到位移时，直接显示工作区。
- `VisionSetupPage`：从设置页进入时显示同一工作区，并提供返回按钮。

这样自动入口与手动入口使用完全相同的画面、状态和动作，不再维护两套标定交互。

### 5.2 双画面布局

- 左侧卡片标题“摄像头原始画面”，显示 `/geometry/stream`。
- 右侧卡片标题“俯视矫正画面”，显示 `/geometry/warped-stream`。
- 横屏左右并排；窄屏上下排列。
- 两个画面均保持完整内容，不裁剪。
- 右侧没有几何时显示“完成 LED 标定后生成俯视画面”，而不是错误图标。

### 5.3 原始画面叠加层

`CameraGeometryOverlay` 使用透明 Canvas 覆盖 `<img>`：

- 根据容器尺寸和原始帧宽高计算 `object-fit: contain` 的统一缩放与上下/左右留白偏移。
- `ready`：半透明绿色 19 条横线、19 条纵线和 361 个小圆点。
- 四角使用不同颜色，并标记“左上、右上、右下、左下”；标签表示人坐位置，不表示相机画面方向。
- 星位点略大，用于快速检查整体方向。
- 标定中：仅绘制 `detected_anchors`，已发现为实心点，当前进度在状态区显示。
- `degraded`：保留旧网格但统一改为红色，明确显示它只用于对比，不能继续实体棋盘功能。

缩放计算和绘图模型提取为纯函数，便于单元测试；组件不自行解释坐标或计算透视。

### 5.4 矫正画面叠加层

矫正流固定为 `out_size × out_size`，Canvas 按等间距绘制完整 19×19 网格：

- 正常为半透明绿色。
- `degraded` 为红色，并显示“旧几何矫正结果”。
- 四角显示 A19、T19、T1、A1，中心显示 K10，辅助验证坐标方向。

### 5.5 状态与操作

- `required`：显示“请清空棋盘”，按钮“已清空，开始自动标定”。
- 标定中：禁用启动按钮，显示阶段、`current/13`、取消按钮和逐点锚点结果。
- `ready`：显示置信度、RMS、最大残差、13/13；实体入口自动继续，设置页保留预览和“重新标定”。
- `degraded`：顶部红色提示“摄像头或棋盘位置已变化”，保留红色旧网格；按钮要求再次确认空盘。
- `failed`：保留已找到锚点和失败原因，可重试；后端继续保留上一有效锁。
- 摄像头断开：两侧画面显示断开状态，禁止启动标定。
- LED 未连接：允许看画面和旧布局，但禁止 LED 标定并明确提示串口状态。

自动重定位的含义是自动检测位移并自动弹出上述工作区；系统绝不在棋盘可能有棋子时自行闪灯。

## 6. 数据流与状态机

```text
实体功能入口
  ├─ ready + session_calibrated ─────────────→ 进入功能
  └─ required/degraded/failed ───────────────→ GeometryCalibrationWorkspace
                                                   │
用户确认空盘 ── POST /geometry/calibrate ──────────┤
                                                   ├─ status: detected_anchors
CameraHub ── raw stream ───────────────────────────┤→ 左侧画面 + Canvas
GeometryLock ── layout ────────────────────────────┤→ 四角 + 361 点
CameraHub + GeometryLock.M ── warped stream ──────┤→ 右侧画面 + Canvas
                                                   │
geometry_drift 连续超阈值 ── phase=degraded ──────┘
```

活动期状态轮询 300 ms；`ready` 时 1 s，以便位移后及时显示工作区。视频流和 JSON 状态相互独立，状态轮询失败不会销毁当前视频元素。

## 7. 错误处理

- 任一 MJPEG 流错误只显示对应卡片的重试按钮，不影响另一画面。
- `layout` 短暂失败时保留最后布局并标记失效，不清空用户正在查看的诊断信息。
- 标定忙返回 409 时前端转为跟随现有任务，不重复启动。
- 取消或页面卸载时不隐式取消其他页面已经启动的标定；只有显式“取消标定”调用 cancel。
- 后端无论成功、失败、取消或异常都执行 LED clear。
- `degraded` 状态阻断所有依赖实体棋盘的功能，直到新标定成功。

## 8. 性能约束

- 原始流与矫正流各目标 5 fps，只用于短时标定页面。
- 前端不复制视频帧到 Canvas，只在透明 Canvas 绘制静态几何。
- `layout` 不按帧传输，361 点 JSON 仅在 revision/phase 变化时刷新。
- 不启动第二个 OpenCV capture，不引入 WebSocket/WebRTC。
- 页面离开后两个 `<img>` 被卸载，后端流生成器随连接关闭。

## 9. 测试与验收

### 9.1 后端自动化

- 标定观察回调按成功顺序发布锚点，失败不发布伪坐标。
- status 返回锚点快照并在新任务开始时清空。
- layout 正确序列化四角、19×19 点、帧尺寸、revision 和 stale。
- 没有有效几何时 layout/warped-stream 返回 409。
- warped-stream 使用当前 `M`、`out_size`，编码后可解码为正方形帧。
- degraded 时 layout 保留旧几何且 `stale=true`。

### 9.2 前端自动化

- `contain` 缩放在横向和纵向留白时都准确。
- ready 绘图模型包含 38 条网格线、361 点、4 个角点和 9 个星位。
- active 状态只显示已发现锚点。
- degraded 使用红色失效样式并阻断子页面。
- 用户确认空盘后才调用 calibrate；取消、失败、摄像头/LED 不可用状态正确。
- `PhysicalBoardGuard` 和 `VisionSetupPage` 都渲染同一工作区。

### 9.3 浏览器与真机验收

- SBC 前端同时显示 HBV 原始画面和俯视矫正画面。
- 标定时四角和九星位按识别顺序出现在原始画面。
- 成功后四角标签方向正确，361 点与实体交叉点重合，矫正画面为规则正方形。
- 轻移摄像头后 3–6 秒内旧网格变红并弹出重标定提示，期间不自动闪灯。
- 用户清盘确认后重新扫描，两个画面恢复绿色正确网格。
- 页面离开后摄像头仍由同一个 CameraHub 服务采集，不发生设备占用冲突。

## 10. 成功标准

用户只通过 KaTrain SBC 前端即可完成以下闭环：看到实时画面，确认 LED 找到的角点，检查最终四角和 361 点，检查俯视矫正结果，发现摄像头位移，确认清盘并重新标定。终端和 curl 仅保留为开发诊断手段，不是用户验收流程。
