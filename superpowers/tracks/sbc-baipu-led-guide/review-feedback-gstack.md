# gstack 评审汇总：Kiosk 摆谱 + LED 引导落子（`sbc-baipu-led-guide`）

> 评审对象：`plan.md` v2。两路并行评审 + Claude 交叉综合。日期 2026-06-16。
> - **设计评审**（`/plan-design-review`）：摆谱页交互 / 触屏体验。
> - **CEO 评审**（`/plan-ceo-review`）：是否还能更省事地拿到数据。
>
> 结构：§0 一句话结论 · §1 **Claude 交叉综合**（含冲突与待你决策项）· §2 设计评审全文 · §3 CEO 评审全文 · §4 建议并入 plan 的改动。

---

## §0 一句话结论

- **设计评审**：计划的*逻辑*扎实，但*操作者体验*几乎没写；3 个**阻断级**问题——失败对操作者不可见（相机掉线=静默采到垃圾）、`退出`紧挨`确认`且无恢复、`确认`键被「落子」与「移除提子」两种相反语义复用。可用现有 theme token 补齐，**不需新架构**。评分 3.5/10 → 可达 8/10。
- **CEO 评审**：计划是「好工程」但**为目标过度建造**——为一次性、单人、单机收几百张训练图，造了串口/LED 服务/LUT/摆谱 UI/采集服务一整套永久子系统。**LED 只负责消除「人工复现*外部* SGF」的摆放歧义，对标签毫无贡献**；若你**自己生成局面**就没有歧义可消、LED 无事可做。结论：**proceed-with-changes，大幅砍**；先做被搁置的「30 分钟分类器基准」，它决定到底要不要 LED。

> ⚠️ 两份评审在**不同高度**：CEO 问「**该不该建** LED 摆谱」（上游前提），设计问「**既然要建**，怎么让操作者能用」（下游执行）。两者的张力需要你先拍一个前提（见 §1.2）。

---

## §1 Claude 交叉综合

### 1.1 两份评审的共识（无论你怎么决策都该做）
1. **保留**：`goBoard.ts` 收敛（CEO 明确赞成，独立价值）、`CaptureService` + manifest、Phase 4 几何迁移（`grid_calibrator` 确认无调用方，退役安全）。两边都不反对这三块。
2. **强烈收敛的同一条建议——加「软性 CV 校验」防摆错**：设计评审 issue #7 与 CEO 都独立指出：LED 消除*位置*歧义，但挡不住*操作者错误*（摆错颜色/摆偏一路/忘了提子）。两边都建议用已有的 `stones.py` 空盘差分，对「实际盘面 vs 期望盘面」做一次轻量比对，**摆错就提示/标记**。这正是项目立项要解决的「人工摆子易污染数据」。≈30 行，强烈建议加。
3. **数据相关性问题**（CEO 提出、设计隐含）：带灯拍每手一帧 → 一局 N 张**高度相关**（只差一子）的图，对 CNN 价值低。应**显式要求采集多样性**（光照/角度/曝光/盘面填充度），少局多样 > 多局相关。

### 1.2 核心冲突 → **需要你先拍的前提**
**CEO 的「砍掉 LED 摆谱」结论，建立在它的假设 #1 之上：「这是一次性、单人、单机的数据采集杂活」。**

但据我们 brainstorming 收敛 + 项目记忆，你的实际定位是：**摆谱 / 打谱(复盘) 是智能棋盘的产品功能**（你明确说过「提子逻辑未来普通打谱流程也复用，一并开发」），LED 硬件是产品的一部分（已设计/已烧固件/已实测）。若如此：
- LED 就**不是纯一次性工具**，CEO 的「砍掉」前提不成立——它有独立产品价值，且 LED 引导对**复现真实职业棋谱**（提供真实的接触/扭断局面分布，这是随机散子 B1 给不了的）确有价值，这点 CEO 略低估了。
- 但 CEO 的**便宜高杠杆建议依然全部成立**（见 1.1 + 1.3），与「保不保留 LED」无关。

👉 **请你先回答一个前提问题：摆谱/LED 是产品功能（要长期留在产品里），还是纯粹一次性采数据的临时工具？**
- 若**产品功能** → 采纳 CEO 的便宜建议，但**保留** LED 摆谱（按设计评审修 UX），照原计划推进。
- 若**纯一次性工具** → 认真考虑 CEO 的 Approach B（自生成局面、免 LED），把 LED 摆谱降级为「Phase 2，仅当确需大规模复现外部 SGF 时再建」。

### 1.3 我的建议（假设是「产品功能」，最可能）
**保留 LED 摆谱，但吸收两份评审的高杠杆项**，合成如下优先级：

**P0（先做，决策门）** — 采纳 CEO：**分类器基准**（autoresearch 侧搁置自 6/5 的 30 分钟任务）：实摆黑/白子→跑 `detect_stones.py`→出混淆矩阵。它决定「CV 自动标注是否可信」，从而决定 LED-exact-label 到底多必要。最便宜、信息量最大。

**P1（设计阻断，若保留摆谱必修）** — 采纳设计评审 3 个 blocker + 布局规范：
- 失败可见：相机/LED 健康常驻状态点 + 相机掉线时**阻断确认**（不是 4 秒 toast）。
- `退出`移出控制行 + 二次确认 + 轻量 resume（localStorage/disk manifest）。
- 提子改为**独立模式**（不同按钮文案/颜色/横幅），打断「落子-确认」节奏。
- 加 Session Page 布局层级规范 + LED 配色图例（红=黑/绿=白/蓝=移除）+ 大`确认`键拇指区人体工学。

**P2（数据质量，两边共识）**：软性 CV 校验防摆错（1.1-#2）+ 采集多样性要求（1.1-#3）。

**保留不变**：`goBoard.ts`、`CaptureService`+manifest、Phase 4 几何迁移。

### 1.4 我对 CEO「砍 LED」的诚实判断
CEO 的核心洞见很锋利且正确：**LED 对标签零贡献，只防外部-SGF 的人工摆放歧义**。如果你只是要一次性数据，B1（脚本自生成局面、屏幕显示、CV 交叉校验、多条件拍）确实能用 1/5 代码拿到同样精确的标签，且数据更去相关——这是真便宜路径，值得认真对待。**但**它的「砍」结论依赖「非产品功能」假设；且随机散子缺真实局面分布。所以我不建议直接照搬「砍」，而建议**先做 P0 基准 + 拍定 1.2 前提**，再决定 LED 摆谱是「现在做」还是「Phase 2 做」。我没有制造无谓的 pivot，也没有无视这条强论点——把决策权交给你。

---

## §2 设计评审全文（`/plan-design-review`）

# Designer's-Eye Plan Review —摆谱 (Kiosk Stone-Placement Guidance)

**Target:** `superpowers/tracks/sbc-baipu-led-guide/plan.md` (v2)
**Reviewer posture:** non-interactive (no live user). I made the AskUserQuestion decisions myself, stated my assumptions, and wrote the complete review. Mockups were not generated (no live approval loop, and the deliverable is a written critique).
**Scope of this review:** the摆谱 page interaction and touchscreen UX only. I deliberately did **not** re-litigate the coordinate system, LED LUT, threading model, or geometry migration. Those are engineering concerns already hammered by the 71-finding adversarial pass. This is about the human standing at a physical board for an hour.

**Overall design-completeness rating: 3.5/10.**
The plan is a 3.5 not because the interaction is wrong, but because it is almost entirely *unspecified*. The state machine in §1.3 is excellent — it nails the logical flow (GUIDING → CHECK_REMOVE → AWAIT_REMOVAL → ADVANCE → CAPTURE). But a state machine is not a UI. The plan says "底部控件(触屏)：`确认`(核心大按钮)、`上一手`、`下一手/跳过`、`重新点灯`、`退出`" and stops. No sizes, no spatial layout, no glanceability strategy, no error visuals, no fatigue model. An engineer handed this ships five MUI `<Button>`s in a row and calls it done. For a heads-down, hands-on, hour-long data-collection job, that is the difference between a tool an operator trusts and one that quietly corrupts the dataset.

The single most important fact this plan under-weights: **the operator's eyes are on the physical board and the LED, not on the screen.** The screen is a *peripheral-vision confirmation surface*, not the primary interface. Almost none of the plan's UI thinking reflects that.

### Design dimensions (0–10)

| Dimension | Score | What would make it a 10 |
|---|---|---|
| **Information architecture / glanceability** | 3 | A screen designed for peripheral vision: one dominant element (current LED target + color), N/total readable from 1.5m, current-player color unmissable. Plan defers all of this to "参考元萝卜" with zero spec. |
| **Touch ergonomics (the big 确认 + controls)** | 2 | Thumb-zone layout, 确认 sized 88px+ and spatially isolated from destructive controls, 退出 guarded, one-handed reachability spec'd for both left/right-handed operators. Plan lists 5 buttons with no geometry and puts 退出 (exit) in the same control row as 确认 (confirm) — accidental-tap landmine. |
| **提子 (capture removal) prompt clarity** | 4 | An unmistakable two-state mode ("PLACE" vs "REMOVE THESE"), with count, screen marker, blue-LED correspondence explained to the operator, and a confirm that can't be fat-fingered into the next move. Plan specifies the *mechanism* (red/blink marker, blue LED, second 确认) but not the *legibility* — and reuses the same 确认 button for two semantically opposite actions. |
| **LED ↔ screen ↔ physical-board feedback coherence** | 4 | An explicit "three surfaces, one truth" contract the operator can verify at a glance: screen highlight color == LED color == stone color, every time, with a documented mapping shown on-screen. Plan has the data model right (规范坐标 one-way) but never specifies the *visual language* that makes the three agree perceptually (e.g., screen highlight must be red for black-to-play, matching the red LED — counterintuitive and unstated). |
| **Error / edge states (the big gap)** | 2 | Every failure has a designed screen state: LED disconnected, camera disconnected, capture failed, mis-placement. Plan's §1.3/§3.3/§4.2 mention "失败仅记日志/小提示" and "400 + WARNING" — backend behavior, not user-facing states. The operator could摆 30 stones with a dead camera and not know the session is worthless. |
| **Progress / session stamina** | 3 | A fatigue-aware session model: large persistent progress, frames-captured count distinct from move count, time-on-task, pause/resume across an hour, and crash recovery. Plan has `k/total` and a DONE summary; nothing for the 45-minute mark or "the app reloaded, did I lose my work?" |
| **Onboarding / non-expert clarity** | 3 | A first-run path that teaches the loop in 10 seconds (place → confirm → repeat) plus a persistent legend. Plan assumes the operator already knows the protocol. No empty state on BaipuListPage, no first-session coachmark, no inline legend. |
| **AI-slop / intentionality** | 6 | This inherits the kiosk's genuinely nice dark/jade theme (theme.ts) and reuses real components, so it won't look generic. But "核心大按钮" with no design = default MUI contained button, which is exactly the templated look. Score is salvageable for free by leaning on existing tokens. |
| **Design-system alignment** | 7 | Strong: reuses LiveBoard, PlayerCard, KifuPage skeleton, kioskTheme. The theme already has 48px touch minimums and scale-on-active. The gap is that 摆谱's ergonomic needs (88px confirm, blink animations, mode banners) exceed what the current components express, and the plan doesn't say how to extend them. |

**Net: 3.5/10 → realistically 8/10 achievable** with the additions below, almost all of which are layout/spec work, not new architecture.

### Top issues

Severity tags: **[Blocker]** = will corrupt data or strand the operator · **[High]** = will cause frequent errors or fatigue · **[Med]** = polish that compounds over a long session.

#### 1. [Blocker] No designed error states — a dead camera/LED is invisible to the operator. (plan §1.3, §3.3, §4.2, §3.4-#4)
The plan treats failures as *backend log lines*: "LED 调用容错：失败仅记日志/小提示" (§3.3), "写失败→400 + WARNING" (§4.2), `is_connected()` is "advisory" (§3.1). But this is a **data-collection tool** whose entire value is clean frames. If the camera silently disconnects at move 40, the operator keeps placing stones, keeps tapping 确认, and produces 80 frames of nothing. The plan's own risk table ranks 坐标系 highest and never lists "operator unknowingly collects garbage" as a risk at all.

There is no specified screen state for: LED service disconnected, camera disconnected, capture returned an error, or capture wrote zero bytes. "小提示" (a small toast) is the wrong pattern — a Snackbar that auto-dismisses in 4s (the KifuPage pattern, line 388-395) is *designed to be missed* by someone whose eyes are on the board.

#### 2. [Blocker] 退出 (exit) lives in the same control row as 确认 (confirm). (plan §1.3 底部控件)
"`确认`(核心大按钮)、`上一手`、`下一手/跳过`、`重新点灯`、`退出`" — five controls, undifferentiated, in the bottom bar. 确认 is tapped ~250 times in a session; 退出 is tapped once. Putting the session-destroying control adjacent to the most-tapped control, with no guard, on a touchscreen, for a heads-down operator, guarantees mid-session accidental exits. Combined with issue #6 (no resume), one fat-finger = lost session.

#### 3. [Blocker] The big 确认 button is overloaded onto two opposite meanings with no visual differentiation. (plan §1.3 state machine: GUIDING confirm vs AWAIT_REMOVAL confirm)
In GUIDING, 确认 means "I placed the stone." In AWAIT_REMOVAL, the *same button* means "I removed the captured stones." These are semantically opposite (add vs remove) and the plan reuses one button for both. The operator in a rhythm of "place, tap, place, tap" will tap straight through the removal prompt without removing anything — the most common capture-handling error, and the plan's design invites it. The removal step needs to *break the rhythm*: different button label, different color, the board visibly in a different mode.

#### 4. [High] Glanceability is undefined — the screen isn't designed for peripheral vision. (plan §1.3 布局, PRD §4.1)
Both PRD and plan say "参考元萝卜" and stop. The operator's eyes are on the physical board; the screen must answer three questions from peripheral vision at ~1.5m: *whose move / what color / where.* The plan inherits KifuPage's `body2` 14px progress text (line 348) and PlayerCard's `body2` name — far too small to read peripherally. Nothing specifies that "current color to place" must be the single dominant on-screen element. Right now the dominant element is the board (correct for *review*, wrong for *placement guidance* where the physical board is the real board and the screen is the instrument panel).

#### 5. [High] The red/green LED ↔ screen color correspondence is counterintuitive and unspecified. (plan §3.1 颜色映射, §1.3 nextMovePoint)
Black stone → **red** LED, white stone → **green** LED (§3.1). That mapping is arbitrary-but-fixed in hardware, and it's *counterintuitive*. For the three surfaces to agree perceptually, the on-screen `nextMovePoint` highlight should also be red-for-black / green-for-white — but the plan only says "醒目实心高亮(无手数)" with no color rule. If the screen highlights the next black move in jade (the theme accent) while the LED glows red, the operator's brain has to translate. Over 250 moves that's real cognitive load and an error source. This must be specified as a hard rule and ideally shown in an on-screen legend.

#### 6. [High] No session resume / crash recovery, and no fatigue model for an hour-long session. (plan §1.3 game_id, §6 不在范围)
`game_id = kifu_${id}_${sessionTs}` is generated "进页时一次性" in React state. A page reload, a kiosk OS hiccup, or an accidental 退出 (issue #2) loses the entire in-progress session — the operator restarts at move 0. For a 150-move game that's 10+ minutes of re-placement, and the partial frames already on disk are now orphaned. The plan explicitly scopes out a backend baipu table (§6), which is fine, but then nothing persists session position. For a "potentially long data-collection session," there is no pause, no "X frames captured / Y remaining / ~Z min left," no fatigue-aware affordance.

#### 7. [High] Mis-placement has zero feedback by design, and the plan knows it. (plan 决策表 "Ko/非法手不校验", review-request §4-#6)
The plan decides not to validate placement: "人若照灯摆错…目前无校验兜底." The review request *itself* flags this as a challenge point. From a data-purity standpoint this is the whole reason the project exists (the PRD: "人工照 SGF 摆子极易摆错位置/方向，污染数据"). The LED removes *positional* ambiguity but not *operator error* — placing the right color one line over, or forgetting to remove a captured group before the next placement. The plan has the camera in hand (CaptureService) and the expected board (reconstructBoard) and chooses not to close the loop even as a *soft visual* check. That's a defensible v1 cut, but it must be a conscious, surfaced decision with a fallback, not a silent gap.

#### 8. [Med] BaipuListPage has no empty state, no "why is this game greyed out" affordance, and no fast re-entry. (plan §1.2)
"非 19 置灰并提示" — greying out non-19×19 games in a list the operator is scanning is a frustration generator with no explanation. There's no empty state ("no 19×19 games found"), no filter to *hide* ineligible games, and no "resume last session" shortcut for the common case of collecting many games back-to-back. The operator re-traverses search → page → select → 开始摆谱 every single game.

#### 9. [Med] Capture timing (~150ms) and the "hand in frame" risk have no operator-facing feedback. (plan §4.2, 决策表 带灯拍时序)
The plan correctly captures *after* 确认 so the hand has withdrawn. But the operator gets no signal that a frame was taken or whether it was clean. A 150ms blind capture with no shutter feedback means the operator can't develop trust ("did it get that one?") and can't catch their own hand lingering in frame. A frame counter that ticks visibly + a subtle capture flash closes this.

### Concrete recommendations

All of these are plan-level edits. I reference the plan section each belongs in.

**A. Add a "摆谱 Session Page layout & hierarchy" spec to §1.3.** Replace "布局(参考元萝卜)" with an actual hierarchy:

```
┌─────────────────────────────────────────────────────────┐
│  TOP STATUS STRIP (always visible, large)                │
│  ●黑 落子 第 47/150 手   ·   已采集 46 帧   ·   ~12 min   │ ← h4/h5, readable @1.5m
├──────────────────────────────────┬──────────────────────┤
│                                  │  PlayerCard (B)  active │
│         LiveBoard                │  PlayerCard (W)         │
│   (nextMovePoint highlighted     │  ┌───────────────────┐ │
│    in LED-matching color)        │  │   NEXT: ● 黑 (red) │ │ ← dominant element:
│                                  │  │   下一手颜色提示     │ │   color chip = LED color
│                                  │  └───────────────────┘ │
├──────────────────────────────────┴──────────────────────┤
│  CONTROL BAR (see rec. B)                                 │
└─────────────────────────────────────────────────────────┘
```
Hierarchy rule: **first = next-move color chip (matches LED), second = N/total progress, third = the board.** The board is a *confirmation mirror*; the physical board is primary.

**B. Redesign the control bar in §1.3 with thumb-zone safety:**
- **确认** (primary): ≥60% width, ≥88px tall, isolated bottom-center, `primary.main` jade, keep scale-on-active.
- **上一手 / 下一手·跳过**: secondary, ≥56px, flanking but not touching 确认.
- **重新点灯**: tertiary, small, off to the side.
- **退出**: move OUT of the control row → top-corner + confirm dialog. Rule: "destructive/session-level controls never adjacent to per-move controls."

**C. Make the提子 step a distinct MODE, not a re-tap (§1.3 AWAIT_REMOVAL):** board enters a visibly different mode (dim placed stones, blink to-remove red), full-width banner "请移除 N 个被提的子 (闪烁处)", action button changes label+color to "已移除 N 子" (warning/info color echoing blue LED), state "蓝灯 = 移除" on the banner, clear transition back to place mode.

**D. Add an "Interaction states" table to the plan (the §1.3/§3.3/§4.2 gap, issue #1):**

| State | LED | Screen | Confirm button |
|---|---|---|---|
| LED service down | n/a | Persistent banner "LED 未连接 — 引导不可用" + status dot | disabled (or explicit screen-only opt-in) |
| Camera down (during collection) | (still guides) | **Persistent** banner "相机未连接 — 本会话不会采集到数据" — NOT a 4s toast | block 确认, or force "继续但不采集" |
| Capture failed (one frame) | — | Inline "第 N 帧采集失败 — 已重试 / 请重摆" + retry | re-capture, don't advance |
| Capturing | next-move LED on | brief shutter flash + frame counter ticks | disabled ~150ms |
| Healthy | — | small green status dots (LED / 相机) in top strip | enabled |

Change §3.3's "失败仅记日志/小提示" to "health shown as persistent status indicator; camera failure during an active session blocks confirmation."

**E. Specify the on-screen color legend + LED-color rule (issue #5, §1.3 nextMovePoint):** highlight color **must** match LED (black-to-play→red, white-to-play→green; not theme accent) — state as hard rule in 决策表. Add persistent legend: "红 = 黑棋 · 绿 = 白棋 · 蓝 = 移除".

**F. Add lightweight session resume (issue #6), no backend table:** persist `{game_id, k, frames_captured}` to localStorage on every ADVANCE (manifest on disk is the real source of truth); on entry offer "继续上次 (第 X 手)" vs "重新开始"; top strip shows "已采集 M 帧" distinct from move N + coarse time estimate.

**G. Make placement error *soft-checkable* without full validation (issue #7, §4.6/决策表):** keep "no hard validation" as v1 default but leave a hook — CaptureService already grabs a frame and reconstructBoard knows the expected board, so let autoresearch (or a later phase) diff captured vs expected and flag suspect frames in the manifest (`"verify": "unchecked"`). Converts a silent gap into a documented, recoverable decision.

**H. BaipuListPage polish (issue #8, §1.2):** default to **filter** (not grey-out) 19×19 with a "仅显示 19 路" toggle; add empty state ("未找到 19 路棋谱"); add "继续上次会话" entry when an in-progress manifest exists.

**I. Capture feedback (issue #9, §4.2):** on successful capture, tick frame counter visibly + subtle shutter flash (~150ms) to build operator trust over a long session.

### What would make摆谱 delightful for the operator
1. **The screen disappears.** Highest compliment: the operator stops looking at it. LED says where+color, operator places, thumb finds the big fixed-position 确认 by muscle memory, a soft sound/flash confirms the frame, next LED lights. Design 确认 to be findable without looking (bottom-center, full-width, generous height).
2. **A confidence heartbeat.** Two persistent green dots (LED · 相机) + live "已采集 N 帧" counter. Never wonder "is this working?"; the moment a dot goes red, they know — without a toast they'd miss.
3. **A satisfying rhythm with a finish line.** Filling progress bar + "本盘预计还剩 ~6 min"; on DONE a real summary ("本盘采集 149 帧 ✓ — 开始下一盘?") + one-tap re-entry with last filter preserved. Stretch: a foot-pedal/physical 确认 later (PRD §8-#2 already raised it) — keep 确认 abstracted behind one event so it can be rebound.

### Assumptions I made
1. Non-interactive review (made design calls myself; no gstack mockups).
2. Single operator, landscape kiosk, ~1.5m viewing, eyes mostly on the physical board.
3. **The physical board is the real board; the screen is an instrument panel** (central reframing).
4. red=black/green=white LED mapping is fixed in hardware; screen conforms to LED.
5. Sessions are long and batched (justifies resume/fatigue/fast-re-entry weight).
6. autoresearch can consume an extra manifest field for the soft-verify placeholder.
7. localStorage available and persists on the kiosk.
8. v2's already-fixed engineering items treated as settled (per review-request "don't repeat §10").

**Bottom line:** the plan's *logic* is sound and well-reviewed; its *operator experience* is largely unwritten, and three gaps are blockers for a data-collection tool — invisible failures, 退出 fat-finger with no resume, and the提子 step overloaded onto the place button. All fixable with layout/spec work and existing theme tokens. Recommend adding a Session Page layout spec, an interaction-states table, a control-bar ergonomics spec, the LED-color legend rule, and lightweight resume before implementation.

---

## §3 CEO 评审全文（`/plan-ceo-review`）

# CEO / Founder-Mode Plan Review: `sbc-baipu-led-guide`

**Mode posture:** non-interactive review, run as **SCOPE REDUCTION + premise challenge** (the requester's question is "is there a simpler/cheaper/faster path to the data?"). The plan survived a 67-agent adversarial pass, so I'm not relitigating internals — I'm asking whether you should build it at all.

**Bottom line up front:** The plan is good engineering aimed at a goal bigger than your actual need. You're proposing a serial protocol layer, a LED service with a bounded-queue threading model, a row/col→LED LUT, a full 摆谱 UI + state machine, a capture service with camera mutual-exclusion, and a geometry migration — **all to collect a few hundred training photos one time, on your own Mac, by yourself.** That's a permanent product subsystem built to serve a one-shot data chore. There is a path that gets you the same labels this week with roughly a fifth of the code. Verdict: **proceed-with-changes, cut hard.**

### Problem reframe
The real goal (prd.md §1): **train a YOLO Go-stone detector that works on this device, because synthetic sim-to-real failed.** To train YOLO you need **real photos of this board + a per-photo label of which intersections are black/white/empty.** Geometry is already locked (`autocal.py`, conf 0.89, ~0.1 cell error, `session.npz`), so the 361 pixel coords are known. The label problem reduces to: **for each photo, what color is at each known intersection?** Two ways to know ground truth: (1) you already know the position (you placed it / have move history) → exact, free, no classifier; (2) a classifier reads it → inferred, fallible.

The crux: **the LED does not help with labeling at all.** Labels come from the SGF. The LED's only job is to stop a human from misplacing a stone while blindly reproducing someone else's SGF on an orientation-less board (prd.md:20-21). It's a **human placement aid**, nothing more. So the founder question: **do you need a human to blindly reproduce external SGFs at all?** If the position is one *you* generate or record, there's no ambiguity to remove, so the entire LED + serial + LUT + 摆谱-state-machine stack has nothing to do.

### Alternative approaches considered

**Approach A — The current plan: LED-guided 摆谱 of known SGFs.**
- Pros: labels *exact* (SGF truth, no classifier guess) even on the hard orange-wood board; can mass-replay thousands of pro positions → huge position diversity; 摆谱 UI has standalone product value (teaching).
- Cons: most expensive path by far (serial + threaded LED service + REST + LUT + 摆谱 page + state machine + capture service + camera mutex; ~9 new files, 6 test files, hardware-in-the-loop). Data is **highly correlated**: a 200-move game = 200 photos differing by one stone. 200 near-identical frames is worth far less to a CNN than 20 diverse boards under 20 conditions.
- Verdict: over-built for the immediate goal; optimizes label-exactness-at-SGF-scale, a property you only need if your CV labeler is untrustworthy AND you need external-SGF replay. Neither established.

**Approach B (RECOMMENDED) — Generate-your-own-positions + exact labels, no LED.**
- B1 — Scripted hand-setup: a script prints "place black at these 30 points, white at these 25"; you set up the whole board at once, photograph under several lighting/angle/exposure conditions, move stones, repeat. Script generated the position → label exact, no LED, no classifier. 20 setups × 5 conditions = 100 diverse decorrelated photos with perfect labels in an afternoon.
- B2 — Capture during normal play: you already have `camera.py` + `VisionService` + a move pipeline; when you play/replay an SGF yourself, the move history is known → exact labels, no LED, reuses existing infra.
- Pros: zero new hardware integration; no serial/LUT/LED service/firmware risk; labels exactly as exact as A; B1 gives decorrelated multi-condition data (strictly better for training); ships this week.
- Cons: B1 means you place without a guide → could fat-finger. Mitigation: script shows target board on screen (existing `LiveBoard` renders it free) + a one-shot classical-CV cross-check (`stones.py` diff) flags "stone where I expected empty" before you snap (~30 lines, not a 4-phase subsystem). B doesn't trivially burn through 5,000 external pro SGFs — but you don't need 5,000 for a first detector.
- Verdict: the 10-star-simplest path; collapses the entire reason for the LED. **Highest-leverage cut available.**

**Approach C — Pure classical-CV auto-labeling, no SGF, no LED.** Scatter stones, photograph, let empty-baseline-diff assign every intersection.
- Pros: cheapest for raw volume.
- Cons: **classifier unproven on real stones** — no confusion matrix exists anywhere; `stones.py` thresholds are self-described "拍脑袋阈值," never fairly tested (the one attempt wrecked by a board bump, SESSION_2026-06-05); the existing `auto_label.py` uses absolute HSV that `stones.py` says fails on bright orange wood. Classifier error **silently corrupts labels** — worse than less data.
- Verdict: good as a *volume multiplier later*, dangerous as the *primary* path until accuracy is measured. Not first.

**The sequencing insight (the actual recommendation):** the honest dependency is you don't yet know if your classical classifier works on real stones — that single unknown determines everything.
1. **First, the long-blocked 30-minute task:** place real stones on the fixed board (no bump), run `detect_stones.py`, get the confusion matrix. autoresearch task #1, blocked since June 5. Cheapest, highest-information action in the whole program.
2. **If classification clears ~99%:** Approach C is safe → free volume; use B for guaranteed-exact diverse boards. **You may never need the LED.**
3. **Only if** you specifically need to replay *external* pro SGFs at scale AND want SGF-exactness over CV labels → build the LED 摆谱 (A). Real use case, but a *phase-2 nice-to-have*, not the critical path to a first working YOLO.

The minimum path to "enough data to train a working YOLO" is **B1 + the 30-min classifier benchmark.** Not four phases of new product infrastructure.

### Verdict
**PROCEED WITH CHANGES — significant scope reduction.** The plan isn't wrong and is genuinely well-built (coordinate normalization, bounded-queue LED threading, camera mutex, `session.npz` 8-field round-trip discipline — sharp work). But it answers "how do we build LED 摆谱 cleanly?" when the question is "how do we get the data cheaply?" Building A *first* pours the most effort into the path with the most moving parts to serve a one-time, single-user, single-machine chore. The LED's sole function — disambiguating human placement of *external* SGFs — evaporates the moment you generate your own positions. I'm not manufacturing a pivot: if you have 3,000 pro SGFs you specifically want to replay and trust SGF labels more than any CV, A is justified. But that case must be *stated*, not assumed. As written, the plan assumes it.

### If proceeding: what to cut / keep / add
**CUT (or defer to a "Phase 2: LED 摆谱" track, only if external-SGF replay is a stated need):**
- Phase 2 entirely — `led_service.py`, `led.py` endpoints, `ledApi.ts`, serial wiring, threading/queue/reconnect (~4 files + `test_led_service.py`); the bulk of new-subsystem risk.
- The LED branches of the state machine in `BaipuSessionPage`.
- The (row,col)↔LED LUT (Appendix A) + its 8 hardware-validation checks. (Note: the "pure formula, no calibration" claim 2026-06-15 *contradicts* SESSION_2026-06-14's "勿信公式/must measure"; cutting LED makes it moot.)

**KEEP regardless:**
- `goBoard.ts` consolidation (Phase 1.1) — good independent of everything (three copies exist incl. a third in `galaxy/components/live/LiveBoard.tsx`; consolidate the two shared-territory ones; helps tsumego). Watch shared-territory double-build.
- `CaptureService` + manifest schema + capture endpoint (Phase 3) — you need to capture + write {photo dir + manifest + SGF} no matter how positions are generated. Feed it from B1/B2 instead of the LED state machine; the `stones_through_move`/`next_move` fields become "full position" fields, arguably simpler.
- Phase 4 geometry migration (autocal → katrain, retire `grid_calibrator.py`) — confirmed safe (zero callers), decoupled, right long-term move; `session.npz` 8-field discipline correct. Keep as-is, run last.

**ADD (cheap high-leverage):**
- **Classifier benchmark, as Phase 0** — before any UI; decides whether you need LED at all; blocked since June 5; ~30 min.
- **A `scripted-setup` capture mode (Approach B1)** instead of LED 摆谱: script generates a position, renders on existing `LiveBoard`, optional `stones.py` diff cross-check, captures under N conditions.
- **Capture-diversity guidance in the manifest/protocol:** vary lighting/exposure/angle/fill; 100 diverse boards beat 1,000 correlated single-move-apart frames. The plan's per-move sequential capture produces exactly the correlated data you don't want — make decorrelation an explicit requirement.
- **If you keep any CV-labeling path:** port `stones.py`'s empty-baseline differencing into `auto_label.py` (currently absolute HSV that fails on orange wood).

### Assumptions I made
1. **The data collection is a one-time, solo, on-Mac chore**, not a recurring end-user feature. If 摆谱 is *also* meant to ship as a user-facing kiosk teaching feature, Approach A regains standalone value — but that's a different justification than "collect training data," and isn't stated.
2. A first working YOLO needs hundreds, not tens of thousands, of labeled frames.
3. You don't yet have a measured stone-classification accuracy number (confirmed: no confusion matrix in either repo).
4. "Generate your own positions" is acceptable for training diversity (2-class per-intersection detection).
5. The hardware "LUT is pure formula" claim (2026-06-15) is accurate; I note only it contradicts an earlier session doc, and cutting LED removes the need to resolve it.

**One-line summary:** Yes, there's a much cheaper path — the LED only stops a human from misplacing *someone else's* SGF; generate your own positions (scripted hand-setup or capture-during-play) and the labels are just as exact with zero serial/LED/LUT code. Do the 30-minute classifier benchmark first (blocked since June 5) — it decides whether you need the LED at all. Keep `goBoard.ts`, `CaptureService`+manifest, and the Phase-4 geometry migration; defer the whole LED 摆谱 stack to a Phase 2 you build only if mass-replaying external pro SGFs is a real, stated requirement.

---

## §4 建议并入 plan 的改动（Claude 汇总，按优先级；标注需你决策）

> ⚠️ 先答 §1.2 的前提问题（摆谱/LED 是产品功能 vs 一次性工具），再决定下面哪些采纳。

**🟥 需你决策**
- **D1**（CEO 核心）：是否把 LED 摆谱降级为 Phase 2、先走 Approach B（自生成局面免 LED）？取决于 §1.2 前提。
- **D2**（CEO）：是否在动 UI 前先做 **Phase 0 分类器基准**（30 min，出混淆矩阵）？我**强烈建议做**——无论 D1 如何，它都便宜且决定后续。

**🟩 建议直接并入（与 D1/D2 无关，两边共识或低风险）**
1. **软性 CV 校验防摆错**（设计 #7 + CEO 共识）：manifest 加 `verify` 占位；用 `stones.py` 差分比对实际/期望盘面，摆错则标记/提示。
2. **采集多样性要求**（CEO）：plan §4 写明变换光照/角度/曝光/填充度；避免一局 N 张高相关帧。
3. **失败可见**（设计 #1 + D 表）：相机/LED 健康常驻状态点；相机掉线**阻断确认**（非 4s toast）。
4. **`退出`移出控制行 + 二次确认 + 轻量 resume**（设计 #2/#6/B/F）。
5. **提子改独立模式**（设计 #3/C）：不同按钮文案+颜色+横幅，打断节奏。
6. **Session 布局层级规范 + LED 配色图例 + 大确认键人体工学**（设计 #4/#5/A/B/E）。
7. **BaipuListPage 过滤(非置灰)+空状态+继续上次**（设计 #8/H）；**采集快门反馈**（设计 #9/I）。

**✅ 两边都同意保留**：`goBoard.ts` 收敛、`CaptureService`+manifest、Phase 4 几何迁移。

**🔧 顺带技术校正**（CEO 提到，待核）：`auto_label.py` 绝对 HSV 在橙木盘失效——若走任何 CV 标注路径需改用空盘差分。

---

*附：本计划此前已过一轮 67-agent 内部对抗评审（见 `plan.md` §10）。本文件为 gstack 设计/CEO 双视角补充。Codex/Gemini 的外部评审见 `review-request.md`（另行收集）。*
