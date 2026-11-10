# Ladder Default Time and Countdown Audio Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建升降级对局默认每方 30 分钟主时间和 3 次 30 秒读秒，并让最后五秒的既有非人声提示音可靠播放、及时停止。

**Architecture:** 只调整两个升降级 UI 入口的初始值，继续显式提交四个时限字段，保持 API 省略字段的旧契约；时限仍在建局时冻结，恢复旧局读取原快照。音频继续使用 `useSound` 的缓存、`audioPrefs.sfx` 和 `countdownbeep.wav`，修复“尝试播放等于已经播放”的错误状态，并在既有计时调用处补齐窗口和页面生命周期。保留现在的数字钟与服务端计时权威，不改为人声，不新建音频服务、状态库或硬件控制链。

**Tech Stack:** React 19 / TypeScript / Vitest、HTMLAudioElement、FastAPI / Pydantic / pytest。

---

## Chunk 1: Evidence, Scope and Implementation

### Investigation and limits

- 调查工作树：`/Users/fan/.config/superpowers/worktrees/katrain-kiosk-debug/ladder-time-audio-20261105`，分支 `fix/ladder-time-audio-20261105`，新鲜 `origin/develop` 基线 `fb916f12516dd510080fb736a48a825dc206bc37`。使用 `worktree add --no-checkout` 后只稀疏检出 `katrain/`、`tests/`、`docs/`、`scripts/` 和根文件；未访问禁止读取的棋谱目录。当前仅新增本计划。
- 用户事发局的已有脱敏证据位于 `/tmp/ladder-mismatch-investigation-20261105/`。`investigation.txt:13` 定位 20:32:21 建局、20:33:15 视觉绑定起钟、20:51:07 结算。本轮不读取更多历史、不恢复/重开该局。
- **时限实际链路：** `kiosk/pages/AiSetupPage.tsx:90–95` 为 ranked 开计时但 `mainTime=0`，`:173–178` 原样传给 `startAiLadderGame`；`features/aiLadder/api.ts` 发 `/api/v1/ai-ladder/start`；`api/v1/endpoints/ai_ladder.py:113–127` 请求模型目前 `time_enabled=False/main_time=0/byo_length=30/byo_periods=3`；`:695–703` 原样保存 `time_control_snapshot`，`:1315–1337` 更新 timer 后 `new_game`。`interface.py:888–889` 建局复制 `active_game_timer`；所有 `main_time` 此处均为**分钟**（`update_timer:1208` 才乘 60），因此新默认应传 **30**，不是 1800。
- **另一入口：** `galaxy/pages/AiSetupPage.tsx:117–121` 当前主时间 10 分钟、3×30 秒，`:217–224` 也向升降级 API 显式提交。自由对弈也用该页面；仅 ranked/rated 的初值改为 30，自由对弈保留各自原默认值。`AiLadderStartPreferences` 字段是必填，两个第一方入口都会显式提交时限。
- **实际音频调用链：** `GamePage` 给 `GameControlPanel` 原始 `gameState`；`GameControlPanel.tsx:631–641` 的 ranked 路径确实挂载两张 `SeatRow`。`SeatRow:282–310` 使用 `useGoClock`，仅当前行、叶子、未结束、未暂停、`settings.sound===true`、未超时且 `ceil(byoLeft)` 在 1–5 时进入窗口，调用 `useSound.play('countdownbeep')`；不是依赖服务端 sound 事件。`goClock.ts:64–68` 另要求 `timer.configured===true`。本地双人另有 `GameControlPanel:437–458` 的同资源窗口逻辑。
- **确证代码缺陷：** `useSound.ts:69–79` 因全局静音可直接返回，也会吞掉 `audio.play()` rejection；但 `SeatRow:308–309` 无论成功与否都立即 `beepingRef=true`。因此拒绝/静音后的本次窗口被错误标成已经播过；同一窗口解除静音或之后获得用户激活时没有可靠补发。没有订阅全局音效变化；音轨已经响起时关闭全局音效不会立即停止。窗口 effect 没有卸载 cleanup，也没有 `visibilitychange` 门禁，可在离页或后台继续响。后续实现先用失败媒体桩及生命周期测试复现这些**可证缺陷**。
- `countdownbeep.wav` 是已有 **5.000 秒、44100Hz、双声道**文件，整轨有 0/1/2/3/4 秒五声；一次窗口只能启动一次，不能每秒重新启动整轨。此次只读本地 WAV 元数据，没有播放或声称听过。
- **RK 窄只读补证：** 2026-11-05 调查时 `useSound.ts` / `GameControlPanel.tsx` / `goClock.ts` / `interface.py` / kiosk `AiSetupPage.tsx` 源码 SHA256 全部与该基线相同。设备当前 timer 配置 `{main_time:20, byo_length:30, byo_periods:5}` 缺少 `sound`；但 `interface.py:297–301` 与 `:888–889` 均已 `setdefault('sound', True)`，故不能把缺省字段当成本局无声根因，也不需要改设备配置。
- 当前实际音频 URL `http://127.0.0.1:8081/assets/sounds/countdownbeep.wav` 返回 **200 / audio/x-wav / 882044 bytes**，SHA256 `f5bc13720e804de9d3c308027aa60fe15221fa236f1438345317ea2a07b9a2aa`。`server.py:1194` 已挂载 `katrain/sounds/`；不需要复制资源。
- 当前 Chromium 主进程有 kiosk/incognito/CDP flags，没有 `--mute-audio` 或 `--autoplay-policy`。只读 CDP 查询只提取音频白名单字段：`kiosk_audio_sfx=null`（现有规则默认开）、`visibility=visible`、`navigator.userActivation.hasBeenActive=true`，加载入口 `/assets/index-CEN5njaD.js`；当前页面没有可读取的 `gameState.timer` 组件。未调用 play/unlock、未改偏好、未导航，也未发开局/付费/点灯动作。
- **不能证实的部分：** 事发时的浏览器 timer props、偏好、实际 bundle、play rejection、系统音频输出和录音均未保留。当前源码/资源/偏好只能排除当前明显缺失，不能证明事发时状态；现有后端日志也不能证明每个五秒窗口实际播了或哪种原因最终导致用户没听到。交付必须保留这一证据边界。
- 已通过 Context7 核对 MDN：[`play()`](https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/play) 成功由 Promise resolve 证明，脚本播放可能以 `NotAllowedError` 失败；[`autoplay`](https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Autoplay) 需要真实手势恢复；[`visibilitychange`](https://developer.mozilla.org/en-US/docs/Web/API/Document/visibilitychange_event) 可用于隐藏时停止。这里的提示是时间事件，回来时应重新评估当前窗口，不能照搬音乐“恢复旧播放位置”。

### Acceptance and exclusions

1. 新升降级首次显示并提交 `time_enabled=true, main_time=30, byo_length=30, byo_periods=3`（双方同规则）。保留用户显式选择其他受支持预设的能力。
2. 默认值仅影响新升降级；自由对弈、本地双人、平台模式的默认值不改；旧预约、活动局、恢复局的时限快照不迁移、不回写。
3. 最后五秒复用非人声五声 WAV；每个有效窗口只有一个播放器。暂停、落子/换轮次、换期、结束、离页、隐藏、任一静音门禁均立即停止；恢复时只按当前剩余窗口播放，不补播错过的音。
4. 浏览器拒绝播放不能被记为成功。真实手势可解锁既有播放器；失败只在当前仍有效的窗口内重试，不产生后台队列或迟到播音。
5. 不实现多语言人声，不改音量策略（现有 0.5）或设备音频设置，不修改云/设备/历史数据，不部署。

### File map

| Path | Responsibility |
| --- | --- |
| `katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx` | ranked 初始主时间 30；free 维持 0。开局真实手势处使用既有音频 hook 的解锁入口。 |
| `katrain/web/ui/src/galaxy/pages/AiSetupPage.tsx` | rated 初始主时间 30；free 维持 10。 |
| `katrain/web/api/v1/endpoints/ai_ladder.py`（只读） | 核对显式时限入参和快照链；不改请求模型默认或恢复逻辑。 |
| `katrain/web/ui/src/hooks/useSound.ts` | 既有缓存增加可确认的播放结果、受控时间偏移、真实手势解锁和取消；保留其他音效的重叠策略。 |
| `katrain/web/ui/src/hooks/useByoyomiCountdownSound.ts`（新增，小 hook） | 仅承接现有窗口 effect 的状态与生命周期，复用 useSound/audioPrefs；不负责计时或资源管理。 |
| `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx` | SeatRow 与现有 local 路径调用小 hook；数字钟计算、布局、服务端计时保持原逻辑。 |
| 对应既有 setup、GameControlPanel 测试及 `src/hooks/useSound.test.tsx`（新增） | 默认值、窗口调用、媒体拒绝/取消的针对性回归。 |
| `tests/web_ui/test_ai_ladder_api.py` | 新 UI 显式时限入参、API 省略兼容性及原快照保持验证。 |

### Task 1: New ladder defaults and snapshot boundary

- [ ] **写并运行失败用例。** 在既有 kiosk/Galaxy setup 测试中，分别进入 ranked/rated、点击 mock 的开始按钮，断言传参四元组 `(true,30,30,3)`；另断言 free 原默认不变和显式选择预设仍按选择提交。只用现有 mock，不调用真实 API。
- [ ] **锁定 API 兼容性。** 两个第一方入口总会显式提交四字段，达成用户所见的新升降级默认不需要修改 `AiLadderStartRequest`。因此保留现有省略字段的 `time_enabled=False/main_time=0/byo=30/3` 契约；在假 API 上核对省略与显式 `main_time=0`、其他合法时限、显式 `time_enabled=False` 仍按原行为处理。本次不把 programmatic 旧调用升级成有时限的新局。
- [ ] **最小实现。** kiosk 初始值用 `useState(isRanked ? 30 : 0)`，Galaxy 用 `useState(isRated ? 30 : 10)`；不修改共享 `TIME_PRESETS`、`config.json`、`TimeSettings` 默认或复局逻辑。若路由测试证明同一实例从 free 切 ranked 保留了旧初值，仅在模式切换这个边界重置相应初始时限，不每次 render 覆盖用户选择。
- [ ] **快照回归。** 在现有 API 测试的假 repository/session 上断言新局记录四字段；已有预约/恢复局继续保留自己的旧四字段。沿用 `test_ai_ladder_api.py` 的 fixture，禁止连接真实数据库。`interface.py` 默认 sound 已正确，不做多余改动。
- [ ] **运行并记录。** `cd katrain/web/ui && npm test -- src/kiosk/pages/AiSetupPage.test.tsx src/galaxy/pages/AiSetupPage.test.tsx`；`CI=true python -m pytest tests/web_ui/test_ai_ladder_api.py -k 'time_control or timer or snapshot or default' -q`。选择器必须实际匹配新增测试，零 collected 不算通过；若已有环境依赖阻塞，做一次合理修复或用准确单测节点运行，保留限制。

### Task 2: Make countdown attempts honest and cancellable

- [ ] **先写失败媒体用例。** 新建 `src/hooks/useSound.test.tsx`，用可控 `HTMLAudioElement.play()` Promise（不要 mock 掉整个 `useSound`）复现 reject/resolve 和 stop 先于迟到 resolve 的顺序；验证全局静音不播放、countdown 复用同一个 cached element、stone/capture 仍允许重叠。用例不能调用实际扬声器。
- [ ] **最小扩展现有 API。** 保留 `play(name)` 兼容调用形式，返回可 await 的成功结果（例如 `Promise<boolean>`，只有实际 play resolve 才为 true）；增加可选 `offsetSeconds` 参数供现有整轨定位。`stop` 使当前异步 attempt 失效、pause 并 rewind，迟到 resolve/rejection 不得复活已取消的声音。使用 hook 实例的轻量 owner/ref 或等价 token，防止旧 SeatRow 的取消停止另一席位刚启动的 singleton；不建通用音频任务队列。
- [ ] **解锁复用同一元素。** 在 `useSound` 中提供仅针对既有 singleton 的 `unlock`：真实用户 pointer/key/start 手势同步进入调用，在音量 0 下短暂 prime 该缓存元素，成功后 pause/rewind/恢复 0.5；复用取消 token，避免异步 prime completion 打断已经开始的有效 countdown。解锁不能设 `beeping=true`，不能发出试音、切换用户偏好或依赖 autoplay-policy 启动参数。kiosk/Galaxy 开始回调在第一个 await 前调用；直接打开/恢复页面通过 hook 安装的真实手势监听补齐。不得因解锁失败阻塞开局或绕过主动静音。
- [ ] **提取最小窗口 hook。** `useByoyomiCountdownSound` 接收当前剩余秒数、窗口身份（game/node/color/period）、当前是否 eligible；不重算钟。用 `useSyncExternalStore(subscribeAudioPref, () => readAudioPref('sfx'))` 复用既有偏好订阅，用一个 visibility listener 保持页面可见状态。每个窗口只允许一个 pending/started attempt；只有播放成功才标 started，失败仍允许下一次真实手势在**同一且仍有效**窗口内重试。Promise 回来时必须再次核对 token 和 eligibility。
- [ ] **取消与重新进入规则。** timer sound false、全局 sfx false、paused、非叶子/终局、离开 1–5 秒、换身份、hidden 和 unmount 都取消当前 owner 的轨。恢复/解除静音/重新可见后，仅当当前权威外推读数仍在窗口内，才从 `offsetSeconds = clamp(5 - secondsLeft, 0, 5)` 启动剩余部分；不回放旧窗口，不从 5 秒整轨开头重新倒数。这里的 `secondsLeft` 用已有小数读数，展示仍用原来的 ceil。
- [ ] **接回既有计时路径。** 删除 `SeatRow` 的旧 `beepingRef` effect，传 `useGoClock` 的现有读数和现有门禁给小 hook；local 路径传现有 `computeClock` 结果，删除旧 localBeepingRef effect。不能把计时提到面板父级造成整栏每 250ms 重画；不改 timeout 判负、数字钟或平台时限。
- [ ] **窗口回归使用现有文件。** 扩展 `GameControlPanel.playAi.test.tsx`：同一五秒窗口仅一次成功启动；相同快照重复 render 不重播；换 node/turn/period 能开启新窗口且旧 owner 取消不影响新 owner；播放中 pause/结束/卸载/hidden/静音立即 stop；失败后真实手势可在当前窗口重试，失效后不补播；3 秒时恢复只从 offset 2 开始。用可控 Promise 专门验证迟到成功不误播。保留已有“非当前席位不重复播放”和 local 路径断言。
- [ ] **运行并记录。** `cd katrain/web/ui && npm test -- src/hooks/useSound.test.tsx src/kiosk/components/game/GameControlPanel.playAi.test.tsx src/utils/audioPrefs.test.ts`，若 prefs 文件实际名称不同用现有确切文件名；再跑 `npx tsc -b`。不展开全仓回归或无关音频重构。

### Task 3: Focused browser evidence and handoff

- [ ] **一次代表性本地浏览器核对。** 使用隔离的现有 kiosk fixture/mock session，不能打生产建局 API。真实浏览器正常 autoplay policy；第一次进入不预先给 autoplay 特权。验证操作开始后实际媒体 `playing` 事件、资源 200、offset/currentTime 推进和停止；用隐藏/显示及 mock timer 切换核对不补播。保留一段有限证据，不为本次音频修复新建长期诊断平台。
- [ ] **默认值实际预览。** 同一目标 kiosk viewport 查看升降级初始用时 `30 分钟 · 3×30 秒`；本次没有视觉重构，只做一个代表性运行时预览并检查与设置选择一致，不扩张成全状态视觉审查。
- [ ] **区分自动化与听觉验收。** 测试的 `play()` Promise、`playing` 事件、解码后的轨道或捕获的 PCM 只能证明各自的链路，不能证明用户设备扬声器听得到。本阶段禁止远程发声；后续 ROOT 统一安排用户在设备上以隔离测试/自愿正常操作确认：末五秒五声“咚咚”可听、落子/暂停立即停、下一轮/下一期只响一次、静音后不响且解除静音跟当前剩余秒对齐。若 ROOT 尚未取得该真实听音结果，完成报告必须写“自动化/浏览器证据已验证，RK 实际听音待确认”，不得写“已听到”。
- [ ] **审查和提交。** 本计划交 ROOT 统一安排 Astra max 计划审（最多两轮），批准前不实现、不自行派审。实施按 SDD；随后由 ROOT 安排独立 Astra max 代码审到通过。只提交本任务相关文件，使用明确 pathspec，不扫描禁止目录；不部署、不改设备/云数据。交付列出实际测试、尚未取得的设备听音证据以及事发最终原因仍不能回溯的限制。

### Stop conditions

- 找到缺省偏好/当前音频 URL 正常，不等于证明当局扬声器正常；不要据此撤掉失败处理。
- autoplay 解锁方案若在目标浏览器的受控检查无效，先回到真实事件/Promise 证据定位，不叠加 WebAudio、TTS、定时器蜂鸣或修改系统启动参数。
- 不改已开局的时间快照，不把 `main_time` 秒/分钟混用，不更新所有模式的共享默认值。
- 达到上述针对性验证后停止；硬件听觉验收归明确记录的后续验收，不自行触发设备声音。
