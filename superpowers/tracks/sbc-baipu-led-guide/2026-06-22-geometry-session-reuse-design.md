# 服务重启后复用棋盘几何设计

**日期：** 2026-06-22
**状态：** 已确认，待实施
**Track：** `sbc-baipu-led-guide`

## 1. 目标

KaTrain 服务重启后，如果摄像头和实体棋盘没有移动，系统已经能加载上次持久化的四角、透视矩阵和 361 个落子点。操作者应能在实时原图和俯视图中检查红色网格，确认对齐后直接恢复摆谱，不必清空已经摆到中途的棋盘。

## 2. 安全边界

- 复用入口仅在 `phase=required`、`last_valid=true`、摄像头已连接时开放。
- `degraded` 表示本次会话已经检测到位移，不允许用人工确认绕过，必须清空并重新标定。
- 无历史几何、标定正在运行、摄像头不可用时拒绝复用。
- 复用不要求 LED 连接，因为不闪灯；空盘自动标定仍要求摄像头和 LED。

## 3. 数据语义

复用的是 `~/.katrain/geometry_lock.npz` 中的历史 `corners/points/M/Minv/xs/ys/out_size/baseline`。其中 baseline 仍是上次标定时的空盘基线，不从当前有子画面重建，也不写回持久化文件。

确认后，本次进程内状态变为 `phase=ready`、`session_calibrated=true`、`geometry_ready=true`，`trigger=operator_reuse`。现有 `on_success` 回调重新向依赖实体棋盘的服务发布同一个 geometry lock，并以当前实时帧初始化本次会话的位移监测。

## 4. API 与前端

新增 `POST /api/v1/geometry/confirm-existing`。接口只执行上述会话确认，不启动 LED 标定。失败返回明确的 409；标定服务未启用返回 404。

标定页面在历史网格可显示且允许复用时，增加“网格无误，使用上次标定”按钮和说明“无需清空棋盘”。原“已清空，开始自动标定”按钮保留。确认成功后 GeometryContext 更新状态，PhysicalBoardGuard 自动放行回到原摆谱入口。

## 5. 验证

- 服务层测试复用成功、不写 baseline/npz、通知 `on_success`、启动位移监测，并拒绝无历史几何、摄像头断开及 degraded。
- API 测试确认路由、状态返回和错误映射。
- 前端测试确认按钮只在 `required + last_valid + camera_ready` 出现，点击调用新 API；degraded 不显示该按钮；成功后 Guard 放行。
- 定向 pytest、Vitest、ESLint、生产构建和 kiosk 2D 构建通过。
