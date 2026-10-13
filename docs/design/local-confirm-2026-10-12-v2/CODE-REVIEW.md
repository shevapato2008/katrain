# 本地逐手确认 v2：代码与后端契约审核

2026-10-12 · 独立代码审核 / 用户代理技术决策。

**GO：本次差异未发现阻塞问题；无需新增或修改后端代码、API、数据库字段或业务状态。** 已收到 root 明确转交的前端实际运行时 GO，并读过 [REVIEW.md](REVIEW.md) 中同尺寸参考、实现、并排及叠加 / 差异图的审核记录；在此前提下批准复用现有确认链路进行集成与发布。

范围是相对 `412ce1526` 的 `LocalConfirmGame.tsx`、`LocalConfirmGame.css`、`LocalConfirmGame.test.tsx` 三文件未提交差异，以及它们直接依赖的既有显示、确认、声音和物理窗口契约。本审核未修改产品代码、操作浏览器或部署。

| 核对项 | 结论与源码依据 |
| --- | --- |
| 停一手与棋盘尺寸 | `LocalConfirmGame.tsx:126` 改用现有 `game:pass`；中文目录中该键为「停一手」，通用 `Pass` 确为「虚着」。`:87` 对现有 `game:board_lines = {n} 路` 替换参数，避免旧写法重复拼接数字和残留 `{n}`。显示键复用现有「坐标 / 手数 / 开 / 关」翻译。 |
| 双方共享显示状态 | `GamePage.tsx:245` 只有一份 `analysisToggles`；`:1400` 向组件传入该值，回调只以函数式 `setAnalysisToggles` 修改对应键。两个 seat 的 `aria-pressed`、开关文案、外侧坐标及 `Board` 均读同一值。`coords` / `numbers` 只决定显示，不进入确认请求、棋谱或后端状态；此次也没有增加持久化承诺。 |
| 等待与确认中边界 | 显示键始终可用，符合已批准设计。停一手、数子、认输和确认的原有禁用条件均保持；等待方只能操作显示和自己的认输，确认中双方八个业务按钮均禁用。棋盘仍由 `busy` / `capable` / 输入模式锁定。等待方去掉 `is-busy` 仅改变样式，未放开业务动作。 |
| 精简文案与触控 | 删除常驻教学、重复手数和门槛段落；完整步骤仍在说明弹窗及开局语音，错误保留当前原因对应的短纠正语。数子门槛的实际判断及按钮禁用保持，提示转到 `title`。新增显示键高 44px，190×108 确认键保持；棋子图像使用已有 `B_stone.png` / `W_stone.png`。几何和预选标记的实际差异已由前端视觉 GO 接受。 |
| 屏幕改选与权威提交 | 组件仍将选点交给 `useLocalMoveConfirmation`，未新增入谱路径。该 hook 的 `select` 仅替换 draft，`send` 读取最后一点并锁住进行中的提交；成功清空预选，失败保留，权威节点 / 回合变化使旧 draft 失效。`GamePage.tsx:428` 的确认响应仍通过 `session.setGameState(response.state)` 应用。 |
| 成功音与终局 | 本次未修改声音链路。`useGameSession` 仍按服务端 `after_node_id` 排队，等待权威节点及 `Board.onPaintedNode` 后播放；显示切换不新增声音事件。开局语音调用保持。`GamePage.tsx:714` 仍在终局或 `awaiting_count` 时退出此布局；停一手、数子、指定一方认输及现有终局流程不变。 |

后端契约决策：`/api/local/ready` 继续负责输入准备和时钟启动，`/api/local/confirm` 继续接收当前 game / node / color、input、action、coords、request_id，并返回 accepted 与权威 state。v2 需求没有引入新的后端权威事实；为显示开关增加 API、服务端镜像状态或新 CV 分支会造成多余实现，不予采用。

实体盘仍使用 `local_confirmation.py` 的完整确认窗口：打开后的新相机帧、相机序号与窗口 token 校验，全盘新增子 / 颜色 / 提子检查，真实规则试走与多帧候选一致，成功后才提交并完成窗口，失败关闭窗口并恢复原回合计时。`worker_inprocess.py` 原路径继续执行多帧投票、否认点处理、参考帧检查及有条件的原始帧参考更新；本次 diff 没有触碰这些代码或绕过它们。

验证依据：本审核实际执行 `git diff --check`，退出码 0；独立阅读新增显示同步 / 翻译 / busy 用例及既有 hook、`tests/test_local_move_confirmation.py`、`tests/test_vision/test_local_confirmation_window.py` 相关用例。root 已报告本轮前端 panel + hook 11 项、后端确认 + 物理窗口 31 项通过，以及真实 UI 等待方显示切换、双侧 pressed 状态和坐标同步通过；这些执行结果属于 root 的本轮验证，本审核未重复运行。真实 UI 的反复改选后仅提交最后一点及一次成功音，由 root 完成最终集成检查。

当前无须为本轮增加全局安全审核、全量回归或物理管线改造。本 GO 证明本次代码与既有后端契约兼容；最终 RK / 发布版本的实际页面验收仍按既定集成步骤记录。
