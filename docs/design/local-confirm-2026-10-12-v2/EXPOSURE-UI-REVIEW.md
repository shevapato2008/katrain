# 曝光五步与严重光照提示：Task 2 审核

2026-10-12 · 独立代码审核 / 用户代理视觉决策。基线 `304431fa4af01be104f6491a02d6cb00713b8a05`，审核对象为 Task 2 最终稳定工作区，包括首手准备与独立重试的小范围补充。

| 审核 | 结论 |
| --- | --- |
| Spec compliance | **GO** |
| Code quality | **GO** |
| 1024×600 frontend visual | **GO** |

无剩余阻塞项。允许提交 Task 2 并进入 Task 3；这是前端切片审核，不是第三轮计划审核，也不表示尚未实现的本地曝光证据、真实 bootstrap→pose 转换或设备发布已经验收。

## 规格与代码

直接检查了 Task 2 diff、新增文件、调用点及对应测试；先完成规格核对，再审查实现质量。

- 五步为准备空盘、曝光收敛并锁定、四角、九星、基线。`converging_exposure` 正确显示第 2/5 步，13 仍只计锚点，不显示虚构曝光百分比。失败/取消优先使用 `stopped_phase`，旧响应保留曝光错误与锚点回退。新增 phase 已进入类型、300ms 活动轮询、摆谱守卫与标定屏；活动期间底部只有取消。
- 设置、实体对弈、做题、摆谱继续复用现有守卫与标定屏。对局中重新标定改走共享 context；202 不提前调用 `visionResetSync`。待处理记录限定原路由、原 session 和旧 revision，失败、取消、请求失败或离开路由时清除。实际新 revision ready 且原局绑定成功后，非本地局只 reset 一次；本地局保留 bind 已准备好的参考帧，不再额外 reset。未为自动外框漂移新增曝光控制。
- `LocalConfirmationState.reason` 包含两项严重曝光原因；`GeometryMetrics` 准确表达 exposure、attempts、原残差与重定位字段，未用 `any` 掩盖契约。标定弹窗只接受 failed 状态下可信统计配合 confirmed reason，或严格曝光 gate 的明确错误；本地页面只消费权威 local reason。普通 pending、timeout、缺少可信统计和单纯 manual readback 错误不变成光照警告；后者保留“曝光没有锁定”诊断。
- MUI 弹窗标题、完整建议与计划一致：先移开遮挡，持续提示才换到光线均匀、合适的位置，不断言一定是环境光问题。关闭弹窗不修改棋谱、提交落子或重启服务。
- 本地光照提示复用已有 `speak/stop`，会打断该实例的开局说明；几何页使用自己的实例。语音仍服从现有偏好，关闭提示停止播放。本地按 game/node/reason、标定按页面 revision/reason 去重；recognizing 的临时空 reason 不重置，revision/节点/方向变化按契约允许新提示，同 revision 重试仍保留诊断。
- 首手准备按实际 bind Promise 与 camera/pose 状态显示准备中、失败和可达重试；冷启动已记录的实体局不先声明屏幕 ready。重试只调用现有 bind，不调用确认落子；开局引导等待实际准备完成。已有局文案要求对齐电子棋谱并拿回未确认棋子，不要求清掉已确认棋子。Task 3 仍负责后端真实 readiness 转换和旧 unavailable reason 的清除。

实现限定为一个共享提示组件、一个页面级提示 hook，以及现有 context/hook 的必要状态补充；未引入新的监控、音频框架或 attempt ID。

## 视觉决定

独立目视核对以下真实 React 浏览器预览，单图均为 **1024×600**，证据位于 `output/rk-led-debug-20261012/`：

- `ui-before.png`、`ui-exposure.png`，以及 `calibration-comparison.png`、`calibration-overlay.png`、`calibration-difference.png`。
- `ui-lighting-warning.png`。
- `first-move-disabled.png`、`ui-local-preparing.png`、`ui-local-prepare-retry.png`，以及 `first-move-comparison.png`、`first-move-overlay.png`、`first-move-difference.png`。
- 最终代表图 `ui-local-prepare-retry-byoyomi.png`：10 颗已确认棋子、双方 30 秒读秒及剩余次数、准备失败和可用重试。

| 核对项 | 结果 |
| --- | --- |
| 构图、几何与滚动 | 标定屏保留原摄像头区、右侧状态栏和固定底部动作。五行完整可见，中段继续可滚动；第 2 步明确高亮，底部 44px 取消键完整可达。对比图未显示布局骨架移位。 |
| 弹窗 | 严重曝光标题和完整正文清楚，无裁切；右侧紧凑弹窗及关闭键均在视口内，保持现有 MUI 样式与焦点阻挡。 |
| 本地准备与恢复 | 保留 512px 棋盘、双侧面板和三层操作区。准备中禁用确认，失败时琥珀色“重新准备实体盘”大键可达；已有局截图保留已确认棋子。 |
| 文案空间 | 审查中收短了已有局准备说明，以及本地严重曝光面板标题/建议；完整曝光建议继续留在弹窗。最终读秒代表图中文字不压读秒或坐标/手数按钮，无需改布局骨架。 |
| 字体、颜色、材质与图标 | 沿用 kiosk 字体、玉绿/琥珀状态、真实木纹棋子和已有图标。并排/叠加图差异集中在新增步骤、状态文字、按钮语义和不同预览画面。 |

预览回执明确标记 `fixture: true`。标定图中的“几何叠加读取失败”是该隔离预览未提供有效 layout 的诚实提示；它不影响五步/操作布局核对，也不能作为实际标定成功或硬件故障的证据。Fixture 留在 ignored output，后续真实集成按计划清理。

## 语音与验证证据

两条真实 MP3 已存在于本轮工作区，准备随 Task 2 提交；旧音频未重生成。Microsoft Xiaoxiao 合成持续返回 403 后，已批准仅新增两条改用本机普通话 **Tingting** 离线生成。生成脚本保留 Xiaoxiao 默认与两条 LINES，并准确注明此次二进制来源例外。

`preview-receipt.json` 记录两条实际资源均 `playing=true`、`ended=true`，时长分别为 **11.09875s / 11.075542s**。独立解码检查均为 24kHz 单声道 MP3，平均音量均 -20.4dB、峰值 -4.5/-4.7dB；现有 `local_confirm_physical` 为 -20.0dB、峰值 -3.9dB，幅度相近、无削顶。

审查模型尝试接收真实音频时，工具明确返回“不支持 audio input”。因此本报告确认实际解码、播放完成、来源与文案，不声称已主观听辨声线或清晰度；不为此扩大工具链排障。

- 已读取 `/tmp/rk-task2-done-vitest.txt`：12 个相关文件、204 项通过。root 另复跑同组 204 项通过；最终短文案改动后实现者报告 92 项相关测试通过。
- root/实现者报告最终 `tsc -b` 通过。root 的 12 个主要相关生产源文件 targeted ESLint exit 0；`GamePage` 仅保留 7 个原有 exhaustive-deps warnings。`api.ts` 原有 24 个 no-explicit-any 与 `pages/GamePage.test.tsx` 原有 lint 问题作为既有基线，未扩大修复范围，未宣称全仓 lint 无问题。
- 审查者在最终文案稳定后执行 `git diff 304431fa4 --check` 通过。`local-preview-receipt.json` 和 `local-byoyomi-receipt.json` 均记录重试可用。

本次审查未操作 RK、原生浏览器或用户棋局，未修改产品代码；仅写本报告。后续继续既定 Task 3 与实际集成、发布验收，不追加无变化的全语言/全状态截图或全 GPU 回归。
