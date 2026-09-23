# Kiosk 实体棋盘对弈体验修复设计

## 目标与范围

修复本轮两盘自由对弈中确认的四项问题：正常落子后反复出现“棋盘已重新检测到”、落子声音早于屏幕棋子、kiosk 限时对局最后 5 秒没有读秒音频，以及“重置识别”按钮语义不清且图标偏位。白 88 未亮灯暂不处理，待设备日志可用后单独诊断。

## 方案

### 1. 只把真实检测失败交给同步状态机

`worker.py` 与实际运行的 `worker_inprocess.py` 当前在运动门控拒绝一帧时仍调用 `SyncStateMachine.update(observed_board=None, board_detected=False)`。普通落子时手臂运动因此被误报为 `board_lost`，下一稳定帧又发 `board_reacquired`。

修复应在事件源消除错误输入：有摄像头帧但运动尚未稳定时跳过本轮同步状态机更新；只有相机掉帧或真正的棋盘定位/透视变换失败才传入 `board_detected=False`。两份 worker 保持相同行为。不采用只隐藏前端 toast 的方案，因为那会掩盖错误状态并继续触发其它 board-lost 恢复逻辑；也不先增加状态机延迟，因为输入本身就不代表棋盘丢失。

### 2. 用 Canvas 绘制确认驱动落子声音

服务端继续按 `game_update` 后 `sound(after_node_id)` 的顺序发送。本次只给 kiosk 对局屏启用严格的 Canvas 确认，不改变 Galaxy、ZenMode 等共享调用方：

- `useGameSession` 增加一个默认关闭的 `deferMoveSoundUntilPaint` 选项，并返回 `acknowledgePaintedNode(nodeId)`。
- kiosk `GamePage` 开启该选项；它唯一可见的 2D `Board` 通过可选回调 `onNodePainted(nodeId)` 回报完成绘制的节点。
- 严格模式下，带 `after_node_id` 的声音必须等到同一节点的绘制确认，再跨过一次实际绘制帧后播放。Galaxy 不开启严格模式，继续使用现有队列与双 `requestAnimationFrame`，因此 Galaxy 同时挂载的隐藏 2D Board 和可见 Board3D 都不会参与确认，也不会造成声音永久积压。
- 换 session、换 game、WebSocket 断开和卸载时仍清空声音与绘制确认；不带 `after_node_id` 的遗留声音仍立即播放。

在 kiosk 严格模式中，这替代现有“仅凭 React 节点提交，再用两次 requestAnimationFrame 猜测 Canvas 已经绘制”的同步条件。固定增加毫秒延迟不采用，因为设备负载变化时仍可能失效，且会无谓拖慢正常设备。

### 3. kiosk 复用 Galaxy 的最后 5 秒读秒规则

本次覆盖用户复现问题的非本地 kiosk 对局玩家卡（自由对弈、升降级及现有使用 `SeatRow` 的对局），不改本地双人对局的独立时钟路径。仅当轮到该方、处于读秒阶段、剩余秒数为 5 至 1 且本秒尚未播过时播放现有 `countdownbeep.wav`；进入新读秒周期后重置去重状态。

播放同时服从两道现有开关：服务端随本局计时设置下发的 `timer.settings.sound` 必须为真，设备级 `audioPrefs('sfx')` 也必须开启。实现复用 `useSound` 的播放器并为它登记 `countdownbeep`，不新增第三份播放器或设置项。不限时、主时间阶段、暂停、终局以及非当前方均不播放。

### 4. 明确“重置识别”动作

实体盘模式下页控条保留常驻自救入口，但由纯循环箭头改为“循环箭头 + 重置识别”的紧凑按钮。`KioskPagebar.action` 增加可选的可见标签能力，只有这一处启用，其它页面的纯图标动作不变。按钮样式显式归零 padding/line-height 并保持 44px 以上触控高度，确保图标与文字居中。

文案必须与实际行为一致：该动作以屏幕上的数字棋局为准重建视觉基线、清除卡住的识别状态；不再使用“让屏幕以实体盘为准”的相反描述。屏幕模式下仍不显示此按钮。

## 验证

- Python：运动不稳定帧不会产生 `board_lost/board_reacquired`；真实定位失败及恢复仍会产生对应事件；两份 worker 的行为都有聚焦测试或共用判定测试。
- Frontend：kiosk 严格模式中的声音必须等待匹配节点的 Canvas 绘制确认；确认晚于声音到达也能正确播放；过期声音仍被丢弃；隐藏/非 kiosk 渲染器不能确认；默认模式和无 `after_node_id` 兼容行为不变。最后 5 秒每秒只播放一次并在新周期重置，同时验证本局 `timer.settings.sound` 与设备 `sfx` 任一关闭时不播放。
- UI：组件测试确认按钮有可见文字、准确 accessible name，并检查 CSS 的触控尺寸与居中规则；在 1024×600 真实页面做一次代表性截图，确认长标题、返回键和新按钮不互相挤压。

## 非目标

- 不处理白 88 LED 漏亮。
- 不改视觉模型、曝光、确认帧数或棋局规则。
- 不调整 Galaxy 的现有读秒交互。
