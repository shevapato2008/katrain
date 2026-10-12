# 本地实体首手不可确认：诊断与最小修复决定

2026-10-12，代码基线 `304431fa4af01be104f6491a02d6cb00713b8a05`。本报告只读取源码、运行隔离的内存复现并写本文档，未操作设备、浏览器或用户当前棋局。前端引用基于该 HEAD，避开正在实施的 Task 2 工作区修改。

**决定：GO，作为 Task 3 的必要追加修复。** 根因已经确定；同时补齐已证实的首次参考帧准备失败后的可达重试。此为新现场缺陷的诊断和实现边界，不是曝光计划第三轮审核，也不改变已批准的严重光照证据要求。

## 现场事实与证据边界

root 提供的只读现场证据：session `cfb261c7d58743d3b934ee4ad6b1fc73`，game `game_2026-10-12_15-31-27_84e94c13`，本地对局第 0 手、黑方、空电子盘；`local_confirmation` 为 enabled / idle / reason=null。geometry 为 READY、13/13、revision=1，camera/geometry/model/recognition/LED 均 ready；vision 却为 `pose_locked=false / sync_state=calibrating`，已绑定该 session。原生界面显示“轮到你落子”，黑方确认、停一手和认输均禁用。此前人机对局可识别黑 Q16 并正常引导灯光。

设备仍为已发布的本地确认 v1 后端 `0b086a7c1` 加 v2 静态 `17562ff2c`；root 已核对相关设备源码 hash。当前曝光修复未部署，因此不能将现场归因于新曝光代码。公开 `/vision/status` 不返回内部 bootstrap/reference 状态，单靠现场 geometry READY 不能断言参考帧已就绪；下面的真实 BIND 离线复现直接证明这条状态缺口。

## 根因链

1. `VisionService.bind_session()` 发出 BIND（`katrain/vision/service.py:157`）；worker 执行 `_sync.bind()` 并清参考帧（`worker_inprocess.py:1591`）。`SyncStateMachine.bind()` 将状态置 CALIBRATING（`sync.py:244`）。
2. 本地模式的 bootstrap 使用真实新鲜帧及完整前处理。`_maybe_capture_reference()` 要求几何存在、无灯、无待定落子/参考否决，并要求投票前和投票后的原始盘面都等于权威棋谱（`worker_inprocess.py:719`）。成功后仅将 `_local_bootstrap_state` 设为 ready（`:1248`），没有完成旧同步状态的转换。
3. 本地模式有意跳过 `_sync.update()`（`:1501`），且窗口外不进入自动落子检测（`:1302`）。因此自由/人机对局能随正常观测推进状态，本地模式却缺少这一转换。恢复常驻 `_sync.update()` 会破坏本地确认隔离，不是修复办法。
4. `_publish_status()` 仍从 `_sync.state` 推导 pose（`:1557`），CALIBRATING 永远报告 unlocked；与此同时内部 `local_confirmation_ready` 可已为 true（`:1572`）。`vision.py:135` 将该旧 pose 原样发给前端。
5. `GamePage.tsx:415` 和 `:1406` 分别以 camera+pose 禁用确认 hook 和界面。`LocalConfirmGame.tsx:64,126–130` 又用该 blocked 状态禁用确认、停一手和认输，却仍显示正常轮到落子的文案（`:115`）。窗口无法打开，故不是窗口内识别不到首子的故障。
6. `tests/test_vision/test_local_confirmation_window.py:72` 的公共 helper 预先调用 `_sync.confirm_pose_lock()`。既有 bootstrap/window 测试从已锁定状态开始，漏掉生产 BIND 路径。

隔离复现使用该文件的相机、帧和模型 stub，但通过实际 `VisionService.bind_session → set_expected_board → set_local_confirmation_mode → worker._loop` 执行；BIND 覆盖 helper 的预先锁定。未修改生产代码：

| 路径 | 参考帧 / local ready | bootstrap | pose / sync | 自动事件 |
| --- | --- | --- | --- | --- |
| 真实 BIND，空盘 4 次相机读取 | true / true | ready | unlocked / calibrating | 0 |
| 上述状态执行现有 confirm_pose_lock 命令 | true / true | ready | locked / synced | 0 |
| 首子先于参考帧出现 | false / false | bootstrap | unlocked / calibrating | 0 |
| 该准备活动到期 | false / false | unavailable | unlocked / calibrating | 0 |
| 拿回首子，显式关闭/重开本地准备 | true / true | ready | unlocked / calibrating | 0 |

空盘路径只推理 1 次；执行 pose 命令后仍为 1 次，参考帧对象、expected board 不变，确认窗口仍为空。它证明状态转换可以独立修复，不需要放宽图像后处理或自动提交。

## 已证实的附带缺口：首子放得早会无法重试

空盘参考帧建立前已经摆首子时，上述 raw==expected 守卫正确拒绝建参考；8 秒 bootstrap 到期成为 unavailable（`worker_inprocess.py:1032`）。必须保留此保护，不能将首子照片标为空盘，也不能临时把实体盘写入 expected。

`vision.py:274–288` 已支持显式 bind 重试并返回“clear the board and retry”，但 `useVisionSync.ts:87–89` 只写 console；`GamePage.tsx:423–426` 把重试藏在被 pose=false 禁用的“确认落子”动作里。故即使补上成功后的 pose 转换，这种真实准备失败仍缺可达恢复入口。

## Task 3 的最小实现要求

- 在真实 bootstrap 成功边界完成本地 pose/sync 转换：当前绑定、当前 session/game/generation、已验证 geometry、camera 可用及真实 reference 齐备后，才可完成既有 `_sync.confirm_pose_lock()` 或等价的本地权威状态发布。所有可到达 ready 的分支保持一致。不能只在 BIND 或“geometry 非空”时无条件锁定；新局、失去 geometry、相机不可用或 stale generation 不能沿用 readiness。
- 保留本地 idle 不推理棋盘、不喂自动 sync、不产生落子事件的隔离。确认仍只开启原有 8 秒窗口，完整 motion/vote/denial/reference/candidate/合法性链与现有严重曝光证据要求均保留。不得用前端忽略 pose 来掩盖后端矛盾。
- 首次 bind 未完成时显示“正在准备实体盘”，完成后再引导摆首子。失败显示明确的准备说明及可点击“重新准备实体盘”；新局提示拿回尚未确认的首子、保持空盘并移开双手。恢复已有局则要求盘面与当前棋谱一致，不能要求清掉已确认棋子。
- 重试是独立的准备操作：复用现有 `/vision/bind`，不调用 `/local/confirm`，不入谱、不换方、不播放落子音。可以直接消费现有 bind Promise 的 pending/success/failure，避免为此新建状态服务。正在准备时避免并发 retry；成功刷新真实状态并清除该次遗留 unavailable 提示，再允许用户摆子、确认。失败仍可再次准备；camera/geometry 真正不可用时保留相应诊断。
- 前端追加在当前 Task 2 写入完成后串行修改，复用获批布局及音频实例。仅准备成功才播开局落子引导，避免先催用户摆子再因参考帧缺失卡住。无须重做 Artifact 或全状态视觉审核。

充分验收限于：一个不预设 pose 的真实 BIND/start-local 回归，证明真参考 ready 后 API pose 与原生确认可用；确认前无自动入谱，用户一次确认仅产生一手、换方、窗口关闭且画面后一次落子音。另一个首子早放→准备失败→拿回首子→显式重试成功的回归，验证没有伪参考、自动落子或重新建局；camera/geometry/旧 generation 的直接相关保护沿用或补一个必要断言。与本次光照的聚焦测试合跑，不扩全 GPU/全回归。

## 保留当前棋局的临时恢复：有条件 GO

现有 `POST /api/v1/vision/pose-lock/confirm` 仅排入 CONFIRM_POSE_LOCK（`vision.py:178`、`service.py:109`、`worker_inprocess.py:1615`），本身不校验 reference，不能盲目调用。允许 root 在当前局使用以下最小核验后恢复状态；本报告没有执行该操作：

1. 记录当前 session/game/node/方/棋子，确认本地局 idle、无确认进行中、仍绑定该 session，camera 和当前 geometry revision 有效。
2. 对该精确 game 调用已有 `/api/local/ready`，`input='physical'`。`LocalConfirmationController.ready():74–79` 会验证绑定、能力及 service 的当前 generation 真实 readiness；失败 409 即停止，不强制解锁。成功只有幂等输入准备、起钟/广播（`:81–83`），不提交棋子、不启动推理、不替换参考；若时钟尚未启动，这一步会按既有规则启动，不能称完全只读。
3. 确認身份和硬件状态未变后，调用一次 pose-lock/confirm。该接口为全局命令，因此这段操作期间若 session/game/geometry 改变就停止，不将旧证据用于新局。
4. 重新读取实际 pose/sync 和原局状态，确认命令已生效、棋子/节点/行棋方未改变；由用户本人按“确认落子”。不代按落子确认，不重启、不解绑、不 resync、不清盘。

不使用 `/vision/bind` 充当临时只读探针：其 unavailable 分支会重新开启 bootstrap。上述恢复只解除已证实的旧状态卡住；不能替代永久修复和用户后续真实落子验收。

### root 实机临时恢复回执

root 按上面顺序执行了精确当前局 physical `/api/local/ready` 校验，HTTP 200；复核相同 game/node/session 后一次 pose-lock/confirm 返回 HTTP 200 / ok=true。设备实际状态变为 locked/synced，黑方确认按钮 disabled=false。前后仍 node=0、stones=[]、player=B，未代用户确认落子、未重启服务。这同时证明本局已有真实参考帧，并非相机没认出第一手；永久修复仍待开发与审核。

### 永久修复发布后的核验

随后永久修复及最终独立 Astra max 审核已完成，`754c24b2e` 部署 RK。新建空盘实体本地局在真实 bind 完成后自动 locked/synced，首手确认键正常可用，未手动调用 pose-lock/confirm。空盘确认返回真实 no_stone，仍第 0 手且黑方行棋；屏幕改选确认只提交最后 K10 一手，设备实际一次落子音。测试局已退出且不保存；用户完成的 101 手棋谱和报告 22 均保留。详细范围及物理摆子验收边界见 [EXPOSURE-RELEASE.md](EXPOSURE-RELEASE.md)。
