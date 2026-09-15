# kiosk-go-play-ai · 实施计划修订设计 r1:终局并发模型

- 对象:`superpowers/tracks/kiosk-go-play-ai/plan.md`(下称 plan)。spec 是 `prd.md`,§6.0 正文不改,本设计也不违反它。
- 输入:Codex C1–C5、五份独立验证(全部 confirmed)、同类扫描 S1–S11、执行流程审计(结果为 `null`)。
- 口径:源码是现状;plan 里的代码是「将要写的」。行号以 2026-09-15 工作树为准(HEAD `ed2a1317`,树干净)。
- 边界:升降级账本 `ai_ladder_ranked.py` / `ai_ladder_catalog.py` 一行不改;终局收尾唯一入口是 `_finish_ended_game`(§6.0 第 1 条)。

---

## 0. 结论

五条发现是同一个病:**「对局结束了没有」由游标上的 `end_state` 临时推出来,检查和写入之间没有互斥,而且 await 之后还按游标重新推一遍**。所以这里不逐条打补丁,只立两件东西,所有写入者都走它们:

1. **终局事实** `WebGame.terminal: Optional[GameEnd]`。
   - 它记的是「这一局在哪一手、以什么结果结束」,不随游标变。
   - 它挂在对局对象上:新开局、载入 SGF、`game/setup` 都会新建 `WebGame`,事实自然就清掉了。
   - 先写的人算数:已经有终局,后到的写入一律被拒;唯一例外是给「双停、还没有结果」的那一手补上数出来的分数。
2. **对局提交锁**:直接复用现有的 `WebKaTrain.ai_ladder_commit_lock`(`threading.RLock`,`interface.py:144`)。
   - 以下动作都在这把锁里做,且各自是一个短临界区:「检查 → 落子」「检查 → 写终局」「挪游标」「时钟结算」。
   - AI 生成、补分析等长等待一律在锁外。

在这两件东西之上:

- **await 之后的复核**:按事先捕获的 `node` / `game` 身份做,不再按游标。
- **收尾**:按捕获的 `GameEnd` 落账。
- **超时请求**:带上期望的局 / 手 / 方,由服务端在锁里核对轮次,并用服务端时钟核实确实用完。
- **断线出口**:新增一条「先离开，不认输」,不经过认输。

---

## 1. 统一终局并发模型

### 1.1 现状:三拨写入者,两把互不相认的锁

| 写入者 | 线程 / 协程 | 今天持的锁 | 源码 |
|---|---|---|---|
| AI 生成 + 提交(`game.play`) | AI 后台线程 | `ai_lock` 贯穿整段生成;只有升降级分支的提交在 `ai_ladder_commit_lock` 里 | `interface.py:1097-1145`,`core/ai.py:1974-1981` |
| AI 认输(写 `end_state`) | AI 后台线程 | `ai_lock` | `core/ai.py:1956-1962` |
| 人的落子:`/api/move`、视觉 | 事件循环线程(async 端点) | `session.lock` | `server.py:992-996`,`:3185`,`:3242` |
| 认输 / 超时 / 数子写 `end_state` | 事件循环线程 | `session.lock` | `interface.py:1464-1469`;`server.py:1904-1906`、`:1981-1983`、`:2130-2132` |
| 悔棋 / 重做 / 导航(挪游标) | 线程池(sync 端点) | `session.lock` | `server.py:1006`、`:1021`、`:1280` → `WebGame.set_current_node`(`interface.py:93`) |
| 远端终局标记 | 请求 / 心跳 | `ai_ladder_commit_lock` | `ai_ladder.py:353-367` |
| 计时结算 `update_timer` | 任意线程(`get_state` 调它) | 无锁 | `interface.py:884-914`、`:431` |
| plan 新增:补分 `ensure_current_score` | `asyncio.to_thread` 工作线程 | 无锁 | plan:1064-1094 |
| plan 新增:收尾 `_finish_ended_game` | 事件循环协程 | `end_game_lock`(asyncio 锁) | plan:1657-1676 |

AI 线程从来不拿 `session.lock`,而 `session.lock` 也不能让它拿:`_do_new_game` 的持锁顺序是 `session.lock → ai_lock`(`interface.py:634-683`),AI 线程若是 `ai_lock → session.lock`,两者就会死锁。所以能把 AI 线程和请求线程放进同一个互斥区的锁只能是一把排在 `ai_lock` 之后的 threading 锁,也就是提交锁。asyncio 锁 AI 线程拿不到,不能用。

### 1.2 两个新判别位

**(a) `GameEnd` 与 `EndgameConflict`,放在 `katrain/web/models.py`**

放这里是因为 `tests/web_ui/conftest.py:90` 会把 `katrain.web.interface` 整个换成 MagicMock。异常类如果定义在 interface 里,`server.py` 的 `except` 在 web_ui 测试里拿到的就是 MagicMock。`models.py` 只依赖 pydantic,interface、session、server 都能 import 它。

```python
class GameEnd(NamedTuple):
    """这一局在哪一手、以什么结果结束。不随游标变 —— 翻手看棋不会让它消失。"""
    game: Any
    node: Any
    result: str

class EndgameConflict(Exception):
    """提交 / 终局判别没通过。reason ∈ already_ended | position_changed | stale_turn
    | not_your_turn | clock_not_expired | remote_ended"""
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason
```

**(b) `WebGame.terminal`(类属性默认 `None`)**

只有两处能写它,两处都在提交锁里:

- `WebKaTrain._commit_end_state(...)`:认输、超时、数子、双停补分、升降级认输、AI 认输,全部从这里写。
- `WebGame.play` 的双停检测:仅在 `play_analyze_mode == MODE_PLAY` 时,第二手停一手落下,就记 `GameEnd(self, node, self.end_result)`。这时结果还没有 `end_state`,称为「待补分」。

载入 SGF 再翻到双停终点**不会**写这个事实:那条路不经过 `play`。所以 plan:1273-1275 担心的「把载入的棋谱记成这个用户的对局」由构造本身排除。

### 1.3 锁序与持锁纪律

**锁序(全局唯一,只许按这个方向嵌套):**

`session.lock` → `ai_lock` → `ai_ladder_commit_lock`(对局提交锁,RLock)→ `Game._lock`(以及引擎内部的 `queue.put`)

各执行者实际走的路径:

- AI 线程:`ai_lock → 提交锁`,从不拿 `session.lock`。
- 请求:`session.lock → 提交锁`。
- 新开局:`session.lock → ai_lock → 提交锁`。
- 远端终局标记:只拿提交锁(`ai_ladder.py:360-367`,锁外才去 `terminate_queries`)。

引擎回调链已核:本地引擎在 `engine.py:558`、HTTP 引擎在 `engine.py:915` 调 `callback` / `update_state` 时都不持 `thread_lock`;`send_query` 只是 `queue.put`(`:609-610`)。所以不存在「持引擎锁 → 要提交锁」的反向边,锁图无环。

asyncio 锁(`end_game_lock`、`record_game_lock`)只在协程里拿,且**持任何 threading 锁时都不 await**,因此两类锁之间也不会互锁。

**持提交锁时只许做:**

- 读写节点和 `game.terminal`;
- `game.play` 与 `set_current_node`;
- `update_timer`(纯算术)。

**持提交锁时禁止:**

- `await`、数据库、网络;
- `update_state()`(它会触发 `_do_game_report` 遍历全树并广播);
- 回头去拿 `session.lock` 或 `ai_lock`;
- 等引擎。

持锁时长只有「链合并 + 建节点 + 入队」,亚毫秒级,事件循环线程最多等 AI 的一次提交,永远不会等生成。

### 1.4 必须经过提交锁的写入者(按 grep 穷举)

穷举来源:`grep -rn "end_state *=" katrain`、`grep -n 'katrain("play"' server.py`、`game.play(` 的调用方,以及 `set_current_node` / `update_timer`。

| # | 写入者 | 临界区内做什么 | 落到哪 |
|---|---|---|---|
| W1 | AI 提交(升降级分支与普通分支**合成一段**) | 先查远端终局(升降级)→ `_game_already_ended(game)` → 当前手仍是开算时的 `cn` → `game.play` | `core/ai.py` |
| W2 | AI 认输 | `_commit_end_state(f"{opp}+R", node=cn)`;没有这个方法(桌面 GUI / 替身)时照旧直写 | `core/ai.py:1956-1962` |
| W3 | `_do_resign(loser)` | 推认输方 → `_commit_end_state` | interface |
| W4 | `_do_timeout(...)` | 旧调用照旧;带绑定时核对局 / 手 / 方 / 叶子 / 服务端时钟 → `_commit_end_state` | interface |
| W5 | 数子 `_complete_count(..., node)` | `_commit_end_state(result, node=node)` | `server.py:1956` |
| W6 | 双停补分 `_score_two_pass_end` | `_commit_end_state(result, node=end.node, fill_pending=True)` | plan 新增 |
| W7 | 升降级认输直写(`server.py:1904-1906`) | 改走 `_commit_end_state(result)` | server |
| W8 | 人的落子 `_do_play(coords, guard, expected_player)` | 已终局 / 轮到 AI / 期望方不符就拒 → `game.play` | interface `:1191` |
| W9 | 挪游标 `WebGame.set_current_node` | 整体进锁 | interface `:93` |
| W10 | `WebGame.play` | 整体进锁(可重入);双停时记终局事实 | interface `:104` |
| W11 | `update_timer` | 整体进锁 | interface `:884` |
| W12 | 远端终局标记 | 已在锁里,不改 | `ai_ladder.py:353` |

**W9 为什么必须进锁**:AI 在锁里核完「当前手仍是 `cn`」之后、`Game.play` 读 `self.current_node` 之前,如果一次导航把游标挪走,着法会落到别的节点上(S2 的窄窗口)。

**W11 为什么必须进锁**:`get_state` 会被广播线程、引擎回调线程、请求线程并发调用。两次 `update_timer` 读到同一个 `last_timer_update`,会把同一段 dt 记两遍。闲了 20 秒后同时调,就会多扣 20 秒;超时由服务端时钟核实以后,这会直接变成「提前判负」。

### 1.5 长等待在锁外;await 之后按捕获的身份复核

| 长等待 | 捕获什么 | 等完怎么复核 |
|---|---|---|
| AI 生成(秒到分钟) | `generate_ai_move` **入口处**取 `cn = game.current_node`(策略本来就替它算,`LadderStrategy` 用的也是 `self.cn`) | W1 在锁里判 `game.current_node is cn` 且未终局 |
| 数子补分(≤15 秒) | `/api/count/request` 在 await **之前**取 `node = game.current_node`;`ensure_current_score(node=node)` 只补这一手 | W5 在锁里:当前手必须仍是 `node`、未终局、对局没被换掉 |
| 双停补分(≤15 秒) | 收尾拿到的 `GameEnd.node` | W6 `fill_pending`:`terminal.node is end.node` 且它还没有 `end_state` |

**一律不用的判据**:

- `session.game_ended`:AI 线程要等节流广播才会置上(`interface.py:806-822`);
- `_recorded`:游客局与落账失败时永远不置;
- `end_game_lock`:认输、超时、AI 线程都不拿;
- 游标上的 `game.end_result`:导航一挪就变。

`generate_ai_move` 的签名不变,入口处自己捕获 `cn`。原因是 `tests/web_ui/test_ladder_injection.py:244`、`:348` 的替身写死了 `(game, mode, settings)`,改签名会把它们全部打红。

### 1.6 收尾按捕获的终局落账,不看游标

**AI 线程**:`_do_ai_move_and_broadcast` 开头记 `before = game.terminal`,`finally` 里在 `update_state()` 之前取 `end = game.terminal`。满足 `before is None and end is not None and self.game is game` 时,调 `game_ended_callback(end)`。

- 这样即便广播之后有人立刻点「上一手」,也不影响回调拿到的是哪一局、哪一手。
- 如果终局是人发出的请求在生成期间写的,回调也会来一次,并与请求自己的收尾在 `end_game_lock` 下串行;`_recorded` 让第二次落账成为空操作。这是有意接受的重复调用,不另立判别位。

**请求路径**(`/api/move` 双停、认输、超时、数子)在 `session.lock` 里写完以后,立刻用 `end = _terminal_of(session)` 读对局级事实:

```python
def _terminal_of(session):
    t = getattr(getattr(session.katrain, "game", None), "terminal", None)
    return t if isinstance(t, GameEnd) else None
```

出锁后 `if end is not None: await _finish_ended_game(session, app, current_user, end)`。四个请求入口与 AI 回调因此全部汇到同一个函数。§6.0 第 1 条合并验收的 grep 要看到的就是这个。

**`_finish_ended_game(session, app, current_user, end)`,`end` 必填、不给默认值**:

```python
if session.player_b_id is not None or session.player_w_id is not None: return
if getattr(session, "mode", "play") == "research": return
async with <end_game_lock>:
    filled = await _score_two_pass_end(session, end)        # 只对「待补分」补;返回补上后的 GameEnd 或 None
    if session.katrain.game is not end.game:                # 等分析期间换了局:旧局的 SGF 已经不在,不落
        log.warning(...); return
    t = getattr(end.game, "terminal", None)
    final = filled or (t if isinstance(t, GameEnd) else end)   # 先到的那次收尾可能已经补过分
    if current_user is not None and session.user_id is not None:
        await _record_ai_game(session, app, current_user, final.result)
```

**`_score_two_pass_end(session, end)`**:

```python
if end.node.end_state or not getattr(session.katrain, "analysis_allowed", False): return None
score = await asyncio.to_thread(session.katrain.ensure_current_score, node=end.node)
if score is None: return None
result, _ = _count_result(score)
with session.lock:
    try:
        filled = session.katrain._commit_end_state(result, node=end.node, fill_pending=True)
    except EndgameConflict:
        return None
    session.game_ended = True
    session.last_state = session.katrain.get_state()
session.katrain.update_state()
return filled
```

### 1.7 超时:绑定服务端权威的轮次,并用服务端时钟核实

**能不能在服务端核实**:能。

- 时钟本来就在服务端累计:`update_timer` 由 `get_state`、`WebGame.play`、`set_current_node`、`_do_play` 驱动。
- 判超时的那一刻在提交锁里先调一次 `update_timer()`,再按设置判「轮到的一方是否用完」。

**请求**:`TimeoutRequest(session_id, expected_game_id?, expected_node_id?, color?)`。三个可选字段要么都给、要么都不给,否则 422。

**`_do_timeout(expected_game_id=None, expected_node_id=None, color=None)`**,整段在提交锁里:

- **不带绑定**(galaxy 旧调用):照旧 `_commit_end_state(f"{cn.player}+T")`。唯一的变化是先写者胜:已经结束就拒,由端点吞成 200 空操作。
- **带绑定**,按顺序判:
  1. `game.terminal` 已有 → `already_ended`;
  2. 局 id 不符、`id(cn)` 不符、`cn.next_player != color`、或 `cn.children` 非空(不在叶子) → `stale_turn`;
  3. `not self.clock_exhausted()` → `clock_not_expired`;
  4. 都通过 → `_commit_end_state(f"{对方}+T")`。

**`clock_exhausted()`** 与 `goClock.ts` 的 `readGoClock` / `isTimedGame`(plan:1888-1916)逐条同口径:

```
update_timer()
暂停 / 非 MODE_PLAY / 没有对局               → False
main_total<=0 且 byo_len<=0                    → False   (isTimedGame 为假)
本方已用主时间 < main_total                     → False
byo_len<=0 或 byo_periods<=0                    → True    (只有主时间;不许借用 update_timer 的 max(1,…))
否则 next_player_info.periods_used >= byo_periods
```

**核实不了时的判据**:暂停、不计时、非对局模式、不在叶子,**一律拒绝、不判负**(fail-closed)。把一个核实不了的「到点」写成输棋,代价是不可逆的。

**已知残留**:

- 服务端只在叶子上走钟。翻到前面看棋时 `get_state` 仍会把 `last_timer_update` 刷成当前时刻,这段时间不计入任何一方——这是今天就有的语义,本轮不改。
- 盒上服务重启以后会话就没了,也就无从判超时。

**前端**:

- 同一个「局 | 手 | 方」只发一次;服务端回 `clock_not_expired` 时,重同步后允许再核**一次**(最多两次)。
- 回 `stale_turn` / `already_ended` 时只重同步:局面换了,键自然变。
- 两边判据万一不一致,这样也不会刷成请求风暴。

### 1.8 断线出口不经过认输

- `connectionLost` 非空时,退出确认框多一颗「先离开，不认输」:只做 `navigate('/kiosk/play')`,不认输,也不清「继续上一局」。
- 回来时新挂载的 `useGameSession` 会重新取状态、重新建连;会话已被回收的,落到 Task 1 的「这一局已经打不开了」。
- 共享 hook 的连接行为不改(prd.md:304 延后项)。

### 1.9 冲突到 HTTP 的映射

`create_app` 注册一个 `@app.exception_handler(EndgameConflict)`,统一回 409:

| reason | detail |
|---|---|
| `already_ended` | `Game is already over`(Task 4 前端 `countFailureMessage` 已按 `already over` 分支) |
| `position_changed` | `Position changed while counting` |
| `stale_turn` | `timeout rejected: stale_turn` |
| `clock_not_expired` | `timeout rejected: clock_not_expired` |
| `not_your_turn` | `Not your turn` |
| `remote_ended` | `Ranked game has ended on another device` |

以下两种场景由端点自己接住:

- **认输**,以及**不带绑定的超时**:撞上 `already_ended` 回 200 空操作,返回真实局面,也不走多人局的落账和广播。这样退出框「认输并退出」在已结束的局上照样能走,galaxy 旧调用也不会弹红条。
- **带绑定的超时**:被拒前先 `session.last_state = get_state()`,让随后的 `GET /api/state` 给出此刻的局面与计时基准,然后照常抛出、回 409。

多人局那条「对方接受数子」的路(`respond_count`)在已结束时从「覆盖结果 + 再记一行」变成 409,落账之前就拒了,不需要额外代码。

### 1.10 有意的行为变化(写进提交信息与 Task 12)

1. **非研究会话结束后冻结**:
   - `/api/move` 与视觉落子回 409 / 被忽略;AI 不再起算;第二个终局写入被拒;翻手看棋照常可用。
   - 影响 galaxy:终局后退几手再点棋盘,从前是静默续下且不落账,现在回 409。
   - 研究会话与星阵平台会话(网关直接调 `katrain("play")`,不带 `guard`)不受影响。
2. **人机局在 AI 回合落子 / 停一手回 409**:从前会把这一子记成 AI 的颜色(S4)。
3. **kiosk 以 `terminal_result` 判「本局已结束」**:从前按一下「上一手」,终局卡、打谱键、「继续上一局」的清除就全部回退成「对局中」(S1)。

---

## 2. 逐条处置

### 2.1 Codex 发现(验证结论全部 confirmed)

| # | 处置 | 模型里的落点 |
|---|---|---|
| C1 超时不绑定轮次与时钟 | 采纳验证的方案 A,并收进统一模型 | 1.7;W4 在提交锁里;前端带期望字段、409 重同步、判叶子 |
| C2 数子 await 后不复核 | 采纳。复核放进 W5 的原子写入,不再依赖锁外预检;反方向(数子已写后认输 / 超时改写)由先写者胜覆盖 | 1.5;W5;1.9 |
| C3 AI 提交与终局写入不互斥 | 采纳验证推荐的「复用提交锁 + 唯一写入口」,并把普通分支、升降级直写、AI 认输、人的落子、挪游标一起纳入 | 1.3、1.4 |
| C4 收尾依赖游标 | 采纳「捕获 `GameEnd` 一路传递」;同类的数子路径按 C2 一并修 | 1.6;W5 / W6 |
| C5 断线出口等于认输 | 采纳验证的方案 C | 1.8 |

### 2.2 同类扫描实例

| # | 严重度 | 处置 | 理由 |
|---|---|---|---|
| S1 终局判定按游标 | high | **本轮修**:终局事实 + `terminal_result` + kiosk 改读 | plan 的收尾、时钟、N21 守卫都建在这个判别位上;不修的话,新加的服务端拒绝会把「静默续下」变成「按一下上一手就卡死」 |
| S2 AI 算完不复核节点 | high | **本轮修**(W1 身份复核 + W9) | 与 W1 是同一个临界区,多一个条件而已 |
| S3 守卫漏掉双停终局 | high | **本轮修**(W10 双停记事实) | 不修,C3 在双停场景下原样存在 |
| S4 单机局轮次只信浏览器 | high | **修一半**:人机局 AI 回合拒绝落子和停一手(W8)。**登记另一半**:本地对局连点「停一手」会把两人的停都按掉 | 后一半要 `/api/move` 带期望节点,改的是共享 `api.ts` / `useGameSession`,需要和 galaxy 一起验收 |
| S5 终局写入无先写者胜 | medium | **本轮修**(`_commit_end_state`) | 就是 C2 的反方向 |
| S6 时钟按游标走钟 | medium | **本轮修**:`useGoClock` 判叶子 + 判终局事实;服务端绑定要求叶子 | 与 C1 同一个函数 |
| S7 视觉落子锁内不复核 | medium | **修提交判别**(`guard=True, expected_player`,升降级分支同改)。**登记** orchestrator 缺一个「终局」暂停原因 | 暂停原因归视觉模块 |
| S8 大厅多人局落账不幂等 | medium | **顺带收窄**:认输 / 超时撞 `already_ended` 时不落账不广播;数子接受走 409。**登记** leave / 登出判负多记一行、`pending_count_request` 不清、timeout 胜方口径 | P8 归「人人对弈」模块(prd §5) |
| S9 替身测不出交错 | medium | **本轮修**:交错测试一律用真 `WebKaTrain` 放 `tests/` 根;web_ui 只证端点接线 | 见第 4 节各 Task 的测试表 |
| S10 本地对局认输方取自浏览器 | low | **登记** | 需要 `/api/resign` 带 `loser` 与期望节点,属共享接口 |
| S11 远端终局 await 后不复核 | low | **本轮顺带**:`_commit_end_state` 与 `_do_play(guard)` 在锁里查 `ai_ladder_remote_ended`,和标记写入同一把锁 | 一行代码 |

### 2.3 refuted 的发现

**无**。五条都 confirmed。验证过程对原文做了三处更正,都不改变修法:

- **C5**:「清掉继续上一局指针」在点「退出」那一刻并不成立——跳转时 GamePage 已经卸载;指针是回到那局、看到终局卡之后才清的。「照做就把这一局终结」仍然成立。
- **C1**:范围比原文大。不断线也会错(人在最后一刻落子);另有 AI 提交与在途人类落子两个缺口,已并入 W1 / W8。
- **C4**:数子路径是同形状的兄弟问题,按 C2 修。

---

## 3. 执行流程审计

证据包里 `procedures` 为 `null`:这一项审计**没有产出结果**(scratchpad `r1/exec-audit/` 里只有一份 vitest 输出格式的试探,没有结论)。本设计不替它编问题。

下面只列本修订**自己带来**的执行流程改动,都写进了第 4 节:

1. **Task 2 起就动共享领地**(`api.ts` 加 `terminal_result` 类型):Task 2 Step 7 追加 `npm run build && npm run build:kiosk-2d`。
2. **提交锁与 `_do_play` 的改动会波及几份用真 `WebKaTrain` 的既有测试**:
   - `tests/web_ui/test_ladder_injection.py`(模块顶部 `sys.modules.pop` 换回真类);
   - `tests/core/test_ladder_strategy.py`、`tests/test_ai_resignation.py`、`tests/test_vision_move_poller.py`、`tests/test_guest_free_play.py`。

   Task 2 Step 4 的运行清单要补上它们,仍按根目录一条命令、web_ui 一条命令分开跑。
3. **替身跟上真接口,端点里不用 `getattr` 迁就替身**(plan:1105 已立的原则):
   - `tests/web_ui/test_ai_ladder_api.py` 的 `FakeKaTrain` 在 Task 2 加提交锁和 `_commit_end_state`;
   - `tests/web_ui/test_ai_game_autosave.py` 的 `_make_mock_session` 在 Task 5 加 `game.terminal`。
4. **Task 6 从「只改 interface 的判别位」变成「改 server / interface / models」**:依赖顺序改成必须排在 Task 5 之后,见第 5 节。
5. **合并验收的 grep 提前到每个相关 Task 结束时跑**,Task 12 再汇总跑一次。

---

## 4. 计划改动清单(按 Task)

标注说明:「plan:N」是 plan.md 行号;测试写明文件、用例名,以及在哪种错误实现下会变红。

### 4.0 Global Constraints 与 File Structure

- **plan:16-36 Global Constraints** 追加一条「对局提交锁」:
  - 锁序:`session.lock → ai_lock → ai_ladder_commit_lock → Game._lock`;
  - 持锁禁止:await、IO、`update_state`、再拿上游锁、等引擎;
  - 终局只经 `_commit_end_state` 写,`WebGame.terminal` 是「这局结束了没有」的唯一判据;
  - await 之后按捕获的 node / game 复核,不按游标。
- **plan:40-55 File Structure**:
  - 新增 `katrain/web/models.py` 一行:`GameEnd`、`EndgameConflict`(Task 2),`TimeoutRequest`(Task 6);
  - `interface.py` 一行补:提交锁覆盖 `play` / `set_current_node` / `update_timer`、`_commit_end_state`、`_do_play(guard, expected_player)`、`clock_exhausted`、`get_state.terminal_result`;
  - `core/ai.py` 一行改为「提交段统一进锁;复核终局事实与开算节点;AI 认输走写入口」;
  - `server.py` 一行补:`EndgameConflict` 处理器;四个终局请求入口经 `_finish_ended_game`;`/api/timeout` 绑定;视觉分支 `guard`;
  - `api.ts` 一行补:`terminal_result?`;
  - 「既有测试文件」补:`tests/web_ui/test_ai_ladder_api.py`(Task 2)、`tests/web_ui/test_ai_game_autosave.py`(Task 5)。
- **plan:57 依赖行**:改写为第 5 节的依赖图。

### 4.1 Task 2(N21)→ 扩为「N21 + 终局事实 + 对局提交锁」

**Files(plan:382-388)**,追加:

- `katrain/web/models.py`
- `katrain/web/interface.py:92-120`(WebGame)、`:884`(`update_timer`)、`:852`(AI 触发条件)、`:560` 附近(`get_state`)、`:1191`(`_do_play`)、`:1467`(`_do_timeout`)
- `katrain/web/server.py`:`create_app` 注册处理器;`/api/move :994`;`/api/resign :1899-1918`(含升降级分支 `:1904-1906`);`/api/timeout :2127-2166`;视觉 `:3185`、`:3242`
- `katrain/web/ui/src/api.ts`(类型)
- `tests/web_ui/test_ai_ladder_api.py`(`FakeKaTrain`)

**Interfaces(plan:390-394)**,改为 Produces:

- `GameEnd`、`EndgameConflict`(models)
- `WebGame.terminal`
- `WebKaTrain._commit_end_state(result, *, node=None, fill_pending=False) -> GameEnd`(冲突时抛 `EndgameConflict`)
- `_do_resign(loser=None)`、`_do_timeout()`(Task 6 扩参)、`_do_play(coords, guard=False, expected_player=None)`
- `get_state()["terminal_result"]`
- `core.ai._game_already_ended(game)`
- server `_terminal_of(session)`

**Step 3 实现(替换 plan:675-740)。**

1. **`_commit_end_state`**(放在 `_do_resign` 之前):

   ```python
   def _commit_end_state(self, result, *, node=None, fill_pending=False):
       with self.ai_ladder_commit_lock:
           if getattr(self, "ai_ladder_remote_ended", False):
               raise EndgameConflict("remote_ended")
           game = self.game
           target = game.current_node if node is None else node
           t = game.terminal
           if fill_pending:
               if t is None or t.node is not target or target.end_state:
                   raise EndgameConflict("position_changed" if t is None else "already_ended")
           elif t is not None:
               raise EndgameConflict("already_ended")
           elif target is not game.current_node:
               raise EndgameConflict("position_changed")
           target.end_state = result
           game.game_result = result          # 只写不读(grep 核过),与数子 / 升降级认输原写法一致
           game.terminal = GameEnd(game, target, result)
           return game.terminal
   ```

2. **`_do_resign(loser=None)`**:plan:678-692 的推算原样保留,整个函数体放进 `with self.ai_ladder_commit_lock:`,最后一行改为 `return self._commit_end_state(f"{winner}+R")`。

3. **`_do_timeout()`**:`with lock: return self._commit_end_state(f"{self.game.current_node.player}+T")`。语义与今天相同,只多了「已结束就拒」。

4. **`WebGame`**:
   - 类属性 `terminal: Optional[GameEnd] = None`;
   - `set_current_node` 与 `play` 的函数体各包一层 `with self.katrain.ai_ladder_commit_lock:`。`WebGame` 只在 `interface.py:710` 由 `WebKaTrain` 构造(grep 核过,测试里没有直接构造);`ai_ladder_commit_lock` 在 `super().__init__` 之前就已赋值(`:144`),所以 `Game.__init__` 期间调到 `set_current_node` 时锁也已经在了,不需要 `getattr` 兜底;
   - `play` 在 `super().play` 之后:若 `self.terminal is None and node.is_pass and node.parent is not None and node.parent.is_pass and self.katrain.play_analyze_mode == MODE_PLAY`,则 `self.terminal = GameEnd(self, node, self.end_result)`。

5. **`update_timer`**:函数体进锁(RLock,`play` / `set_current_node` 里再调它可以重入)。

6. **`_do_play(coords, guard=False, expected_player=None)`**:
   - 原函数体的「`update_timer` → minimal_use → `game.play`」放进锁里;
   - 进锁后先判:
     - `guard` 且 `self.game.terminal is not None` → `already_ended`;
     - `guard` 且 `MODE_PLAY` 且 `self.next_player_info.ai` → `not_your_turn`;
     - `expected_player` 不等于 `current_node.next_player` → `stale_turn`;
   - `play_stone_sound` 挪到锁外。

7. **`_do_update_state`**(`:852` 那组条件):加一条 `and self.game.terminal is None`。防的是平台局双停之后仍收到镜像落子时,「AI 提交被拒 → update_state → 再起算」的空转。

8. **`get_state`**:加 `"terminal_result": self.game.terminal.result if self.game.terminal else None`。

9. **`core/ai.py`**(替换 plan:695-722):
   - `_game_already_ended(game)` = `getattr(game, "terminal", None) is not None or bool(getattr(game.current_node, "end_state", None))`;
   - `generate_ai_move` 入口处取 `cn = game.current_node`;
   - 认输分支:
     - 有 `game.katrain._commit_end_state` 时 `try: commit(result, node=cn) except Exception as e: log(DEBUG) ; return None`(core 不 import web;异常面只有 `EndgameConflict`);
     - 没有时照旧直写;
   - 提交段:两条分支共用一个 `with commit_lock or nullcontext():`,依次判:
     - 升降级且远端已结束 → `raise LadderUnavailable`;
     - `_game_already_ended(game) or game.current_node is not cn` → `return None`;
     - 否则 `played_node = game.play(move)`。

10. **`server.py`**:
    - **处理器**:按 1.9 注册。
    - **`/api/move :994`**:改为 `session.katrain("play", …, guard=session.mode != "research")`。
    - **`/api/resign`**:
      - 升降级分支 `:1904-1906` 两行直写,换成 `session.katrain._commit_end_state(result)`,`game_ended` 与 `_state` 的写法保留;
      - 非升降级分支(plan:727-739):`try: …katrain("resign"[, loser]) ; wrote = True except EndgameConflict: wrote = False`;
      - 多人局落账与广播的条件加 `and wrote`;
      - 单机落账那一支本 Task 不动(Task 5 统一改)。
    - **`/api/timeout :2131`**:同认输,`try/except` 加 `wrote` 闸。
    - **视觉**:
      - `:3242` 改为 `session.katrain("play", move.coords, guard=True, expected_player=move_player)`,外包 `try: … except EndgameConflict as e: log.info(...); _rearm_detection(); return 0.5`;
      - 升降级分支 `:3185` 同样传两个参数,并把 `EndgameConflict` 加进 `:3186` 那个 `except`。
      - 与跨平台 N13 在同一段相邻改动,合并时逐段对。

11. **`FakeKaTrain`**(`tests/web_ui/test_ai_ladder_api.py:97` 起):
    - 加 `self.ai_ladder_commit_lock = threading.RLock()`;
    - 加 `_commit_end_state(result, *, node=None, fill_pending=False)`:锁里先判「`getattr(game, "terminal", None)` 或 `current_node.end_state` → 抛 `EndgameConflict`」,再写 `end_state`、`game.terminal`、`_state["end_result"]`,`game.end_result` 用 `try/except AttributeError` 写(兼容 `:1596` 那个只读属性的对局);
    - `resign` / `timeout` 两个分支同样写 `game.terminal`。

**Step 1 追加测试。**

`tests/test_play_ai_endgame.py`(根目录,真 `WebKaTrain`,**不与 web_ui 同命令**):

| 用例 | 做法 | 在哪种错误实现下变红 |
|---|---|---|
| `test_a_terminal_write_racing_the_ai_commit_is_never_erased[mode×writer]` | mode ∈ {`"test:instant"`, `AI_LADDER`};writer ∈ {`w._do_resign()`、`w._commit_end_state("W+R")`}。<br>`monkeypatch.setitem(ai.STRATEGY_REGISTRY, mode, 立即回白 15,15)`;把 `ai._game_already_ended` 换成包装:先调真函数,若当前线程名是 `ai-commit` 且第一次进入,就置 `reached` 并 `release.wait(2)`。<br>`threading.Thread(target=ai.generate_ai_move, args=(w.game, mode, {}), name="ai-commit")`。<br>断言 `reached.wait(2)`;writer 另起线程后 `assert not writer_done.wait(0.1)`;放行、join。<br>最终 `w.game.terminal.node is w.game.current_node and w.game.end_result == "W+R"` | ① plan 原样(普通分支不拿锁):writer 0.1 秒内写完,且 `end_result` 事后为 None;<br>② 复核放在锁外:停点不在锁里,writer 不等;<br>③ 某个写入者绕开写入口 / 不拿锁;<br>④ `_game_already_ended` 不在提交段里调:`reached` 超时 |
| `test_a_resign_during_generation_does_not_wait_for_the_engine` | 策略在 `generate_move` 里 `go.wait(5)`;另一线程 `w._do_resign()`,`assert writer_done.wait(1.0)`;放行后 `generate_ai_move` 返回 None,当前手仍是人那一手 | 锁包住整段生成,或写入者去拿 `ai_lock` |
| `test_an_ai_move_computed_for_a_position_that_was_undone_is_dropped` | 两人座位下 B、W 各一手,再把白改成 AI;策略在 `generate_move` 里 `self.game.undo(1)` 后返回白着 | 不复核开算节点:返回非 None,且父节点多出一个白子分支 |
| `test_once_the_game_has_ended_nothing_continues_it` | 两人座位下 B、W 各一手 → `w._do_resign()` → `w.game.undo(1)`。<br>断言 `get_state()["end_result"] is None` 且 `["terminal_result"] == w.game.terminal.result`;`_do_play((4,4), guard=True)`、`_do_resign()`、`_commit_end_state("B+1.0")` 都抛 `EndgameConflict`;终局那一手的 `end_state` 不变。<br>正对照:不带 guard 的 `_do_play((4,4))` 成功(研究 / 平台路径)。<br>双停变体:`_do_play(None, guard=True)` 两次 → `terminal` 已置而 `current_node.end_state is None`;第三次停一手抛异常;`ai.generate_ai_move(w.game, "test:instant", {})` 返回 None。<br>远端变体:新局上 `w.ai_ladder_remote_ended = True` → `_commit_end_state` 抛 `remote_ended` | 终局判据仍读游标;双停不记事实(第三手被接受 / AI 落子,即 S3);`get_state` 漏字段 |
| `test_a_human_move_on_the_ai_seat_is_refused` | `_seat(w, {"B"})`,`w._do_play((3,3), guard=True)` 之后,`_do_play((4,4), guard=True)` 与 `_do_play(None, guard=True)` 都抛 `not_your_turn` | 缺 AI 座位判别(S4) |
| `test_a_vision_stone_after_the_game_ended_is_not_played` | 真 `WebKaTrain` + `server._handle_confirmed_move`;`app` / `vision` / 会话照 `tests/test_vision_move_poller.py:24-113` 的 `SimpleNamespace` 形状。认输后送一颗轮到方颜色的 `ConfirmedMove`;断言返回 0.5、没有新节点、`vision.expected_pushes` 非空 | 视觉分支漏传 `guard` |

`tests/web_ui/test_play_ai_endgame_api.py`(替身会话,只证接线):

| 用例 | 做法 | 在哪种错误实现下变红 |
|---|---|---|
| `test_a_move_refused_by_the_runtime_is_a_409_not_a_500` | `katrain.analysis_allowed = False`(让 `tracks_auto_analysis` 走 nullcontext);`side_effect` 收到 `"play"` 就抛 `EndgameConflict("already_ended")`。断言 409、detail 含 `already over`、`assert_any_call("play", (3, 3), guard=True)` | 端点没传 `guard`;没注册处理器(变 500) |
| `test_resigning_an_ended_lobby_game_neither_records_nor_broadcasts` | 多人会话;`side_effect` 收到 `"resign"` 就抛冲突;替换 `manager._schedule_broadcast` 收集消息。断言 200、没有 `game_end`、`app.state.game_repo.record_multiplayer_game` 未被调用 | 多人局落账 / 广播没加 `wrote` 闸 |

`tests/core/test_ai_commit_after_end.py`(plan:481-561)不改用例,docstring 注明「只证宽窗口;窄窗口在 `tests/test_play_ai_endgame.py` 用真类证」。

**Step 2 Expected(plan:668-671)**:追加以上新用例在实现前都 FAIL,各自理由:

- 竞态用例:writer 不等锁;
- 撤销用例:返回非 None;
- 冻结用例:`AttributeError` 找不到 `terminal` / `_commit_end_state`;
- AI 座位用例:`TypeError` 不认识 `guard`;
- 视觉用例:多了新节点;
- 两条 web_ui 用例:500 / 调用参数不符。

**Step 4 运行(plan:744-750)**,仍然分两条命令:

- 根目录:`tests/test_play_ai_endgame.py tests/core/test_ai_commit_after_end.py tests/core/test_ladder_strategy.py tests/test_ai_resignation.py tests/test_vision_move_poller.py tests/test_guest_free_play.py`
- web_ui:`tests/web_ui/test_play_ai_endgame_api.py tests/web_ui/test_game_termination_and_chat_identity.py tests/web_ui/test_ai_game_autosave.py tests/web_ui/test_ai_ladder_api.py tests/web_ui/test_ladder_injection.py tests/web_ui/test_navigation_guards.py`

**Step 5 / 6 前端(plan:753-799)**,在原两条认输框用例之外追加一条,并同步改实现。

- 用例 `终局后退到前一手:仍是终局,不把「继续上一局」写回来`:
  - Task 1 的 `MockPanelProps` 加 `isGameOver?: boolean`,替身渲染 `<span data-testid="panel-over">{String(p.isGameOver)}</span>`;
  - `makeState({ end_result: null, terminal_result: 'W+R', children: [['W',[3,3]]] })`;
  - 断言 `panel-over` 为 `true`、`clearActiveSession('game')` 被调、`writeActiveSession` 未被调;
  - 变红条件:`isGameOver` 仍然只读 `end_result`。
- 实现(`GamePage.tsx`):
  - 加 `const endResultOf = (gs: GameState) => gs.end_result || gs.terminal_result || null;`;
  - `:361` `isGameOver = !!endResultOf(gameState)`;
  - `:84` `aiThinking`、`:123` `KioskResultBadge result`、`:231` activeSession effect(依赖项加 `terminal_result`)都改读它;
  - `handleBoardMove`(`:446`)开头加 `if (isGameOver) return;`。
- `api.ts` 的 `GameState` 加 `terminal_result?: string | null;`。

**Step 7(plan:801-819)**:

- 追加 `npm run build && npm run build:kiosk-2d`(`api.ts` 是共享领地)。
- `git add` 补上 `katrain/web/models.py`、`katrain/web/ui/src/api.ts`、`tests/web_ui/test_ai_ladder_api.py`。
- 提交信息补一句:「终局事实挂在对局上、先写者胜;AI 提交 / 终局写入 / 落子 / 挪游标共用对局提交锁;非研究会话终局后不再接受落子(galaxy 终局后翻手落子改回 409)」。

### 4.2 Task 4(A12)

**Files(plan:937-943)**:补 `server.py:1956-2000`(`_complete_count`)。

**Interfaces(plan:945-948)**:

- `ensure_current_score(self, timeout_s=None, node=None)`,`node` 为 None 时才取当前手;
- `_complete_count(session, app, current_user, node=None)`。

**实现**:

1. **`ensure_current_score`**(plan:1078):`node = self.game.current_node if node is None else node`,其余不变。

2. **`/api/count/request` 的 else 分支**:用下面这段替换 plan:1097-1103 的那一行 await 以及其后的锁块:

   ```python
   game = session.katrain.game
   node = game.current_node                      # 数的是这一局这一手;等分析的这几秒里局面可能变
   await asyncio.to_thread(session.katrain.ensure_current_score, node=node)
   with session.lock:
       guard_ai_ladder_ranked_human_action(session, current_user, "request-count")
       result, needs_record = _complete_count(session, app, current_user, node=node)
       state = session.katrain.get_state()
       session.last_state = state
   ```

   复核不在端点里写:`_complete_count` 内部的 `_commit_end_state(result, node=node)` 在提交锁里原子地核「没被别人先结束、仍是当前手、对局没被换掉」,冲突交给处理器回 409。

3. **`_complete_count(..., node=None)`**:
   - `node = current if None`;
   - 先做一次非原子预检 `if _terminal_of(session): raise EndgameConflict("already_ended")`——只为分析超时时说对原因;
   - `score = node.score`,为 None 时照旧 400;
   - `result, winner_color = _count_result(score)`(把格式化抽成纯函数,Task 5 复用);
   - 调 `session.katrain._commit_end_state(result, node=node)` 写入;
   - `session.game_ended = True`;
   - 多人局落账和广播不变:冲突在它们之前就抛出了。

4. **`FakeKaTrain.ensure_current_score(self, timeout_s=None, node=None)`**(plan:1108):返回 `(node or self.game.current_node).score`。

5. **前端 `countFailureMessage`**(plan:1176-1183):加一支 `message.includes('Position changed') ? t('game:count_position_changed', '数子这几秒里局面变了，请重新数子')`。

**Step 1 追加测试。**

`tests/test_play_ai_endgame.py`(根目录,真类,走 TestClient):

- 夹具照 `tests/test_guest_free_play.py:17-57`:`isolated_session_factory`,游客会话 + 两边坐人,避免 AI 线程;
- 用 `/api/move` 下几手;把会话实例的 `count_min_moves` 替成 `lambda: 0`;
- `ensure_current_score` 换成一个阻塞函数,它会断言 `node is 开算时的当前手`,再在函数体里经 TestClient 发请求。

| 用例 | 在补分的阻塞函数里做什么 | 断言 | 在哪种错误实现下变红 |
|---|---|---|---|
| `test_count_that_waited_for_analysis_does_not_overwrite_a_resignation` | `client.post("/api/resign")`,然后令 `node.score = 2.5` 并返回 | resign 200;count 409 且 detail 含 `already over`;`w.game.terminal.result` 仍是认输结果;`w.game.end_result` 不是 `B+2.5` | plan 原样(await 后无条件写,count 200 并改写结果);只在 await 前检查;写入绕开 `_commit_end_state` |
| `test_count_does_not_finish_a_position_that_changed_while_it_waited` | `client.post("/api/undo", json={"session_id": sid, "n_times": 1})`,然后令 `node.score = -1.5` 并返回 | count 409 且 detail 含 `Position changed`;`w.game.terminal is None`;新游标那一手 `end_state is None` | 不带 `node` 复核(按游标数了另一手) |

`tests/web_ui/test_play_ai_endgame_api.py`:plan 的 `test_count_fills_the_missing_score_before_counting` 改为断言 `ensure_current_score.assert_called_once_with(node=session.katrain.game.current_node)`。变红条件:漏传 `node`。

`GamePage.playAi.test.tsx`:A12 describe 里加一条「局面变了」文案用例,1 个 `it`。

**Run(plan:1113)**:根目录命令补 `tests/test_play_ai_endgame.py`;web_ui 命令补 `tests/web_ui/test_ai_game_autosave.py tests/web_ui/test_game_termination_and_chat_identity.py tests/web_ui/test_navigation_guards.py`。

**提交信息(plan:1229-1233)**:补一句「等分析期间对局被结束或局面变了,数子不改写;先写者胜」。

### 4.3 Task 5(N22)

**Interfaces(plan:1249-1256)**:

- `WebKaTrain.game_ended_callback: Optional[Callable[[GameEnd], None]]`
- `SessionManager.on_game_ended: Callable[[WebSession, GameEnd], Awaitable[None]]`
- `_on_game_ended(session_id, end)`、`_schedule_game_ended(session, end)`
- server `_count_result(score)`、`async _score_two_pass_end(session, end) -> Optional[GameEnd]`、`async _finish_ended_game(session, app, current_user, end)`
- `_on_game_ended_off_request(session, end)`
- 删掉 plan 里的 `_apply_counted_result`:它的写入职责已经归 `_commit_end_state`,格式化归 `_count_result`。

**实现**:

1. **`_do_ai_move_and_broadcast`**(替换 plan:1526-1548):
   - 开头 `game = self.game; before = getattr(game, "terminal", None)`;
   - `finally` 里先 `end = getattr(game, "terminal", None) if game is not None else None`,再 `update_state()`;
   - 条件改为 `callback is not None and before is None and end is not None and self.game is game` 时调 `callback(end)`。
2. **`session.py`**(plan:1573、:1579-1607):
   - `lambda end, sid=session_id: self._on_game_ended(sid, end)`;
   - `hook(session, end)`。
3. **`server.py`**:
   - `_score_two_pass_end` 与 `_finish_ended_game` 按 1.6 替换 plan:1612-1678,删除 plan:1615-1630 的 `_apply_counted_result` 抽取;
   - `_on_game_ended_off_request(session, end)`(plan:1680-1689)把 `end` 传下去。
4. **四个请求入口统一收尾**,都是在 `session.lock` 里写完后立刻 `end = _terminal_of(session)`,出锁后 `if end is not None: await _finish_ended_game(session, app, current_user, end)`:
   - `/api/move`(替换 plan:1706-1713):收尾之后再 `state = get_state(); session.last_state = state`;
   - `/api/resign :1948-1952`:单机分支改为 `elif not is_multiplayer and end is not None`;平台分支同样在 `state` 之后读 `end`;
   - `/api/timeout :2160-2164`:同上;
   - `/api/count/request` 单机分支(Task 4 的 `needs_record` 分支):改为 `if end is not None`。

   四处都不再直接调 `_record_ai_game(`。

5. **`tests/web_ui/test_ai_game_autosave.py::_make_mock_session`**(`:18`):加 `game.terminal = GameEnd(game, game.current_node, end_result) if end_result else None`,并 `from katrain.web.models import GameEnd`。

**测试**:

- **plan:1265-1336 hook 文件**:
  - `_on_game_ended(session.session_id, end)` 与 `hook(s, end)` 跟着改签名;`end = GameEnd(None, None, "B+R")` 即可(钩子只转发);
  - `test_create_session_wires_the_ai_thread_callback` 改为 `session.katrain.game_ended_callback(end)`,断言 `called == [(sid, end)]`。
- **plan:1366-1502 根目录收尾用例:改用真对象**。
  - `_ended_session` 改为造真 `WebKaTrain`:两人座位,打出双停或认输,见各用例;再造真 `WebSession(session_id, katrain=w, user_id=42)`,并设 `game_type = "free"`;实例上替掉 `ensure_current_score`;调用处传 `end = w.game.terminal`。
  - `test_two_pass_end_is_scored_before_it_is_recorded` 断言 `w.game.terminal.result == "B+2.5"` 且 `end.node.end_state == "B+2.5"`。
  - 原先的 MagicMock 版证不出填写那一步。
- **新增 `test_stepping_back_or_starting_over_while_the_end_is_scored[action]`**,`action ∈ {undo_score_2.5, undo_score_None, new_game}`:

  | action | 补分函数里做什么 | 断言 |
  |---|---|---|
  | undo | `with session.lock: w("undo", 1)` | 游标停在 `end.node.parent`(收尾不拽游标);`user_games_create` 恰好 1 次;`result` 为 `B+2.5`,或分数为 None 时为 `end.result`;`end.node.parent.end_state is None` |
  | new_game | `w._do_new_game()` | `user_games_create` 未被调用 |

  补分替身返回 `score if node is end.node else 99.0`。变红条件:
  - plan 原样:比游标 + 游标回退值,两个 undo 用例都记不上;
  - 写到游标那一手:`parent.end_state` 非空;
  - 补分漏传 `node`:得到 `B+99.0`;
  - 拽回游标:第一条断言红;
  - 换局后不放弃:new_game 用例落了账。
- **`_ai_thread_game`(plan:1397-1415)**:
  - 回调改为 `lambda end: calls.append(end)`;
  - 加变体 `update_state = lambda **_k: w.game.undo(1)`,断言 `len(calls) == 1 and calls[0].node.is_pass`;
  - 变红条件:在 `update_state` 之后按游标取终局。
- **plan:1429-1501 六处调用**:补上 `end` 参数。

**Step 4 运行(plan:1722-1724)**:web_ui 那条保持原清单(已含 `test_ai_game_autosave.py`);两条命令之后追加 §6.0 的合并 grep:

```
grep -n "_record_ai_game(" katrain/web/server.py
```

期望只剩定义,以及 `_finish_ended_game` 里的那一次调用。

### 4.4 Task 6(A18)

**Files(plan:1749-1756)**:补

- `katrain/web/models.py`(`TimeoutRequest`)
- `katrain/web/server.py:2119-2166`
- `katrain/web/interface.py`(`_do_timeout`、`clock_exhausted`)
- `katrain/web/ui/src/api.ts:391`(`timeout` 第三参数)
- `tests/web_ui/test_play_ai_endgame_api.py`

**Interfaces(plan:1758-1766)**:

- Consumes 改为「Task 2 的提交锁 / `_commit_end_state` / `terminal_result`,Task 5 的 `_finish_ended_game`」;
- Produces 补 `TimeoutRequest`、`WebKaTrain.clock_exhausted()`、`_do_timeout(expected_game_id=None, expected_node_id=None, color=None)`、`API.timeout(sessionId, token?, expect?)`。

**Step 1 扩为「判别位 + 超时绑定」**,在原 `timer_configured` 之后追加:

1. **models**:
   - `TimeoutRequest`,带 `@model_validator(mode="after")`:三字段要么全给要么全无;
   - `color: Optional[Literal["B","W"]]`。
2. **interface**:按 1.7 写 `clock_exhausted()` 与 `_do_timeout(...)`,整段在提交锁里。
3. **server `/api/timeout`**:
   - 请求模型换成 `TimeoutRequest`;
   - `bound = request.expected_node_id is not None`;
   - 锁里:bound 时调 `session.katrain("timeout", expected_game_id=…, expected_node_id=…, color=…)`,否则调 `session.katrain("timeout")`;
   - `except EndgameConflict`:先 `session.last_state = get_state()`,bound 就 `raise`,否则 `wrote = False`;
   - 其余沿用 Task 2 / Task 5 的写法。

**测试**:

`tests/test_play_ai_endgame.py`(根目录;`monkeypatch.setattr(katrain.web.interface, "time", fake)`,`fake` 提供 `time` / `monotonic` / `sleep`):

| 用例 | 做法 | 在哪种错误实现下变红 |
|---|---|---|
| `test_a_timeout_for_a_turn_the_server_has_moved_past_is_refused` | 读秒 30×3、不暂停、`MODE_PLAY`、两人座位。黑落子 → `stale = w.get_state()`(轮到白)→ 服务端落白 → 假时钟前进 91 秒(黑也用完)。<br>`pytest.raises(EndgameConflict)` 包 `w._do_timeout(stale["game_id"], stale["current_node_id"], "W")`,`end_result is None`;再用新一帧的节点和 `"B"` 调用 → `W+T` | 不绑定(今天的写法写出 `W+T`);只核时钟不核轮次(黑也耗尽,同样写出 `W+T`) |
| `test_a_timeout_for_an_older_node_of_the_same_colour_is_refused` | 漏两手,两帧都轮到黑,服务端已耗尽,拿旧节点调用 → `stale_turn` | 只核 `color` 不核节点 |
| `test_the_server_clock_must_have_run_out` | 轮次与方都对:前进 89 秒 → `clock_not_expired`;再前进 2 秒 → `W+T`(白胜) | 省掉时钟核实 |
| `test_main_time_only_game_expires_exactly_at_main_time_end` | 主时间 1 分钟、读秒 0/0,前进 60 秒 → 被接受 | 复用 `update_timer` 的 `max(1,…)`(要 61 秒)——前端停在「超时」而服务端永远不判 |
| `test_a_bound_timeout_that_waited_for_the_ai_commit_is_stale` | 沿用 Task 2 竞态用例的停点:AI 停在提交段内;另一线程拿 AI 提交之前那一帧的节点做带绑定的超时;断言它被阻塞;放行后抛 `stale_turn`,`end_result is None` | 轮次核对放在提交锁外(读到旧节点、写到 AI 那一手上) |
| `test_an_unbound_timeout_keeps_its_old_meaning` | 不带参数 `_do_timeout()` → 写 `f"{cn.player}+T"` | 把 galaxy 的旧调用一并改了语义 |

`tests/web_ui/test_play_ai_endgame_api.py`:

- `test_timeout_passes_the_expected_turn_and_maps_a_refusal_to_409`:
  - `side_effect` 抛 `EndgameConflict("stale_turn")`;带三字段 POST → 409;`assert_any_call("timeout", expected_game_id="g", expected_node_id=5, color="W")`;
  - 同文件再加一条参数化:不带字段 → `assert_any_call("timeout")`、200;冲突为 `already_ended` 时仍 200;
  - 变红条件:模型没加字段(被丢弃)、没接异常(500)、旧调用被改。

`GamePage.playAi.test.tsx`(替换 plan:2134-2160 第一条,另两条保留):

| 用例 | 断言 | 在哪种错误实现下变红 |
|---|---|---|
| `到点 → API.timeout 带上局 / 手 / 方` | `vi.spyOn(API,'timeout')` 以 `('play-ai-s1', undefined, { expected_game_id: 'g', expected_node_id: 5, color: 'B' })` 被调用;同一帧点两次只调一次 | 仍走 `handleAction('timeout')`,或不带期望字段 |
| `服务端说轮次过期 → 重同步,不上红条` | `API.timeout` 以 `new ApiError(409, 'Request failed 409: {"detail":"timeout rejected: stale_turn"}')` 拒绝 → `API.getState` 被调,`sessionMock.setGameState` 收到新帧;屏上没有错误文案 | 409 被吞掉,或被写成红条 |
| `服务端说时间没到 → 同一手只再核一次` | `clock_not_expired` 拒绝:点第二次调用数为 2,点第三次仍为 2 | 没有重试,或无限重试 |
| `翻到了前面(不在叶子)不判超时` | `makeState({ children: [['W',[3,3]]] })` 点 `MOCK_TIMEOUT_B` → 不调用 | 缺叶子闸 |

`GameControlPanel.playAi.test.tsx` 追加:

- `有子节点或已有终局事实时时钟不走、不回调`:`children` 非空 / `terminal_result` 有值,前进 31 秒,`onTimeout` 未被调用。变红条件:`active` 缺这两个条件。
- `换了一手、仍已耗尽 → 再回调一次`:`rerender`,`current_node_id` 从 7 换成 9,仍轮到 B 且已耗尽 → 调用 2 次。变红条件:`useEffect` 依赖只有 `[expired]`。

**实现(替换 plan:2165-2188,改 plan:1924、:1954)**:

1. **`useGoClock`**:
   - `active` 加 `&& (gameState.children?.length ?? 0) === 0 && !gameState.terminal_result`;
   - `useEffect(() => { if (expired) onExpiredRef.current?.(); }, [expired, baseKey]);`。
2. **`api.ts:391`**:`timeout: (sessionId, token?, expect?: { expected_game_id: string; expected_node_id: number; color: 'B'|'W' }) => apiPost("/api/timeout", { session_id: sessionId, ...expect }, token)`。第三参可选,`useGameSession.ts:189` 与 galaxy 不用改。
3. **GamePage**:
   - `timeoutSentForNodeRef` 换成 `timeoutAttemptsRef = useRef(new Map<string, number>())`;
   - `handleClockExpired(color)` 先保留 plan:2177-2181 的三道闸,再加 `if (isGameOver || gameState.children.length > 0) return;`;
   - 键 `k = ${game_id}|${current_node_id}|${color}`,已发次数 `n ≥ (allowRetry.has(k) ? 2 : 1)` 就 return;
   - 发送:`void API.timeout(sessionId, undefined, { expected_game_id: gameState.game_id, expected_node_id: gameState.current_node_id, color })`;
     - 成功:`.then(res => res?.state && session.setGameState(res.state))`;
     - 失败:`.catch(async e => { if (e instanceof ApiError && (e.status === 409 || e.status === 403)) { if (e.message.includes('clock_not_expired')) allowRetry.add(k); const f = await API.getState(sessionId).catch(() => null); if (f?.state) session.setGameState(f.state); } })`;
   - 被拒时不走 `handleAction`,也就不上红条。
   - 调用 `API.timeout` / `API.getState` 时是否带 token,与数子分支(plan:1195)取同一种形式。

**Step 6 `git add`(plan:2308-2312)**:补 `katrain/web/models.py katrain/web/server.py tests/web_ui/test_play_ai_endgame_api.py`。

**提交信息**:补一句「超时请求带期望的局 / 手 / 方,服务端在对局提交锁里核对轮次并用服务端时钟核实;核实不了一律不判负」。

### 4.5 Task 11(N25)

**Step 2(plan:3311-3347)**,在 Task 2 改过标题的退出确认框(`GamePage.tsx:760-784`)`DialogActions` 里,「取消」与「退出」之间加:

```tsx
{session.connectionLost && (
  <Button data-testid="exit-leave-keep" onClick={() => { setShowExitConfirm(false); navigate('/kiosk/play'); }}>
    {t('game:leave_keep_game', '先离开，不认输')}
  </Button>
)}
```

- 这颗按钮不许调 `handleAction('resign')`、`clearActiveSession`、`clearPhysicalEngineError`。
- 为什么 `rejected` 也要给:凭据失效时认输会被 401 / 403 拒掉,人一样走不掉。

**文案**:

- plan:3343 改为「实时连接断了，棋盘不会自动更新。点「退出对局」→「先离开，不认输」，再从「继续上一局」回来就会重新连上」;
- plan:3334-3336 的注释同步改;
- plan:3265 的正则仍然匹配。

**Step 1(plan:3249-3277)**:N25 describe 追加两条,imports 补 `within`。

| 用例 | 断言 | 在哪种错误实现下变红 |
|---|---|---|
| `断线时照文案走:退出对局 → 先离开，不认输 → 到对弈首页;不认输、不清继续上一局` | 到达 `PLAY_PAGE`;`handleAction` 未以 `'resign'` 调用;`clearActiveSession` 未被调用 | 只改文案不加按钮(现状实测为红);按钮复用认输回调;顺手清了指针;按钮放进 Alert 而不在退出框里 |
| `连着的时候,退出框里没有「先离开」` | 按钮不存在 | 按钮常驻 |

**提交信息(plan:3372-3373)**:补一句「断线时退出框多一个不认输的离开」。

### 4.6 Task 12

**Step 1(plan:3392-3404)**:在全量回归之后追加三条源码闸。它们是命令,不是新测试文件;判读前先去掉注释行:

```bash
grep -n "end_state *=" katrain/web/server.py          # 期望:无
grep -n "end_state *=" katrain/web/interface.py       # 期望:只在 _commit_end_state 里
grep -n "_record_ai_game(" katrain/web/server.py      # 期望:定义 + _finish_ended_game 内一处(§6.0 第 1 条)
```

跨平台赛道合并进来的 `_do_end_without_result` 若直写 `'Void'`,第二条闸会红。合并方应改走 `_commit_end_state`:平台双停之后补结果时传 `fill_pending=True`。这里只写合并闸,不改 §6.0 正文。

**Step 4 上板清单(plan:3441-3450)**,加两行:

| # | 条目 | 步骤 | 通过判据 |
|---|---|---|---|
| 8 | 终局后翻手 | 自由对弈(已登录)认输或双停结束后,立刻点「上一手」,再点「最后一手」 | 结果卡与打谱键始终在;屏 01 没有「继续上一局」;「全部对局」里只有一局 |
| 9 | 断线出口 | 对局中重启 katrain 服务,等断线红条 → 退出对局 → 先离开，不认输 → 屏 01 点「继续上一局」 | 看到「这一局已经打不开了」+「回到对弈」;全程没有认输,也没有卡死的屏 |

**`board-checklist.md` 末尾追加「本轮登记的后续项(非上板)」**:第 6 节全部条目。

### 4.7 Self-Review(plan:3488-3498)

类型一致性段落改写或补上:

- `_commit_end_state(result, *, node=None, fill_pending=False) -> GameEnd`
- `_do_play(coords, guard=False, expected_player=None)`
- `_do_timeout(expected_game_id=None, expected_node_id=None, color=None)`
- `ensure_current_score(timeout_s=None, node=None)`:Task 4 端点与 Task 5 补分都**以 `node=` 调用**(原文写的是「均无参调用」)
- `_FINISH_ENDED_GAME_FN(session, app, current_user, end)`
- `game_ended_callback(end)` / `on_game_ended(session, end)`
- `API.timeout(sessionId, token?, expect?)`
- `GameState.terminal_result?`

---

## 5. 依赖顺序与可并行性

**原图(plan:57)**:1 独立;2 → 3 → 4 → 5;6 依赖 2;7、8 独立;9 依赖 6;10、11 依赖 1。

隐含依赖(原图就有但没写):Task 2 Step 5 往 Task 1 新建的 `GamePage.playAi.test.tsx` 里追加用例,所以 1 → 2。

**修订后**:

```
1 → 2 → 3 → 4 → 5 → 6 → 9 → 10 → 11 → 12
                         7 → 8 ─────────┘
```

- **6 必须排在 5 之后**:现在要改 `server.py` / `interface.py` / `models.py`,与 3、4、5 同文件;前端部分还要读 Task 2 的 `terminal_result`,并改 Task 4 刚改过的 `GamePage.tsx`。
- **11 依赖 2**:同一个退出确认框。
- **9、10、11**:都改 `GamePage.tsx`,原本就是串行。
- **7 → 8**:两者都改 `AiSetupPage.tsx`,彼此串行;与主链文件不相交(`AiSetupPage*`、`features/aiLadder/startErrors.ts`、`useAiLadderStatus.ts`)。

**给 subagent 并行实施的约束**:

1. **同一个 worktree 同一时刻只能有一个写入 agent**:index、工作树、`katrain/config.json` 污染面、`/tmp/kgpa-*` 基线文件、8002 / 5173 端口都是共用的。这是记忆「复审 agent 会冲掉共用工作树」那条教训。主链 1 → … → 12 只能逐 Task 串行派发。
2. **能真正并行的只有 7 → 8 这条支线**,前提是开独立 worktree:从当前 `HEAD` 开 `git worktree add` 出一个子分支,做完再 cherry-pick 回主分支。支线的全量基线 diff 不能与主链同时跑,因为两边共用 `~/.katrain/config.json` 与端口。如果调度方不愿多开 worktree,就把 7、8 串在主链的 Task 5 与 6 之间。
3. **只读的复审 / 验证 agent 可以并行**,但一律在 `r1/copy` 这类镜像上跑,不在主工作树上 `git checkout`。

**Task 规模**:

- Task 2 明显变大(后端约 150 行 + 前端约 15 行 + 8 条新用例 + 替身)。建议仍是一次提交,但派发时分两个 subagent 回合:先后端 Step 1–4,再前端 Step 5–7,中间要求 Step 4 那两条命令全绿再继续。
- Task 6 从「前端为主」变成前后端各半。

---

## 6. 本轮登记的后续项(写进 board-checklist 附录)

1. **本地对局连点「停一手」会把两人的停都按掉**(S4 另一半):需要 `/api/move` 带 `expected_node_id`,改共享 `api.ts` / `useGameSession`,要与 galaxy 一起验收。
2. **galaxy**:
   - `GamePage.handleTimeout`、`PlayerCard`、`RightSidebarPanel` 仍发不带绑定的超时(`galaxy/pages/GamePage.tsx:185-194`),与 C1 同病;
   - galaxy 前端不读 `terminal_result`,终局后翻手再点棋盘现在回 409(从前静默续下且不落账)。
3. **视觉 orchestrator 缺一个「终局」暂停原因**(S7):终局后识别仍在跑,只是落子被拒并重新布防。
4. **大厅多人局**(S8 余项):
   - `/api/multiplayer/leave` 与登出判负(`auth.py:419-472`)在已结束时仍会多记一行;
   - 认输时不清 `pending_count_request`;
   - `timeout` 的胜方按请求者座位算,盘面却按轮次写;
   - 归「人人对弈」模块。
5. **本地对局认输框点名的一方取自浏览器状态,请求里不带**(S10)。
6. **服务端时钟在翻手看棋期间不计时**(`update_timer` 的叶子判断),且盒上服务重启后计时状态丢失。本轮保持现有语义。

---

## 7. 评审吸收(设计评审 4 major + 7 minor)

逐条回源码核过后处理如下。「改动」一栏是对前 1–6 节的覆盖;与前文冲突时以本节为准。

### 7.1 major

| # | 评审意见 | 结论 | 改动 |
|---|---|---|---|
| M1 | 空操作的认输 / 超时仍进收尾:`end is not None` 不看这次写没写,可能排在补分后面等 15 秒、再补一次分 | **采纳** | 请求路径只收尾**本次请求造出来的终局**:`session.lock` 里派发前 `before = _terminal_of(session)`,派发后 `end = _new_terminal(session, before)`(`after is not None and after is not before`);认输 / 超时再加 `wrote`。AI 线程同理用 `end is not before`(不再是 `before is None`,理由见 M2)。新增根目录 TestClient 用例:双停补分被阻塞时发 `/api/resign`,1 秒内 200 且 `ensure_current_score` 只被调 1 次(错误实现下 >1 秒、调 2 次,不会挂死) |
| M2 | 整局冻结连带停掉 galaxy / ZenMode「悔棋后接着下」,是越出 PRD 的产品决定 | **采纳 (b),并比评审多走一步** | 冻结收窄到**局面线**:`WebGame.ended_at(node)` = 终局手是 `node` 或其祖先。AI 触发闸、`_game_already_ended`、`_do_play(guard)` 都改用它。**`_commit_end_state` 也按局面线判**(评审 (b) 第 3 点原写「仍按整局判」,不采纳这一半):整局判会让 galaxy「悔棋 → 另开分支 → 认输」静默 200 空操作、棋盘上什么都不发生,是新的回退;按局面线判则另开分支可以再结束一次,`game.terminal` 换成新分支的终局,单机账由 `_recorded` 保证只落一次(与今天相同)。竞态(C2 反方向、C3、S2、S3)全部发生在同一条局面线上,照样被挡。kiosk 仍靠前端 `terminal_result` 冻结,并补 `handleBoardMove` 的前端闸与用例(服务端不再替 kiosk 挡「翻回去再点盘」)。已知残留:大厅多人局终局后导航回去另开分支再认输会再记一行 —— 今天就是这样,归 S8 登记,不在本轮收 |
| M3 | 按 §6.0 合并跨平台落账走不通;grep 闸在落账丢失时仍报绿 | **采纳 (c)(d),(a)(b) 改写成可执行的合并指引** | (c) 真 `_commit_end_state` 在 `target.end_state` 已有值时同样抛 `already_ended`(与替身同口径)。(a) 本分支里 `_finish_ended_game` 的多人局早退**是对的**(本分支上平台局落账走 `record_multiplayer_game`),合并时在它**之前**插星阵人机局分流(`is_platform_engine_session` 为真 → `_record_platform_engine_game(session, app, current_user, end.result)`),写成代码放 plan Task 12。(b) 合并指引改为:`_do_end_without_result` 走 `_commit_end_state("Void")`;只有当前手上已有「双停、待补分」的终局事实时才传 `fill_pending=True` —— 而按 minor 9 的处理,平台局不带 guard 的落子根本不记双停终局,这一支实际走不到。**不采纳**给 `_finish_ended_game` 加 `data_overrides` 形参:本分支的 `_record_ai_game` 没有这个参数,加了就是一个没有调用方的占位;星阵的 overrides 由它自己的薄 helper 构造。(d) Task 12 在 grep 之外加行为验收:本分支 `test_resign_writes_one_ledger_row_or_none[platform-*]`;合并时再加跨平台 `tests/platforms/test_engine_game_ledger_e2e.py` 三条全绿 |
| M4 | `/api/resign` 平台分支 `wrote` 未定义 → 平台局认输 500 | **采纳** | `wrote = True` 提到所有分支之前;平台分支 `except EndgameConflict`(非 `already_ended` 照抛)。新增 web_ui 参数化用例 `[lobby|platform] × [写上了|撞上已结束]`:落账行数 1/0、`game_end` 广播 1/0、状态码 200 |

### 7.2 minor

| # | 评审意见 | 结论 | 改动 |
|---|---|---|---|
| m5 | 真对象收尾用例在正确实现下也 TypeError(裸 `WebKaTrain.message_callback` 是 None) | **采纳** | `_web_katrain()` 夹具里装 `message_callback = lambda *a, **k: None`,注释写明是夹具要补的、不是生产 bug(生产会话由 `SessionManager.create_session` 装上) |
| m6 | AI 认输写入吞掉所有异常 | **采纳** | 只吞带 `reason` 属性的冲突;其余照抛,由 `_do_ai_move_and_broadcast` 记 ERROR |
| m7 | 超时请求遇 503 / 401 / 网络错被静默吞掉;token 绕开 | **采纳** | token 取 `useAuth()` 的同一来源(`token ?? undefined`);409/403 重同步;其余按 2 s / 5 s / 10 s 退避重发,三次都没送达就在屏上说「超时判定没有送达」;补一条假时钟用例 |
| m8 | 补分读的是换局后的 `analysis_allowed` | **采纳** | `_finish_ended_game` 进锁后先判 `session.katrain.game is end.game`,`_score_two_pass_end` 开头再判一次 |
| m9 | 平台人人局双停后被永久冻结,OGS 恢复对局下不了 | **采纳** | 双停终局事实只由本地对局路径记:`_do_play(guard=True)` 与 AI 提交段调 `WebGame.record_two_pass_end(node)`;`WebGame.play` 本身不再记。研究会话与平台网关(`_local_play`、`_on_opponent_move`)不带 guard,双停后既不冻结也不记。补用例 |
| m10 | W11/W9 进锁没有能变红的测试;竞态用例对「查完放锁再落子」只偶发变红 | **采纳** | 新增 `update_timer` 互斥用例(假 `time` 在第一个结算者读时钟时停住,第二个结算者 0.2 秒内不许读到时钟);竞态用例停点处用非阻塞 acquire 断言 AI 线程持锁,并把 `game.play` 包一层断言落子时锁在 AI 线程手里;W9 作为竞态用例的 `nav` 写入者参数 |
| m11 | 升降级落账仍按游标读结果(`server.py:1714`) | **采纳实现,不补测试** | `actual_result` 优先取 `game.terminal.result`,退回原写法;补进 1.5/1.6 的游标读者清单。**未经测试证实**:升降级局禁悔棋 / 禁导航,今天两者恒等,写不出在错实现下变红的用例;守护靠既有 `test_ranked_natural_result_saves_once_then_settles_once` 等保持绿 |

### 7.3 由吸收带出的其它改动

- **AI 线程回调条件**:`end is not None and end is not before and self.game is game`(`before is None` 在局面线语义下会漏掉「另开分支后的第二次终局」)。
- **`_complete_count` 的非原子预检**改为 `terminal.node is node`,不读 `node.end_state` 的真值(web_ui 替身会话的 `end_state` 是真值 MagicMock)。
- **绊线续命**:`tests/web_ui/test_ai_ladder_api.py::test_every_place_that_writes_a_terminal_result_by_hand_also_ends_the_game` 只认 `current_node.end_state = ` —— server.py 改走 `_commit_end_state` 之后它扫不到任何东西(闸会过期)。谓词扩成「直写 `end_state` 或调 `._commit_end_state(`」,正对照同步喂两种写法。
- **`test_ai_game_autosave.py::_make_mock_session`**:终局事实不再预先挂上,改由替身在收到 `resign` / `timeout` / `play` 时写(M1 之后「预先就有」等于「不是这次请求写的」,原设计的写法会让 5 条自动落账用例全红)。
- **`_ai_thread_game`**:改走真 `generate_ai_move` + 桩策略(`ai:default` 换掉),因为双停事实在它的提交段里记;原 plan 直接调 `game.play` 的替身会绕过它。
