# Four Go Fixes — Independent Astra max Plan Review

Round 1 · 2026-11-05 · base `fb916f12516dd510080fb736a48a825dc206bc37`

## Decision

| Plan | Verdict | Required changes |
|---|---|---|
| `2026-11-05-vision-legal-move-mismatch.md` | **change required** | V1、V2，下述两项异步所有权缺口 |
| `2026-11-05-territory-view-dismissal.md` | **approved** | 无 |
| `2026-11-05-ladder-default-time-countdown-audio.md` | **approved** | 无 |
| `2026-11-05-kiosk-home-section-heading-size.md` | **approved** | 无 |

其他三项可以进入各自实施。领地的视觉确认 gate 仅阻塞其 Task 4 后端契约变更；不阻塞该项前端 Demo，也不阻塞另外三项。Round 2 只需核对 V1、V2 的计划修订，不重开已通过项目的审查。

本轮只读核对四份计划、两份指定调查报告及相关源码/测试配置，未改产品或计划，未启动 app、测试、设备操作或部署。未读取、遍历、stat 或以 git-status pathspec 访问禁读的棋谱数据目录。下述并发问题来自明确的调用关系和可发生的调度，不宣称已在设备复现。

## Required changes

### V1 · Important — 给迟到快照分配“当前”代次，不能保证旧绑定或旧盘面失效

**计划位置：** vision 计划 68–69、89–98、127–136 行。

计划让 `VisionService` 在缓存/发送时分配 epoch、revision，并在 await 返回后“完成结果前”检查 epoch，但真实 expected 发布者没有携带来源绑定：

- `katrain/web/core/physical_play_orchestrator.py:99–108` 的 `wrapped` 保存旧 session 的 `_orig`，随后调用同一个 `self.on_game_state(state)`；`on_game_state:151–184` 只检查当前 `_session_id` 非空，随后覆盖 `_latest_state`、改变暂停/模式并推 expected。
- `katrain/web/interface.py:1007–1011` 先捕获 callback，再读取 state、调用 callback。AI 线程可已捕获 A 的 wrapper，主线程随后解绑 A、绑定 B，A 的旧 wrapper 再继续。恢复 `update_state_callback` 并不能撤销这个已进入执行的 wrapper。
- `katrain/vision/service.py:116–129` 的 expected API 当前只有 board/node，无法区分该快照来自 A 还是 B。在上述调度下，单纯按 Service 到达时刻分配 epoch 会把 A 的盘重新盖章成 B 的当前盘；短 RLock 只能串行化这个错误，不能识别来源。
- 同样，`server.py:5353–5372` 的 bridge await 后会调用当前全局 orchestrator，`:5421–5445` 的 gateway 结果会操作当前全局 recovery tracker/rearm。仅在最后发送结果 ACK 前检查旧 epoch，挡不住前面已作用到新绑定的副作用。

另外，结果命令若携带另一份 expected 快照（计划 96 行），必须说明快照的 revision 在哪里固定。先读旧快照、后来才按“与缓存不同”分配新 revision，会把迟到旧盘标为更高版本；“拒绝低 revision”无法解决它。

**最小修改：**

1. 把实际 expected 发布者 `physical_play_orchestrator.py` 纳入文件图；在绑定时捕获来源 session/game/epoch，旧 wrapper 在碰当前 orchestrator/vision 前即被拒绝。来源身份应传到服务入口并在同一短临界区检查，不能从到达时的当前绑定推断。
2. 把 await 后检查的位置写成“在任何共享 tracker、rearm、orchestrator 或结果回推副作用之前”，保留远端对其原 session 的既有权威落子规则。
3. 优先让 `RESOLVE_CONFIRMED_MOVE` 只结算当前 token，不再成为第二条 expected 快照写入通道；数字盘继续经既有 expected 发布路径更新。若确需携带快照，须写明权威快照取得与版本绑定/发布的顺序，不能给迟到快照重新分配更高版本。
4. 在已有 orchestrator/service/poller harness 内补一个有 barrier 的场景：A wrapper 已捕获或 A bridge 正在 await → 绑定 B → 释放 A。断言 B 的 expected、当前 pending、暂停状态和 recovery episode 均不变。再用同一 harness 证明旧快照不会以新 revision 回滚新盘。无需新测试框架。

这不是要求扩大为通用状态总线；它是现计划“旧 ACK/旧结果不能影响 B 局”承诺所缺的真实接线。

### V2 · Important — “远端 pending 接管”必须对应真实出口，不能留下没有结束者的单点豁免

**计划位置：** vision 计划 90–98、134 行。

计划允许 finally 把未解决 token 交给“明确的权威 pending 结果”，并计划用 fake gateway 的 explicit pending 覆盖。但当前移动 API 的实际含义不同：

- `katrain/web/platforms/gateway.py:176–177` 的 `reason="pending"` 表示**上一动作**还在等待，当前这次移动尚未提交；不能据此认为当前 token 已被平台接管。
- OGS `_play_ogs_action:300–305` 会保留 `ctx.is_pending`、设 `needs_resync`，然后抛 `engine_error`/`position_changed`，不是返回 `{status:"pending"}`。普通平台成功则先本地落子再返回（`:197–202`），星阵引擎成功也在返回前提交权威棋局（`:405–468`）。
- `server.py:5421–5442` 把这些异常送入既有恢复机制。`engine_recovery.py:16,111–113` 对 `pending` 不计次数且重新布防；保留一个没有具体完成通知的 vision token 会与“只允许一颗自动确认”组合成永久隐藏/阻塞，或者反过来在误判拒绝时重现合法等待中的紫灯。计划目前没有确定哪段真实代码接管哪颗子、在哪里解除该 token。

**最小修改：**

1. 列清现有真实出口：await 尚未结束、已权威提交、明确拒绝、上一动作 pending、OGS 不确定发送、取消。上一动作 pending 必须释放当前 token；不能仅因 `ctx.is_pending` 为真就保留当前点豁免。
2. 默认把归属限制在该次实际提交调用的生命周期，return/exception/cancel 经 finally 明确结算。若要保留 OGS 调用结束后的归属，必须绑定到这次动作的 session/game/坐标/序号，并指出现有 echo/reconcile/terminal/取消中的具体释放点；没有已接线的 owner 就不留下 detached pending。不要为未出现的返回形式扩建一个泛化协议。
3. 将虚构的“explicit pending 返回值”测试换成真实 gateway 契约的最小桩场景：当前点遇到 previous-action pending 不能获豁免；不确定发送随后确认或解除 pending 时，当前 token 一定收敛。复用现有 poller/gateway 测试，不增加组合矩阵。

## Approved plans and proportionality

**Vision 的方向本身成立。** `_drain_worker` 确实在 `service.py:394–428` 将落子和 dict 拆成两个 deque；只把 pump 改为先消费落子，无法覆盖星阵约数十秒至更久的 await，也无法保证 worker 第五帧不先生成错误。worker 在同步比较前登记一个精确待提交点、有明确拒绝释放，是合理的最小共享修复。保留真实 expected、不丢整帧 payload、不重置成熟异常证据、拒绝后立即恢复 actionable、monitor/local-window 不接管，这些约束和测试足够针对根因。epoch 有真实重绑定依据；V1 的 ACK 简化可减少额外 revision/快照排序面，不必合并队列或增加网络阻塞总线。

**领地 approved。** 当前结果与 visible 分离、当前 game/account/position 的 generation、渲染时 currentScope 检查、零额度缓存复看、请求中关闭后迟到不复活、失败同 request ID，以及星阵独立 area 缓存，都在计划内。实施需让 Star 的缓存恢复与 Canvas/弹窗实际渲染使用同一当前身份判断，不能只清理后台缓存。当前 ranked 和 Star 这两种对局的规则/棋盘规格由本局契约确定；不需要为此建立跨页或历史局面缓存服务。

计费仍由升降级三次成功账本和星阵账号道具分别负责。`score_lead` 从同次分析选择，明确黑方视角且兼容旧 receipt；ownership 阈值格点不冒充绝对得分。关闭只撤 Canvas，不清全局灯。两个来源各一个 1024×600 预览和已有生命周期测试与这次新增弹窗相称。

**默认用时/音频 approved。** 两个入口显式传分钟值 30，API 省略契约与旧局快照保持；无需改全局预设或服务端默认。源码确实吞掉 `play()` rejection 而调用方立即置 beeping。复用既有 WAV、让 Promise 成功才记录 started、singleton owner 与取消、当前剩余窗口 offset、手势解锁与静音/隐藏门禁，解决的是已有实际链路，不是新音频服务。保留石子音重叠与两席位竞争的聚焦断言即可。媒体 Promise/playing/PCM 不等于 RK 扬声器可听；计划明确保留设备实际听音待确认，不能在交付时升级成已听到。

**字号 approved。** 单页局部 22px 和 30px 标题行使用已有变量，限制在历史滚动区；其他首页的差异有既有设计依据。单文件 diff 检查和一张相同 large/1024×600 预览充分，不应追加测试层、全站字号统一或重复视觉审查。

## Test and startup boundary

- 只静态检查，没有启动任何命令证明“测试通过”。
- 领地 `playwright.visual.config.ts:20–24` 只启动 Vite，计划明确使用独占端口和 mock API/WS；避免默认 backend-launching 配置正确。
- `test_ai_ladder_territory.py` 使用临时 SQLite 与窄 FastAPI/ASGI fixture。`test_ai_ladder_api.py:234–303` 也注入临时数据库，普通 ASGITransport 场景不主动进入 lifespan；该文件另有显式 lifespan 测试，不能因为某个窄用例隔离就把整个文件当作无启动副作用。
- vision 总验包含 `test_local_move_confirmation.py:19–27` 的真实 TestClient lifespan。应保留禁止访问数据目录的硬边界，实施时先复核实际启动路径/环境；如有不满足隔离的启动检查，缩到既有纯 harness，不运行整库或棋谱扫描来“补证”。当前 base 的 `server.py` 没有旧 album-root 扫描初始化，不能把历史版本的启动风险当作已证实的本版本缺陷。

未提出额外安全清单、模糊测试、全站回归或新的审计基础设施。

## Round 2 — Final verdict

2026-11-05 · 仅复核更新后的 210 行 vision 计划对 V1/V2 的修订；未重审已通过的三项，未启动 app/tests 或设备操作。

**Vision plan: approved。V1、V2 均已关闭；无剩余 blocking/important 计划问题。可进入实施，不需要第三轮计划审。**

- **V1 closed：** 修订版 68–69、83–97 行明确在 wrapper/await 发起前捕获来源，在当前实体状态副作用前校验；列入真正的 orchestrator、初始绑定、中央 mirror 和 fallback 发布点。同一绑定的迟到 callback 在既有权威锁内重读当前盘，取得快照至固定 revision/入队之间不释放该锁；锁序明确为游戏锁 → Service 元数据锁。101–105 行把 ACK 收敛为 `RELEASE_CONFIRMED_MOVE(token)`，由同一 publisher 在 release 前 flush 真实变化，避免原 callback 延迟时重新暴露已合法提交的点，也没有第二条 expected 快照通道。160–161 行的旧 wrapper/bridge barrier 和旧节点回调场景直接覆盖首轮证据。
- **V2 closed：** 99–119 行把归属限制在本次实际调用内，所有出口经 finally 释放；区分上一动作 pending 与本次 await，OGS 不确定发送只取消临时视觉归属、不宣称远端拒绝、不改变平台 ctx/reconcile。迟到 echo/snapshot 继续由既有 manager 的真实权威更新收敛，无 detached owner。155、159 行要求驱动真实 gateway 分支与 manager 路径，不再用自造 pending 返回值证明生命周期。

三项原 approved 结论保持。领地用户视觉确认仍只约束该项 Task 4 后端，其他工作可独立继续。计划通过只授权按既定范围实施与验证，不代表代码或设备验收已完成；后续按用户既定独立代码审流程检查实际接线即可。
