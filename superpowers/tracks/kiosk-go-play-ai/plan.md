# 围棋 kiosk · 对弈·AI/升降级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让盒上一局棋从开局到结束胜负判对、记进账、结算得了,屏上说的每一句话都是真的(PRD §3 的 11 组条目)。

**Architecture:** 先修后端判胜负与收尾(`interface.py` 认输方 / 数子门槛 / 补分,`core/ai.py` 终局后不落子,
`server.py` 一个共用的终局收尾函数 + `session.py` 在请求之外结束对局时调用它),再修前端对局屏(加载失败出口、数子在途与原因、
玩家卡倒计时、右栏按对局类型、实体盘降级、错误条),最后是开局设置的策略 id 与升降级 503 分原因。
升降级的账本与结算逻辑一行不改,只给它补调用方;升降级局的终局判目等 Fan 拍板,不进本计划。

**Tech Stack:** Python 3.13 / FastAPI / pytest + pytest-asyncio;React 19 + TypeScript + Vite / vitest + Testing Library / Playwright(真浏览器 1024×600)。

**Spec:** `superpowers/tracks/kiosk-go-play-ai/prd.md`(本计划只覆盖其 §3「本轮做」;§4 待拍板的一概不做)

## 修订记录

**r1(2026-09-15，阶段 A 已补齐并自查)** —— Codex adversarial review 5 条发现(五份独立验证全部 confirmed)、同类扫描 S1–S11、设计评审 4 major + 7 minor。
五条发现是同一个病:「这局结束了没有」由游标上的 `end_state` 临时推,检查与写入之间没有互斥,await 之后又按游标重推一遍。
所以不逐条打补丁,立两件东西:**终局事实** `WebGame.terminal`(按局面线判,`WebGame.ended_at`)与**对局提交锁**(复用 `ai_ladder_commit_lock`)。

- **C1 超时不绑定轮次与时钟** → 采纳:请求带期望的局 / 手 / 方,服务端在提交锁里核轮次、用服务端时钟核实,核实不了一律拒、不判负;前端 409 重同步、网络类失败退避重发 → Task 6(Step 1、Step 4)、Task 2(`_commit_end_state`)。
- **C2 数子 await 之后不复核** → 采纳:`/api/count/request` 在 await 前取节点,`_commit_end_state(result, node=node)` 原子地核「没被先结束、仍是当前手」,冲突 409;反方向(数子已写后认输)由先写者胜覆盖 → Task 4(Step 1、Step 2)、Task 2。
- **C3 AI 提交与终局写入不互斥** → 采纳:AI 提交(普通与升降级合成一段)、AI 认输、人的落子、挪游标、时钟结算、全部终局写入都进对局提交锁;长等待在锁外 → Task 2(Step 1、Step 3),Global Constraints「对局提交锁」。
- **C4 收尾依赖游标** → 采纳:收尾函数签名带捕获的 `GameEnd`,按它落账;请求路径只收尾本次请求造出来的终局 → Task 5(Step 1–3)。
- **C5 断线出口等于认输** → 采纳:断线时退出框多一颗「先离开，不认输」 → Task 11(Step 1、Step 2)。
- **执行流程审计** → 证据包里 `procedures` 为 `null`(审计没产出结论,不替它编问题);本修订自带的流程改动已落:共享领地 `api.ts` 从 Task 2 起跑两套构建、既有真类测试补进运行清单、替身跟上真接口、合并 grep 前移到各 Task、依赖改为主链串行、派发约束 → Global Constraints、File Structure、依赖行、Task 2/4/5/12。
- **设计评审吸收**(详见 `superpowers/tracks/kiosk-go-play-ai/r1/design-r1.md` §7):M1 空操作不进收尾;M2 冻结收窄到局面线(`_commit_end_state` 也按局面线,另开分支可以再结束一次);M3 合并指引写成代码 + 行为验收;M4 `/api/resign` 平台分支 `wrote`;m5–m11 夹具 / 异常面 / 超时退避 / 换局判定 / 平台双停 / 锁的确定性用例 / 升降级读终局事实 → 各 Task 内标「评审 r1」处。

- **本次补齐**:Task 6 叶子/终局闸、timeout 第三参、409/403 重同步和 2/5/10 秒退避;Task 11 不认输离开及同局返回测试;Task 12 源码闸、合并行为验收、上板与后续项;Self-Review 接口清单。Task 0 实测基线为 116 个失败名称，收集错误继续运行、失败行锚定和三处测试污染清理已写进所有 Task 的基线命令。视觉证据只标「待 Fan 确认」。

## Global Constraints

> **开工前先读 `prd.md` §6.0**：五条赛道的共享文件归属与合并顺序（尤其 `server.py` 终局落账只留一条入口）。与本 plan 冲突时以 §6.0 为准。

- 在 worktree `/Users/fan/Repositories/katrain-kiosk-go-play-ai`(分支 `feature/kiosk-go-play-ai`)里开发;**不 push、不合并 develop**,合并由 Fan 决定;**不在别的 worktree 里 checkout**。所有命令用绝对路径或先 `cd` 到本 worktree。
- 环境(2026-09-15 handoff 实测):本 worktree 已完成 `uv sync --extra web` 与 `npm ci`;vitest 161 文件绿(1725 passed / 5 skipped)、`npx tsc -b` 绿。复用本仓环境，不借主仓环境。macOS 系统 git 的 xcrun 临时缓存受限时用 `/opt/homebrew/bin/git`。
- 改了共享领地(`src/components`、`src/hooks`、`src/api.ts` + `src/api/`、`src/features`、`src/context`、`src/utils`、`src/types`)必须 `npm run build` 与 `npm run build:kiosk-2d` 都绿;kiosk 边界(`npm run verify:kiosk-2d`,已串在 `build:kiosk-2d` 里)不许破。共享文件不许 import `src/kiosk`/`src/galaxy`/`src/pages`。
- 类型检查用 `npx tsc -b`(`npx tsc --noEmit` 检查 0 个文件);`*.test.ts(x)` 不在 tsc 范围内,测试文件的类型错不会红。
- 盒上 token 恒为 null:任何「发不发请求 / 渲不渲染」的判别位用 `isAuthenticated`(或服务端下发的 `analysis_delivered` 等字段),不用 `token`。
- 新文案一律 `t('ns:key', '中文默认')`;**不往 PO 里加 key**(补不补 PO 待 Fan 裁定)。
- 格式化:Python `uv run black -l 120 <改到的 .py>`(⚠️ `katrain/web/server.py` 基线就有一处 black 不合规 —— `:341-343` 那个 `asyncio.create_task(_report_settlement_loop(...))` 三行;black 会顺手把它压成一行。提交前 `git diff katrain/web/server.py` 看到这一处就还原,不夹带:另外四条赛道也在改 server.py);前端 `npx eslint <改到的文件>` 不新增 error(基线已有的不算)。
- 前端单测:`cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui && npx vitest run <文件>`;后端:`cd /Users/fan/Repositories/katrain-kiosk-go-play-ai && CI=true uv run pytest <文件> --continue-on-collection-errors -q`。
- **测试判据是基线 diff**:Task 0 在干净树上记录失败用例名字集合;每个 Task 结束比名字集合(`comm -13 基线 本次`),不比条数。报告里写「新增失败 = 空」。每个 Task 都跑后端和前端全量；后端基线在 `/tmp/kgpa-baseline/pytest-failed.txt`，可从 `r1/baseline-pytest-failed.txt` 恢复（70 failed / 46 errors，共 116 个名字，两次一致）。全量必须带 `--continue-on-collection-errors`（缺 cv2/boto3/fontTools 导致 28 个模块收集失败，否则一条也不跑）；日志仅提取 `^(FAILED|ERROR) tests/`，避免把 logger 的 ERROR 行当成用例。
- 基线名单排序固定 `LC_ALL=C`，读取 handoff 的既有名单先用 `LC_ALL=C sort -u <文件> -o <文件>` 规范顺序（名称集合不变）；否则 macOS `C.UTF-8` 与此前排序不同会让 comm 假报新增。Node 26 的原生 Web Storage 若覆盖 jsdom，vitest 加 `NODE_OPTIONS=--no-experimental-webstorage`，不修改测试基础设施。
- **真 `WebKaTrain` 的后端测试放 `tests/` 根目录**:`tests/web_ui/conftest.py:90` 把 `sys.modules["katrain.web.interface"]` 整个换成 MagicMock,放进 `tests/web_ui/` 就只是在测替身（原 `tests/web_ui/test_count_api.py::TestIntegration` 随 Task 3 移到真类文件，消除这类替身误判）。这类测试文件首个用例断言拿到的是真类。
- **单跑时 `tests/test_play_ai_endgame.py` 不许和任何 `tests/web_ui/…` 文件放进同一条 pytest 命令**:参数里只要有一个 `tests/web_ui/` 下的文件,pytest 在**收集任何模块之前**就加载 `tests/web_ui/conftest.py`(initial conftest),`sys.modules["katrain.web.interface"]` 当场变成 MagicMock,根目录文件的 `from katrain.web.interface import WebKaTrain` 拿到的就是替身 —— 首条「真类」用例红,其余结论全不作数(2026-09-14 审查时用玩具目录复现)。本计划里凡是两者同跑的地方都已拆成两条命令;全量 `pytest tests` 不受影响(按名字排序,根目录的 `test_play_ai_endgame.py` 先于 `web_ui/` 被收集)。
- 后端测试污染：跑前确认 `katrain/config.json`、`katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json` 无待保留改动，且没有既存 `test_user_data.db`；跑后检查。每次全量结束均 `git restore --source=HEAD --` 这两个文件并删除本次生成的 `test_user_data.db`，绝不提交。前者由 `force_package_config=True` 写回；后者由 `tests/platforms/test_engine_manager.py::test_dump_engine_game_state_fixture` 改写。若已有用户改动先备份恢复，不覆盖。
- **Playwright e2e 打的是构建产物**(`playwright.config.ts` 起 `python -m katrain --ui=web --port 8002` 服务 `katrain/web/static`):改源码后先 `npm run build` 再跑。跑前 `lsof -nP -iTCP:8002 -sTCP:LISTEN`(四图用 `:5173`),端口若被**别的 worktree** 的进程占着(`lsof -p <PID> | grep cwd` 看目录),`reuseExistingServer` 会让你测到别人的包 —— 等它结束或与对方协调,不要杀别人的进程。`--ui web` 退出时会改 `~/.katrain/config.json`:跑 e2e 前 `cp ~/.katrain/config.json /tmp/kgpa-katrain-config.json`,跑完拷回。
- 视觉/布局改动走 CLAUDE.md 的四图对比与承重实测关卡:`npm run fourup` 重跑被改到的屏,跑两次 diff 两次结果得本屏抖动地板,只提交有内容变化的屏(`git checkout HEAD -- <屏目录>` 前先确认没有未提交的活);jsdom 不作布局证据;**视觉通过需 Fan 确认**；本次只产截图和对比，标「待 Fan 确认」，继续已授权的后续 Task，不自行判通过。
- 升降级账本:`katrain/web/core/ai_ladder_ranked.py` 与 `ai_ladder_catalog.py` 本计划**一行不改**;升降级局不补分析(`analysis_allowed` 为假时一律不补)。
- 新建文件前先 `git ls-files <路径>` 与 `ls <路径>` 确认不存在,不用 `cat >` 覆盖既有文件;zsh 不做词分割,循环文件列表用数组或逐个写。
- 每个 Task 一次提交,提交信息结尾带 `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`;提交前 `git add` 明确列文件后用 `git diff --cached --stat` 确认(仓里 `.gitignore` 有 `log*`,macOS 大小写不敏感,新文件可能被静默吞掉)。
- **对局提交锁(r1,Task 2 起生效)**:
  - 锁序全局唯一,只许按这个方向嵌套:`session.lock` → `ai_lock` → `WebKaTrain.ai_ladder_commit_lock`(对局提交锁,`RLock`)→ `Game._lock` / 引擎 `queue.put`。AI 线程走 `ai_lock → 提交锁`,**从不**拿 `session.lock`;asyncio 锁(`end_game_lock`、`record_game_lock`)只在协程里拿,且**持任何 threading 锁时不 await**。
  - 持提交锁时只许:读写节点与 `game.terminal`、`game.play`、`set_current_node`、`update_timer`(纯算术)。**禁止**:`await`、数据库 / 网络、`update_state()`(它会遍历全树并广播)、回头拿 `session.lock` / `ai_lock`、等引擎。AI 生成、补分析这类长等待一律在锁外。
  - 终局结果**只经** `WebKaTrain._commit_end_state` 写(双停的待补分终局只经 `WebGame.record_two_pass_end` 记);「这一手所在的局面结束过没有」**只认** `WebGame.ended_at(node)`,「这一局结束过没有」(给前端冻结用)只认 `get_state()["terminal_result"]`。游标上的 `end_result`、`session.game_ended`、`_recorded`、`end_game_lock` 都不是判据。
  - await 之后按事先捕获的 `node` / `game` / `GameEnd` 身份复核,不按游标;请求路径只收尾**本次请求造出来的**终局(`_new_terminal(session, before)`)。
- **派发约束(r1)**:同一个 worktree 同一时刻只能有一个写入 agent(index、工作树、`katrain/config.json` 污染面、`/tmp/kgpa-*` 基线文件、8002 / 5173 端口都是共用的);主链 `1 → 2 → 3 → 4 → 5 → 6 → 9 → 10 → 11 → 12` 逐 Task 串行派发。能并行的只有 `7 → 8` 这条支线,前提是 `git worktree add` 出独立子分支、做完 cherry-pick 回来,且支线的全量基线 diff 不与主链同时跑(两边共用 `~/.katrain/config.json` 与端口);不愿多开 worktree 就把 7、8 串在 Task 5 与 6 之间。只读的复审 / 验证 agent 可以并行,但一律在镜像目录上跑,不在主工作树上 `git checkout`。Task 2 规模明显变大:仍是一次提交,派发时分两个回合(先后端 Step 1–4、Step 4 两条命令全绿后再前端 Step 5–7)。

## File Structure

| 文件 | 职责 | Task |
|---|---|---|
| `katrain/web/models.py` | `GameEnd`、`EndgameConflict`(Task 2);`TimeoutRequest`(Task 6)。放这里是因为 `tests/web_ui/conftest.py:90` 把 `katrain.web.interface` 整个换成 MagicMock,异常类定义在 interface 里,server 的 `except` 在 web_ui 测试里拿到的就是 MagicMock | 2、6 |
| `katrain/core/ai.py` | 提交段统一进对局提交锁(普通与升降级合成一段);复核开算节点与终局事实(`_game_already_ended(game, node)`);双停经 `record_two_pass_end` 记;AI 认输走 `_commit_end_state` | 2 |
| `katrain/web/interface.py` | `WebGame.terminal` / `ended_at` / `record_two_pass_end`,`play` / `set_current_node` / `update_timer` 进提交锁;`_commit_end_state`、`_do_resign(loser)`、`_do_play(coords, guard, expected_player)`、`get_state()["terminal_result"]`、AI 触发闸按局面线;`count_min_moves()`、`ensure_current_score(timeout_s, node)`、`game_ended_callback(end)`、`timer_configured`、`clock_exhausted()`、`_do_timeout(expected_*)` | 2、3、4、5、6 |
| `katrain/web/server.py` | `EndgameConflict` → 409 处理器;`/api/move`、视觉两支带 `guard`;`/api/resign` 多人局传认输方 + `wrote` 闸(平台分支同);`/api/count/request` 用新门槛、await 前取节点并补分;`_terminal_of` / `_new_terminal` / `_count_result` / `_score_two_pass_end` / `_finish_ended_game(end)` / 装钩子;四个终局请求入口只经 `_finish_ended_game`;`/api/timeout` 绑定轮次;升降级落账读终局事实 | 2、3、4、5、6 |
| `katrain/web/session.py` | `WebSession.end_game_lock`;`SessionManager.on_game_ended(session, end)`、`_on_game_ended(sid, end)`,`create_session` 装 `game_ended_callback`(`_on_state` 不动) | 5 |
| `katrain/web/ui/src/kiosk/pages/GamePage.tsx` | 加载失败出口、认输框写明哪一方、「本局已结束」读终局事实并挡落子、数子在途与原因、超时带轮次与重试、按需分析条件、实体盘降级、错误条、断线时「先离开，不认输」 | 1、2、4、6、9、10、11 |
| `katrain/web/ui/src/kiosk/components/game/goClock.ts`(新) | 计时读数纯函数 + `useGoClock` | 6 |
| `katrain/web/ui/src/kiosk/components/game/gameKinds.ts`(新) | `isFreeVsAi` —— 胜率块/悔棋/按需分析共用的对局类型判别 | 9 |
| `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx` | 玩家卡时钟、升降级撤分析键、非胜率局显示棋谱 | 6、9 |
| `katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx` | 策略 id 与说明;升降级开局 503 分原因 | 7、8 |
| `katrain/web/ui/src/features/aiLadder/startErrors.ts`(新)、`useAiLadderStatus.ts`(`copy.ts` 不改) | 升降级 503 按 detail 分原因(共享领地) | 8 |
| `katrain/web/ui/src/kiosk/components/physical/PhysicalSyncEscalationDialog.tsx`、`components/game/RecalibrationModal.tsx`、`components/vision/VisionSyncOverlay.tsx` | 降级回调与文案 | 10 |
| `katrain/web/ui/src/hooks/useGameSession.ts` | `connectionLost`、`clearError`(共享领地,纯增量) | 11 |
| `katrain/web/ui/src/api.ts` | `GameState.terminal_result?: string \| null`(Task 2)、`GameState.timer.configured?: boolean`(Task 6)、`API.timeout(sessionId, token?, expect?)`(Task 6)—— 共享领地,第三参可选,galaxy 调用不用改 | 2、6 |
| 测试(新建) | `tests/test_play_ai_endgame.py`、`tests/core/test_ai_commit_after_end.py`、`tests/web_ui/test_game_end_hook.py`、`tests/web_ui/test_play_ai_endgame_api.py`、`src/kiosk/pages/GamePage.playAi.test.tsx`、`src/kiosk/components/game/goClock.test.ts`、`src/kiosk/components/game/GameControlPanel.playAi.test.tsx`、`src/features/aiLadder/startErrors.test.ts`、`src/hooks/useGameSession.connection.test.tsx`、`tests/kiosk-screen-05-play-ai.spec.ts` | 各 Task |
| 测试(既有,r1 起要改) | `tests/web_ui/test_ai_ladder_api.py`(`FakeKaTrain` 加提交锁与 `_commit_end_state`、终局绊线谓词扩到 `_commit_end_state(` —— Task 2;`ensure_current_score(node=)` —— Task 4)、`tests/web_ui/test_ai_game_autosave.py`(`_make_mock_session` 由替身在派发时写终局事实 —— Task 5) | 2、4、5 |

阶段:**Phase 1(P0/P1)= Task 0–8**,**Phase 2(P2/P3)= Task 9–11**,Task 12 收尾验证。

依赖(r1 修订):主链 `1 → 2 → 3 → 4 → 5 → 6 → 9 → 10 → 11 → 12` 逐个串行;支线 `7 → 8`,与主链文件不相交,可按 Global Constraints「派发约束」开独立 worktree 并行,或串在 5 与 6 之间。理由:
- 1 → 2:Task 2 往 Task 1 新建的 `GamePage.playAi.test.tsx` 里追加用例(原图漏写的隐含依赖)。
- 2 → 3 → 4 → 5 → 6:同改 `server.py` / `interface.py`;Task 6 现在还改 `models.py` 与 `/api/timeout`,读 Task 2 的 `terminal_result`、用 Task 5 的 `_new_terminal` / `_finish_ended_game`,并改 Task 4 刚改过的 `GamePage.tsx`。
- 6 → 9:同改 `GameControlPanel.tsx`;9、10、11 都改 `GamePage.tsx`,原本就是串行。11 依赖 2(同一个退出确认框)。
- 7 → 8:都改 `AiSetupPage.tsx`;涉及文件 `AiSetupPage*`、`features/aiLadder/startErrors.ts`、`useAiLadderStatus.ts`,与主链不相交。

---

### Task 0: 环境与基线

**Files:**
- 无源码改动;基线输出写 `/tmp/kgpa-baseline/`

**Interfaces:**
- Consumes: 无
- Produces: `/tmp/kgpa-baseline/pytest-failed.txt`、`/tmp/kgpa-baseline/vitest-failed.txt`(失败用例名,每行一个,已排序去重),后续每个 Task 用它做 `comm -13`

- [x] **Step 1: 装环境**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
git status --short            # 记录现有改动，不覆盖；prd/plan 已提交，Task 0 已完成
git rev-parse HEAD            # 记录实际提交号，不硬编码旧 HEAD
uv sync --extra web
cd katrain/web/ui && npm ci
```
Expected: 两条安装都成功;`uv run python -c "import fastapi"` 不报错。

- [x] **Step 2: 后端基线**

```bash
mkdir -p /tmp/kgpa-baseline
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
git status --short katrain/config.json   # 期望:空
CI=true uv run pytest tests --continue-on-collection-errors -q -rfE -p no:cacheprovider 2>&1 | tee /tmp/kgpa-baseline/pytest.log
grep -E '^(FAILED|ERROR) tests/' /tmp/kgpa-baseline/pytest.log | sed -E 's/ - .*//' | LC_ALL=C sort -u > /tmp/kgpa-baseline/pytest-failed.txt
wc -l /tmp/kgpa-baseline/pytest-failed.txt
git restore --source=HEAD -- katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json
rm -f test_user_data.db
git status --short katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json test_user_data.db   # 期望:空
```
Expected: 跑完(失败条数不重要,名字集合才是判据)。

- [x] **Step 3: 前端基线**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
npx vitest run --reporter=verbose 2>&1 | tee /tmp/kgpa-baseline/vitest.log
grep -E '^\s+×' /tmp/kgpa-baseline/vitest.log | sed -E 's/^\s+×\s+//; s/ [0-9]+ms$//' | LC_ALL=C sort -u > /tmp/kgpa-baseline/vitest-failed.txt
wc -l /tmp/kgpa-baseline/vitest-failed.txt
npx tsc -b && echo TSC_OK
```
Expected: `TSC_OK`;若 tsc 在干净树上就红,把输出存 `/tmp/kgpa-baseline/tsc.log` 并在报告里说明,后续 Task 以「不新增 tsc 错误」为准。

- [x] **Step 4: 不提交**(本 Task 没有源码改动)

每个后续 Task 的「基线 diff」都用下面两套命令；只能在本 worktree 串行运行，不与其它 agent 的全量并行。失败日志必须保留完整 summary，不能把中断当成空集合。

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
CI=true uv run pytest tests --continue-on-collection-errors -q -rfE -p no:cacheprovider 2>&1 | tee /tmp/kgpa-now-pytest.log
grep -E '^(FAILED|ERROR) tests/' /tmp/kgpa-now-pytest.log | sed -E 's/ - .*//' | LC_ALL=C sort -u > /tmp/kgpa-now-pytest-failed.txt
LC_ALL=C comm -13 /tmp/kgpa-baseline/pytest-failed.txt /tmp/kgpa-now-pytest-failed.txt   # 期望:无输出
git restore --source=HEAD -- katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json
rm -f test_user_data.db
git status --short katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json test_user_data.db   # 期望:空
cd katrain/web/ui
npx vitest run --reporter=verbose 2>&1 | tee /tmp/kgpa-now-vitest.log
grep -E '^\s+×' /tmp/kgpa-now-vitest.log | sed -E 's/^\s+×\s+//; s/ [0-9]+ms$//' | LC_ALL=C sort -u > /tmp/kgpa-now-vitest-failed.txt
LC_ALL=C comm -13 /tmp/kgpa-baseline/vitest-failed.txt /tmp/kgpa-now-vitest-failed.txt   # 期望:无输出
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
```

---

## Phase 1 · P0 / P1

### Task 1: N17 对局屏取状态失败时给出口(P0)

**执行记录（2026-09-15）**：红灯 2 failed / 1 passed（缺两种出口）；三文件 80 passed；全量前端 1728 passed / 5 skipped；后端与前端新增失败名称均为空；tsc 绿、eslint 无新增 error。截图已产出并验证返回 `/kiosk/play`，**待 Fan 确认**；截图后端不可达，因此后端提供的顶栏 logo 未加载。环境差异是 Node 26 原生 Web Storage 与名单排序口径，已按 Global Constraints 处理，无业务实现偏离。

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx`(`activeSession` 那个 effect 之后加一个 effect;`:352-357` 早退分支整段替换)
- Create: `katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx`(本赛道 GamePage 行为测试的共用测试文件,后续 Task 往里追加 `describe`)

**Interfaces:**
- Consumes: `useGameSession()` 已有返回值 `gameState`、`error`;`clearActiveSession(kind)`(`kiosk/utils/activeSession.ts`)
- Produces: 对局屏两种早退态 —— `data-testid="game-loading"`(转圈 + 「回到对弈」)与 `data-testid="game-unavailable"`(标题「这一局已经打不开了」+ 原因句 + 「回到对弈」);测试文件导出的桩对象 `sessionMock` / `vision` / `makeState` 形状供 Task 2/4/6/9/10/11 复用(同文件内)

- [x] **Step 1: 写失败的测试(新建测试文件,含本赛道共用的桩)**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
git ls-files src/kiosk/pages/GamePage.playAi.test.tsx; ls src/kiosk/pages/GamePage.playAi.test.tsx   # 期望:都没有
```

`katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import { API, type GameState } from '../../api';
import GamePage from './GamePage';

/**
 * 对弈·AI/升降级赛道(superpowers/tracks/kiosk-go-play-ai)的 GamePage 行为测试。
 * 只证行为与文案(jsdom 没有布局引擎);右栏几何在 tests/kiosk-screen-05-play-ai.spec.ts 里用真浏览器量。
 * 身份按盒上口径桩:`token: null`、`isAuthenticated: true`。
 */

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: null, isAuthenticated: true, user: { id: 1, username: 'box-user' } }),
}));
// 棋盘桩是一颗按钮:点它 = 在 (3,3) 落子。Task 2 用它证「终局之后点盘不发落子」。
vi.mock('../../components/Board', () => ({
  default: (p: { onMove?: (x: number, y: number) => void }) => (
    <button type="button" data-testid="board" onClick={() => p.onMove?.(3, 3)} />
  ),
}));

interface MockPanelProps { onAction: (a: string) => void; onTimeout?: (c: 'B' | 'W') => void; isGameOver?: boolean }
vi.mock('../components/game/GameControlPanel', () => ({
  default: (p: MockPanelProps) => (
    <div data-testid="game-control-panel">
      <button onClick={() => p.onAction('resign')}>MOCK_RESIGN</button>
      <button onClick={() => p.onAction('count')}>MOCK_COUNT</button>
      <button onClick={() => p.onTimeout?.('B')}>MOCK_TIMEOUT_B</button>
      {/* Task 2:右栏拿到的「本局已结束」 */}
      <span data-testid="panel-over">{String(p.isGameOver)}</span>
    </div>
  ),
}));

const { clearActiveSession, writeActiveSession } = vi.hoisted(() => ({
  clearActiveSession: vi.fn(),
  writeActiveSession: vi.fn(),
}));
vi.mock('../utils/activeSession', () => ({ clearActiveSession, writeActiveSession }));
vi.mock('../../api/geometryApi', () => ({ GeometryAPI: { calibrate: vi.fn().mockResolvedValue({}) } }));
vi.mock('../../features/aiLadder/api', () => ({ getAiLadderStatus: vi.fn() }));

const vision = vi.hoisted(() => ({ enabled: false, poseLocked: true }));
vi.mock('../context/VisionContext', () => ({
  useVision: () => ({
    visionStatus: {
      enabled: vision.enabled, cameraConnected: true, poseLocked: vision.poseLocked,
      syncState: 'idle', boundSessionId: null, ledConnected: null,
    },
    isVisionEnabled: vision.enabled,
    refreshStatus: vi.fn(),
  }),
}));
vi.mock('../hooks/useVisionSync', () => ({
  useVisionSync: () => ({ syncEvents: [], latestEvent: null, setupProgress: null, isSetupComplete: false }),
}));

const sessionMock = vi.hoisted(() => ({
  gameState: null as unknown,
  error: null as string | null,
  connectionLost: null as 'rejected' | 'dropped' | null,
  physicalReminder: null as unknown,
  handleAction: vi.fn(),
  onMove: vi.fn(),
  setGameState: vi.fn(),
  clearError: vi.fn(),
}));
vi.mock('../../hooks/useGameSession', () => ({
  useGameSession: () => ({
    sessionId: 'play-ai-s1',
    setSessionId: vi.fn(),
    gameState: sessionMock.gameState,
    setGameState: sessionMock.setGameState,
    error: sessionMock.error,
    connectionLost: sessionMock.connectionLost,
    clearError: sessionMock.clearError,
    onMove: sessionMock.onMove,
    onNavigate: vi.fn(),
    handleAction: sessionMock.handleAction,
    physicalReminder: sessionMock.physicalReminder,
    physicalEngineError: null,
    clearPhysicalEngineError: vi.fn(),
    awaitingRemovalReminder: null,
  }),
}));

const seat = (type: string, name: string) => ({
  player_type: type, player_subtype: '', name, calculated_rank: null, periods_used: 0, main_time_used: 0,
});

const makeState = (over: Partial<GameState> = {}): GameState => ({
  game_id: 'g', board_size: [19, 19], komi: 7.5, handicap: 0, ruleset: 'chinese',
  current_node_id: 5, current_node_index: 5, history: [], player_to_move: 'B', stones: [], last_move: null,
  prisoner_count: { B: 0, W: 0 }, analysis: null, commentary: '', is_root: false, is_pass: false, end_result: null,
  children: [], ghost_stones: [], note: '', language: 'cn', game_type: 'free', count_min_moves: 100,
  ui_state: {
    show_children: false, show_dots: false, show_hints: false, show_policy: false,
    show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false,
  },
  players_info: { B: seat('player:human', '我'), W: seat('player:ai', 'KataGo') },
  ...over,
} as GameState);

// 单独拎出来,是为了 `rerender(pageTree())` 能用同一棵树:改完桩的值再重渲,组件身份不变。
const pageTree = () => (
  <ThemeProvider theme={kioskTheme}>
    <MemoryRouter initialEntries={['/kiosk/play/ai/game/play-ai-s1']}>
      <Routes>
        <Route path="/kiosk/play/ai/game/:sessionId" element={<GamePage />} />
        <Route path="/kiosk/play" element={<div>PLAY_PAGE</div>} />
      </Routes>
    </MemoryRouter>
  </ThemeProvider>
);

const renderPage = () => render(pageTree());

beforeEach(() => {
  vi.clearAllMocks();
  sessionMock.gameState = null;
  sessionMock.error = null;
  sessionMock.connectionLost = null;
  sessionMock.physicalReminder = null;
  vision.enabled = false;
  vision.poseLocked = true;
  sessionStorage.clear();
  sessionMock.handleAction.mockResolvedValue(undefined);
  sessionMock.onMove.mockResolvedValue(undefined);
  vi.spyOn(API, 'hintDismiss').mockResolvedValue({ ok: true });
});

describe('N17 · 取状态失败时对局屏给出口', () => {
  it('状态还没回来:转圈旁边就有「回到对弈」', () => {
    renderPage();
    expect(screen.getByTestId('game-loading')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '回到对弈' }));
    expect(screen.getByText('PLAY_PAGE')).toBeInTheDocument();
  });

  it('取状态失败:说清打不开、清掉「继续上一局」、给「回到对弈」', async () => {
    sessionMock.error = 'Failed to connect to game';
    renderPage();
    expect(screen.getByTestId('game-unavailable')).toBeInTheDocument();
    expect(screen.getByText('这一局已经打不开了')).toBeInTheDocument();
    await waitFor(() => expect(clearActiveSession).toHaveBeenCalledWith('game'));
    fireEvent.click(screen.getByRole('button', { name: '回到对弈' }));
    expect(screen.getByText('PLAY_PAGE')).toBeInTheDocument();
  });

  it('局面已经在屏上时,连接类错误不会把整屏换成「打不开」', () => {
    sessionMock.gameState = makeState();
    sessionMock.error = '实时连接已断开，棋盘不会自动更新，请刷新页面';
    renderPage();
    expect(screen.queryByTestId('game-unavailable')).toBeNull();
    expect(clearActiveSession).not.toHaveBeenCalled();
  });
});
```

- [x] **Step 2: 跑测试确认失败**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui && npx vitest run src/kiosk/pages/GamePage.playAi.test.tsx`
Expected: 前两条 FAIL(找不到 `game-loading` / `game-unavailable`),第三条 PASS。

- [x] **Step 3: 实现**

在 `GamePage.tsx` 里 `activeSession write-on-load / clear-on-end` 那个 `useEffect`(`:227-238`)之后插入:

```tsx
  // N17:取状态失败 = 这一局在服务端已经不在了(盒子重启、闲置超过 1 小时被回收),
  // 或者它不属于当前账号。「继续上一局」那个指针再留着,只会把人一次次领回这块打不开的屏。
  // 判据是「没有局面 **且** 有错」:局面到过之后的错(WS 断开)不在这里处理。
  const loadFailed = !session.gameState && !!session.error;
  useEffect(() => {
    if (loadFailed) clearActiveSession('game');
  }, [loadFailed]);
```

把早退分支(`if (!session.gameState) { return (<Box …><CircularProgress /></Box>); }`)整段替换为:

```tsx
  if (!session.gameState) {
    // N17:早退分支上没有页控条、没有 Dock、没有主页键 —— 这里不给出口,盒上就是一块死页
    // (全屏 chromium 没有地址栏,也没有后退手势)。转圈时也给,因为取状态可能一直不回来。
    return (
      <Box
        data-testid={loadFailed ? 'game-unavailable' : 'game-loading'}
        sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              gap: 2, height: '100%', px: 4, textAlign: 'center' }}
      >
        {loadFailed ? (
          <>
            <Typography sx={{ color: 'text.primary', fontSize: 18, fontWeight: 600 }}>
              {t('game:unavailable_title', '这一局已经打不开了')}
            </Typography>
            <Typography sx={{ color: 'text.secondary', fontSize: 14, maxWidth: 520 }}>
              {t('game:unavailable_reason', '可能是盒子重启过、这一局闲置太久被清理，或者它属于另一个账号。')}
            </Typography>
          </>
        ) : (
          <CircularProgress />
        )}
        <button type="button" className="kiosk-btn kiosk-btn--secondary" onClick={() => navigate('/kiosk/play')}>
          {t('game:back_to_play', '回到对弈')}
        </button>
      </Box>
    );
  }
```

- [x] **Step 4: 跑测试确认通过 + 类型 + lint**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
npx vitest run src/kiosk/pages/GamePage.playAi.test.tsx src/kiosk/pages/GamePage.test.tsx src/kiosk/__tests__/GamePageEngine.test.tsx
npx tsc -b && echo TSC_OK
npx eslint src/kiosk/pages/GamePage.tsx
```
Expected: 三个文件全 PASS;`TSC_OK`;eslint 只有基线就有的 warning,无新增 error。

- [x] **Step 5: 真实运行时看一眼(一张图,不做四图 —— 稿子没有这一态)**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
lsof -nP -iTCP:5173 -sTCP:LISTEN   # 被别的 worktree 占着就换个时间,不要杀
npm run dev -- --host 127.0.0.1 --port 5173
```
另开终端用 `/browse`(gstack)打开 `http://127.0.0.1:5173/kiosk/play/ai/game/does-not-exist`,viewport 1024×600,截图存
`/Users/fan/Repositories/katrain-kiosk-go-play-ai/superpowers/tracks/kiosk-go-play-ai/visual/n17-game-unavailable-1024x600.png`。
Expected: 屏上是标题 + 原因句 + 「回到对弈」按钮,按钮可见不被裁;点按钮到对弈首页。截图交 Fan 确认。

- [x] **Step 6: 基线 diff(后端 + 前端)后提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
# 基线 diff(后端 + 前端)，两个 comm -13 均须为空
CI=true uv run pytest tests --continue-on-collection-errors -q -rfE -p no:cacheprovider 2>&1 | tee /tmp/kgpa-now-pytest.log
grep -E '^(FAILED|ERROR) tests/' /tmp/kgpa-now-pytest.log | sed -E 's/ - .*//' | LC_ALL=C sort -u > /tmp/kgpa-now-pytest-failed.txt
LC_ALL=C comm -13 /tmp/kgpa-baseline/pytest-failed.txt /tmp/kgpa-now-pytest-failed.txt   # 期望:无输出
git restore --source=HEAD -- katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json
rm -f test_user_data.db
git status --short katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json test_user_data.db   # 期望:空
cd katrain/web/ui
npx vitest run --reporter=verbose 2>&1 | tee /tmp/kgpa-now-vitest.log
grep -E '^\s+×' /tmp/kgpa-now-vitest.log | sed -E 's/^\s+×\s+//; s/ [0-9]+ms$//' | LC_ALL=C sort -u > /tmp/kgpa-now-vitest-failed.txt
LC_ALL=C comm -13 /tmp/kgpa-baseline/vitest-failed.txt /tmp/kgpa-now-vitest-failed.txt   # 期望:无输出
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
git add katrain/web/ui/src/kiosk/pages/GamePage.tsx katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx superpowers/tracks/kiosk-go-play-ai/visual/n17-game-unavailable-1024x600.png
git diff --cached --stat
git commit -m "fix(kiosk): 对局屏取状态失败时整屏转圈没有出口 —— 给「回到对弈」并清掉失效的「继续上一局」

N17(P0)。盒上 katrain 重启或会话闲置被回收后,「继续上一局」领进来的是一块只有转圈的死页。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: N21 认输判错方;终局之后 AI 着法不再落下 —— 终局事实 + 对局提交锁(r1)

**执行记录（2026-09-15，已完成）**
- TDD 红测：根目录 20 failed / 4 passed，首条真类断言通过；HTTP 4 failed / 3 passed。日志 `/tmp/kgpa-task2-red-root.log`、`/tmp/kgpa-task2-red-web.log`。Kivy 在沙盒内收集时崩溃，真类测试改在已授权沙盒外运行。
- 以源码修正三处计划遗漏：`_complete_count` 本 Task 即改走唯一终局写入口；`_do_play` 快着状态及非法落子日志在提交锁外发出；认输/超时单机落账也以 `wrote` 为闸。新增测试先红分别见 `/tmp/kgpa-task2-red-count.log`（200 而非 409）、`/tmp/kgpa-task2-red-notices.log`（另一线程两次均拿不到提交锁）、`/tmp/kgpa-task2-red-noop.log`（两个空操作均重入落账）。对应代码片段已同步。
- 最终指定回归：根目录 **93 passed / 4 skipped**；独立 web_ui **326 passed**，日志 `/tmp/kgpa-task2-green-root.log`、`/tmp/kgpa-task2-green-web.log`。第二组在最终 `wrote` 条件修正后重跑；第一组代码未再改动。现存 warnings 为 auth 的 `datetime.utcnow()` 弃用提示。
- 唯一写入闸通过：server 无 `end_state` 赋值；interface 仅 `_commit_end_state` 的 `target.end_state`；core 仅桌面回退 `cn.end_state`（grep 增词边界，避免把局部变量 `commit_end_state` 当字段写入）。`git diff --check` 通过；两份账本、PRD 均未改；三处测试污染文件检查为干净；server 的原有 `_report_settlement_loop` 三行格式保持。

- 前端红灯 3 failed / 4 passed（本地认输方、终局回看状态、终局禁止落子），修复后三文件 84 passed；全量 1732 passed / 5 skipped。tsc 与两套构建通过；kiosk 边界干净。api.ts 原有 26 条 eslint error，新增为零。
- 只读并发复审补出插入模式导航提示：`Game.set_current_node` 会调用 `controls.set_status`，WebGame 改为锁内仅判别/导航、锁外发拒绝提示。跨线程探针先红（`[False]` 而非 `[True]`），修复后最终真类组 **94 passed / 4 skipped**。日志 `/tmp/kgpa-task2-red-insert.log`、`/tmp/kgpa-task2-green-root-final.log`。
- 首次全量新增 3 个失败名称已定位：时钟测试在执行时重新 import 被 web_ui 替换的 interface，改为收集时保留真模块；`test_board_lifespan_camera_degraded.py` 的空 models 模块补 `EndgameConflict` / `GameEnd` 两个真类型。测试适配随本 Task 提交，不修改生产实现迁就替身。


- 最终后端全量：69 failed / 3589 passed / 46 errors，名称集合对原始基线 **新增为空**；前端集合新增也为空。完整日志 `/tmp/kgpa-task2-pytest-final.log`、`/tmp/kgpa-task2-vitest.log`；web_ui 最终为 **328 passed**（含两条相机启动替身适配）。全量后的三处污染均已清理。

补充导入：`interface.py` constants import 增加 `STATUS_ERROR`，用于锁外的插入模式导航拒绝提示。

**Files:**
- Modify: `katrain/web/models.py`(文件末尾加 `GameEnd`、`EndgameConflict`;typing import)
- Modify: `katrain/web/interface.py`:import 区;`:92-120`(`WebGame` 整段:`terminal` / `ended_at` / `record_two_pass_end`,`play` / `set_current_node` 进锁);`:560` 附近 `get_state`(`terminal_result`);`:852` 附近 `_do_update_state`(AI 触发闸);`:884-913`(`update_timer` 进锁);`:1191-1223`(`_do_play`);`:1464-1469`(`_do_resign` / `_do_timeout`,之前加 `_commit_end_state`)
- Modify: `katrain/core/ai.py:1849-1850`(`_ladder_remote_terminal` 之后加 `_game_already_ended`)、`:1946-1986`(`generate_ai_move` 整段)
- Modify: `katrain/web/server.py`:`:13`(`fastapi.responses` import 加 `JSONResponse`)、`:34`(models import)、`create_app` 里 `app = FastAPI(lifespan=lifespan)` 之后(注册 `EndgameConflict` 处理器)、`:994`(`/api/move` 带 `guard`)、`:1874-1954`(`/api/resign` 整段)、`:2119-2165`(`/api/timeout` 整段)、`:3185-3186`(视觉升降级分支)、`:3240-3242`(视觉非平台分支)
- Modify: `katrain/web/ui/src/api.ts`(`GameState` 加 `terminal_result?`)—— **共享领地**
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx`(两个确认框的 `DialogTitle`;`endResultOf` 与它的五个读者;`handleBoardMove` 开头)
- Modify(测试替身与绊线): `tests/web_ui/test_ai_ladder_api.py`(`FakeKaTrain` `:97` 起;`test_every_place_that_writes_a_terminal_result_by_hand_also_ends_the_game` 与它的正对照 `:4318-4371`)
- Modify(全量测试替身): `tests/web_ui/test_board_lifespan_camera_degraded.py`（models 替身补真异常/终局类型）
- Create: `tests/test_play_ai_endgame.py`、`tests/core/test_ai_commit_after_end.py`、`tests/web_ui/test_play_ai_endgame_api.py`
- Test: `katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx`(追加)

**Interfaces:**
- Consumes: Task 1 的 `sessionMock` / `makeState` / `renderPage` / `pageTree` 前端测试桩
- Produces:
  - `katrain.web.models.GameEnd(NamedTuple: game, node, result: str)`;`katrain.web.models.EndgameConflict(reason: str)`,`reason ∈ already_ended | position_changed | stale_turn | not_your_turn | clock_not_expired | remote_ended`
  - `WebGame.terminal: Optional[GameEnd]`(类属性默认 None);`WebGame.ended_at(node) -> bool`;`WebGame.record_two_pass_end(node) -> None`
  - `WebKaTrain._commit_end_state(self, result: str, *, node=None, fill_pending: bool = False) -> GameEnd`(冲突抛 `EndgameConflict`)
  - `WebKaTrain._do_resign(self, loser: Optional[str] = None) -> GameEnd`(`"B"`/`"W"` 为认输方,`None` 时由座位推);`_do_timeout(self) -> GameEnd`(Task 6 扩参)
  - `WebKaTrain._do_play(self, coords, guard: bool = False, expected_player: Optional[str] = None) -> None`
  - `get_state()["terminal_result"]: Optional[str]`;TS `GameState.terminal_result?: string | null`
  - `katrain.core.ai._game_already_ended(game, node=None) -> bool`
  - HTTP:`EndgameConflict` 一律 409,detail 见 Step 3 的 `ENDGAME_CONFLICT_DETAIL`;`/api/resign` 撞上 `already_ended` 回 200 空操作(不落账、不广播)
  - 测试文件 `tests/test_play_ai_endgame.py` 的 `_web_katrain()` / `_seat()` / `_Instant` / `_ai_parked_inside_its_commit()` 与
    `tests/web_ui/test_play_ai_endgame_api.py` 的 `client` / `_make_user` / `_login` / `_inject_session` 供 Task 3/4/5/6 追加用例

- [x] **Step 1: 写失败的后端测试**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
for f in tests/test_play_ai_endgame.py tests/core/test_ai_commit_after_end.py tests/web_ui/test_play_ai_endgame_api.py; do git ls-files "$f"; ls "$f" 2>/dev/null; done   # 期望:无输出
grep -n "class GameEnd\|class EndgameConflict" katrain/web/models.py   # 期望:无输出
```

**先加两个判别位类型(纯类型,不改任何行为)** —— 测试文件要 import 它们;不先加,Step 2 的红全是 `ImportError`,
连「拿到的是真类」那一条都跑不到,说明不了任何行为。

`katrain/web/models.py` 第 1 行 `from typing import Any, Dict, List, Optional, Union` 改为 `from typing import Any, Dict, List, NamedTuple, Optional, Union`,文件末尾加:

```python


class GameEnd(NamedTuple):
    """这一局在哪一手、以什么结果结束(r1)。不随游标变 —— 翻手看棋不会让它消失。

    `game` / `node` 是运行时对象(`WebGame` / `GameNode`)。类型放 models 而不放 interface:
    `tests/web_ui/conftest.py` 把 `katrain.web.interface` 整个换成 MagicMock,定义在那里的类在 web_ui 测试里是假的。"""

    game: Any
    node: Any
    result: str


class EndgameConflict(Exception):
    """终局 / 提交判别没通过(r1)。`reason` ∈ already_ended | position_changed | stale_turn | not_your_turn
    | clock_not_expired | remote_ended。server 在 `create_app` 里统一映射成 409。"""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason
```

`tests/test_play_ai_endgame.py`:

```python
"""对弈·AI/升降级赛道:终局判定在**真** WebKaTrain 上的行为(superpowers/tracks/kiosk-go-play-ai)。

⚠️ 放在 tests/ 根目录是有意的:`tests/web_ui/conftest.py` 会把 `katrain.web.interface` 整个换成
MagicMock,放进那个目录就只是在测替身。第一条用例先证明拿到的是真类。
"""

# 主线程先把 kivymd 的窗口单例暖起来 —— 理由同 tests/test_local_play_setup.py 顶部那段。
import kivymd.app  # noqa: F401

import threading

import pytest

from katrain.core import ai
from katrain.core.constants import AI_DEFAULT, AI_LADDER, PLAYER_AI, PLAYER_HUMAN
from katrain.core.sgf_parser import Move
import katrain.web.interface as interface_module
from katrain.web.interface import WebKaTrain
from katrain.web.models import EndgameConflict, GameEnd


def _web_katrain():
    w = WebKaTrain(force_package_config=True, enable_engine=False)
    # force_package_config=True 时 save_config 会写回仓里的 katrain/config.json(update_config 末尾就调它)
    w.save_config = lambda *args, **kwargs: None
    # 裸 WebKaTrain 的 message_callback 是 None,而 `_do_update_state` 在终局手上无条件发 `game_report`
    # (interface.py `self.message_callback("game_report", …)` 没判空)。这是**夹具要补的,不是生产 bug**:
    # 生产会话一律由 `SessionManager.create_session` 装上回调(评审 r1 m5 实跑复现过 TypeError)。
    w.message_callback = lambda *args, **kwargs: None
    w.start()
    return w


def _seat(w, human_colors):
    """直接改座位,不走 `w("update_player")`:那条路会 update_state,轮到 AI 时起一条后台线程,
    活得比用例长(见 tests/test_guest_free_play.py `_seat_two_humans` 的说明)。"""
    for bw in ("B", "W"):
        if bw in human_colors:
            w.players_info[bw].update(player_type=PLAYER_HUMAN)
        else:
            w.players_info[bw].update(player_type=PLAYER_AI, player_subtype=AI_DEFAULT)


def test_this_module_runs_against_the_real_interface():
    assert isinstance(WebKaTrain, type)
    assert WebKaTrain.__module__ == "katrain.web.interface"


# ---------------------------------------------------------------- N21 认输方


def test_resigning_while_the_ai_is_thinking_is_a_loss_for_the_human():
    w = _web_katrain()
    _seat(w, human_colors={"B"})
    w.game.play(Move(coords=(3, 3), player="B"))  # 人刚落子,轮到 AI(白)在算
    assert w.game.current_node.next_player == "W"
    w._do_resign()
    assert w.game.current_node.end_state == "W+R"


def test_resigning_on_the_humans_own_turn_is_still_a_loss_for_the_human():
    w = _web_katrain()
    _seat(w, human_colors={"W"})
    w.game.play(Move(coords=(3, 3), player="B"))  # AI(黑)已落子,轮到人(白)
    w._do_resign()
    assert w.game.current_node.end_state == "B+R"


def test_two_humans_face_to_face_the_side_to_move_resigns():
    w = _web_katrain()
    _seat(w, human_colors={"B", "W"})
    w.game.play(Move(coords=(3, 3), player="B"))  # 轮到白
    w._do_resign()
    assert w.game.current_node.end_state == "B+R"


def test_an_explicit_loser_wins_over_the_seats():
    w = _web_katrain()
    _seat(w, human_colors={"B"})
    w.game.play(Move(coords=(3, 3), player="B"))
    w._do_resign("W")  # 多人局由 /api/resign 按请求者座位显式传
    assert w.game.current_node.end_state == "B+R"


# ---------------------------------------------------------------- r1 终局事实 + 对局提交锁(C3 / S1–S4 / S7 / S11)


class _Instant(ai.AIStrategy):
    """立即回白 15,15 的桩策略 —— 竞态用例只关心提交段,不关心算什么。"""

    def generate_move(self):
        return Move(coords=(15, 15), player="W"), "instant"


def _ai_parked_inside_its_commit(monkeypatch, w, mode):
    """起一条 AI 线程跑真 `generate_ai_move`,让它停在提交段里(`_game_already_ended` 那一次调用之后)。

    返回 `finish()`:放行、join,返回 `(generate_ai_move 的返回值, 线程里收集到的错误)`。
    停点用 `_game_already_ended` 包装而不是 sleep:提交段里复核终局就是调它,所以停住的那一刻 AI 线程**应当**
    正持有对局提交锁 —— 返回之前先用非阻塞 acquire 查这一点(评审 r1 m10:「锁里复核、放锁再落子」这种错实现
    只靠写入者抢不抢得到锁,只会偶发变红)。`game.play` 也包一层:落子那一刻锁不在 AI 线程手里就记一条错误。"""
    monkeypatch.setitem(ai.STRATEGY_REGISTRY, mode, _Instant)
    reached, release = threading.Event(), threading.Event()
    real_check = ai._game_already_ended
    errors, out = [], {}

    def parked_check(game, node=None):
        verdict = real_check(game, node)
        if threading.current_thread().name == "ai-commit" and not reached.is_set():
            reached.set()
            release.wait(2)
        return verdict

    monkeypatch.setattr(ai, "_game_already_ended", parked_check)
    real_play = w.game.play

    def play_checking_the_lock(*args, **kwargs):
        if threading.current_thread().name == "ai-commit" and not w.ai_ladder_commit_lock._is_owned():
            errors.append("AI 落子时没持有对局提交锁")
        return real_play(*args, **kwargs)

    monkeypatch.setattr(w.game, "play", play_checking_the_lock)

    def run():
        try:
            out["result"] = ai.generate_ai_move(w.game, mode, {})
        except Exception as e:  # noqa: BLE001 —— 线程里的异常要带回主线程断言
            errors.append(repr(e))

    thread = threading.Thread(target=run, name="ai-commit", daemon=True)
    thread.start()
    assert reached.wait(2), "AI 线程没走到提交段里的终局复核"
    got = w.ai_ladder_commit_lock.acquire(blocking=False)
    if got:
        w.ai_ladder_commit_lock.release()
    assert not got, "停在终局复核时 AI 线程没持有对局提交锁"

    def finish():
        release.set()
        thread.join(5)
        assert not thread.is_alive()
        return out.get("result"), errors

    return finish


@pytest.mark.parametrize("mode", ["test:instant", AI_LADDER])
@pytest.mark.parametrize("writer", ["resign", "commit", "nav"])
def test_a_terminal_write_or_navigation_racing_the_ai_commit_waits_for_it(monkeypatch, mode, writer):
    """C3 + S2:AI 的「复核 → 落子」与认输 / 终局写入 / 挪游标互斥。普通分支与升降级分支是同一段提交。"""
    w = _web_katrain()
    _seat(w, human_colors={"B"})
    w.game.play(Move(coords=(3, 3), player="B"))  # 轮到 AI(白)
    cn = w.game.current_node
    finish = _ai_parked_inside_its_commit(monkeypatch, w, mode)

    act = {
        "resign": w._do_resign,
        "commit": lambda: w._commit_end_state("W+R"),
        "nav": lambda: w.game.set_current_node(w.game.root),
    }[writer]
    done = threading.Event()
    threading.Thread(target=lambda: (act(), done.set()), daemon=True).start()
    assert not done.wait(0.1), "写入者没等 AI 的提交段 —— 它会在「复核」与「落子」之间改掉局面"

    result, errors = finish()
    assert done.wait(2)
    assert errors == []
    ai_node = result[1]
    assert ai_node.parent is cn
    if writer == "nav":
        assert w.game.current_node is w.game.root
    else:
        # 认输排在 AI 那一手之后,写在 AI 那一手上 —— 从前是认输先写在 cn 上、AI 随后落子把它「复活」
        assert w.game.terminal.node is ai_node is w.game.current_node
        assert w.game.end_result == "W+R"


def test_a_resign_during_generation_does_not_wait_for_the_engine(monkeypatch):
    """锁只包提交段,不包生成:AI 想几分钟,认输也要立刻生效。"""
    go, thinking = threading.Event(), threading.Event()

    class _Slow(ai.AIStrategy):
        def generate_move(self):
            thinking.set()
            go.wait(5)
            return Move(coords=(15, 15), player="W"), "slow"

    monkeypatch.setitem(ai.STRATEGY_REGISTRY, "test:slow", _Slow)
    w = _web_katrain()
    _seat(w, human_colors={"B"})
    w.game.play(Move(coords=(3, 3), player="B"))
    human_node = w.game.current_node
    out = {}
    worker = threading.Thread(
        target=lambda: out.update(result=ai.generate_ai_move(w.game, "test:slow", {})), daemon=True
    )
    worker.start()
    assert thinking.wait(2)

    resigned = threading.Event()
    threading.Thread(target=lambda: (w._do_resign(), resigned.set()), daemon=True).start()
    assert resigned.wait(1.0), "认输在等 AI 算完 —— 锁包住了整段生成"
    go.set()
    worker.join(5)

    assert out["result"] is None
    assert w.game.current_node is human_node and not human_node.children
    assert w.game.end_result == "W+R"


def test_an_ai_move_computed_for_a_position_that_was_undone_is_dropped(monkeypatch):
    """S2:AI 算的这段时间人悔了一手,算出来的着法属于一个已经不在盘上的局面。"""

    class _UndoneMeanwhile(ai.AIStrategy):
        def generate_move(self):
            self.game.undo(1)
            return Move(coords=(15, 15), player="W"), "stale"

    monkeypatch.setitem(ai.STRATEGY_REGISTRY, "test:undone", _UndoneMeanwhile)
    w = _web_katrain()
    _seat(w, human_colors={"B"})
    w.game.play(Move(coords=(3, 3), player="B"))
    human_node = w.game.current_node

    assert ai.generate_ai_move(w.game, "test:undone", {}) is None
    assert w.game.current_node is w.game.root
    assert w.game.root.children == [human_node]  # 根上没有多出一个白子分支


def test_a_position_that_has_ended_accepts_nothing_more(monkeypatch):
    """终局那一手上:带 guard 的落子 / 停一手、再认输、再写结果、AI 着法,一律被拒;结果不被改写。"""
    monkeypatch.setitem(ai.STRATEGY_REGISTRY, "test:instant", _Instant)
    w = _web_katrain()
    _seat(w, human_colors={"B", "W"})
    w._do_play((3, 3), guard=True)
    w._do_play((15, 15), guard=True)
    w._do_resign()  # 两人座位、轮到黑 ⇒ 黑认输
    ended = w.game.terminal
    assert isinstance(ended, GameEnd)
    assert ended.node is w.game.current_node and ended.result == "W+R"

    for attempt in (
        lambda: w._do_play((4, 4), guard=True),
        lambda: w._do_play(None, guard=True),
        w._do_resign,
        lambda: w._commit_end_state("B+1.0"),
    ):
        with pytest.raises(EndgameConflict, match="already_ended"):
            attempt()
    assert ai.generate_ai_move(w.game, "test:instant", {}) is None
    assert ended.node.end_state == "W+R" and not ended.node.children
    assert w.get_state()["terminal_result"] == "W+R"


def test_stepping_back_keeps_the_game_ended_but_an_earlier_position_can_branch_off():
    """S1 + 评审 r1 M2:终局事实挂在对局上,翻手看棋不让它消失(kiosk 靠 `terminal_result` 冻住);
    冻结只到「终局那一手和它之后」—— galaxy / ZenMode 悔棋后在更早的局面另开分支,服务端照旧接受,
    那条分支自己还能再结束一次(单机账只落一次,由 `_recorded` 管,与今天相同)。"""
    w = _web_katrain()
    _seat(w, human_colors={"B", "W"})
    w._do_play((3, 3), guard=True)
    w._do_play((15, 15), guard=True)
    w._do_resign()
    ended = w.game.terminal

    w.game.undo(1)
    state = w.get_state()
    assert state["end_result"] is None
    assert state["terminal_result"] == "W+R"

    w._do_play((4, 4), guard=True)  # 在白那一手之前另开分支
    branch = w.game.current_node
    assert branch.parent is ended.node.parent and w.game.terminal is ended
    w._commit_end_state("B+3.5")
    assert w.game.terminal.node is branch and w.game.terminal.result == "B+3.5"
    assert ended.node.end_state == "W+R"


def test_two_passes_end_the_game_even_before_a_score_is_known(monkeypatch):
    """S3:双停第二手落下就记终局事实(结果待补分);之后的停一手与 AI 着法都被挡住。"""
    monkeypatch.setitem(ai.STRATEGY_REGISTRY, "test:instant", _Instant)
    w = _web_katrain()
    _seat(w, human_colors={"B", "W"})
    w._do_play(None, guard=True)
    w._do_play(None, guard=True)
    terminal = w.game.terminal
    assert terminal is not None and terminal.node is w.game.current_node
    assert terminal.node.end_state is None
    with pytest.raises(EndgameConflict, match="already_ended"):
        w._do_play(None, guard=True)
    assert ai.generate_ai_move(w.game, "test:instant", {}) is None


def test_moves_without_the_guard_neither_record_nor_freeze_a_two_pass_end():
    """评审 r1 m9:研究会话与跨平台网关(`_local_play`、`_on_opponent_move`)不带 guard。
    OGS 双停后进点目阶段还能恢复对局,恢复后的落子必须照常落进本地棋盘 —— 双停不记终局事实、也不冻结。"""
    w = _web_katrain()
    _seat(w, human_colors={"B", "W"})
    w._do_play(None)
    w._do_play(None)
    assert w.game.terminal is None
    w._do_play((3, 3))
    assert w.game.current_node.move.coords == (3, 3)


def test_a_ranked_game_ended_on_another_device_takes_nothing_locally():
    """S11:远端终局标记与本地写入同一把锁;标记之后本地既不写结果,也不接受带 guard 的落子。"""
    w = _web_katrain()
    _seat(w, human_colors={"B", "W"})
    w._do_play((3, 3), guard=True)
    w.ai_ladder_remote_ended = True
    with pytest.raises(EndgameConflict, match="remote_ended"):
        w._commit_end_state("W+R")
    with pytest.raises(EndgameConflict, match="remote_ended"):
        w._do_play((4, 4), guard=True)
    assert w.game.terminal is None and w.game.current_node.move.coords == (3, 3)


def test_a_human_move_on_the_ai_seat_is_refused():
    """S4(一半):人机局轮到 AI 时,人发来的落子 / 停一手从前会被记成 AI 的颜色。"""
    w = _web_katrain()
    _seat(w, human_colors={"B"})
    w._do_play((3, 3), guard=True)
    for coords in ((4, 4), None):
        with pytest.raises(EndgameConflict, match="not_your_turn"):
            w._do_play(coords, guard=True)
    assert w.game.current_node.move.coords == (3, 3)


def test_a_vision_stone_after_the_game_ended_is_not_played():
    """S7:视觉非平台分支带 guard + 期望颜色。被拒时照「不轮到」那一支重新布防,返回 0.5 秒节流。"""
    import asyncio
    import logging
    from types import SimpleNamespace

    from katrain.vision.ipc import ConfirmedMove
    from katrain.web.server import _handle_confirmed_move

    w = _web_katrain()
    _seat(w, human_colors={"B", "W"})
    w._do_play((3, 3), guard=True)
    w._do_resign()  # 轮到白 ⇒ 白认输,B+R
    ended_node = w.game.current_node
    session = SimpleNamespace(katrain=w, last_state=w.get_state(), lock=threading.Lock())

    class _Manager:
        def get_session(self, session_id):
            return session

    class _Vision:
        def __init__(self):
            self.expected_pushes = []

        def set_expected_from_stones(self, stones, board_size=19):
            self.expected_pushes.append(stones)

    vision = _Vision()
    app = SimpleNamespace(state=SimpleNamespace(session_manager=_Manager()))
    white_stone = ConfirmedMove(col=15, row=15, color=2)  # 颜色 = 帧上轮到的一方,过得了 R1.3 的轮次检查

    delay = asyncio.run(_handle_confirmed_move(app, vision, "s", white_stone, logging.getLogger("play-ai-test")))

    assert delay == 0.5
    assert w.game.current_node is ended_node and not ended_node.children
    assert vision.expected_pushes


def test_two_threads_settling_the_clock_do_not_count_the_same_seconds_twice(monkeypatch):
    """W11:`update_timer` 读 `last_timer_update` → 记 dt → 写回,不互斥时两个并发结算读到同一个基准、把同一段 dt
    记两遍 —— 超时由服务端时钟核实以后(Task 6),这会直接变成「提前判负」。假 `time` 让第一个结算者停在读时钟那一刻,
    第二个结算者 0.2 秒内不许读到时钟(没有锁就会立刻读到)。"""
    # interface_module 在模块收集时 import，避免 web_ui/conftest 随后换掉真模块。
    w = _web_katrain()
    real_time = interface_module.time
    first_reading, release, second_read = threading.Event(), threading.Event(), threading.Event()

    class _Clock:
        def time(self):
            name = threading.current_thread().name
            if name == "settle-a" and not first_reading.is_set():
                first_reading.set()
                release.wait(2)
            elif name == "settle-b":
                second_read.set()
            return real_time.time()

        def monotonic(self):
            return real_time.monotonic()

        def sleep(self, seconds):
            real_time.sleep(seconds)

    monkeypatch.setattr(interface_module, "time", _Clock())
    first = threading.Thread(target=w.update_timer, name="settle-a", daemon=True)
    first.start()
    assert first_reading.wait(2)
    second = threading.Thread(target=w.update_timer, name="settle-b", daemon=True)
    second.start()
    assert not second_read.wait(0.2), "第二个结算没等第一个 —— 两边读到同一个 last_timer_update"
    release.set()
    first.join(2)
    second.join(2)
    assert second_read.is_set()


@pytest.mark.parametrize("notice", ["too_fast", "illegal_move"])
def test_play_notices_are_emitted_after_releasing_the_commit_lock(monkeypatch, notice):
    """UI callbacks can broadcast; they must never run inside the commit lock."""
    w = _web_katrain()
    _seat(w, human_colors={"B", "W"})
    if notice == "too_fast":
        w.timer_paused = False
        w.active_game_timer.update(main_time=0, minimal_use=100)
    else:
        w._do_play((3, 3), guard=True)
    before = w.game.current_node
    emitted, lock_available = [], []

    def capture(message, *args, **kwargs):
        emitted.append(message)

        def probe():
            acquired = w.ai_ladder_commit_lock.acquire(blocking=False)
            lock_available.append(acquired)
            if acquired:
                w.ai_ladder_commit_lock.release()

        worker = threading.Thread(target=probe)
        worker.start()
        worker.join(2)
        assert not worker.is_alive()

    monkeypatch.setattr(w, "log", capture)
    w._do_play((3, 3), guard=True)

    assert w.game.current_node is before
    assert len(emitted) == 1
    assert lock_available == [True], "状态/错误回调正在持有提交锁时发出"
    if notice == "illegal_move":
        assert "Illegal Move at (3, 3)" in emitted[0]
```

`tests/core/test_ai_commit_after_end.py`:

```python
"""N21:对局一旦有了终局结果,后台还在算的 AI 着法不许再落到盘上。

人刚落子、AI 在算时按认输(或超时),结果写在 AI 开算时的那个节点上;从前 AI 算完照常 `game.play(move)`,
新节点没有终局标记,盘面回到对局中。

这里用替身对局,**只证宽窗口**(生成期间写上的结果在提交前被看见;替身没有 `ended_at`,走 `end_state` 回退)。
窄窗口 —— 复核与落子之间的交错、复核是否在对局提交锁里 —— 在 tests/test_play_ai_endgame.py 用真 WebKaTrain 证。
"""

from katrain.core import ai
from katrain.core.constants import AI_LADDER
from katrain.core.sgf_parser import Move


class _Node:
    def __init__(self):
        self.player, self.next_player = "B", "W"
        self.end_state = None
        self.depth = 0


class _Katrain:
    ai_ladder_remote_ended = False
    ai_ladder_commit_lock = None

    def log(self, *a, **k):
        pass

    def config(self, *a, **k):
        return {}


class _Game:
    def __init__(self):
        self.board_size = (19, 19)
        self.current_node = _Node()
        self.katrain = _Katrain()
        self.played = []

    def play(self, move):
        self.played.append(move)
        self.current_node = _Node()
        return self.current_node


def _ends_mid_generation(end_state):
    class _EndsMidGeneration(ai.AIStrategy):
        def generate_move(self):
            self.game.current_node.end_state = end_state  # 人在这段时间里认输/超时了
            return Move(coords=(3, 3), player="W"), "thought"

    return _EndsMidGeneration


def test_a_move_finished_after_the_game_ended_is_not_played(monkeypatch):
    monkeypatch.setitem(ai.STRATEGY_REGISTRY, "test:ends-mid-generation", _ends_mid_generation("W+R"))
    game = _Game()
    assert ai.generate_ai_move(game, "test:ends-mid-generation", {}) is None
    assert game.played == []
    assert game.current_node.end_state == "W+R"


def test_the_ladder_commit_path_refuses_too(monkeypatch):
    monkeypatch.setitem(ai.STRATEGY_REGISTRY, AI_LADDER, _ends_mid_generation("B+R"))
    game = _Game()
    assert ai.generate_ai_move(game, AI_LADDER, {}) is None
    assert game.played == []


def test_an_ordinary_move_is_still_played(monkeypatch):
    """正对照:没有终局时照常落子 —— 否则上面两条的 None 可能只是这条路本来就不通。"""

    class _Plain(ai.AIStrategy):
        def generate_move(self):
            return Move(coords=(3, 3), player="W"), "thought"

    monkeypatch.setitem(ai.STRATEGY_REGISTRY, "test:plain", _Plain)
    game = _Game()
    assert ai.generate_ai_move(game, "test:plain", {}) is not None
    assert len(game.played) == 1
```

`tests/web_ui/test_play_ai_endgame_api.py`:

```python
"""对弈·AI/升降级赛道的 HTTP 端点测试(superpowers/tracks/kiosk-go-play-ai)。

会话一律手工注入、katrain 是 MagicMock(`tests/web_ui/conftest.py` 把 interface 换成了替身):
这里证的是**端点把什么交给了 katrain、按什么顺序**;katrain 自己怎么判在 tests/test_play_ai_endgame.py 用真类证。
"""

import threading
import uuid
from unittest.mock import MagicMock

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from katrain.web.models import EndgameConflict
from katrain.web.server import create_app


@pytest.fixture
def client(isolated_session_factory):
    app = create_app(enable_engine=False)
    app.state.session_factory = isolated_session_factory  # 必须在 TestClient 之前:lifespan 用它重建全部 repo
    with TestClient(app) as c:
        yield c
        for s in list(c.app.state.session_manager._sessions.values()):
            c.app.state.session_manager._sessions.pop(s.session_id, None)


def _make_user(client, name: str):
    from passlib.context import CryptContext

    unique = f"{name}-{uuid.uuid4().hex[:8]}"
    hashed = CryptContext(schemes=["bcrypt"], deprecated="auto").hash("password")
    user = client.app.state.user_repo.create_user(unique, hashed)
    return user["id"], unique


def _login(client, username: str) -> dict:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": "password"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _inject_session(client, *, user_id=None, player_b_id=None, player_w_id=None, game_type="free"):
    session = MagicMock()
    session.session_id = uuid.uuid4().hex
    session.user_id = user_id
    session.player_b_id = player_b_id
    session.player_w_id = player_w_id
    session.mode = "play"
    session.game_type = game_type
    session.lock = threading.Lock()
    session.sockets = set()
    session.last_access = 0.0
    session.last_state = {"end_result": None}
    session.pending_count_request = None
    session.pending_count_timestamp = None
    session.game_ended = False
    session._recorded = False

    katrain = MagicMock()
    katrain.game_type = game_type
    katrain.get_sgf.return_value = "(;FF[4]SZ[19];B[pd])"
    katrain.get_state.return_value = {"end_result": None, "history": []}
    katrain.game.end_result = None
    session.katrain = katrain
    client.app.state.session_manager._sessions[session.session_id] = session
    return session


# ---------------------------------------------------------------- N21


def test_lobby_resign_is_decided_by_the_seat_of_the_player_who_pressed_it(client):
    black_id, _ = _make_user(client, "alice")
    white_id, white_name = _make_user(client, "bob")
    session = _inject_session(client, user_id=black_id, player_b_id=black_id, player_w_id=white_id)

    resp = client.post("/api/resign", json={"session_id": session.session_id}, headers=_login(client, white_name))

    assert resp.status_code == 200, resp.text
    session.katrain.assert_any_call("resign", "W")


def test_single_player_resign_leaves_the_loser_to_the_seats(client):
    """正对照:单机局不传认输方,交给 `_do_resign` 从座位推。"""
    session = _inject_session(client)

    resp = client.post("/api/resign", json={"session_id": session.session_id})

    assert resp.status_code == 200, resp.text
    session.katrain.assert_any_call("resign")


# ---------------------------------------------------------------- r1 端点接线(真判定在 tests/test_play_ai_endgame.py)


def test_a_move_refused_by_the_runtime_is_a_409_not_a_500(client):
    session = _inject_session(client)

    def refuse(action, *args, **kwargs):
        if action == "play":
            raise EndgameConflict("already_ended")

    session.katrain.side_effect = refuse

    resp = client.post("/api/move", json={"session_id": session.session_id, "coords": [3, 3]})

    assert resp.status_code == 409, resp.text
    assert "already over" in resp.json()["detail"]
    session.katrain.assert_any_call("play", (3, 3), guard=True)


class _PlatformGateway:
    """跨平台网关替身:`resign` 远端成功后走本地 `_local_resign`(即 `session.katrain("resign")`)。
    `local_conflict=True` 模拟本地这一局早已结束 —— 远端认输成功,本地写入撞上 `already_ended`。"""

    def __init__(self, session, local_conflict):
        self.session = session
        self.local_conflict = local_conflict
        self.resigned = []

    def is_platform_game(self, session_id):
        return session_id == self.session.session_id

    async def resign(self, session_id, user_id):
        self.resigned.append((session_id, user_id))
        if self.local_conflict:
            raise EndgameConflict("already_ended")
        self.session.katrain("resign")
        return {"status": "ok"}


@pytest.mark.parametrize("where", ["lobby", "platform"])
@pytest.mark.parametrize("already_ended", [False, True])
def test_resign_writes_one_ledger_row_or_none(client, monkeypatch, where, already_ended):
    """评审 r1 M4 + S8:认输真的写出了终局 → 多人局恰好记一行、广播一次 `game_end`;撞上已结束的局 → 200 空操作,
    不记、不广播。平台局(OGS / 星阵)也走多人局落账那一行 —— `wrote` 若只在非平台分支里赋值,这里就是 500。"""
    me, my_name = _make_user(client, "resigner")
    if where == "lobby":
        other, _ = _make_user(client, "opponent")
        session = _inject_session(client, user_id=me, player_b_id=me, player_w_id=other)
        if already_ended:

            def refuse(action, *args, **kwargs):
                if action == "resign":
                    raise EndgameConflict("already_ended")

            session.katrain.side_effect = refuse
    else:
        session = _inject_session(client, user_id=me, player_b_id=me, player_w_id=-1)
        client.app.state.platform_gateway = _PlatformGateway(session, local_conflict=already_ended)
    client.app.state.game_repo = MagicMock()
    sent = []
    monkeypatch.setattr(
        client.app.state.session_manager, "_schedule_broadcast", lambda s, payload: sent.append(payload)
    )

    resp = client.post("/api/resign", json={"session_id": session.session_id}, headers=_login(client, my_name))

    assert resp.status_code == 200, resp.text
    expected_rows = 0 if already_ended else 1
    assert client.app.state.game_repo.record_multiplayer_game.call_count == expected_rows
    assert [p["type"] for p in sent if p.get("type") == "game_end"] == ["game_end"] * expected_rows


def test_count_uses_the_same_atomic_result_writer(client):
    """Count must not bypass the result lock used by resignation and AI commits."""
    session = _inject_session(client)
    session.katrain.config.return_value = 0
    session.katrain.game.current_node.score = 3.5
    session.katrain._commit_end_state.side_effect = EndgameConflict("already_ended")

    resp = client.post("/api/count/request", json={"session_id": session.session_id})

    assert resp.status_code == 409, resp.text
    session.katrain._commit_end_state.assert_called_once()
    assert session.katrain._commit_end_state.call_args.args == ("B+3.5",)


@pytest.mark.parametrize("action", ["resign", "timeout"])
def test_already_ended_single_player_request_does_not_retry_recording(client, action):
    """An already-ended response is a no-op even if a prior save has not completed."""
    me, my_name = _make_user(client, "already-ended-solo")
    session = _inject_session(client, user_id=me)
    session.katrain.game.end_result = "W+R"
    session.katrain.get_state.return_value = {"end_result": "W+R", "history": []}

    def refuse(received_action, *args, **kwargs):
        if received_action == action:
            raise EndgameConflict("already_ended")

    session.katrain.side_effect = refuse
    resp = client.post(f"/api/{action}", json={"session_id": session.session_id}, headers=_login(client, my_name))

    assert resp.status_code == 200, resp.text
    # Recording always starts by obtaining this game's SGF; no-op requests must not enter it.
    session.katrain.get_sgf.assert_not_called()
    assert session._recorded is False
```

- [x] **Step 2: 跑测试确认失败**

Run(两条命令,理由见 Global Constraints「不许同跑」):
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
CI=true uv run pytest --continue-on-collection-errors tests/test_play_ai_endgame.py tests/core/test_ai_commit_after_end.py -q
CI=true uv run pytest --continue-on-collection-errors tests/web_ui/test_play_ai_endgame_api.py -q
```
Expected(原 5 条 + r1 新增,各自红的理由):
- `test_resigning_while_the_ai_is_thinking…`(得到 `B+R`)、`test_an_explicit_loser…`(`TypeError: _do_resign() takes 1 positional argument`)、
  `tests/core/test_ai_commit_after_end.py` 两条「不落子」用例(`played` 非空)、`test_lobby_resign…`(实际调用是 `("resign",)`)。
- `test_a_terminal_write_or_navigation_racing_the_ai_commit_waits_for_it` 6 格:`AttributeError: <module 'katrain.core.ai'> has no attribute '_game_already_ended'`(monkeypatch 找不到停点)。
- `test_a_resign_during_generation_does_not_wait_for_the_engine`:`out["result"]` 不是 None(AI 落子把认输「复活」)。
- `test_an_ai_move_computed_for_a_position_that_was_undone_is_dropped`:返回非 None,根上多出一个白子分支。
- `test_a_position_that_has_ended_accepts_nothing_more`、`test_stepping_back_…`、`test_two_passes_…`、`test_a_ranked_game_ended_…`、
  `test_a_human_move_on_the_ai_seat_is_refused`、`test_a_vision_stone_after_the_game_ended_is_not_played`:`TypeError: _do_play() got an unexpected keyword argument 'guard'`。
- `test_moves_without_the_guard_neither_record_nor_freeze_a_two_pass_end`:`AttributeError: 'WebGame' object has no attribute 'terminal'`。
- `test_two_threads_settling_the_clock_do_not_count_the_same_seconds_twice`:「第二个结算没等第一个」(`update_timer` 无锁)。
- web_ui:`test_a_move_refused_by_the_runtime_is_a_409_not_a_500`(没有处理器,`EndgameConflict` 直接抛出到 TestClient);
  `test_resign_writes_one_ledger_row_or_none` 的 `already_ended=True` 两格(同上,异常直接抛出)。

其余 PASS:`test_this_module_runs_against_the_real_interface`、`test_resigning_on_the_humans_own_turn…` 与 `test_two_humans…`(旧代码在这两种情形下碰巧对)、
两条正对照、`test_resign_writes_one_ledger_row_or_none` 的 `already_ended=False` 两格 —— 这两格是改动后的回归护栏:`wrote` 若只在非平台分支里赋值,`platform` 那格会变 500(评审 r1 M4)。
**若 `test_this_module_runs_against_the_real_interface` 红,停下来** —— 说明拿到的是 conftest 的替身,这个文件的其余结论都不作数。

- [x] **Step 3: 实现后端**

(`katrain/web/models.py` 的两个类型在 Step 1 已加。)

**① `katrain/web/interface.py`**

import 区 `from katrain.gui.theme import Theme` 之后加:

```python
from katrain.web.models import EndgameConflict, GameEnd
```

`class WebGame(Game):`(`:92-120`)整段替换为:

```python
class WebGame(Game):
    #: r1:这一局在哪一手、以什么结果结束(`GameEnd`),不随游标变。只有两处写它,都在对局提交锁里:
    #: `WebKaTrain._commit_end_state` 与 `record_two_pass_end`。新开局 / 载入 SGF / `game/setup` 都会新建 WebGame,
    #: 事实自然清掉;载入棋谱再翻到双停终点不经过这两处,所以不会被当成「在这里下完的一局」。
    terminal: Optional[GameEnd] = None

    def ended_at(self, node) -> bool:
        """`node` 所在的局面线是否已经结束过:终局那一手就是 `node` 或它的祖先。

        翻回终局之前另开分支**不算** —— galaxy / ZenMode「悔棋后接着下」照旧可用(评审 r1 M2)。
        kiosk 要的「这一局结束了」认 `get_state()["terminal_result"]`,不认这里。"""
        terminal = self.terminal
        cursor = node
        while terminal is not None and cursor is not None:
            if cursor is terminal.node:
                return True
            cursor = cursor.parent
        return False

    def record_two_pass_end(self, node):
        """双停第二手落下时记终局事实;结果先是「终局」(`end_result`),分数由收尾补(Task 5)。

        **只由本地对局路径调**:`WebKaTrain._do_play(guard=True)` 与 `core/ai.py` 的 AI 提交段。`play` 本身不记 ——
        研究会话与跨平台网关的落子不带 guard,OGS 双停后进点目阶段还能恢复对局,记了就会把它冻住(评审 r1 m9)。"""
        with self.katrain.ai_ladder_commit_lock:
            if (
                node is self.current_node
                and node.is_pass
                and node.parent is not None
                and node.parent.is_pass
                and self.katrain.play_analyze_mode == MODE_PLAY
                and not node.end_state
                and not self.ended_at(node)
            ):
                self.terminal = GameEnd(self, node, self.end_result)

    def set_current_node(self, node):
        # r1:挪游标进对局提交锁。AI 在锁里核完「当前手仍是开算那一手」之后、`Game.play` 读 `current_node`
        # 之前,一次导航若能插进来,着法会落到别的节点上(S2)。`ai_ladder_commit_lock` 在
        # `WebKaTrain.__init__` 调 `super().__init__` 之前就赋值了(`:144`),构造期间调到这里锁也已经在。
        with self.katrain.ai_ladder_commit_lock:
            # Update timer for the *previous* node/player before switching
            if self.katrain and hasattr(self.katrain, "update_timer"):
                self.katrain.update_timer()

            blocked = self.insert_mode
            if not blocked:
                super().set_current_node(node)

            # Reset timer baseline for the *new* node/player
            if self.katrain and hasattr(self.katrain, "last_timer_update"):
                self.katrain.last_timer_update = time.time()
        if blocked:
            self.katrain.controls.set_status(i18n._("finish inserting before navigating"), STATUS_ERROR)

    def play(self, move, ignore_ko=False, analyze=True):
        # r1:整段进对局提交锁(RLock 可重入:`_do_play` 与 AI 提交段调到这里时已经拿着它)。
        with self.katrain.ai_ladder_commit_lock:
            # Update timer for the *previous* node/player before switching
            if self.katrain and hasattr(self.katrain, "update_timer"):
                self.katrain.update_timer()

            # R1: board-mode play suppresses the per-node auto eval (genmove still runs).
            if analyze and self.katrain and getattr(self.katrain, "should_suppress_auto_eval", None):
                if self.katrain.should_suppress_auto_eval():
                    analyze = False

            node = super().play(move, ignore_ko=ignore_ko, analyze=analyze)

            # Reset timer baseline for the *new* node/player
            if self.katrain and hasattr(self.katrain, "last_timer_update"):
                self.katrain.last_timer_update = time.time()

            return node
```

`get_state` 里 `"end_result": self.game.end_result,` 之后加:

```python
            # r1 S1:「这一局结束过没有」—— 对局级的终局事实,翻手看棋不会让它变回 None(`end_result` 读的是游标)。
            # kiosk 据此冻结对局屏;galaxy 不读它。
            "terminal_result": self.game.terminal.result if self.game.terminal is not None else None,
```

`_do_update_state` 里触发 AI 的那组条件(**不是**上面 `teaching_undo` 那组,那组也有 `not self.game.end_result`)

```python
            if (
                next_player.ai
                and not cn.children
                and not self.game.end_result
                and not (teaching_undo and cn.auto_undo is None)
                and not self._ladder_stall_blocks_retrigger()
            ):
```

改为

```python
            if (
                next_player.ai
                and not cn.children
                and not self.game.end_result
                # r1:局面线已经结束过就不起算 —— 否则「AI 提交被拒 → finally 里 update_state → 再起算」会空转。
                and not self.game.ended_at(cn)
                and not (teaching_undo and cn.auto_undo is None)
                and not self._ladder_stall_blocks_retrigger()
            ):
```

`update_timer`(`:884-913`)整段替换为:

```python
    def update_timer(self):
        # r1:整段进对局提交锁。`get_state` 会被广播线程、引擎回调线程、请求线程并发调用;两次结算读到同一个
        # `last_timer_update` 会把同一段 dt 记两遍 —— 超时由服务端时钟核实(Task 6)以后,这就是「提前判负」。
        # RLock:`play` / `set_current_node` / `_do_play` 里再调它可以重入。
        with self.ai_ladder_commit_lock:
            now = time.time()
            dt = now - self.last_timer_update
            self.last_timer_update = now

            if self.timer_paused or self.play_analyze_mode != MODE_PLAY or not self.game:
                return

            cn = self.game.current_node
            if cn.children:  # Only count time for the active leaf node
                return

            main_time = self.active_game_timer.get("main_time", 0) * 60
            byo_len = max(1, self.active_game_timer.get("byo_length", 30))
            byo_num = max(1, self.active_game_timer.get("byo_periods", 5))

            current_player = self.next_player_info.player
            main_time_used = self.main_time_used_by_player.get(current_player, 0)
            main_time_left = main_time - main_time_used

            if main_time_left > 0:
                used_main = min(dt, main_time_left)
                self.main_time_used_by_player[current_player] = main_time_used + used_main
                dt -= used_main

            if dt > 0:
                cn.time_used += dt
                while cn.time_used > byo_len and self.next_player_info.periods_used < byo_num:
                    cn.time_used -= byo_len
                    self.next_player_info.periods_used += 1
```

`_do_play`(`:1191-1223`)整段替换为:

```python
    def _do_play(self, coords, guard=False, expected_player=None):
        """落一手。

        `guard=True` 是**本地对局路径**(`/api/move` 的非研究会话、视觉的两支):这一手所在的局面线已经结束过、
        升降级已在别的设备上结束、或者人机局轮到 AI,就拒绝;落下的是双停第二手时记终局事实。
        `expected_player` 是调用方以为轮到的那一方(视觉按棋子颜色传),与服务端不符就拒。
        研究会话与跨平台网关(`_local_play`、`_on_opponent_move`)不带 guard:打谱或照镜像落子,双停后还可能恢复对局。
        判别与落子在对局提交锁里一次做完 —— 否则 AI 线程可以在「查完」与「落下」之间提交(C3 / S4)。
        冲突抛 `EndgameConflict`;落子音在锁外发。"""
        from katrain.core.game import IllegalMoveException, Move
        from katrain.core.constants import STATUS_TEACHING

        played = False
        status_message = error_message = None
        with self.ai_ladder_commit_lock:
            self.update_timer()
            game = self.game
            current_node = game and self.game.current_node
            if guard and current_node:
                if getattr(self, "ai_ladder_remote_ended", False):
                    raise EndgameConflict("remote_ended")
                if current_node.end_state or game.ended_at(current_node):
                    raise EndgameConflict("already_ended")
                if self.play_analyze_mode == MODE_PLAY and self.next_player_info.ai:
                    raise EndgameConflict("not_your_turn")
            if expected_player is not None and current_node and current_node.next_player != expected_player:
                raise EndgameConflict("stale_turn")
            if (
                current_node
                and not current_node.children
                and not self.next_player_info.ai
                and not self.timer_paused
                and self.play_analyze_mode == MODE_PLAY
                and self.active_game_timer.get("main_time", 0) * 60
                - self.main_time_used_by_player.get(self.next_player_info.player, 0)
                <= 0
                and current_node.time_used < self.active_game_timer.get("minimal_use", 0)
            ):
                status_message = i18n._("move too fast").format(num=self.active_game_timer.get("minimal_use", 0))
            else:
                try:
                    node = self.game.play(Move(coords, player=self.next_player_info.player))
                    played = True
                    if guard:
                        self.game.record_two_pass_end(node)
                except IllegalMoveException as e:
                    # 坐标必须记 —— 2026-08-25 查「自由对弈无法落子」时，日志里 4 条
                    # `Illegal Move: Space occupied` 拿不出**点的是哪一路**，只能靠时间戳
                    # 间隔（5 秒、3 秒）反推「是人在反复点」。少这一个字段，定位多花了几小时。
                    error_message = f"Illegal Move at {coords}: {e}"
                finally:
                    self.last_timer_update = time.time()
        # Status and log callbacks may broadcast; emit them after releasing the commit lock.
        if status_message is not None:
            self.controls.set_status(status_message, STATUS_TEACHING)
        if error_message is not None:
            self.log(error_message, OUTPUT_ERROR)
        if played:
            self.play_stone_sound()
```

`_do_resign` / `_do_timeout`(`:1464-1469`)整段替换为:

```python
    def _commit_end_state(self, result, *, node=None, fill_pending=False):
        """终局结果的**唯一**写入口(r1)—— 认输、超时、数子、双停补分、升降级认输、AI 认输都从这里写。

        在对局提交锁里一次做完「判 → 写」,先写者胜:
          · 普通写:`node` 缺省为当前手。它的局面线已经结束过、或节点上已有结果 → `already_ended`;
            它已不是当前手(等分析的这几秒里人悔了棋)→ `position_changed`。
          · 补分(`fill_pending=True`):只给「双停、还没有结果」的那一手写上数出来的分数 —— `node` 必须仍是这一局的
            终局手(否则 `position_changed`)且节点上还没有结果(否则 `already_ended`)。**不要求它是当前手**:
            补分期间人点了「上一手」,结果照样写在终局那一手上,游标留在人挪到的地方(C4)。
        局面线之外(翻回终局之前另开的分支)可以再结束一次,`game.terminal` 换成新分支的终局(评审 r1 M2)。
        升降级已在别的设备上结束 → `remote_ended`(与 `mark_ai_ladder_remote_terminal` 同一把锁,S11)。
        持锁时不 await、不做 IO、不调 `update_state`(见 Global Constraints「对局提交锁」)。"""
        with self.ai_ladder_commit_lock:
            if getattr(self, "ai_ladder_remote_ended", False):
                raise EndgameConflict("remote_ended")
            game = self.game
            target = game.current_node if node is None else node
            if fill_pending:
                terminal = game.terminal
                if terminal is None or terminal.node is not target:
                    raise EndgameConflict("position_changed")
                if target.end_state:
                    raise EndgameConflict("already_ended")
            else:
                if target.end_state or game.ended_at(target):
                    raise EndgameConflict("already_ended")
                if target is not game.current_node:
                    raise EndgameConflict("position_changed")
            target.end_state = result
            game.game_result = result  # 只写不读(grep 核过),与数子 / 升降级认输原写法一致
            game.terminal = GameEnd(game, target, result)
            return game.terminal

    def _do_resign(self, loser: Optional[str] = None):
        """认输。`loser` 是认输的那一方(`"B"`/`"W"`);不给时从这一局的座位推。

        从前写的是 `current_node.player + "+R"` —— 胜方 = **最后落子的一方**。人刚落子、AI 还在算时按认输,
        最后落子的正是人自己,于是这盘被记成人赢(N21)。判据改成「谁在认输」,不是「轮到谁」:
          · 恰好一方是 `player:human`(人机局):认输的一定是人;
          · 两方都是人(本地对局)或都不是(多人局的座位是裸 `human` 字面量):退回「轮到落子的一方」——
            多人局由 `/api/resign` 按请求者座位显式传 `loser`,不走这条回退。
        星阵(跨平台)局认输走平台网关,网关落回本地时同样经这里。
        推算与写入在同一次持锁里:这一局已经结束过就抛 `already_ended`,由 server 当成 200 空操作。
        """
        with self.ai_ladder_commit_lock:
            if loser not in ("B", "W"):
                humans = [bw for bw, info in self.players_info.items() if info.human]
                loser = humans[0] if len(humans) == 1 else self.game.current_node.next_player
            winner = "W" if loser == "B" else "B"
            return self._commit_end_state(f"{winner}+R")

    def _do_timeout(self):
        """End game due to timeout - current player loses on time"""
        # r1:语义与从前相同,只多了「已经结束过就拒」。带轮次绑定的版本在 Task 6。
        with self.ai_ladder_commit_lock:
            return self._commit_end_state(f"{self.game.current_node.player}+T")
```

**② `katrain/core/ai.py`**

在 `_ladder_remote_terminal`(`:1849-1850`)之后加:

```python
def _game_already_ended(game, node=None) -> bool:
    """`node`(缺省为当前手)所在的局面线是否已经结束过。

    生成一手可能要几秒到几分钟;这段时间里人按了认输,再把算出来的着法落下去会生出一个没有终局标记的
    新节点,盘面回到对局中(N21)。web 对局(`WebGame`)认对局级的终局事实 `ended_at`:翻手看棋不会让它消失,
    双停在补上分数之前也算结束;桌面版与测试替身没有它,退回读节点上的 `end_state`。
    **只在提交段里、对局提交锁内调**(tests/test_play_ai_endgame.py 的竞态用例把停点设在这里)。
    """
    node = getattr(game, "current_node", None) if node is None else node
    ended_at = getattr(game, "ended_at", None)
    if callable(ended_at) and ended_at(node) is True:
        return True
    return bool(getattr(node, "end_state", None))
```

`generate_ai_move`(`:1946-1986`)整段替换为:

```python
def generate_ai_move(game: Game, ai_mode: str, ai_settings: Dict) -> Optional[Tuple[Move, GameNode]]:
    """
    Generate a move using the selected AI strategy.

    Returns:
        Tuple of (Move, GameNode) if a move was played, or None if AI resigned — or if the position the move
        was computed for is gone or has ended by the time it would be committed (see the commit section).
    """
    game.katrain.log(f"Generate AI move called with mode: {ai_mode}", OUTPUT_DEBUG)
    # r1:开算时的那一手。签名不变(tests/web_ui/test_ladder_injection.py 的替身写死了 (game, mode, settings)),
    # 所以在入口自己捕获;策略本来就替它算(`AIStrategy.cn`)。
    cn = game.current_node

    # Check resignation conditions before generating a move
    resignation_settings = game.katrain.config("ai/resignation") or {}
    if ai_mode != AI_LADDER and should_ai_resign(game, resignation_settings):  # ladder never global-resigns
        ai_player = cn.next_player
        opponent = "W" if ai_player == "B" else "B"
        # end_state format: "{winner}+R" (e.g., "W+R" means White wins by resignation)
        result = f"{opponent}+R"
        commit_end_state = getattr(game.katrain, "_commit_end_state", None)
        if commit_end_state is None:
            cn.end_state = result  # 桌面 GUI / 没有对局提交锁的调用方:照旧直写
        else:
            try:
                commit_end_state(result, node=cn)
            except Exception as e:
                # core 不 import web:按鸭子类型认 `EndgameConflict`(带 `reason`)。**只吞冲突** ——
                # 签名不符、属性缺失这类编程错误照抛,由 `_do_ai_move_and_broadcast` 记 ERROR;
                # 吞掉的话认输没写上、AI 也不落子,屏上永远「AI 思考中」(评审 r1 m6)。
                if getattr(e, "reason", None) is None:
                    raise
                game.katrain.log(f"AI ({ai_player}) resignation not recorded: {e.reason}", OUTPUT_DEBUG)
                return None
        game.katrain.log(f"AI ({ai_player}) resigns due to low winrate", OUTPUT_INFO)
        return None

    # Create the appropriate strategy based on mode
    strategy = STRATEGY_REGISTRY[ai_mode](game, ai_settings)

    # Generate the move
    game.katrain.log(f"Generating move using {strategy.__class__.__name__}", OUTPUT_DEBUG)
    move, ai_thoughts = strategy.generate_move()

    # Play the move and return
    game.katrain.log(f"Playing move {move.gtp()} and creating game node", OUTPUT_DEBUG)
    # r1(C3):「复核 → 落子」在对局提交锁里一次做完,普通分支与升降级分支是同一段。生成在锁外 ——
    # 认输 / 超时 / 数子 / 人的落子 / 挪游标最多等一次提交,永远不等生成。
    commit_lock = getattr(getattr(game, "katrain", None), "ai_ladder_commit_lock", None)
    with commit_lock if commit_lock is not None else nullcontext():
        if ai_mode == AI_LADDER and _ladder_remote_terminal(game):
            raise LadderUnavailable("ranked game ended remotely before move commit")
        # 算的这段时间里局面换了(悔棋 / 导航,S2),或这一手所在的局面线被结束了(认输 / 超时 / 双停,N21):
        # 这一手不属于盘上的局面,丢掉。
        if game.current_node is not cn or _game_already_ended(game, cn):
            return None
        played_node = game.play(move)
        record_two_pass_end = getattr(game, "record_two_pass_end", None)
        if record_two_pass_end is not None:
            record_two_pass_end(played_node)  # AI 跟停 = 双停第二手:记终局事实(S3)
    game.katrain.log(f"AI thoughts: {ai_thoughts}", OUTPUT_DEBUG)
    played_node.ai_thoughts = ai_thoughts

    game.katrain.log(f"Move generation complete: {move.gtp()}", OUTPUT_DEBUG)
    return move, played_node
```

**③ `katrain/web/server.py`**

`:13` `from fastapi.responses import FileResponse` 改为 `from fastapi.responses import FileResponse, JSONResponse`;
`:34` `from katrain.web.models import *` 之后加一行 `from katrain.web.models import EndgameConflict, GameEnd`(星号 import 本来也带进来,显式写出是给读的人看)。

`CHAT_MAX_LEN = 200` 之后加:

```python


#: r1:`EndgameConflict.reason` → 409 detail。`already_ended` 那句与数子旧文案同形 ——
#: kiosk `countFailureMessage`(Task 4)按 `already over` 分支说「这一局已经结束了」。
ENDGAME_CONFLICT_DETAIL = {
    "already_ended": "Game is already over",
    "position_changed": "Position changed while counting",
    "stale_turn": "timeout rejected: stale_turn",
    "clock_not_expired": "timeout rejected: clock_not_expired",
    "not_your_turn": "Not your turn",
    "remote_ended": "Ranked game has ended on another device",
}
```

`create_app` 里 `app.state.ranked_analysis_activity = RankedAnalysisActivity()` 之后加:

```python

    @app.exception_handler(EndgameConflict)
    async def endgame_conflict_to_409(request: Request, exc: EndgameConflict):
        """r1:运行时的终局 / 提交判别没通过 → 409。端点自己接住的只有两种:认输与不带绑定的超时撞上 `already_ended`
        (200 空操作)。其余一律到这里 —— 没有它就是 500。"""
        detail = ENDGAME_CONFLICT_DETAIL.get(exc.reason, f"Endgame conflict: {exc.reason}")
        return JSONResponse(status_code=409, content={"detail": detail})
```

`/api/move`(`:994`)`session.katrain("play", None if coords is None else tuple(coords))` 改为:

```python
                # r1:非研究会话带 guard —— 这一手所在的局面线已结束 / 轮到 AI 就拒(409),双停第二手记终局事实。
                # 研究会话照旧打谱,不冻结。
                session.katrain("play", None if coords is None else tuple(coords), guard=session.mode != "research")
```

`/api/resign`(`:1874-1954`)整段替换为(本 Task 只动判负方、`wrote` 闸与升降级直写;单机落账那一支 Task 5 统一改):

```python
    @app.post("/api/resign")
    async def resign(request: ToggleAnalysisRequest, current_user: User = Depends(get_current_user_optional)):
        session = _get_session_or_404(manager, request.session_id)
        guard_session_terminator(session, current_user, "resign")
        ranked_ai = is_ai_ladder_ranked_session(session)
        if ranked_ai:
            guard_ai_ladder_ranked_owner(session, current_user, "resign")
            await _guard_ai_ladder_cloud_active(app, session, current_user)

        # For multiplayer games, record the result
        is_multiplayer = session.player_b_id is not None or session.player_w_id is not None
        # r1:这次认输有没有真的写出终局。撞上一局已经结束过的(退出框在终局上点「认输并退出」、galaxy 离页即认输、
        # 连点、平台远端认输成功而本地早已结束)是 200 空操作:返回真实局面,不落账、不广播。
        # **在所有分支之前**赋值 —— 平台局也会走到下面的多人局落账,只在某一支里赋值就是 UnboundLocalError → 500(评审 r1 M4)。
        wrote = True

        # Route through platform gateway for cross-platform games
        gateway = getattr(app.state, "platform_gateway", None)
        platform_game = bool(not ranked_ai and gateway and gateway.is_platform_game(request.session_id))
        if platform_game:
            from katrain.web.platforms.gateway import PlatformMoveRejectedError

            try:
                user_id = current_user.id if current_user else 0
                await gateway.resign(request.session_id, user_id)
            except PlatformMoveRejectedError as e:
                raise HTTPException(status_code=409, detail=str(e))
            except EndgameConflict as e:
                # 远端认输已经成功,网关落回本地(`_local_resign`)时撞上本地早已结束的局:按空操作处理。
                if e.reason != "already_ended":
                    raise
                wrote = False

        if not platform_game:
            with session.lock:
                try:
                    if ranked_ai:
                        snapshot = guard_ai_ladder_ranked_owner(session, current_user, "resign")
                        guard_ai_ladder_ranked_not_ended(session, "resign")
                        winner = "W" if snapshot.user_color == "B" else "B"
                        result = f"{winner}+R"
                        # r1:结果只经对局提交锁里的唯一写入口写(与 AI 提交、远端终局标记互斥)。
                        session.katrain._commit_end_state(result)
                        if hasattr(session.katrain, "_state"):
                            session.katrain._state["end_result"] = result
                        # This branch writes the result straight onto the tree instead of going
                        # through `session.katrain(...)`, so the `update_state` -> `_on_state`
                        # callback that normally sets `game_ended` never fires. Nothing else sets
                        # it on this path, and it is the only thing that stops the ranked heartbeat:
                        # without this line a resigned game goes on reporting a player at the board
                        # forever, the cloud reservation never becomes takeable, and the account is
                        # locked out of ranked play on every device it owns.
                        session.game_ended = True
                    else:
                        # N21:多人局按**请求者的座位**判负(`winner_id` 下面也是这么算的,两边必须一致);
                        # 单机局不传,交给 `_do_resign` 从座位推。
                        loser = None
                        if is_multiplayer and current_user is not None:
                            if current_user.id == session.player_b_id:
                                loser = "B"
                            elif current_user.id == session.player_w_id:
                                loser = "W"
                        if loser is None:
                            session.katrain("resign")
                        else:
                            session.katrain("resign", loser)
                except EndgameConflict as e:
                    if e.reason != "already_ended":
                        raise
                    wrote = False
                state = session.katrain.get_state()
                session.last_state = state
        else:
            state = session.katrain.get_state()
            session.last_state = state

        # Record game result for multiplayer
        if is_multiplayer and current_user and wrote:
            winner_id = session.player_w_id if current_user.id == session.player_b_id else session.player_b_id
            result = f"{'W' if winner_id == session.player_w_id else 'B'}+R"
            try:
                app.state.game_repo.record_multiplayer_game(
                    sgf_content=session.katrain.get_sgf(),
                    result=result,
                    game_type=getattr(session, "game_type", "free"),
                    black_id=session.player_b_id,
                    white_id=session.player_w_id,
                )
            except Exception as e:
                logging.getLogger("katrain_web").error(f"Failed to record game result: {e}")

            # 广播**不在** try 里:它告诉对面「这局结束了」,而 try 守的是落账。
            # 两件事捆在一个 try 里时,落账一失败对面就永远收不到终局 —— 盒上
            # `app.state.game_repo` 恒为 None(`server.py` board 模式那一段),
            # 于是这条路上每一次认输/超时都会静默地把对面挂在「还在等你走」。
            # 数子(`_complete_count`)和退出(forfeit)两处本来就是这么写的,这里对齐。
            manager._schedule_broadcast(
                session,
                {"type": "game_end", "data": {"reason": "resign", "winner_id": winner_id, "result": result}},
            )
        elif not is_multiplayer and current_user and session.user_id and wrote:
            result = state.get("end_result") or session.katrain.game.end_result
            if result:
                await _record_ai_game(session, app, current_user, result)

        return {"session_id": session.session_id, "state": state}
```

`/api/timeout`(`:2119-2165`)里

```python
        with session.lock:
            guard_ai_ladder_ranked_human_action(session, current_user, "timeout")
            session.katrain("timeout")
            state = session.katrain.get_state()
            session.last_state = state

        # Record game result for multiplayer
        if is_multiplayer and current_user:
```

替换为(函数其余部分本 Task 不动,Task 6 整段重写):

```python
        # r1:撞上已经结束过的局是 200 空操作(不落账、不广播),同 `/api/resign`。
        wrote = True
        with session.lock:
            guard_ai_ladder_ranked_human_action(session, current_user, "timeout")
            try:
                session.katrain("timeout")
            except EndgameConflict as e:
                if e.reason != "already_ended":
                    raise
                wrote = False
            state = session.katrain.get_state()
            session.last_state = state

        # Record game result for multiplayer
        if is_multiplayer and current_user and wrote:
```

**Task 2 执行修正（2026-09-15）**：`/api/timeout` 的单机落账 `elif` 同认输补上 `and wrote`，已结束请求的 200 空操作不得重试落账。两条接口回归用 `get_sgf.assert_not_called()` 钉住记录入口，原写法两格都红。

`_complete_count` 的结果写入也在本 Task 改走唯一入口（Task 4 再补显式 `node` 绑定）：

```python
        session.katrain._commit_end_state(result)
        session.game_ended = True
```

删除它原来的 `game.game_result = result` / `game.current_node.end_state = result`。原计划 Step 3 留直写到 Task 4，与本 Task Step 4「server 不再直写」的验收冲突；补的 `test_count_uses_the_same_atomic_result_writer` 先在原写法上得到 200（期望 409），再改为提交入口。断言只钉住结果与调用次数，Task 4 的节点绑定由其新增竞态用例验证。

视觉升降级分支(`:3184-3186`)

```python
                move = vision_move_to_katrain(move_data.col, move_data.row, move_data.color, board_size=19)
                session.katrain("play", move.coords)
        except (HTTPException, ValueError) as exc:
```

替换为

```python
                move = vision_move_to_katrain(move_data.col, move_data.row, move_data.color, board_size=19)
                # r1:守卫在对局提交锁里再判一次(已终局 / 远端已结束 / 不是这颗子的颜色)。
                session.katrain("play", move.coords, guard=True, expected_player=move_player)
        except (HTTPException, ValueError, EndgameConflict) as exc:
```

视觉非平台分支(`:3240-3242`)

```python
    else:
        with session.lock:
            session.katrain("play", move.coords)
```

替换为

```python
    else:
        # r1(S7):上面按 `last_state` 做的轮次检查读的是可能过期的广播帧;真正的判别在对局提交锁里
        # (已终局 / 轮到 AI / 不是这颗子的颜色)。被拒时照「不轮到」那一支重新布防、节流 0.5 秒。
        # 与跨平台 N13 在同一函数相邻改动,合并时逐段对。
        try:
            with session.lock:
                session.katrain("play", move.coords, guard=True, expected_player=move_player)
        except EndgameConflict as exc:
            log.info("Vision move %s refused for session %s: %s", move_player, session_id, exc.reason)
            _rearm_detection()
            return 0.5
```

**④ 测试替身跟上真接口**(`tests/web_ui/test_ai_ladder_api.py`;端点里不用 `getattr` 迁就替身)

import 区 `from katrain.web.server import create_app` 之后加 `from katrain.web.models import EndgameConflict, GameEnd`。

`FakeKaTrain.__init__` 里 `self.calls = []` 之前加 `self.ai_ladder_commit_lock = threading.RLock()`;`self.game = SimpleNamespace(` 里 `end_result=None,` 之后加一行 `terminal=None,`。

`__call__` 里

```python
        elif action == "resign":
            self.game.end_result = "W+R"
            self.game.current_node.end_state = "W+R"
            self._state["end_result"] = "W+R"
        elif action == "timeout":
            self.game.end_result = "W+T"
            self.game.current_node.end_state = "W+T"
            self._state["end_result"] = "W+T"
```

替换为

```python
        elif action == "resign":
            self._commit_end_state("W+R")
        elif action == "timeout":
            self._commit_end_state("W+T")
```

`def update_config(self, setting, value):` 之前加:

```python
    def _commit_end_state(self, result, *, node=None, fill_pending=False):
        # 与真 `WebKaTrain._commit_end_state` 同口径:已有终局事实或节点上已有结果就拒(`already_ended`);
        # 写结果、终局事实与替身自己的 `_state`。替身没有导航,不必分局面线。
        with self.ai_ladder_commit_lock:
            target = self.game.current_node if node is None else node
            if getattr(self.game, "terminal", None) is not None or target.end_state:
                raise EndgameConflict("already_ended")
            target.end_state = result
            try:
                self.game.end_result = result
            except AttributeError:
                pass  # `test_ranked_resign_supports_real_game_read_only_end_result` 换上的对局 `end_result` 只读
            self.game.terminal = GameEnd(self.game, target, result)
            self._state["end_result"] = result
            return self.game.terminal
```

绊线续命(同文件 `:4318-4371`):server.py 改走 `_commit_end_state` 之后,只认 `current_node.end_state = ` 的绊线**一处都扫不到**,
长得和「守得很好」一模一样。把两条用例改成共用一个谓词 —— `def test_every_place_that_writes_a_terminal_result_by_hand_also_ends_the_game():` 之前加:

```python
def _writes_a_terminal_result_by_hand(line: str) -> bool:
    """r1:server.py 不再直写 `end_state`,终局一律经 `WebKaTrain._commit_end_state` —— 那同样绕过了
    `session.katrain(...)`,同样不触发 `_on_state`。只认前一种写法的话,这条绊线在 Task 2 之后就扫不到任何东西了。"""
    return "current_node.end_state = " in line or "._commit_end_state(" in line
```

该用例循环里的 `if "current_node.end_state = " not in line:` 改为 `if not _writes_a_terminal_result_by_hand(line):`。
正对照 `test_the_tripwire_can_actually_see_a_missing_flag` 里

```python
    fake = (
        "                    session.katrain.game.current_node.end_state = result\n" * 1 + "                    pass\n"
    )
    lines = fake.splitlines()
    hits = [
        i
        for i, line in enumerate(lines)
        if "current_node.end_state = " in line and "session.game_ended = True" not in "\n".join(lines[i : i + 12])
    ]
    assert hits, "扫描逻辑抓不到缺失的置位 —— 上面那条断言说明不了任何事情"
```

替换为

```python
    fake = (
        "                    session.katrain.game.current_node.end_state = result\n"
        "                    pass\n"
        "                    session.katrain._commit_end_state(result)\n"
        "                    pass\n"
    )
    lines = fake.splitlines()
    hits = [
        i
        for i, line in enumerate(lines)
        if _writes_a_terminal_result_by_hand(line) and "session.game_ended = True" not in "\n".join(lines[i : i + 12])
    ]
    assert hits == [0, 2], "扫描逻辑抓不到缺失的置位 —— 上面那条断言说明不了任何事情"
```

- [x] **Step 4: 跑后端测试确认通过**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
uv run black -l 120 katrain/web/models.py katrain/web/interface.py katrain/core/ai.py katrain/web/server.py \
  tests/test_play_ai_endgame.py tests/core/test_ai_commit_after_end.py tests/web_ui/test_play_ai_endgame_api.py tests/web_ui/test_ai_ladder_api.py
git diff katrain/web/server.py | grep -n "_report_settlement_loop"   # 见 Global Constraints「格式化」:black 顺手压行的那一处要还原
# 根目录(真 WebKaTrain)与 tests/web_ui 分两条跑。提交锁与 `_do_play` 的改动会波及几份用真类的既有测试,一并跑:
CI=true uv run pytest --continue-on-collection-errors tests/test_play_ai_endgame.py tests/core/test_ai_commit_after_end.py tests/core/test_ladder_strategy.py \
  tests/test_ai_resignation.py tests/test_vision_move_poller.py tests/test_guest_free_play.py -q
CI=true uv run pytest --continue-on-collection-errors tests/web_ui/test_play_ai_endgame_api.py tests/web_ui/test_game_termination_and_chat_identity.py tests/web_ui/test_ai_game_autosave.py \
  tests/web_ui/test_ai_ladder_api.py tests/web_ui/test_ladder_injection.py tests/web_ui/test_navigation_guards.py -q
git status --short katrain/config.json   # 期望:空
# 唯一写入口的源码闸(判读前先去掉注释行):
grep -nE '(^|[^[:alnum:]_])end_state[[:space:]]*=' katrain/web/server.py      # 期望:无
grep -nE '(^|[^[:alnum:]_])end_state[[:space:]]*=' katrain/web/interface.py   # 期望:只有 `_commit_end_state` 里 `target.end_state = result` 一处
grep -nE '(^|[^[:alnum:]_])end_state[[:space:]]*=' katrain/core/ai.py         # 期望:只有桌面版回退那一处 `cn.end_state = result`
```
Expected: 全 PASS(`tests/test_ai_resignation.py` 四条引擎用例在 `CI=true` 下 skip);三条 grep 如注释所写。
`test_ladder_injection.py` 模块顶部 `sys.modules.pop` 换回真类,它的三条「无限重生循环」用例是 `_do_update_state` 加 `ended_at` 之后最可能打红的地方;
`test_ai_ladder_api.py` 的 `test_ranked_resign_supports_real_game_read_only_end_result`、`test_repeated_ranked_resign_is_rejected_without_changing_authoritative_result`、
终局绊线两条是替身与绊线改动最可能打红的地方。

- [x] **Step 5: 写失败的前端测试(追加到 `GamePage.playAi.test.tsx` 末尾)**

```tsx
describe('N21 · 本地对局的认输框说出是哪一方', () => {
  it('两个人面对面、轮到白:标题是「白方认输？」', () => {
    sessionMock.gameState = makeState({
      game_type: 'pvp_local', player_to_move: 'W',
      players_info: { B: seat('player:human', '小明'), W: seat('player:human', '小红') },
    });
    renderPage();
    fireEvent.click(screen.getByText('MOCK_RESIGN'));
    expect(screen.getByText('白方认输？')).toBeInTheDocument();
  });

  it('人机局仍是「确认认输？」—— 认输的一定是人,不用点名', () => {
    sessionMock.gameState = makeState();
    renderPage();
    fireEvent.click(screen.getByText('MOCK_RESIGN'));
    expect(screen.getByText('确认认输？')).toBeInTheDocument();
  });
});

describe('S1(r1)· 「本局已结束」认服务端的终局事实,翻手看棋不回退', () => {
  // 终局之后按了「上一手」:游标上的 end_result 变回 null,但这一局的终局事实还在。
  const steppedBack = () => makeState({ end_result: null, terminal_result: 'W+R', children: [['W', [3, 3]]] });

  it('终局后退到前一手:右栏与终局卡仍是终局,「继续上一局」照样清掉、不写回来', async () => {
    sessionMock.gameState = steppedBack();
    renderPage();
    expect(screen.getByTestId('panel-over').textContent).toBe('true');
    expect(screen.getByTestId('endgame-card')).toBeInTheDocument();
    await waitFor(() => expect(clearActiveSession).toHaveBeenCalledWith('game'));
    expect(writeActiveSession).not.toHaveBeenCalled();
  });

  it('终局之后点棋盘不发落子 —— 服务端只冻住终局那一手之后,翻回去的局面它照样收', () => {
    sessionMock.gameState = steppedBack();
    renderPage();
    fireEvent.click(screen.getByTestId('board'));
    expect(sessionMock.onMove).not.toHaveBeenCalled();
  });
});
```

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui && npx vitest run src/kiosk/pages/GamePage.playAi.test.tsx`
Expected: 「白方认输？」那条 FAIL;S1 两条 FAIL(`panel-over` 是 `false`、没有 `endgame-card`、`writeActiveSession` 被调;`onMove` 被调一次);其余 PASS。

- [x] **Step 6: 实现前端**

`GamePage.tsx` 里 `const humanColor = deriveHumanColor(gameState);` 之后加:

```tsx
  // N21:两个人面对面下时,认输的是**轮到落子的那一方**(`interface.py` `_do_resign` 的回退)。
  // 确认框必须把这一方说出来 —— 否则按下去的人不知道自己替谁认了输。人机局认输的一定是人,不用点名。
  const bothHuman = gameState.players_info.B.player_type === 'player:human'
    && gameState.players_info.W.player_type === 'player:human';
  const resignSide = gameState.player_to_move === 'B' ? t('game:black_side', '黑方') : t('game:white_side', '白方');
  const resignTitle = bothHuman
    ? t('game:resign_confirm_side', '{side}认输？').replace('{side}', resignSide)
    : t('Confirm resign?', '确认认输？');
  const exitResignTitle = bothHuman
    ? t('game:exit_resign_confirm_side', '对局进行中，{side}认输并退出？').replace('{side}', resignSide)
    : t('Game in progress. Resign and exit?', '对局进行中，认输并退出？');
```

认输确认框的标题 `<DialogTitle sx={{ color: 'text.primary' }}>{t('Confirm resign?', '确认认输？')}</DialogTitle>` 改为
`<DialogTitle sx={{ color: 'text.primary' }}>{resignTitle}</DialogTitle>`;
退出确认框的 `<DialogTitle>{t('Game in progress. Resign and exit?', '对局进行中，认输并退出？')}</DialogTitle>` 改为 `<DialogTitle>{exitResignTitle}</DialogTitle>`。

**S1(r1):「本局已结束」认终局事实。**

`api.ts` 的 `GameState` 里 `end_result: string | null;` 之后加:

```ts
  /** r1:这一局结束过没有(服务端对局级的终局事实)。`end_result` 读的是游标,终局后按「上一手」会变回 null;这个不会。老服务端不带。 */
  terminal_result?: string | null;
```

`GamePage.tsx` 里 `export function deriveAiTurnState(` 那段注释之前(模块级)加:

```tsx
// S1(r1):「这一局结束了没有」认服务端的终局事实 `terminal_result`,不只认游标上的 `end_result` ——
// 后者在终局后按一下「上一手」就变回 null,终局卡、打谱键、「继续上一局」的清除会一起回退成「对局中」。
// 老服务端不带 `terminal_result` ⇒ 退回 `end_result`,一切照旧。
const endResultOf = (gs: GameState): string | null => gs.end_result || gs.terminal_result || null;
```

五个读者改读它:
1. `deriveAiTurnState` 里 `const aiThinking = !!aiColor && gameState.player_to_move === aiColor && !gameState.end_result;` 改为 `const aiThinking = !!aiColor && gameState.player_to_move === aiColor && !endResultOf(gameState);`;
2. `EndgameCard` 里 `<KioskResultBadge result={gameState.end_result!} rules={gameState.ruleset} />` 改为 `<KioskResultBadge result={endResultOf(gameState)!} rules={gameState.ruleset} />`;
3. `activeSession write-on-load / clear-on-end` 那个 effect 里 `if (gs.end_result) { clearActiveSession('game'); return; }` 改为 `if (endResultOf(gs)) { clearActiveSession('game'); return; }`,依赖数组 `[session.gameState?.current_node_id, session.gameState?.end_result, sessionId]` 改为 `[session.gameState?.current_node_id, session.gameState?.end_result, session.gameState?.terminal_result, sessionId]`;
4. AI 落子横幅那个 effect 里 `if (gs.last_move && gs.end_result === null && human && gs.player_to_move === human) {` 改为 `if (gs.last_move && !endResultOf(gs) && human && gs.player_to_move === human) {`(否则终局后翻手,实体盘上会冒出「AI 已落子,请摆到亮灯处」);
5. `const isGameOver = !!gameState.end_result;` 改为 `const isGameOver = !!endResultOf(gameState);`。

`handleBoardMove` 开头(`try {` 之前)加:

```tsx
    // S1(r1):服务端只冻住「终局那一手和它之后」(galaxy 悔棋后另开分支要用);kiosk 终局后翻回去点盘不许另开分支。
    if (isGameOver) return;
```

- [x] **Step 7: 验证并提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
npx vitest run src/kiosk/pages/GamePage.playAi.test.tsx src/kiosk/pages/GamePage.test.tsx src/kiosk/__tests__/GamePageEngine.test.tsx
npx tsc -b && echo TSC_OK
npx eslint src/kiosk/pages/GamePage.tsx src/api.ts
npm run build && npm run build:kiosk-2d          # api.ts 是共享领地:两套都要绿
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
# 基线 diff(后端 + 前端)，两个 comm -13 均须为空
CI=true uv run pytest tests --continue-on-collection-errors -q -rfE -p no:cacheprovider 2>&1 | tee /tmp/kgpa-now-pytest.log
grep -E '^(FAILED|ERROR) tests/' /tmp/kgpa-now-pytest.log | sed -E 's/ - .*//' | LC_ALL=C sort -u > /tmp/kgpa-now-pytest-failed.txt
LC_ALL=C comm -13 /tmp/kgpa-baseline/pytest-failed.txt /tmp/kgpa-now-pytest-failed.txt   # 期望:无输出
git restore --source=HEAD -- katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json
rm -f test_user_data.db
git status --short katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json test_user_data.db   # 期望:空
cd katrain/web/ui
npx vitest run --reporter=verbose 2>&1 | tee /tmp/kgpa-now-vitest.log
grep -E '^\s+×' /tmp/kgpa-now-vitest.log | sed -E 's/^\s+×\s+//; s/ [0-9]+ms$//' | LC_ALL=C sort -u > /tmp/kgpa-now-vitest-failed.txt
LC_ALL=C comm -13 /tmp/kgpa-baseline/vitest-failed.txt /tmp/kgpa-now-vitest-failed.txt   # 期望:无输出
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
git add katrain/web/models.py katrain/web/interface.py katrain/core/ai.py katrain/web/server.py katrain/web/ui/src/api.ts \
  katrain/web/ui/src/kiosk/pages/GamePage.tsx katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx \
  tests/test_play_ai_endgame.py tests/core/test_ai_commit_after_end.py tests/web_ui/test_play_ai_endgame_api.py tests/web_ui/test_ai_ladder_api.py
git diff --cached --stat
git commit -m "fix(play): AI 思考中认输被记成人赢,AI 那一手随后又落下 —— 认输按座位判,终局事实 + 对局提交锁

N21(P1)。_do_resign 原来写「最后落子的一方胜」;人机局改判人输,多人局按请求者座位判,
本地对局确认框点名是哪一方。
终局事实挂在对局上(WebGame.terminal,按局面线判)、先写者胜,结果只经 _commit_end_state 写;
AI 提交 / 终局写入 / 人的落子 / 挪游标 / 时钟结算共用对局提交锁,AI 只在锁里复核开算节点后落子。
有意的行为变化:终局那一手之后不再接受带 guard 的落子(409);人机局在 AI 回合落子 / 停一手回 409;
kiosk「本局已结束」读 terminal_result。galaxy 悔棋后另开分支照旧可下。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: N23 数子门槛按路数缩放

**执行记录（2026-09-15，已完成）**：真类红灯 3 failed；HTTP 门槛红灯 1 failed（100 而非 22）。按源码将计划夹具的 config 明确为 100，让测试因门槛来源错误变红，避免 MagicMock 的 TypeError。生产实现无偏离。指定回归复现旧 `test_count_api.py::TestIntegration` 因 MagicMock 缺 history 失败（此前全量依赖其他文件赋值才绿）；将这两条原断言迁到根目录真类文件，复用 `_web_katrain` 并双人座位隔离 AI 线程。

最终验证：真类 **29 passed**、web_ui **278 passed**，tsc 绿；后端全量 69 failed / 3593 passed / 46 errors，前端全量 1732 passed / 5 skipped，两个基线名称集合 **新增均为空**；三处测试污染已清理。日志 `/tmp/kgpa-task3-green-root-final.log`、`/tmp/kgpa-task3-green-web-final.log`、`/tmp/kgpa-task3-pytest.log`、`/tmp/kgpa-task3-vitest.log`。未改共享前端，无需重复两套构建。

**Files:**
- Modify: `katrain/web/interface.py:281-284`(`analysis_allowed` 之后加 `count_min_moves()`)、`:611`(`get_state` 的 `count_min_moves` 键)
- Modify: `katrain/web/server.py:2015-2019`(`/api/count/request` 的门槛)
- Modify(真类测试归位): `tests/web_ui/test_count_api.py` 的 `TestIntegration` 移到 `tests/test_play_ai_endgame.py`
- Test: `tests/test_play_ai_endgame.py`、`tests/web_ui/test_play_ai_endgame_api.py`(追加)

**Interfaces:**
- Consumes: Task 2 的测试夹具 `_web_katrain()`、`client`、`_inject_session()`
- Produces: `WebKaTrain.count_min_moves(self) -> int`;`get_state()["count_min_moves"]` 即它的值;`/api/count/request` 只读 `get_state()` 下发的这个值(前后端同源)

- [x] **Step 1: 写失败的测试**

追加到 `tests/test_play_ai_endgame.py` 末尾:

```python
# ---------------------------------------------------------------- N23 数子门槛按路数


@pytest.mark.parametrize("size,expected", [(19, 100), (13, 46), (9, 22)])
def test_count_threshold_scales_with_board_size(size, expected):
    """配置里的 100 是 19 路的数;小棋盘按交叉点数等比缩小,和 AI 认输门槛(core/ai.py should_ai_resign)同一种缩放。"""
    w = _web_katrain()
    w._do_new_game(size=size)
    assert w.count_min_moves() == expected
    assert w.get_state()["count_min_moves"] == expected
```

追加到 `tests/web_ui/test_play_ai_endgame_api.py` 末尾:

```python
# ---------------------------------------------------------------- N23


def test_count_refuses_with_the_threshold_the_session_reports(client):
    """门槛只有一个来源:`get_state()` 下发的 `count_min_moves`(前端读的也是它)。"""
    session = _inject_session(client)
    session.katrain.config.return_value = 100
    session.katrain.get_state.return_value = {"end_result": None, "history": [{}] * 21, "count_min_moves": 22}

    resp = client.post("/api/count/request", json={"session_id": session.session_id})

    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"] == "Cannot count before 22 moves"
```

Run（分两条）：

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai && CI=true uv run pytest tests/test_play_ai_endgame.py -q -k "threshold"
CI=true uv run pytest tests/web_ui/test_play_ai_endgame_api.py -q -k "threshold"
```
Expected: 13/9 路两条 FAIL(`AttributeError: 'WebKaTrain' object has no attribute 'count_min_moves'`,19 路那条同样 FAIL);API 那条 FAIL(detail 是 `…before 100 moves` 而非 `…before 22 moves`)。

- [x] **Step 2: 实现**

`katrain/web/interface.py`,`analysis_allowed` 属性之后加:

```python
    def count_min_moves(self) -> int:
        """数子门槛(手数)。配置里的 `game/count_min_moves` 是 **19 路**的数;
        小棋盘按交叉点数等比缩小 —— 与 AI 认输门槛(`core/ai.py` `should_ai_resign`)同一种缩放。
        不缩放时 9 路盘 81 个交叉点、几十手就下完,数子键整局都是灰的(N23)。"""
        configured = self.config("game/count_min_moves", 100)
        if not self.game:
            return configured
        width, height = self.game.board_size
        return max(1, int(configured * width * height / 361))
```

`get_state` 里 `"count_min_moves": self.config("game/count_min_moves", 100),` 改为 `"count_min_moves": self.count_min_moves(),`。

`katrain/web/server.py` `/api/count/request` 里

```python
        state = session.katrain.get_state()
        count_min_moves = session.katrain.config("game/count_min_moves", 100)
```

改为

```python
        state = session.katrain.get_state()
        # 门槛认 get_state 下发的那个数(按路数缩放过,前端显示的也是它)。状态里没有这个键时回落到配置 ——
        # 不许回落成写死的 100:tests/web_ui/test_ai_ladder_api.py 的 FakeKaTrain 状态里没有这个键、
        # 配置给的是 0,`test_ranked_session_allows_human_turn_terminal_actions[/api/count/request]` 期望 200。
        count_min_moves = state.get("count_min_moves")
        if count_min_moves is None:
            count_min_moves = session.katrain.config("game/count_min_moves", 100)
```

- [x] **Step 3: 跑测试确认通过**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
uv run black -l 120 katrain/web/interface.py katrain/web/server.py tests/test_play_ai_endgame.py tests/web_ui/test_play_ai_endgame_api.py
CI=true uv run pytest tests/test_play_ai_endgame.py -q
CI=true uv run pytest tests/web_ui/test_play_ai_endgame_api.py tests/web_ui/test_count_api.py tests/web_ui/test_ai_ladder_api.py -q
git status --short katrain/config.json   # 期望:空
```
Expected: 全 PASS(`test_ai_ladder_api.py` 里三条 `terminal_actions` 参数化用例是改 `/api/count/request` 最可能打红的地方)。前端无改动:`GameControlPanel.tsx:188` 读的就是 `gameState.count_min_moves`,「数子要下满 N 手」自动变成 22/46/100。

- [x] **Step 4: 基线 diff 后提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
# 基线 diff(后端 + 前端)，两个 comm -13 均须为空
CI=true uv run pytest tests --continue-on-collection-errors -q -rfE -p no:cacheprovider 2>&1 | tee /tmp/kgpa-now-pytest.log
grep -E '^(FAILED|ERROR) tests/' /tmp/kgpa-now-pytest.log | sed -E 's/ - .*//' | LC_ALL=C sort -u > /tmp/kgpa-now-pytest-failed.txt
LC_ALL=C comm -13 /tmp/kgpa-baseline/pytest-failed.txt /tmp/kgpa-now-pytest-failed.txt   # 期望:无输出
git restore --source=HEAD -- katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json
rm -f test_user_data.db
git status --short katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json test_user_data.db   # 期望:空
cd katrain/web/ui
npx vitest run --reporter=verbose 2>&1 | tee /tmp/kgpa-now-vitest.log
grep -E '^\s+×' /tmp/kgpa-now-vitest.log | sed -E 's/^\s+×\s+//; s/ [0-9]+ms$//' | LC_ALL=C sort -u > /tmp/kgpa-now-vitest-failed.txt
LC_ALL=C comm -13 /tmp/kgpa-baseline/vitest-failed.txt /tmp/kgpa-now-vitest-failed.txt   # 期望:无输出
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
git add katrain/web/interface.py katrain/web/server.py tests/test_play_ai_endgame.py tests/web_ui/test_play_ai_endgame_api.py
git diff --cached --stat
git commit -m "fix(play): 9 路与多数 13 路整局数不了子 —— 数子门槛按交叉点数缩放,前后端同源

N23(P2)。count_min_moves 固定 100 不分路数;改为 configured×w×h/361(19/13/9 路 = 100/46/22),
/api/count/request 只读 get_state 下发的同一个数。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: A12 数子前服务端补分;数子在途与失败原因说真话

**执行记录（2026-09-15，已完成）**：后端红灯为真类 7 failed / 29 passed（缺补分方法、端点未进入认输/悔棋回调），HTTP 1 failed / 13 passed（补分未接入，仍回 400）；后端指定两条独立命令分别 51 passed、316 passed。前端新增 4 条先红（旧错误文案与缺少在途提示），三文件回归 89 passed；tsc 绿、eslint 0 errors / 4 条既有 warnings。源码偏差：`GameNode.score` 是只读属性，真实并发测试通过 `set_analysis` 写入根分数；Task 2 已让数子走 `_commit_end_state`，因此 runtime 拒绝 → 409 用例现为既有行为正对照，不再期望红灯。测试不重导入 `interface`，继续使用模块收集时捕获的真类。另补正常点击重试的正对照：错误刚显示后重试进入在途，旧 Snackbar 由既有 clickaway 关闭；该测试首次即绿，未为未复现的遮挡问题改生产代码。

首次后端全量唯一新增 `test_http_engine_no_spawn.py::test_concurrent_post_json_share_one_session`（本机并发请求 502）；该文件单独复核 **9 passed**，未改引擎或测试代码，第二次全量同一用例再次出现单路 502。检查发现 stdlib 测试服务器 listen backlog 为 5，低于该用例同时创建的 8 个连接；仅将本地测试服务器 backlog 提到 16，保留 8 路并发、结果与会话复用断言，生产引擎不改，再做全量验证。前端全量 **1737 passed / 5 skipped**，名称集合新增为空。

最终全量：后端 **69 failed / 3603 passed / 46 errors**，前端 **1737 passed / 5 skipped**，对原始基线两个名称集合 **新增均为空**；三处污染已清理。日志 `/tmp/kgpa-task4-pytest-verified.log`、`/tmp/kgpa-task4-vitest.log`。本 Task 未改共享前端，无需重复两套构建。

**Files:**
- Modify(基线稳定性): `tests/test_http_engine_no_spawn.py`（本地测试服务器 backlog 容纳既有 8 路并发）
- Modify: `katrain/web/interface.py`(`count_min_moves()` 之后加 `ENSURE_SCORE_TIMEOUT_S` 与 `ensure_current_score(timeout_s=None, node=None)`)
- Modify: `katrain/web/server.py`:`create_app` 之前加模块级 `_terminal_of` / `_count_result`;`:1956-2006`(`_complete_count` 整段);`:2066-2076`(`/api/count/request` 的 HvAI / pvp_local 分支:await 之前取节点、补分、按节点数)
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx:433-444`(`handleAction` 的 `count` 分支)+ 状态声明区 + 一个 `Snackbar`
- Test: `tests/test_play_ai_endgame.py`、`tests/web_ui/test_play_ai_endgame_api.py`、`katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx`(追加)
- Modify(测试替身): `tests/web_ui/test_ai_ladder_api.py` 的 `FakeKaTrain`(`:97` 起)补一个 `ensure_current_score(timeout_s=None, node=None)` —— 端点新调的方法替身没有,
  `test_ranked_session_allows_human_turn_terminal_actions[/api/count/request]` 会从 200 变 500

**Interfaces:**
- Consumes: Task 1 的 `sessionMock` / `makeState` / `renderPage` / `pageTree`； Task 3 的 `count_min_moves()`;Task 2 的 `_commit_end_state` / `EndgameConflict` / 409 处理器与测试夹具
- Produces:
  - `WebKaTrain.ENSURE_SCORE_TIMEOUT_S: float = 15.0`;`WebKaTrain.ensure_current_score(self, timeout_s: Optional[float] = None, node=None) -> Optional[float]`
    (阻塞;`node` 为 None 时补当前手;升降级局与无引擎时不请求、立即返回已有值)。Task 5 以 `node=` 调用。
  - server 模块级 `_terminal_of(session) -> Optional[GameEnd]`、`_count_result(score: float) -> tuple[str, str]`(Task 5 复用)
  - server 闭包 `_complete_count(session, app, current_user, node=None) -> tuple[str, bool]`(写入经 `_commit_end_state(result, node=node)`,冲突 409)
  - 测试夹具 `web_client`(真 `create_app` + TestClient)与 `_two_human_guest_game(client, moves)`,供 Task 5 复用

- [x] **Step 1: 写失败的后端测试**

追加到 `tests/test_play_ai_endgame.py` 末尾:

```python
# ---------------------------------------------------------------- A12 数子前补分


class _InstantEngine:
    """一请求就同步回一份分析的假引擎 —— 只实现 GameNode.analyze 用到的那一个方法。"""

    def __init__(self, score):
        self.score = score
        self.requests = 0

    def request_analysis(self, node, callback, **kwargs):
        self.requests += 1
        callback({"rootInfo": {"scoreLead": self.score, "winrate": 0.6, "visits": 5}, "moveInfos": []}, False)


def _free_game_with_moves(engine):
    w = _web_katrain()
    _seat(w, human_colors={"B"})
    w.game.play(Move(coords=(3, 3), player="B"))
    w.game.play(Move(coords=(15, 15), player="W"))
    w.engine = engine  # 落子之后再换:game.play 用的是开局时的 NullEngine,不会先把分补上
    return w


def test_missing_score_is_filled_by_one_analysis():
    engine = _InstantEngine(score=3.5)
    w = _free_game_with_moves(engine)
    assert w.game.current_node.score is None
    assert w.ensure_current_score(timeout_s=1) == 3.5
    assert engine.requests == 1


def test_an_existing_score_is_not_requested_again():
    engine = _InstantEngine(score=-2.0)
    w = _free_game_with_moves(engine)
    w.ensure_current_score(timeout_s=1)
    w.ensure_current_score(timeout_s=1)
    assert engine.requests == 1


def test_ranked_games_are_never_analysed_for_a_score():
    """升降级终局怎么判目等 Fan 拍板(PRD §4 A12-R);在那之前一次都不许替它算。"""
    engine = _InstantEngine(score=3.5)
    w = _free_game_with_moves(engine)
    w.game_type = "ai_ladder_ranked"
    assert w.ensure_current_score(timeout_s=1) is None
    assert engine.requests == 0


def test_no_engine_returns_at_once_instead_of_waiting_out_the_timeout():
    import time

    w = _web_katrain()  # enable_engine=False ⇒ NullEngine,请求永远不会回来
    started = time.monotonic()
    assert w.ensure_current_score(timeout_s=5) is None
    assert time.monotonic() - started < 1


def test_an_explicit_node_is_scored_even_when_the_cursor_has_moved():
    """C2 / C4:补的是「开始数子 / 双停」的那一手,不是游标此刻那一手。"""
    engine = _InstantEngine(score=1.5)
    w = _free_game_with_moves(engine)
    counted = w.game.current_node
    w.game.undo(1)
    assert w.ensure_current_score(timeout_s=1, node=counted) == 1.5
    assert counted.score == 1.5 and w.game.current_node.score is None


# ---------------------------------------------------------------- C2 数子等分析的这几秒里局面变了(真 create_app)


@pytest.fixture
def web_client(isolated_session_factory):
    """真 `create_app` + 真 SessionManager / WebKaTrain 的 TestClient。
    会话收尾照 tests/test_guest_free_play.py:进程级会话不跟着 TestClient 走,不收掉会污染后面的文件。"""
    from fastapi.testclient import TestClient

    from katrain.web.server import create_app

    app = create_app(enable_engine=False)
    app.state.session_factory = isolated_session_factory  # 必须在 TestClient 之前:lifespan 用它重建全部 repo
    with TestClient(app) as c:
        yield c
        for s in list(c.app.state.session_manager._sessions.values()):
            c.app.state.session_manager.remove_session(s.session_id)


def _two_human_guest_game(client, moves):
    """游客会话、两边坐人(不起 AI 线程),按 `/api/move` 下完 `moves`(None = 停一手)。返回 `(session_id, WebKaTrain)`。"""
    sid = client.post("/api/session", json={}).json()["session_id"]
    for bw, name in (("B", "游客"), ("W", "游客2")):
        r = client.post(
            "/api/player",
            json={"session_id": sid, "bw": bw, "player_type": "player:human", "player_subtype": "human", "name": name},
        )
        assert r.status_code == 200, r.text
    for coords in moves:
        body = {"session_id": sid, "pass_move": True} if coords is None else {"session_id": sid, "coords": list(coords)}
        r = client.post("/api/move", json=body)
        assert r.status_code == 200, r.text
    w = client.app.state.session_manager.get_session(sid).katrain
    assert isinstance(w, WebKaTrain)
    return sid, w


def test_count_that_waited_for_analysis_does_not_overwrite_a_resignation(web_client):
    """C2:补分的阻塞里有人认输了。数子不许把认输改写成目数结果,回 409「这一局已经结束了」。"""
    sid, w = _two_human_guest_game(web_client, [(3, 3), (15, 15)])
    counted = w.game.current_node
    w.count_min_moves = lambda: 0
    seen = {}

    def score_while_someone_resigns(timeout_s=None, node=None):
        assert node is counted  # 补的是开始数子那一手
        seen["resign"] = web_client.post("/api/resign", json={"session_id": sid})
        node.set_analysis({"rootInfo": {"scoreLead": 2.5, "winrate": 0.6, "visits": 5}, "moveInfos": []})
        return 2.5

    w.ensure_current_score = score_while_someone_resigns
    r = web_client.post("/api/count/request", json={"session_id": sid})

    assert seen["resign"].status_code == 200, seen["resign"].text
    assert r.status_code == 409, r.text
    assert "already over" in r.json()["detail"]
    assert w.game.terminal.result == "W+R"  # 两人座位、轮到黑 ⇒ 黑认输
    assert w.game.end_result == "W+R"


def test_count_does_not_finish_a_position_that_changed_while_it_waited(web_client):
    """C2:补分的阻塞里人悔了一手。数子不许把游标上那一手记成结束,回 409「局面变了」。"""
    sid, w = _two_human_guest_game(web_client, [(3, 3), (15, 15)])
    counted = w.game.current_node
    w.count_min_moves = lambda: 0
    seen = {}

    def score_while_someone_undoes(timeout_s=None, node=None):
        assert node is counted
        seen["undo"] = web_client.post("/api/undo", json={"session_id": sid, "n_times": 1})
        node.set_analysis({"rootInfo": {"scoreLead": -1.5, "winrate": 0.4, "visits": 5}, "moveInfos": []})
        return -1.5

    w.ensure_current_score = score_while_someone_undoes
    r = web_client.post("/api/count/request", json={"session_id": sid})

    assert seen["undo"].status_code == 200, seen["undo"].text
    assert r.status_code == 409, r.text
    assert "Position changed" in r.json()["detail"]
    assert w.game.terminal is None
    assert w.game.current_node is counted.parent
    assert counted.end_state is None and counted.parent.end_state is None
```

追加到 `tests/web_ui/test_play_ai_endgame_api.py` 末尾:

```python
# ---------------------------------------------------------------- A12


def _countable(session):
    session.katrain.get_state.return_value = {"end_result": None, "history": [{}] * 101, "count_min_moves": 100}
    session.katrain.game.current_node.score = None


def test_count_fills_the_missing_score_before_counting(client):
    session = _inject_session(client)
    _countable(session)

    def fill_score(*_args, **_kwargs):
        session.katrain.game.current_node.score = 2.5
        return 2.5

    session.katrain.ensure_current_score.side_effect = fill_score

    resp = client.post("/api/count/request", json={"session_id": session.session_id})

    assert resp.status_code == 200, resp.text
    assert resp.json()["result"] == "B+2.5"
    counted = session.katrain.game.current_node
    # C2:补的、数的、写的都是 await 之前取的那一手;写入只经唯一写入口(在对局提交锁里复核)
    session.katrain.ensure_current_score.assert_called_once_with(node=counted)
    session.katrain._commit_end_state.assert_called_once_with("B+2.5", node=counted)


def test_a_count_refused_by_the_runtime_is_a_409(client):
    """`_commit_end_state` 在锁里发现局面已结束 / 变了 → 处理器回 409,不是 500、也不是 200。"""
    session = _inject_session(client)
    _countable(session)
    session.katrain.ensure_current_score.return_value = 2.5
    session.katrain.game.current_node.score = 2.5
    session.katrain._commit_end_state.side_effect = EndgameConflict("position_changed")

    resp = client.post("/api/count/request", json={"session_id": session.session_id})

    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == "Position changed while counting"


def test_count_still_says_why_when_no_score_can_be_had(client):
    """补不出来(升降级局 / 引擎不可用)时照旧 400,detail 原样 —— 前端靠它说对原因。"""
    session = _inject_session(client)
    _countable(session)
    session.katrain.ensure_current_score.return_value = None

    resp = client.post("/api/count/request", json={"session_id": session.session_id})

    assert resp.status_code == 400
    assert resp.json()["detail"].startswith("Analysis not available")
```

Run（分两条）：

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai && CI=true uv run pytest tests/test_play_ai_endgame.py --continue-on-collection-errors -q
CI=true uv run pytest tests/web_ui/test_play_ai_endgame_api.py --continue-on-collection-errors -q
```
Expected:
- 五条 interface 用例 FAIL(`AttributeError: … 'ensure_current_score'`,含 `test_an_explicit_node_is_scored_even_when_the_cursor_has_moved`);
- `test_count_that_waited_for_analysis_does_not_overwrite_a_resignation` FAIL(端点不调补分,阻塞函数里的认输从没发生:`KeyError: 'resign'`;若只补了分而不按节点复核,则是 count 200 并把结果改写成 `B+2.5`);
- `test_count_does_not_finish_a_position_that_changed_while_it_waited` FAIL(同理 `KeyError: 'undo'`;若补了分但数的是游标那一手,则是 400 而不是 409);
- web_ui:`test_count_fills_the_missing_score_before_counting` FAIL(400,端点没调补分);`test_a_count_refused_by_the_runtime_is_a_409` PASS(Task 2 已统一原子写入,作为 409 正对照);
- `test_count_still_says_why…` PASS(现状就是 400)。

- [x] **Step 2: 实现后端**

`katrain/web/interface.py`,`count_min_moves()` 之后加:

```python
    #: 数子 / 双停终局时服务端自己补一次形势分析,最多等这么久(秒)。
    ENSURE_SCORE_TIMEOUT_S = 15.0

    def ensure_current_score(self, timeout_s: Optional[float] = None, node=None) -> Optional[float]:
        """`node`(缺省为当前手)的目差(`scoreLead`,正数黑领先);没有就补一次快速分析并**同步等它算完**。

        盒上逐手分析是关的(`should_suppress_auto_eval`),当前手常常没有分数;从前数子全靠前端「图表」开关每手补一次,
        游客、关了开关、分析没回来就点,一律 400(A12)。这里让判胜负不再依赖前端开关。

        · `node`:数子 / 双停收尾在 await **之前**捕获的那一手(r1 C2 / C4)。等分析的这几秒里人可能悔棋 / 导航,
          补的必须是开始数子的那一手,不是游标此刻那一手。
        · 只给允许分析的局补(`analysis_allowed`):升降级局原样返回已有值(通常是 None)——
          升降级终局怎么判目等 Fan 拍板(PRD §4 A12-R)。
        · 不走 `__call__` 的 ANALYSIS_ACTIONS 闸:这不是交付给玩家看的分析,是判胜负用的内部量;上一条就是它的闸。
        · 阻塞调用,**不许在事件循环线程里直接调**,也**不许持对局提交锁调** —— 服务端用 `asyncio.to_thread`。
        """
        timeout_s = self.ENSURE_SCORE_TIMEOUT_S if timeout_s is None else timeout_s
        if not self.game:
            return None
        node = self.game.current_node if node is None else node
        if node.analysis_complete and node.score is not None:
            return node.score
        if not self.analysis_allowed:
            return node.score
        try:
            engine = self.analysis_engine()
        except Exception:
            engine = self.engine
        if engine is None or isinstance(engine, NullEngine):
            return node.score
        if not node.analysis_exists:
            node.analyze(engine, analyze_fast=True)
        deadline = time.monotonic() + timeout_s
        while not node.analysis_complete and time.monotonic() < deadline:
            time.sleep(0.1)
        return node.score
```

`katrain/web/server.py`,`ENDGAME_CONFLICT_DETAIL`(Task 2 加的)之后加两个模块级 helper:

```python


def _terminal_of(session):
    """这一局的终局事实(`WebGame.terminal`);没有、或会话是替身(MagicMock 属性)时为 None。"""
    terminal = getattr(getattr(getattr(session, "katrain", None), "game", None), "terminal", None)
    return terminal if isinstance(terminal, GameEnd) else None


def _count_result(score):
    """目差 → 终局结果(正数黑领先)。数子与双停补分(Task 5)共用同一种格式。返回 `(result, winner_color)`。"""
    if score >= 0:
        return f"B+{abs(score):.1f}", "B"
    return f"W+{abs(score):.1f}", "W"
```

`_complete_count`(`:1956-2006`)整段替换为:

```python
    def _complete_count(session, app, current_user, node=None):
        """数子并结束对局。返回 `(result, needs_record)`:needs_record 为真时调用方在**放开 session.lock 之后**落账
        (单机 / 本地对局);多人局在这里同步记录并广播。

        `node` 是开始数子时的那一手(`/api/count/request` 在 await 补分之前取);不给就数当前手。
        写入走 `_commit_end_state(result, node=node)`:它在对局提交锁里核「没被别人先结束、仍是当前手」,
        冲突抛 `EndgameConflict` → 409,**在多人局记录与广播之前**(r1 C2;多人局「对方接受数子」的路也因此不再覆盖结果)。
        """
        node = session.katrain.game.current_node if node is None else node
        terminal = _terminal_of(session)
        if terminal is not None and terminal.node is node:
            # 非原子预检,只为说对原因:等分析的这几秒里这一局被认输 / 超时了,分数多半也没补上,
            # 不预检的话会先撞上下面的 400「分析没算出来」。真正的判别在 `_commit_end_state` 里。
            raise EndgameConflict("already_ended")
        score = node.score

        if score is None:
            raise HTTPException(
                status_code=400, detail="Analysis not available yet. Please wait for KataGo analysis to complete."
            )

        result, winner_color = _count_result(score)
        session.katrain._commit_end_state(result, node=node)
        session.game_ended = True

        # Record multiplayer game result
        is_multiplayer = session.player_b_id is not None or session.player_w_id is not None
        if is_multiplayer:
            winner_id = session.player_b_id if winner_color == "B" else session.player_w_id
            try:
                app.state.game_repo.record_multiplayer_game(
                    sgf_content=session.katrain.get_sgf(),
                    result=result,
                    game_type=getattr(session, "game_type", "free"),
                    black_id=session.player_b_id,
                    white_id=session.player_w_id,
                )
            except Exception as e:
                logging.getLogger("katrain_web").error(f"Failed to record count game result: {e}")

            manager._schedule_broadcast(
                session, {"type": "game_end", "data": {"reason": "count", "winner_id": winner_id, "result": result}}
            )
            return result, False

        needs_record = current_user is not None and session.user_id is not None
        return result, needs_record
```

`/api/count/request` 的 `else:` 分支(`:2066-2076`)

```python
        else:
            # HvAI / pvp_local: complete immediately
            with session.lock:
                guard_ai_ladder_ranked_human_action(session, current_user, "request-count")
                result, needs_record = _complete_count(session, app, current_user)
                state = session.katrain.get_state()
                session.last_state = state
```

替换为

```python
        else:
            # HvAI / pvp_local: complete immediately
            # A12:当前手没有分数就先补一次分析再数。阻塞等待放线程里,不占事件循环;
            # 升降级局在 interface 里就不补,照旧走到 _complete_count 的 400。
            # r1 C2:数的是**这一局这一手** —— 在 await 之前取。等分析的这几秒里局面可能变(认输 / 悔棋 / 新开局),
            # 复核不在这里写,交给 `_complete_count` 里的 `_commit_end_state(result, node=node)` 在对局提交锁里原子地做。
            node = session.katrain.game.current_node
            await asyncio.to_thread(session.katrain.ensure_current_score, node=node)
            with session.lock:
                guard_ai_ladder_ranked_human_action(session, current_user, "request-count")
                result, needs_record = _complete_count(session, app, current_user, node=node)
                state = session.katrain.get_state()
                session.last_state = state
```

(其后 `if needs_record: await _record_ai_game(...)` 与 `return` 本 Task 不动,Task 5 统一改。)

`tests/web_ui/test_ai_ladder_api.py` 的 `FakeKaTrain` 里 `def config(self, setting, default=None):` 之前加(替身要跟上真接口,不在端点里 `getattr` 迁就替身):

```python
    def ensure_current_score(self, timeout_s=None, node=None):
        # 真 WebKaTrain 对升降级局不补分析,原样返回那一手已有的分数(A12);替身的当前手本来就带 3.5。
        return (self.game.current_node if node is None else node).score
```

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
uv run black -l 120 katrain/web/interface.py katrain/web/server.py tests/test_play_ai_endgame.py tests/web_ui/test_play_ai_endgame_api.py tests/web_ui/test_ai_ladder_api.py
CI=true uv run pytest tests/test_play_ai_endgame.py tests/test_guest_free_play.py --continue-on-collection-errors -q
CI=true uv run pytest tests/web_ui/test_play_ai_endgame_api.py tests/web_ui/test_count_api.py tests/web_ui/test_ai_ladder_api.py \
  tests/web_ui/test_ai_game_autosave.py tests/web_ui/test_game_termination_and_chat_identity.py tests/web_ui/test_navigation_guards.py --continue-on-collection-errors -q
git status --short katrain/config.json
grep -n "end_state *=" katrain/web/server.py   # 期望:无(判读前去掉注释行)
```
Expected: 全 PASS;config.json 无改动;grep 无输出。

- [x] **Step 3: 写失败的前端测试(追加到 `GamePage.playAi.test.tsx` 末尾)**

```tsx
describe('A12 · 数子在途与失败原因', () => {
  const countable = () => makeState({
    history: Array.from({ length: 120 }, (_, i) => ({ node_id: i, score: null, winrate: null })) as GameState['history'],
  });
  const noScore = 'Request failed 400: {"detail":"Analysis not available yet. Please wait for KataGo analysis to complete."}';

  it('服务端说「分析没算出来」时照实说,不再说成手数不够', async () => {
    sessionMock.gameState = countable();
    vi.spyOn(API, 'requestCount').mockRejectedValue(new Error(noScore));
    renderPage();
    fireEvent.click(screen.getByText('MOCK_COUNT'));
    expect(await screen.findByText('形势分析没算出来，暂时数不了子，请稍后再试')).toBeInTheDocument();
    expect(screen.queryByText(/手数不足/)).toBeNull();
  });

  it('升降级局同一个 400 说「升降级对局现在数不了子」', async () => {
    sessionMock.gameState = { ...countable(), game_type: 'ai_ladder_ranked' };
    vi.spyOn(API, 'requestCount').mockRejectedValue(new Error(noScore));
    renderPage();
    fireEvent.click(screen.getByText('MOCK_COUNT'));
    expect(await screen.findByText('升降级对局现在数不了子（本局不做形势分析）')).toBeInTheDocument();
  });

  it('在途时说「正在数子…」,重复点击不发第二个请求', async () => {
    sessionMock.gameState = countable();
    let finish!: (v: unknown) => void;
    const spy = vi.spyOn(API, 'requestCount').mockImplementation(() => new Promise((r) => { finish = r; }));
    renderPage();
    fireEvent.click(screen.getByText('MOCK_COUNT'));
    fireEvent.click(screen.getByText('MOCK_COUNT'));
    expect(await screen.findByText('正在数子…')).toBeInTheDocument();
    expect(spy).toHaveBeenCalledTimes(1);
    finish({ state: sessionMock.gameState });
    await waitFor(() => expect(screen.queryByText('正在数子…')).toBeNull());
  });

  it('失败后重试在途时清掉旧错误，只显示正在数子', async () => {
    sessionMock.gameState = countable();
    let finish!: (v: unknown) => void;
    const spy = vi.spyOn(API, 'requestCount')
      .mockRejectedValueOnce(new Error(noScore))
      .mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
    renderPage();
    fireEvent.click(screen.getByText('MOCK_COUNT'));
    expect(await screen.findByText('形势分析没算出来，暂时数不了子，请稍后再试')).toBeInTheDocument();

    fireEvent.click(screen.getByText('MOCK_COUNT'));
    expect(screen.queryByText('形势分析没算出来，暂时数不了子，请稍后再试')).toBeNull();
    expect(screen.getByText('正在数子…')).toBeInTheDocument();
    expect(spy).toHaveBeenCalledTimes(2);
    finish({ state: sessionMock.gameState });
    await waitFor(() => expect(screen.queryByText('正在数子…')).toBeNull());
  });

  it('r1 C2:等分析的这几秒里局面变了 → 说「局面变了，请重新数子」', async () => {
    sessionMock.gameState = countable();
    vi.spyOn(API, 'requestCount').mockRejectedValue(new Error('Request failed 409: {"detail":"Position changed while counting"}'));
    renderPage();
    fireEvent.click(screen.getByText('MOCK_COUNT'));
    expect(await screen.findByText('数子这几秒里局面变了，请重新数子')).toBeInTheDocument();
  });
});
```

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui && npx vitest run src/kiosk/pages/GamePage.playAi.test.tsx`
Expected: 四条 A12 用例 FAIL(文案仍是「暂时不能数子（对局手数不足或已结束）」、没有「正在数子…」、spy 被调两次;「局面变了」那条同样落在旧文案上)。

- [x] **Step 4: 实现前端**

`GamePage.tsx` 状态声明区(`const [countError, setCountError] = useState<string | null>(null);` 之后)加:

```tsx
  // A12:数子可能要等几秒(当前手没有分数时服务端先补一次分析,上限 15 秒)。
  // ref 挡同一帧里的连点(state 要等下一次渲染才看得见),state 负责屏上那句「正在数子…」。
  const countingRef = useRef(false);
  const [counting, setCounting] = useState(false);
```

`const isRanked = isRankedGameType(gameState.game_type);` 之后加:

```tsx
  // A12:数子失败**按服务端给的原因**说话。从前一律「对局手数不足或已结束」,
  // 把盒上最常见的「这一手还没有分数」也说成了手数不够。
  const countFailureMessage = (message: string) =>
    message.includes('Cannot count before') ? t('game:count_too_early', '手数还不够，暂时不能数子')
    : message.includes('already over') ? t('game:count_game_over', '这一局已经结束了')
    : message.includes('Position changed') ? t('game:count_position_changed', '数子这几秒里局面变了，请重新数子')
    : message.includes('only allowed on the human turn') ? t('game:count_not_your_turn', '轮到你落子时才能数子')
    : message.includes('Analysis not available') ? (isRanked
      ? t('game:count_ranked_unscored', '升降级对局现在数不了子（本局不做形势分析）')
      : t('game:count_no_score', '形势分析没算出来，暂时数不了子，请稍后再试'))
    : t('game:count_failed', '数子没有成功，请稍后再试');
```

`handleAction` 的 `count` 分支整段替换为:

```tsx
    if (action === 'count') {
      // 数子:人机 / 本地对局由服务端当场数完并结束对局(没有对手握手)。
      if (!sessionId || countingRef.current) return;
      countingRef.current = true;
      setCounting(true);
      try {
        const res = await API.requestCount(sessionId);
        if (res?.state) session.setGameState(res.state);
      } catch (e) {
        setCountError(countFailureMessage(e instanceof Error ? e.message : ''));
      } finally {
        countingRef.current = false;
        setCounting(false);
      }
      return;
    }
```

在 `{/* Count (数子) error toast */}` 那个 `Snackbar` 之前加:

```tsx
      {/* 数子在途 —— 服务端可能正在给这一手补分析,这几秒里屏上不能什么都不说 */}
      <Snackbar open={counting} anchorOrigin={{ vertical: 'top', horizontal: 'center' }}>
        <Alert severity="info">{t('game:counting', '正在数子…')}</Alert>
      </Snackbar>
```

- [x] **Step 5: 验证并提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
npx vitest run src/kiosk/pages/GamePage.playAi.test.tsx src/kiosk/pages/GamePage.test.tsx src/kiosk/__tests__/GamePageEngine.test.tsx
npx tsc -b && echo TSC_OK
npx eslint src/kiosk/pages/GamePage.tsx
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
# 基线 diff(后端 + 前端)，两个 comm -13 均须为空
CI=true uv run pytest tests --continue-on-collection-errors -q -rfE -p no:cacheprovider 2>&1 | tee /tmp/kgpa-now-pytest.log
grep -E '^(FAILED|ERROR) tests/' /tmp/kgpa-now-pytest.log | sed -E 's/ - .*//' | LC_ALL=C sort -u > /tmp/kgpa-now-pytest-failed.txt
LC_ALL=C comm -13 /tmp/kgpa-baseline/pytest-failed.txt /tmp/kgpa-now-pytest-failed.txt   # 期望:无输出
git restore --source=HEAD -- katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json
rm -f test_user_data.db
git status --short katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json test_user_data.db   # 期望:空
cd katrain/web/ui
npx vitest run --reporter=verbose 2>&1 | tee /tmp/kgpa-now-vitest.log
grep -E '^\s+×' /tmp/kgpa-now-vitest.log | sed -E 's/^\s+×\s+//; s/ [0-9]+ms$//' | LC_ALL=C sort -u > /tmp/kgpa-now-vitest-failed.txt
LC_ALL=C comm -13 /tmp/kgpa-baseline/vitest-failed.txt /tmp/kgpa-now-vitest-failed.txt   # 期望:无输出
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
git add katrain/web/interface.py katrain/web/server.py katrain/web/ui/src/kiosk/pages/GamePage.tsx \
  katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx tests/test_play_ai_endgame.py tests/web_ui/test_play_ai_endgame_api.py \
  tests/web_ui/test_ai_ladder_api.py
git diff --cached --stat
git commit -m "fix(play): 盒上数子几乎总是 400 且把原因说成手数不足 —— 服务端先补分再数,前端按真实原因说话

A12(P1)。board 模式不做逐手分析,数子原来全靠前端「图表」开关每手补分。新增 ensure_current_score
(升降级局不补,等 Fan 拍板),/api/count/request 放线程里等它;数子在途说「正在数子…」。
等分析期间对局被结束或局面变了,数子不改写(await 前取节点,_commit_end_state 在锁里复核,先写者胜 → 409)。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```
**必须上板**(记进 Task 12 清单):RK3562 上自由对弈关掉领地与图表,第 100 手后点数子,记录从点击到出结果的耗时。

---

### Task 5: N22 终局收尾一个函数:双停先补分再落账;AI 收尾的局也落账/进结算

**Files:**
- Modify: `katrain/web/interface.py`(`__init__` 加 `game_ended_callback`;`_do_ai_move_and_broadcast`(`:1084-1095`)在 AI 线程写出新的终局事实时调它一次)
- Modify: `katrain/web/session.py:6-12`(typing import 与 `GameEnd` import)、`:15-33`(`WebSession` 加 `end_game_lock`)、`:36-45`(`SessionManager.__init__` 加 `on_game_ended`)、`create_session`(`:80-81`,装 `game_ended_callback`)+ 新方法 `_on_game_ended` / `_schedule_game_ended`。**`_on_state` 不动**(理由见 Step 2)
- Modify: `katrain/web/server.py`:模块级 `_count_result` 之后加 `_new_terminal`;`_complete_count` 之后 / `@app.post("/api/count/request")` 之前(新增 `_score_two_pass_end` / `_finish_ended_game` / `_on_game_ended_off_request` 并装到 `manager`);四个终局请求入口的收尾段 —— `/api/move`(`:990-1003`)、`/api/resign`(Task 2 改过的锁块与单机落账支)、`/api/count/request` 单机分支、`/api/timeout`(Task 2 改过的锁块与单机落账支);`_record_ai_game_locked` 升降级分支读结果那一行(`:1714`)
- Modify(测试替身): `tests/web_ui/test_ai_game_autosave.py::_make_mock_session`(`:18` 起)
- Create: `tests/web_ui/test_game_end_hook.py`
- Test: `tests/test_play_ai_endgame.py`(追加)

**Interfaces:**
- Consumes: Task 2 的 `GameEnd` / `WebGame.terminal` / `_commit_end_state(…, fill_pending=True)` / `record_two_pass_end`;Task 4 的 `ensure_current_score(node=)`、`_terminal_of`、`_count_result`、`web_client` / `_two_human_guest_game`;既有 `_record_ai_game(session, app, current_user, result)`(不改)
- Produces:
  - `_complete_count(session, app, current_user, node=None) -> str`（覆盖 Task 4 的 `tuple[str, bool]`；收尾由调用方拿新 GameEnd 触发）
  - `WebSession.end_game_lock: asyncio.Lock`
  - `WebKaTrain.game_ended_callback: Optional[Callable[[GameEnd], None]]`(**只有 AI 后台线程调**:`_do_ai_move_and_broadcast` 结束时这一局的终局事实与开始时不是同一个)
  - `SessionManager.on_game_ended: Optional[Callable[[WebSession, GameEnd], Awaitable[None]]]`(server 装上;`create_session` 把 `katrain.game_ended_callback` 接到 `SessionManager._on_game_ended(session_id, end)`,后者置 `game_ended` 并对非研究模式的会话调度一次钩子);`SessionManager._schedule_game_ended(session, end)`
  - server 模块级 `_new_terminal(session, before) -> Optional[GameEnd]`(`after is not None and after is not before`);server 闭包 `async _score_two_pass_end(session, end: GameEnd) -> Optional[GameEnd]`、
    `async _finish_ended_game(session, app, current_user, end: GameEnd) -> None`(`end` 必填、无默认值)、`async _on_game_ended_off_request(session, end)`;测试钩子 `katrain.web.server._FINISH_ENDED_GAME_FN`
  - 删掉旧版 plan 的 `_apply_counted_result`:写入职责归 `_commit_end_state`,格式化归 `_count_result`

- [ ] **Step 1: 写失败的测试**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
git ls-files tests/web_ui/test_game_end_hook.py; ls tests/web_ui/test_game_end_hook.py   # 期望:都没有
```

`tests/web_ui/test_game_end_hook.py`:

```python
"""N22:对局在**请求之外**结束(AI 后台线程下出双停第二手 / AI 认输)时,SessionManager 要把收尾交给事件循环。

从前 AI 线程结束对局时 `_on_state` 只置 `game_ended`,不落账:由 AI 收尾的局不进对局记录,升降级局不进结算、心跳停掉。

触发点是 `WebKaTrain.game_ended_callback`(只有 AI 线程调),**不是** `_on_state` 里「end_result 由无变有」——
后者在「对局会话里载入一份 SGF 再翻到双停终点」时同样成立(galaxy `ZenModeApp` 就用 play 会话 `loadSGF`),
会把一份不是在这里下的棋谱补分、再记成这个用户的对局。「每局只收尾一次」由 server 的 `_finish_ended_game` 保证。
"""

import asyncio
from unittest.mock import MagicMock

from katrain.web.models import GameEnd
from katrain.web.session import SessionManager, WebSession

#: 钩子只转发,不看里面装的是什么;真对象的收尾在 tests/test_play_ai_endgame.py 证。
END = GameEnd(None, None, "B+R")


async def _manager_with_hook(session):
    manager = SessionManager(enable_engine=False)
    manager._sessions[session.session_id] = session
    manager.attach_loop(asyncio.get_running_loop())
    seen = []

    async def hook(s, end):
        seen.append((s.session_id, end))

    manager.on_game_ended = hook
    return manager, seen


async def test_the_ai_thread_ending_a_game_runs_the_hook():
    session = WebSession(session_id="s-ai-pass", katrain=MagicMock())
    manager, seen = await _manager_with_hook(session)
    # AI 线程就是从事件循环以外的线程回调的
    await asyncio.to_thread(manager._on_game_ended, session.session_id, END)
    await asyncio.sleep(0.05)
    assert seen == [("s-ai-pass", END)]  # 捕获的终局事实原样交给收尾(C4),不在事件循环里按游标重推
    assert session.game_ended is True


async def test_research_sessions_never_run_the_hook():
    """研究模式载入一份带结果的棋谱不是「下完了一局」,不许被当成对局记下来。"""
    session = WebSession(session_id="s-research", katrain=MagicMock(), mode="research")
    manager, seen = await _manager_with_hook(session)
    await asyncio.to_thread(manager._on_game_ended, session.session_id, END)
    await asyncio.sleep(0.05)
    assert seen == []


async def test_a_broadcast_that_merely_shows_an_ended_game_does_not_run_the_hook():
    """翻到载入棋谱的双停终点同样会推一帧带 end_result 的状态 —— 那不是在这里下完的一局。"""
    session = WebSession(session_id="s-nav", katrain=MagicMock())
    manager, seen = await _manager_with_hook(session)
    await asyncio.to_thread(manager._on_state, session.session_id, {"end_result": "B+R"})
    await asyncio.sleep(0.05)
    assert seen == []
    assert session.game_ended is True  # `_on_state` 原有语义不变(心跳靠它停)


def test_create_session_wires_the_ai_thread_callback(monkeypatch):
    """接线只有一行;漏了它,上面几条全绿而 N22 在真机上整条是死的。"""
    import katrain.web.session as session_module

    monkeypatch.setattr(session_module, "WebKaTrain", MagicMock())
    manager = SessionManager(enable_engine=False)
    session = manager.create_session(user_id=7)
    called = []
    monkeypatch.setattr(manager, "_on_game_ended", lambda sid, end: called.append((sid, end)))
    session.katrain.game_ended_callback(END)
    assert called == [(session.session_id, END)]
```

追加到 `tests/test_play_ai_endgame.py` 末尾:

```python
# ---------------------------------------------------------------- N22 终局收尾


import asyncio  # noqa: E402
import time  # noqa: E402
import types  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402


@pytest.fixture(scope="module")
def server_module():
    import katrain.web.server as server

    # `_FINISH_ENDED_GAME_FN` 是 create_app 里的闭包,建一次 app 才会挂到模块上(同 tests/test_local_play_recording.py)
    server.create_app(enable_engine=False)
    return server


def _ended_session(*, how="two_pass", game_type="free", user_id=42, mode="play"):
    """真 WebKaTrain + 真 WebSession(r1:MagicMock 版证不出「补分写在哪一手」):两人座位下 B、W 各一手,
    再按 `how` 结束 —— 双停(终局事实已记、结果待补分)或认输(两人座位、轮到黑 ⇒ 黑认输,`W+R`)。
    返回 `(session, end)`;`end` 就是这一局的终局事实,收尾函数只认它,不看游标。
    `game_type` 同时写在会话和运行时上:`"ranked"` 让 `analysis_allowed` 为假,又不走升降级账本那一支。"""
    from katrain.web.session import WebSession

    w = _web_katrain()
    _seat(w, human_colors={"B", "W"})
    w._do_play((3, 3), guard=True)
    w._do_play((15, 15), guard=True)
    if how == "two_pass":
        w._do_play(None, guard=True)
        w._do_play(None, guard=True)
    else:
        w._do_resign()
    w.game_type = game_type
    session = WebSession(session_id=f"s-{how}-{game_type}-{mode}", katrain=w, user_id=user_id, mode=mode)
    session.game_type = game_type
    return session, w.game.terminal


def _recording_app():
    app = MagicMock()
    app.state.repository_dispatcher.user_games_create = AsyncMock(return_value={"id": "g1"})
    return app


_USER = types.SimpleNamespace(id=42, username="小明")


def test_create_app_installs_the_off_request_hook(server_module):
    app = server_module.create_app(enable_engine=False)
    assert app.state.session_manager.on_game_ended is not None


class _Reply(ai.AIStrategy):
    """AI 线程的桩策略:回 `REPLY`(None = 停一手)。走真 `generate_ai_move` —— 双停终局事实是在它的提交段里记的,
    直接调 `game.play` 的替身会绕过那一步(r1)。"""

    REPLY = None

    def generate_move(self):
        return Move(coords=type(self).REPLY, player=self.cn.next_player), "reply"


def _ai_thread_game(monkeypatch, human_first, ai_reply, step_back_on_broadcast=False):
    """真 WebKaTrain:人(黑)先下 `human_first`,AI 线程(`_do_ai_move_and_broadcast`)回 `ai_reply`。
    `ai:default` 换成桩策略;`update_state` 置空 —— 只证回调,不起下一条 AI 线程。
    `step_back_on_broadcast=True`:广播那一刻人点了「上一手」(`update_state` 里悔一手)。"""
    w = _web_katrain()
    _seat(w, human_colors={"B"})
    w._do_play(human_first, guard=True)
    calls = []
    w.game_ended_callback = lambda end: calls.append(end)
    if step_back_on_broadcast:
        w.update_state = lambda **_kwargs: w.game.undo(1)
    else:
        w.update_state = lambda **_kwargs: None
    monkeypatch.setattr(_Reply, "REPLY", ai_reply)
    monkeypatch.setitem(ai.STRATEGY_REGISTRY, AI_DEFAULT, _Reply)
    w._do_ai_move_and_broadcast(w.game.current_node)
    return w, calls


def test_the_ai_thread_reports_a_game_it_ended(monkeypatch):
    """人先停一手、AI 跟停 —— 盒上最常见的收官。这条回调就是 N22 收尾在 AI 这条路上的唯一入口。"""
    w, calls = _ai_thread_game(monkeypatch, human_first=None, ai_reply=None)
    assert len(calls) == 1
    assert calls[0] is w.game.terminal and calls[0].node.is_pass


def test_the_ai_thread_captures_the_end_before_anyone_can_step_back(monkeypatch):
    """C4:广播之后人立刻点「上一手」,回调拿到的仍是那一局、那一手的终局事实。
    错误实现(在 `update_state()` 之后按游标取 `end_result`)在这里一次都不叫。"""
    w, calls = _ai_thread_game(monkeypatch, human_first=None, ai_reply=None, step_back_on_broadcast=True)
    assert len(calls) == 1
    assert calls[0].node.is_pass and calls[0].node.parent.is_pass
    assert w.game.current_node is calls[0].node.parent  # 游标确实被挪走了


def test_an_ordinary_ai_move_reports_nothing(monkeypatch):
    """正对照:没结束就不叫 —— 否则上一条的「叫了一次」可能只是每手都叫。"""
    _, calls = _ai_thread_game(monkeypatch, human_first=(3, 3), ai_reply=(15, 15))
    assert calls == []


async def test_two_pass_end_is_scored_before_it_is_recorded(server_module):
    session, end = _ended_session()
    assert end is not None and end.node.end_state is None  # 双停:终局事实已记,结果待补分
    asked = []
    session.katrain.ensure_current_score = lambda timeout_s=None, node=None: asked.append(node) or 2.5
    app = _recording_app()

    await server_module._FINISH_ENDED_GAME_FN(session, app, _USER, end)

    assert asked == [end.node]  # 补的是终局那一手
    data = app.state.repository_dispatcher.user_games_create.await_args.kwargs["data"]
    assert data["result"] == "B+2.5"
    assert end.node.end_state == "B+2.5"
    assert session.katrain.game.terminal.result == "B+2.5"


async def test_games_that_forbid_analysis_are_recorded_without_a_score(server_module):
    """升降级局走的就是这一支:不补分,照旧按「终局」落账(无结论)—— 怎么判目等 Fan 拍板。"""
    session, end = _ended_session(game_type="ranked")
    asked = []
    session.katrain.ensure_current_score = lambda timeout_s=None, node=None: asked.append(node)
    app = _recording_app()

    await server_module._FINISH_ENDED_GAME_FN(session, app, _USER, end)

    assert asked == []
    data = app.state.repository_dispatcher.user_games_create.await_args.kwargs["data"]
    assert data["result"] == end.result
    assert end.node.end_state is None


async def test_a_resigned_game_is_recorded_as_is(server_module):
    session, end = _ended_session(how="resign")
    asked = []
    session.katrain.ensure_current_score = lambda timeout_s=None, node=None: asked.append(node)
    app = _recording_app()

    await server_module._FINISH_ENDED_GAME_FN(session, app, _USER, end)

    assert asked == []
    assert app.state.repository_dispatcher.user_games_create.await_args.kwargs["data"]["result"] == "W+R"


async def test_request_and_ai_thread_finishing_together_score_and_record_once(server_module):
    session, end = _ended_session()
    calls = []
    session.katrain.ensure_current_score = lambda timeout_s=None, node=None: calls.append(node) or 2.5
    app = _recording_app()

    await asyncio.gather(
        server_module._FINISH_ENDED_GAME_FN(session, app, _USER, end),
        server_module._FINISH_ENDED_GAME_FN(session, app, _USER, end),
    )

    assert len(calls) == 1
    create = app.state.repository_dispatcher.user_games_create
    assert create.await_count == 1
    assert create.await_args.kwargs["data"]["result"] == "B+2.5"  # 后到的那次收尾认的是补过分的终局事实


@pytest.mark.parametrize("action,score", [("undo", 2.5), ("undo", None), ("new_game", 2.5)])
async def test_stepping_back_or_starting_over_while_the_end_is_scored(server_module, action, score):
    """C4:收尾按捕获的终局落账,不看游标。补分的那几秒里人点了「上一手」或开了新局:
    落账的是**那一局那一手**(新局就不落),游标留在人挪到的地方,结果不写到游标那一手上。"""
    session, end = _ended_session()
    w = session.katrain

    def scoring(timeout_s=None, node=None):
        if action == "undo":
            with session.lock:
                w("undo", 1)
        else:
            w._do_new_game()
        return score if node is end.node else 99.0

    w.ensure_current_score = scoring
    app = _recording_app()

    await server_module._FINISH_ENDED_GAME_FN(session, app, _USER, end)

    create = app.state.repository_dispatcher.user_games_create
    if action == "new_game":
        create.assert_not_awaited()  # 旧局的 SGF 已经不在会话上,落了就是把新局的空谱记成那一局
        return
    assert w.game.current_node is end.node.parent
    assert create.await_count == 1
    assert create.await_args.kwargs["data"]["result"] == ("B+2.5" if score is not None else end.result)
    assert end.node.parent.end_state is None


async def test_multiplayer_research_and_guest_games_are_not_recorded_here(server_module):
    lobby, lobby_end = _ended_session()
    lobby.player_b_id, lobby.player_w_id = 1, 2
    research, research_end = _ended_session(mode="research")
    guest, guest_end = _ended_session(user_id=None)
    asked = {"lobby": [], "research": []}
    lobby.katrain.ensure_current_score = lambda timeout_s=None, node=None: asked["lobby"].append(node)
    research.katrain.ensure_current_score = lambda timeout_s=None, node=None: asked["research"].append(node)
    guest.katrain.ensure_current_score = lambda timeout_s=None, node=None: 1.5
    app = _recording_app()

    await server_module._FINISH_ENDED_GAME_FN(lobby, app, _USER, lobby_end)
    await server_module._FINISH_ENDED_GAME_FN(research, app, _USER, research_end)
    await server_module._FINISH_ENDED_GAME_FN(guest, app, None, guest_end)

    assert asked == {"lobby": [], "research": []}
    assert guest_end.node.end_state == "B+1.5"  # 游客的局照样分出胜负,只是不落账
    app.state.repository_dispatcher.user_games_create.assert_not_awaited()


def test_a_resign_on_a_game_already_being_finished_returns_at_once(web_client):
    """评审 r1 M1:撞上已结束的认输是空操作 —— 不许排进正在补分的那次收尾后面(最多 15 秒),也不许再补一次分。
    真实触发路径:galaxy 离页即认输、kiosk 引擎出错框的「认输」、连点。

    双停第二手的 `/api/move` 在补分里被挡住;挡住期间另起线程发 `/api/resign`,最多等 1 秒。
    错误实现(收尾看的是「这局结束过」而不是「这次请求写出了终局」)下认输排在 `end_game_lock` 后面:
    1 秒到了照样放行补分,认输随后进收尾、**再补一次分**(第二次调用立即返回)—— 不会挂死,只会红。"""
    sid, w = _two_human_guest_game(web_client, [None])  # 黑先停一手
    calls = []
    resign = {}

    def blocking_score(timeout_s=None, node=None):
        calls.append(node)
        if len(calls) == 1:
            started = time.monotonic()

            def send():
                resign["response"] = web_client.post("/api/resign", json={"session_id": sid})
                resign["elapsed"] = time.monotonic() - started

            sender = threading.Thread(target=send, daemon=True)
            sender.start()
            sender.join(1.0)
            resign["thread"] = sender
        return None  # 补不出分:收尾照「终局」处理

    w.ensure_current_score = blocking_score
    r = web_client.post("/api/move", json={"session_id": sid, "pass_move": True})  # 白跟停 ⇒ 双停

    resign["thread"].join(5)
    assert r.status_code == 200, r.text
    assert resign["response"].status_code == 200, resign["response"].text
    assert resign["elapsed"] < 1.0, "认输排在补分后面等了"
    assert len(calls) == 1
    assert w.game.terminal.node.end_state is None  # 认输没有改写双停终局
```

Run（分两条）：

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai && CI=true uv run pytest tests/test_play_ai_endgame.py -q
CI=true uv run pytest tests/web_ui/test_game_end_hook.py -q
```
Expected: hook 文件里 `test_the_ai_thread_ending_a_game_runs_the_hook`、`test_research_sessions_never_run_the_hook`(两条都是 `AttributeError: … '_on_game_ended'`)、
`test_create_session_wires_the_ai_thread_callback`(`called == []`:`game_ended_callback` 没装,调到的是替身属性)FAIL,`test_a_broadcast_that_merely_shows…` PASS(现状本来就不叫);
根目录文件里:
- `test_create_app_installs_the_off_request_hook` 与 6 条 `_FINISH_ENDED_GAME_FN` 用例(含 `test_stepping_back_or_starting_over_while_the_end_is_scored` 3 格)FAIL(`AttributeError: module 'katrain.web.server' has no attribute '_FINISH_ENDED_GAME_FN'`);
  这些用例改用真对象之后,各自在错误实现下的红法:比游标 + 游标回退值 → 两个 `undo` 格记不上;结果写到游标那一手 → `parent.end_state` 非空;补分漏传 `node` → 得到 `B+99.0`;
  收尾拽回游标 → `current_node` 断言红;换局后不放弃 → `new_game` 格落了账;不在 `end_game_lock` 下串行或后到者不认补过的分 → `calls` 为 2 或结果不是 `B+2.5`。
- `test_the_ai_thread_reports_a_game_it_ended`、`test_the_ai_thread_captures_the_end_before_anyone_can_step_back` FAIL(`calls == []`)。
- `test_a_resign_on_a_game_already_being_finished_returns_at_once` FAIL(`/api/move` 还不补分,`blocking_score` 从没被调:`KeyError: 'thread'`)。
- `test_an_ordinary_ai_move_reports_nothing` PASS。

- [ ] **Step 2: 实现 `interface.py` 与 `session.py`**

**为什么触发点放在 AI 线程、不放在 `_on_state`**:`_on_state` 看到的是「这一帧状态带 `end_result`」,它分不出「这一局刚在这里下完」和
「有人把一份载入的 SGF 翻到了双停终点」(galaxy `ZenModeApp` 就是 play 会话 + `loadSGF`)。放在那里会把别人的棋谱补分、再记成这个用户的对局。
人发出的四条路(`/api/move` 双停、认输、超时、数子)各自在请求里收尾;缺的只有 AI 线程这一条,所以只补这一条。

`interface.py` `__init__` 里 `self.update_state_callback: Optional[Callable] = None` 之后加:

```python
        # N22:AI 后台线程写出新的终局事实(AI 跟停 / AI 认输)时调一次,参数是那个 `GameEnd`;SessionManager 装上。
        self.game_ended_callback: Optional[Callable[[GameEnd], None]] = None
```

`_do_ai_move_and_broadcast` 整段替换为(`finally` 里原有那段注释照抄保留):

```python
    def _do_ai_move_and_broadcast(self, cn):
        """Background thread: generate AI move then broadcast state update."""
        game = self.game
        before = getattr(game, "terminal", None)
        try:
            self._do_ai_move(cn)
        except Exception as e:
            self.log(f"Error in AI move generation: {e}", OUTPUT_ERROR)
        finally:
            self._ai_move_pending = False
            # r1 C4:终局事实要在 update_state() **之前**取 —— 广播之后人可能立刻点「上一手」,
            # 而收尾要的是「哪一局、在哪一手结束」,不是游标此刻在哪。
            end = getattr(game, "terminal", None) if game is not None else None
            # Use update_state() instead of bare callback — this both broadcasts
            # AND re-runs _do_update_state(), which re-triggers AI if the game
            # tree changed (e.g., user undid + replayed while this thread ran).
            self.update_state()
            # N22:这条线程跑完时这一局的终局事实与开始时不是同一个 —— 告诉会话去收尾(补分、落账、进结算)。
            # 用「不是同一个」而不是「开始时没有」:悔棋另开分支后的第二次终局也要叫(局面线语义,评审 r1 M2)。
            # 若终局是人在生成期间发请求写的,这里也会叫一次,与请求自己的收尾在 `end_game_lock` 下串行,
            # `_recorded` 让第二次落账成为空操作 —— 有意接受的重复调用,不另立判别位。
            callback = getattr(self, "game_ended_callback", None)
            if callback is not None and end is not None and end is not before and self.game is game:
                try:
                    callback(end)
                except Exception as e:
                    self.log(f"Error in game-ended callback: {e}", OUTPUT_ERROR)
```

`session.py`:

typing import 行改为 `from typing import Awaitable, Callable, Dict, Optional, Set, List`;`from katrain.web.interface import WebKaTrain` 之后加 `from katrain.web.models import GameEnd`。

`WebSession` 里 `record_game_lock` 那一行之后加:

```python
    # N22:终局收尾(先补分、再落账)的会话级串行锁。人发出的双停第二手和 AI 线程触发的收尾可能同时到,
    # 不串行的话先落账的那一方会把「终局」写进账,补出来的分数就再也进不去了(`_recorded` 已置)。
    end_game_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)
```

`SessionManager.__init__` 末尾加:

```python
        #: N22:对局在**请求之外**结束(AI 后台线程下出双停第二手 / AI 认输)时调用的收尾函数,由 server.py 装上。
        #: 人发出的请求自己也调同一个函数;两边靠 `WebSession.end_game_lock` 与 `_record_ai_game` 的幂等只收尾一次。
        self.on_game_ended: Optional[Callable[[WebSession, GameEnd], Awaitable[None]]] = None
```

`create_session` 里 `session.katrain.message_callback = lambda …` 那一行之后加:

```python
        session.katrain.game_ended_callback = lambda end, sid=session_id: self._on_game_ended(sid, end)
```

**`_on_state` 不改**(它照旧置 `game_ended`,升降级心跳靠它停)。在 `_on_message` 之前加:

```python
    def _on_game_ended(self, session_id: str, end: GameEnd):
        """AI 后台线程写出新的终局事实时由 `WebKaTrain.game_ended_callback` 调(N22)。只有这一个触发点 ——
        `_on_state` 分不出「刚在这里下完」和「翻到了一份载入棋谱的双停终点」。
        `end` 是 AI 线程在广播**之前**捕获的终局事实,原样交给收尾;事件循环里不按游标重推(r1 C4)。"""
        try:
            session = self.get_session(session_id)
        except KeyError:
            return
        session.game_ended = True
        self._schedule_game_ended(session, end)

    def _schedule_game_ended(self, session: WebSession, end: GameEnd):
        """把收尾交给事件循环。研究模式不收尾:那里下出的双停不是「下完了一局」。"""
        hook = self.on_game_ended
        if hook is None or session.mode == "research":
            return
        if not self._loop or not self._loop.is_running():
            return

        def _log_failure(fut):
            if fut.cancelled():
                return
            exc = fut.exception()
            if exc is not None:
                logging.getLogger("katrain_web").error("game-ended hook failed for %s: %s", session.session_id, exc)

        if threading.get_ident() == self._loop_thread_id:
            self._loop.create_task(hook(session, end)).add_done_callback(_log_failure)
        else:
            asyncio.run_coroutine_threadsafe(hook(session, end), self._loop).add_done_callback(_log_failure)
```

- [ ] **Step 3: 实现 `server.py`**

① 模块级 `_count_result`(Task 4 加的)之后加:

```python


def _new_terminal(session, before):
    """派发之后这一局的终局事实,**仅当它是这次派发造出来的**(与 `before` 不是同一个);否则 None。

    评审 r1 M1:只看「这局结束过没有」的话,撞上已结束的认输 / 超时 / 落子也会进收尾 —— 排在正在补分的那次收尾
    后面等最多 15 秒,还可能再补一次分。认输 / 超时另有 `wrote` 闸。"""
    after = _terminal_of(session)
    return after if after is not None and after is not before else None
```

② `_complete_count` 函数结束之后(`@app.post("/api/count/request")` 之前)加:

```python
    async def _score_two_pass_end(session, end):
        """双方各停一手结束、还没有胜负的局:补一次分析,按数子的格式写在**终局那一手**上。
        返回补上后的 `GameEnd`;没补(不是双停 / 不许分析 / 补不出分 / 被别人抢先)返回 None。

        升降级局不补(`analysis_allowed` 为假,interface 的 `ensure_current_score` 也不补),照旧记「无结论」;
        升降级怎么判目等 Fan 拍板(PRD §4 A12-R)。补的是 `end.node` 不是游标;写入走
        `_commit_end_state(…, fill_pending=True)`:等分析的这几秒里局面被换掉 / 终局被别人先补上,它在对局提交锁里拒绝,
        这里就放弃(r1 C4)。"""
        if session.katrain.game is not end.game or end.node.end_state:
            # 换了局 —— 下面的 `analysis_allowed` 就属于新局了(评审 r1 m8)—— 或者这一手已经有结果
            return None
        if not getattr(session.katrain, "analysis_allowed", False):
            return None
        score = await asyncio.to_thread(session.katrain.ensure_current_score, node=end.node)
        if score is None:
            return None
        result, _ = _count_result(score)
        with session.lock:
            try:
                filled = session.katrain._commit_end_state(result, node=end.node, fill_pending=True)
            except EndgameConflict:
                return None
            session.game_ended = True
            session.last_state = session.katrain.get_state()
        session.katrain.update_state()  # 推给前端:结果从「终局」变成「黑+3.5」;在两把锁之外调
        return filled

    async def _finish_ended_game(session, app, current_user, end):
        """对局结束后的收尾 —— 人发出的四个请求(`/api/move` 双停、认输、超时、数子)与 AI 后台线程
        (`manager.on_game_ended`)共用这一个函数(N22;prd §6.0 第 1 条的唯一入口)。

        `end` 必填、不给默认值:调用方捕获的终局事实(请求路径是「本次请求造出来的」,AI 线程是「这条线程写出来的」)。
        按它落账,不看游标 —— 补分的几秒里人点「上一手」、开新局,都不影响记的是哪一局哪一手(r1 C4)。
        顺序是承重的:**先补分,再落账**。`_record_ai_game` 落过一次就置 `_recorded`,之后补出的分数进不了账;
        所以两条路在 `end_game_lock` 下串行,且都先走补分。
        多人局 / 跨平台局在各自端点里落账并广播 `game_end`,不走这里 —— 合并跨平台 N13 时,星阵人机局在下面这条早退
        **之前**分流(见 Task 12「合并指引」)。研究模式里按出的双停不是「下完了一局」(PRD N22 验收 3)。
        游客局照样补分出胜负,只是不落账。"""
        if session.player_b_id is not None or session.player_w_id is not None:
            return
        if getattr(session, "mode", "play") == "research":
            return
        lock = getattr(session, "end_game_lock", None)
        if not isinstance(lock, asyncio.Lock):
            lock = asyncio.Lock()
            session.end_game_lock = lock
        log = logging.getLogger("katrain_web")
        async with lock:
            if session.katrain.game is not end.game:
                log.warning("game-ended finish skipped for %s: the game was replaced before finishing", session.session_id)
                return
            filled = await _score_two_pass_end(session, end)
            if session.katrain.game is not end.game:
                # 等分析期间换了局:旧局的 SGF 已经不在会话上,落了就是把新局的空谱记成那一局
                log.warning("game-ended finish skipped for %s: the game was replaced while scoring", session.session_id)
                return
            terminal = getattr(end.game, "terminal", None)
            # 先到的那次收尾可能已经给同一手补过分(同一手、结果不同的 GameEnd)。另开分支后的终局(`node` 不同)
            # 是另一次收尾的事,这里不认。
            final = filled or (terminal if isinstance(terminal, GameEnd) and terminal.node is end.node else end)
            if current_user is not None and session.user_id is not None:
                await _record_ai_game(session, app, current_user, final.result)

    globals()["_FINISH_ENDED_GAME_FN"] = _finish_ended_game

    async def _on_game_ended_off_request(session, end):
        """AI 后台线程让对局结束时没有请求可取 `current_user`,按会话主人从库里取(盒上是本机影子用户)。"""
        user = None
        if session.user_id is not None:
            repo = getattr(app.state, "user_repo", None)
            user_dict = repo.get_user_by_id(session.user_id) if repo is not None else None
            user = User(**user_dict) if user_dict else None
        await _finish_ended_game(session, app, user, end)

    manager.on_game_ended = _on_game_ended_off_request
```

③ `_complete_count` 的返回值收成 `result`(单机那一支的「调用方落账」从此由收尾函数接手,`needs_record` 没有使用者了)。
函数 docstring 开头两行

```python
        """数子并结束对局。返回 `(result, needs_record)`:needs_record 为真时调用方在**放开 session.lock 之后**落账
        (单机 / 本地对局);多人局在这里同步记录并广播。
```

改为

```python
        """数子并结束对局,返回 `result`。单机 / 本地对局由调用方在放开 session.lock 之后经 `_finish_ended_game` 收尾;
        多人局在这里同步记录并广播。
```

多人局那一支的 `return result, False` 改为 `return result`;函数末尾

```python
        needs_record = current_user is not None and session.user_id is not None
        return result, needs_record
```

改为

```python
        return result
```

两处多人局调用(`/api/count/request` 的「对方也请求 = 接受」分支、`/api/count/respond` 的接受分支)里的 `result, _ = _complete_count(session, app, current_user)` 都改为 `result = _complete_count(session, app, current_user)`。

④ 四个终局请求入口只经 `_finish_ended_game`。共同写法:在 `session.lock` 里派发**之前**记 `before = _terminal_of(session)`,
派发之后 `end = _new_terminal(session, before)`(认输 / 超时再加 `wrote`),出锁后 `if end is not None: await _finish_ended_game(...)`,
收尾之后重读 `state`。

**`/api/move`**(Task 2 改过的 `:990-1003`)

```python
        with analysis_context:
            with session.lock:
                guard_ai_ladder_ranked_human_action(session, current_user, "play-move")
                # r1:非研究会话带 guard —— 这一手所在的局面线已结束 / 轮到 AI 就拒(409),双停第二手记终局事实。
                # 研究会话照旧打谱,不冻结。
                session.katrain("play", None if coords is None else tuple(coords), guard=session.mode != "research")
                state = session.katrain.get_state()
                session.last_state = state
        # Natural (two-pass) game end never hits resign/count/timeout — record here so
        # local face-to-face games ending by both passing are still saved (end_result
        # auto-becomes truthy on two consecutive passes; requestCount then refuses).
        is_multiplayer = session.player_b_id is not None or session.player_w_id is not None
        if state.get("end_result") and not is_multiplayer and current_user and session.user_id:
            await _record_ai_game(session, app, current_user, state["end_result"])
        return {"session_id": session.session_id, "state": state}
```

替换为

```python
        with analysis_context:
            with session.lock:
                guard_ai_ladder_ranked_human_action(session, current_user, "play-move")
                before = _terminal_of(session)
                # r1:非研究会话带 guard —— 这一手所在的局面线已结束 / 轮到 AI 就拒(409),双停第二手记终局事实。
                # 研究会话照旧打谱,不冻结。
                session.katrain("play", None if coords is None else tuple(coords), guard=session.mode != "research")
                end = _new_terminal(session, before)
                state = session.katrain.get_state()
                session.last_state = state
        # 自然终局(双停)不经过认输 / 数子 / 超时,在这里收尾:先补分出胜负,再落账(N22)。只收尾**这一手造出来的**终局(r1 M1)。
        # AI 线程下出双停第二手时走的是 `manager.on_game_ended`,两条路是同一个函数、会话内串行。
        # 收尾必须在 `analysis_context` 之外:`persistent_analysis_activity` 在 `activity.lock` 里 yield,那把锁不许跨 await。
        if end is not None:
            await _finish_ended_game(session, app, current_user, end)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}
```

**`/api/resign`**：完整替换 Task 2 版本。本地派发前后捕获位于同一 `session.lock`；平台 gateway await 前后单独捕获，不跨 await 持线程锁。

```python
    @app.post("/api/resign")
    async def resign(request: ToggleAnalysisRequest, current_user: User = Depends(get_current_user_optional)):
        session = _get_session_or_404(manager, request.session_id)
        guard_session_terminator(session, current_user, "resign")
        ranked_ai = is_ai_ladder_ranked_session(session)
        if ranked_ai:
            guard_ai_ladder_ranked_owner(session, current_user, "resign")
            await _guard_ai_ladder_cloud_active(app, session, current_user)

        # For multiplayer games, record the result
        is_multiplayer = session.player_b_id is not None or session.player_w_id is not None
        # r1:这次认输有没有真的写出终局。撞上一局已经结束过的(退出框在终局上点「认输并退出」、galaxy 离页即认输、
        # 连点、平台远端认输成功而本地早已结束)是 200 空操作:返回真实局面,不落账、不广播。
        # **在所有分支之前**赋值 —— 平台局也会走到下面的多人局落账,只在某一支里赋值就是 UnboundLocalError → 500(评审 r1 M4)。
        wrote = True
        end = None

        # Route through platform gateway for cross-platform games
        gateway = getattr(app.state, "platform_gateway", None)
        platform_game = bool(not ranked_ai and gateway and gateway.is_platform_game(request.session_id))
        if platform_game:
            from katrain.web.platforms.gateway import PlatformMoveRejectedError

            before = _terminal_of(session)

            try:
                user_id = current_user.id if current_user else 0
                await gateway.resign(request.session_id, user_id)
            except PlatformMoveRejectedError as e:
                raise HTTPException(status_code=409, detail=str(e))
            except EndgameConflict as e:
                # 远端认输已经成功,网关落回本地(`_local_resign`)时撞上本地早已结束的局:按空操作处理。
                if e.reason != "already_ended":
                    raise
                wrote = False

        if not platform_game:
            with session.lock:
                before = _terminal_of(session)
                try:
                    if ranked_ai:
                        snapshot = guard_ai_ladder_ranked_owner(session, current_user, "resign")
                        guard_ai_ladder_ranked_not_ended(session, "resign")
                        winner = "W" if snapshot.user_color == "B" else "B"
                        result = f"{winner}+R"
                        # r1:结果只经对局提交锁里的唯一写入口写(与 AI 提交、远端终局标记互斥)。
                        session.katrain._commit_end_state(result)
                        if hasattr(session.katrain, "_state"):
                            session.katrain._state["end_result"] = result
                        # This branch writes the result straight onto the tree instead of going
                        # through `session.katrain(...)`, so the `update_state` -> `_on_state`
                        # callback that normally sets `game_ended` never fires. Nothing else sets
                        # it on this path, and it is the only thing that stops the ranked heartbeat:
                        # without this line a resigned game goes on reporting a player at the board
                        # forever, the cloud reservation never becomes takeable, and the account is
                        # locked out of ranked play on every device it owns.
                        session.game_ended = True
                    else:
                        # N21:多人局按**请求者的座位**判负(`winner_id` 下面也是这么算的,两边必须一致);
                        # 单机局不传,交给 `_do_resign` 从座位推。
                        loser = None
                        if is_multiplayer and current_user is not None:
                            if current_user.id == session.player_b_id:
                                loser = "B"
                            elif current_user.id == session.player_w_id:
                                loser = "W"
                        if loser is None:
                            session.katrain("resign")
                        else:
                            session.katrain("resign", loser)
                except EndgameConflict as e:
                    if e.reason != "already_ended":
                        raise
                    wrote = False
                end = _new_terminal(session, before) if wrote else None
                state = session.katrain.get_state()
                session.last_state = state
        else:
            end = _new_terminal(session, before) if wrote else None
            state = session.katrain.get_state()
            session.last_state = state

        # Record game result for multiplayer
        if is_multiplayer and current_user and wrote:
            winner_id = session.player_w_id if current_user.id == session.player_b_id else session.player_b_id
            result = f"{'W' if winner_id == session.player_w_id else 'B'}+R"
            try:
                app.state.game_repo.record_multiplayer_game(
                    sgf_content=session.katrain.get_sgf(),
                    result=result,
                    game_type=getattr(session, "game_type", "free"),
                    black_id=session.player_b_id,
                    white_id=session.player_w_id,
                )
            except Exception as e:
                logging.getLogger("katrain_web").error(f"Failed to record game result: {e}")

            # 广播**不在** try 里:它告诉对面「这局结束了」,而 try 守的是落账。
            # 两件事捆在一个 try 里时,落账一失败对面就永远收不到终局 —— 盒上
            # `app.state.game_repo` 恒为 None(`server.py` board 模式那一段),
            # 于是这条路上每一次认输/超时都会静默地把对面挂在「还在等你走」。
            # 数子(`_complete_count`)和退出(forfeit)两处本来就是这么写的,这里对齐。
            manager._schedule_broadcast(
                session,
                {"type": "game_end", "data": {"reason": "resign", "winner_id": winner_id, "result": result}},
            )
        elif not is_multiplayer and end is not None:
            await _finish_ended_game(session, app, current_user, end)
            state = session.katrain.get_state()
            session.last_state = state

        return {"session_id": session.session_id, "state": state}
```

**`/api/count/request` 单机分支**(Task 4 版)

```python
            node = session.katrain.game.current_node
            await asyncio.to_thread(session.katrain.ensure_current_score, node=node)
            with session.lock:
                guard_ai_ladder_ranked_human_action(session, current_user, "request-count")
                result, needs_record = _complete_count(session, app, current_user, node=node)
                state = session.katrain.get_state()
                session.last_state = state
            if needs_record:
                await _record_ai_game(session, app, current_user, result)
            return {"session_id": session.session_id, "state": state, "result": result}
```

替换为

```python
            node = session.katrain.game.current_node
            await asyncio.to_thread(session.katrain.ensure_current_score, node=node)
            with session.lock:
                guard_ai_ladder_ranked_human_action(session, current_user, "request-count")
                before = _terminal_of(session)
                result = _complete_count(session, app, current_user, node=node)
                end = _new_terminal(session, before)
                state = session.katrain.get_state()
                session.last_state = state
            if end is not None:
                await _finish_ended_game(session, app, current_user, end)
                state = session.katrain.get_state()
                session.last_state = state
            return {"session_id": session.session_id, "state": state, "result": result}
```

**`/api/timeout`**(Task 2 版)两处:

```python
        wrote = True
        with session.lock:
            guard_ai_ladder_ranked_human_action(session, current_user, "timeout")
            try:
                session.katrain("timeout")
            except EndgameConflict as e:
                if e.reason != "already_ended":
                    raise
                wrote = False
            state = session.katrain.get_state()
            session.last_state = state
```

替换为

```python
        wrote = True
        with session.lock:
            guard_ai_ladder_ranked_human_action(session, current_user, "timeout")
            before = _terminal_of(session)
            try:
                session.katrain("timeout")
            except EndgameConflict as e:
                if e.reason != "already_ended":
                    raise
                wrote = False
            end = _new_terminal(session, before) if wrote else None
            state = session.katrain.get_state()
            session.last_state = state
```

```python
        elif not is_multiplayer and current_user and session.user_id:
            result = session.katrain.game.end_result
            if result:
                await _record_ai_game(session, app, current_user, result)
```

替换为

```python
        elif not is_multiplayer and end is not None:
            await _finish_ended_game(session, app, current_user, end)
            state = session.katrain.get_state()
            session.last_state = state
```

⑤ `_record_ai_game_locked` 升降级分支(`:1714`)

```python
                actual_result = state.get("end_result") or getattr(session.katrain.game, "end_result", None)
```

替换为

```python
                # r1 m11:结果认这一局的终局事实,不认游标。今天升降级禁悔棋 / 禁导航,两者恒等 —— 所以这一行
                # **没有能在错实现下变红的用例**;守的是放开导航的那一天,落账不跟着游标漏。
                terminal = _terminal_of(session)
                actual_result = (
                    (terminal.result if terminal is not None else None)
                    or state.get("end_result")
                    or getattr(session.katrain.game, "end_result", None)
                )
```

⑥ 测试替身跟上「只收尾本次请求写出来的终局」:`tests/web_ui/test_ai_game_autosave.py` 的 `_make_mock_session`,
import 区 `from katrain.web.server import create_app` 之后加 `from katrain.web.models import GameEnd`;`katrain.game = game` 之后加:

```python
    # r1:收尾只认「这次请求写出来的」终局事实(Task 5 `_new_terminal`)。真 WebKaTrain 在认输 / 超时 / 双停那一刻才写它,
    # 替身也在收到派发时写 —— 预先挂上的话,端点会当成「早就结束了」,这个文件的自动落账用例全红。
    game.terminal = None

    def _dispatch(action, *args, **kwargs):
        if action in ("resign", "timeout", "play") and end_result and game.terminal is None:
            game.terminal = GameEnd(game, game.current_node, end_result)

    katrain.side_effect = _dispatch
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
uv run black -l 120 katrain/web/interface.py katrain/web/session.py katrain/web/server.py tests/web_ui/test_game_end_hook.py tests/test_play_ai_endgame.py tests/web_ui/test_ai_game_autosave.py
git diff katrain/web/server.py | grep -n "_report_settlement_loop"   # 期望:无(black 压行那一处要还原)
# 根目录(真 WebKaTrain)与 tests/web_ui 分两条跑 —— 见 Global Constraints
CI=true uv run pytest tests/test_play_ai_endgame.py tests/test_local_play_recording.py tests/test_guest_free_play.py \
  tests/web/test_session_cleanup_does_not_block.py tests/test_vision_move_poller.py -q
CI=true uv run pytest tests/web_ui/test_game_end_hook.py tests/web_ui/test_play_ai_endgame_api.py tests/web_ui/test_count_api.py tests/web_ui/test_ai_game_autosave.py \
  tests/web_ui/test_ai_ladder_api.py tests/web_ui/test_game_termination_and_chat_identity.py tests/web_ui/test_ladder_injection.py tests/web_ui/test_navigation_guards.py -q
git status --short katrain/config.json   # 期望:空
# prd §6.0 第 1 条合并验收的 grep,提前到本 Task 跑(判读前先去掉注释行):
grep -n "_record_ai_game(" katrain/web/server.py
```
Expected: 全 PASS。`test_ai_ladder_api.py` 里 `test_ranked_session_still_allows_human_move_and_pass`、`test_ranked_natural_result_saves_once_then_settles_once` 必须仍绿 —— 它们守的是升降级账本只落一次。
grep 恰好两行:`async def _record_ai_game(` 定义,以及 `_finish_ended_game` 里那一次调用;四个请求入口与 `_on_game_ended_off_request` 都不再直接调它。

- [ ] **Step 5: 基线 diff(后端 + 前端)后提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
# 基线 diff(后端 + 前端)，两个 comm -13 均须为空
CI=true uv run pytest tests --continue-on-collection-errors -q -rfE -p no:cacheprovider 2>&1 | tee /tmp/kgpa-now-pytest.log
grep -E '^(FAILED|ERROR) tests/' /tmp/kgpa-now-pytest.log | sed -E 's/ - .*//' | LC_ALL=C sort -u > /tmp/kgpa-now-pytest-failed.txt
LC_ALL=C comm -13 /tmp/kgpa-baseline/pytest-failed.txt /tmp/kgpa-now-pytest-failed.txt   # 期望:无输出
git restore --source=HEAD -- katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json
rm -f test_user_data.db
git status --short katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json test_user_data.db   # 期望:空
cd katrain/web/ui
npx vitest run --reporter=verbose 2>&1 | tee /tmp/kgpa-now-vitest.log
grep -E '^\s+×' /tmp/kgpa-now-vitest.log | sed -E 's/^\s+×\s+//; s/ [0-9]+ms$//' | LC_ALL=C sort -u > /tmp/kgpa-now-vitest-failed.txt
LC_ALL=C comm -13 /tmp/kgpa-baseline/vitest-failed.txt /tmp/kgpa-now-vitest-failed.txt   # 期望:无输出
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
git add katrain/web/interface.py katrain/web/session.py katrain/web/server.py tests/web_ui/test_game_end_hook.py tests/test_play_ai_endgame.py \
  tests/web_ui/test_ai_game_autosave.py
git diff --cached --stat
git commit -m "fix(play): AI 收尾的局不落账、升降级不结算;双停只有「终局」没有胜负 —— 终局收尾合成一个函数

N22(P1)。AI 线程下出双停第二手或认输时只置 game_ended、不落账;AI 线程新增 game_ended_callback(end) →
SessionManager.on_game_ended,与 /api/move、认输、超时、数子四个请求入口共用 _finish_ended_game:会话内串行,
先补分(非升降级)再落账,每局一次。收尾按捕获的终局事实落账、不看游标;请求路径只收尾本次请求造出来的终局
(撞上已结束的认输 / 超时是空操作,不排队、不再补分)。账本代码未改。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```
**必须上板**(记进 Task 12 清单):自由对弈人先停、AI 跟停 → 屏上出现胜负、「全部对局」里有这一局;升降级局双停后「继续」按钮消失、能开下一局。

---

### Task 6: A18 玩家卡倒计时 / 读秒 / 到点判超时(r1:超时绑定轮次,服务端时钟核实)

**Files:**
- Modify: `katrain/web/models.py`(`TimeoutRequest`;typing / pydantic import)
- Modify: `katrain/web/interface.py:205`(`__init__` 加 `timer_configured`)、`update_config`(`timer/` 分支)、`get_state` 的 `"timer"` 字典(`:593-599`);Task 2 改过的 `_do_timeout`(整段替换)与它之前新增的 `clock_exhausted`
- Modify: `katrain/web/server.py:2119-2165`(`/api/timeout` 整段,请求模型换成 `TimeoutRequest`)
- Modify: `katrain/web/ui/src/api.ts:63-75`(`timer` 类型加 `configured?: boolean`)、`:391-392`(`API.timeout` 加可选第三参)—— **共享领地**
- Create: `katrain/web/ui/src/kiosk/components/game/goClock.ts`、`goClock.test.ts`、`GameControlPanel.playAi.test.tsx`
- Create: `katrain/web/ui/tests/kiosk-screen-05-play-ai.spec.ts`
- Modify: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx`(import、Props、`clockFor` 注释、两处 `<PlayerRow>` 换成 `<SeatRow>`)
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx`(import 加 `ApiError`;`handleClockExpired` / `sendTimeout` / 没送达的 `Snackbar` 与传参)
- Test: `tests/test_play_ai_endgame.py`、`tests/web_ui/test_play_ai_endgame_api.py`、`katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx`(追加)

**Interfaces:**
- Consumes: Task 2 的对局提交锁 / `_commit_end_state` / `EndgameConflict` 处理器 / `terminal_result` / `_ai_parked_inside_its_commit`;Task 4 的 `_terminal_of`；Task 5 的 `_new_terminal` / `_finish_ended_game`;
  Task 1 测试文件的 `sessionMock` / `makeState` / `seat` / `pageTree`
- Produces:
  - `katrain.web.models.TimeoutRequest(session_id, expected_game_id?, expected_node_id?, color?: 'B'|'W')`(三个 expected 字段要么都给、要么都不给,否则 422)
  - `WebKaTrain.clock_exhausted(self) -> bool`(与 `goClock.ts` 的 `readGoClock` / `isTimedGame` 逐条同口径;核实不了一律 False)
  - `WebKaTrain._do_timeout(self, expected_game_id=None, expected_node_id=None, color=None) -> GameEnd`(不带绑定 = galaxy 旧语义;带绑定时冲突 `already_ended` / `stale_turn` / `clock_not_expired`)
  - TS `API.timeout(sessionId: string, token?: string, expect?: { expected_game_id: string; expected_node_id: number; color: 'B' | 'W' })`
  - `get_state()["timer"]["configured"]: bool`;TS `GameState['timer']['configured']?: boolean`
  - `goClock.ts`:`interface GoClockReading { mainLeft: number; byoLeft: number | null; periodsLeft: number; expired: boolean }`、
    `readGoClock(input: GoClockInput): GoClockReading`、`isTimedGame(timer: GameState['timer']): boolean`、
    `useGoClock(gameState: GameState, color: 'B' | 'W', onExpired?: () => void): GoClockReading | null`
  - `GameControlPanel` 新 prop `onTimeout?: (color: 'B' | 'W') => void`(Task 9 同文件继续改)
  - `tests/kiosk-screen-05-play-ai.spec.ts` 的 `open(page, state)` / `baseState(over)` / `seat()` 供 Task 9 追加

- [ ] **Step 1: 后端判别位(测试 → 实现)**

追加到 `tests/test_play_ai_endgame.py` 末尾:

```python
# ---------------------------------------------------------------- A18 计时判别位


def test_timer_is_configured_only_after_a_setup_wrote_it():
    """星阵人机 / 大厅房间局没人设过时限,却继承 config.json 默认的 20 分 + 30 秒×5 且不暂停;
    前端必须能分出「这局的时限是开局设置定的」,否则星阵局会凭空倒计时、20 分钟后自己判负。"""
    w = _web_katrain()
    assert w.get_state()["timer"]["configured"] is False
    w.update_config("timer/main_time", 5)
    assert w.get_state()["timer"]["configured"] is True
```

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-play-ai && CI=true uv run pytest tests/test_play_ai_endgame.py -q -k timer_is_configured` → Expected: FAIL(`KeyError: 'configured'`)。

实现 —— `interface.py` `__init__` 里 `self.timer_paused = True` 之后加:

```python
        # A18:这一局的时限是不是**开局设置**写的(`/api/game/setup`、升降级 `/start` 都经 update_config("timer/…"))。
        # 没写过的局(星阵人机、大厅房间)继承 config.json 默认时限且不暂停,前端不许把它当计时局。
        self.timer_configured = False
```

`update_config` 里 `if setting == "timer/paused":` 之前加:

```python
        if setting.startswith("timer/"):
            self.timer_configured = True
```

`get_state` 的 `"timer": {` 字典里 `"settings": self.active_game_timer,` 之后加一行 `"configured": bool(getattr(self, "timer_configured", False)),`。

Run 同上 → Expected: PASS;`git status --short katrain/config.json` 为空。

**Step 1 续:超时绑定轮次,服务端时钟核实(r1 C1 / S6)—— 测试 → 实现**

服务端能核实:时钟本来就在服务端累计(`update_timer` 由 `get_state`、`WebGame.play`、`set_current_node`、`_do_play` 驱动),
判超时那一刻在对局提交锁里先结算一次,再按设置判「轮到的一方是否用完」。核实不了(暂停、不计时、非对局模式、不在叶子)一律拒绝、不判负。

追加到 `tests/test_play_ai_endgame.py` 末尾:

```python
# ---------------------------------------------------------------- r1 C1 超时绑定轮次 + 服务端时钟


class _FakeClock:
    """`katrain.web.interface.time` 的替身:只有 `time()` 可以被拨快;`monotonic` / `sleep` 照真的走。"""

    def __init__(self):
        import time as real_time

        self._real = real_time
        self.now = real_time.time()

    def time(self):
        return self.now

    def monotonic(self):
        return self._real.monotonic()

    def sleep(self, seconds):
        self._real.sleep(seconds)

    def advance(self, seconds):
        self.now += seconds


def _timed_game(monkeypatch, *, main_time=0, byo_length=30, byo_periods=3):
    """两人座位、开局设置配过时限(`timer_configured`)、不暂停的真 WebKaTrain,时钟由测试拨。默认「仅读秒 30 秒 × 3」。"""
    import katrain.web.interface as interface_module

    clock = _FakeClock()
    monkeypatch.setattr(interface_module, "time", clock)
    w = _web_katrain()
    _seat(w, human_colors={"B", "W"})
    w.update_config("timer/main_time", main_time)
    w.update_config("timer/byo_length", byo_length)
    w.update_config("timer/byo_periods", byo_periods)
    w.update_config("timer/paused", False)
    w.last_timer_update = clock.now
    return w, clock


def test_a_timeout_for_a_turn_the_server_has_moved_past_is_refused(monkeypatch):
    """C1:前端那一帧还轮到白,服务端已经落了白(人在最后一刻落子 / 在途)。黑随后也把钟用完了 ——
    只核时钟不核轮次的实现会把这一帧的「白超时」写成结果。"""
    w, clock = _timed_game(monkeypatch)
    w._do_play((3, 3), guard=True)
    stale = w.get_state()
    assert stale["player_to_move"] == "W"
    w._do_play((15, 15), guard=True)
    clock.advance(91)

    with pytest.raises(EndgameConflict, match="stale_turn"):
        w._do_timeout(stale["game_id"], stale["current_node_id"], "W")
    assert w.game.end_result is None and w.game.terminal is None

    fresh = w.get_state()
    w._do_timeout(fresh["game_id"], fresh["current_node_id"], "B")
    assert w.game.end_result == "W+T"


def test_a_timeout_for_an_older_node_of_the_same_colour_is_refused(monkeypatch):
    """同色不同手:漏收了两手广播,两帧都轮到黑。只核 `color` 不核节点的实现会放行。"""
    w, clock = _timed_game(monkeypatch)
    w._do_play((3, 3), guard=True)
    w._do_play((15, 15), guard=True)
    stale = w.get_state()
    w._do_play((4, 4), guard=True)
    w._do_play((16, 16), guard=True)
    clock.advance(91)

    with pytest.raises(EndgameConflict, match="stale_turn"):
        w._do_timeout(stale["game_id"], stale["current_node_id"], "B")
    assert w.game.terminal is None


def test_the_server_clock_must_have_run_out(monkeypatch):
    """轮次与方都对,但服务端时钟还没耗尽:拒绝;耗尽之后同一个请求被接受。"""
    w, clock = _timed_game(monkeypatch)
    w._do_play((3, 3), guard=True)  # 轮到白
    clock.advance(89)
    s = w.get_state()

    with pytest.raises(EndgameConflict, match="clock_not_expired"):
        w._do_timeout(s["game_id"], s["current_node_id"], "W")
    assert w.game.terminal is None

    clock.advance(2)
    w._do_timeout(s["game_id"], s["current_node_id"], "W")
    assert w.game.end_result == "B+T"


def test_main_time_only_game_expires_exactly_at_main_time_end(monkeypatch):
    """只有主时间(读秒 0 / 0):主时间用完那一刻就算耗尽,与前端 `readGoClock` 同口径。
    复用 `update_timer` 的 `max(1, …)` 会要 61 秒以上 —— 前端停在「超时」而服务端永远不判。"""
    w, clock = _timed_game(monkeypatch, main_time=1, byo_length=0, byo_periods=0)
    w._do_play((3, 3), guard=True)
    clock.advance(60)
    s = w.get_state()

    w._do_timeout(s["game_id"], s["current_node_id"], "W")
    assert w.game.end_result == "B+T"


def test_a_bound_timeout_that_waited_for_the_ai_commit_is_stale(monkeypatch):
    """AI 停在提交段里;另一线程拿 AI 提交之前那一帧做带绑定的超时 —— 它必须等 AI 提交完,然后发现轮次过期。
    轮次核对放在对局提交锁外的实现会读到旧节点、写到 AI 那一手上。"""
    w, clock = _timed_game(monkeypatch)
    _seat(w, human_colors={"B"})  # 白是 AI
    w._do_play((3, 3), guard=True)
    clock.advance(91)  # 白(AI)的钟也耗尽了
    stale = w.get_state()
    finish = _ai_parked_inside_its_commit(monkeypatch, w, "test:instant")

    outcome = {}

    def bound_timeout():
        try:
            w._do_timeout(stale["game_id"], stale["current_node_id"], "W")
            outcome["error"] = None
        except EndgameConflict as e:
            outcome["error"] = e.reason

    worker = threading.Thread(target=bound_timeout, daemon=True)
    worker.start()
    worker.join(0.1)
    assert worker.is_alive(), "带绑定的超时没等 AI 的提交段"

    result, errors = finish()
    worker.join(2)
    assert errors == [] and result is not None
    assert outcome == {"error": "stale_turn"}
    assert w.game.end_result is None and w.game.terminal is None


def test_an_unbound_timeout_keeps_its_old_meaning(monkeypatch):
    """galaxy 的旧调用不带绑定:语义照旧(最后落子的一方胜、不核时钟),只多了「已经结束过就拒」。"""
    w, _clock = _timed_game(monkeypatch)
    w._do_play((3, 3), guard=True)
    w._do_timeout()
    assert w.game.end_result == "B+T"
    with pytest.raises(EndgameConflict, match="already_ended"):
        w._do_timeout()
```

追加到 `tests/web_ui/test_play_ai_endgame_api.py` 末尾:

```python
# ---------------------------------------------------------------- r1 C1 超时绑定(端点接线)


def test_timeout_passes_the_expected_turn_and_maps_a_refusal_to_409(client):
    session = _inject_session(client)

    def refuse(action, *args, **kwargs):
        if action == "timeout":
            raise EndgameConflict("stale_turn")

    session.katrain.side_effect = refuse

    resp = client.post(
        "/api/timeout",
        json={"session_id": session.session_id, "expected_game_id": "g", "expected_node_id": 5, "color": "W"},
    )

    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == "timeout rejected: stale_turn"
    session.katrain.assert_any_call("timeout", expected_game_id="g", expected_node_id=5, color="W")


@pytest.mark.parametrize("conflict", [None, "already_ended"])
def test_an_unbound_timeout_keeps_the_old_call_and_an_ended_game_is_a_no_op(client, conflict):
    """galaxy 的旧调用只带 session_id:照旧 `katrain("timeout")`;撞上已结束的局是 200 空操作,不弹红条。"""
    session = _inject_session(client)
    if conflict is not None:

        def refuse(action, *args, **kwargs):
            if action == "timeout":
                raise EndgameConflict(conflict)

        session.katrain.side_effect = refuse

    resp = client.post("/api/timeout", json={"session_id": session.session_id})

    assert resp.status_code == 200, resp.text
    session.katrain.assert_any_call("timeout")


def test_timeout_expectations_come_all_or_nothing(client):
    session = _inject_session(client)

    resp = client.post("/api/timeout", json={"session_id": session.session_id, "expected_node_id": 5})

    assert resp.status_code == 422, resp.text
```

Run（分两条）：

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai && CI=true uv run pytest tests/test_play_ai_endgame.py -q -k "timeout or clock"
CI=true uv run pytest tests/web_ui/test_play_ai_endgame_api.py -q -k timeout
```
Expected:
- 根目录前五条 FAIL(`TypeError: _do_timeout() takes 1 positional argument`);`test_an_unbound_timeout_keeps_its_old_meaning` PASS(Task 2 已经让它「已经结束过就拒」)——
  它是改动后的回归护栏:错把 galaxy 旧调用也改成核时钟,它会红(不暂停但钟没到 ⇒ `clock_not_expired`)。
- web_ui:`test_timeout_passes_the_expected_turn…` FAIL(请求模型没有这三个字段,被丢弃,调用是 `("timeout",)`);
  `test_timeout_expectations_come_all_or_nothing` FAIL(200,不是 422);`test_an_unbound_timeout…` 两格 PASS(Task 2 的写法)。

实现 —— `katrain/web/models.py`:第 1 行 typing import 改为 `from typing import Any, Dict, List, Literal, NamedTuple, Optional, Union`,
第 3 行 `from pydantic import BaseModel, Field` 改为 `from pydantic import BaseModel, Field, model_validator`;`class ToggleAnalysisRequest` 之后加:

```python


class TimeoutRequest(BaseModel):
    """`/api/timeout`(r1 C1)。kiosk 带上它以为超时的那一局、那一手、那一方,由服务端在对局提交锁里核对轮次并用
    服务端时钟核实;galaxy 的旧调用只带 `session_id`,语义照旧。三个 expected 字段要么都给、要么都不给。"""

    session_id: str
    expected_game_id: Optional[str] = None
    expected_node_id: Optional[int] = None
    color: Optional[Literal["B", "W"]] = None

    @model_validator(mode="after")
    def _expected_fields_come_together(self):
        given = [value is not None for value in (self.expected_game_id, self.expected_node_id, self.color)]
        if any(given) and not all(given):
            raise ValueError("expected_game_id, expected_node_id and color must be given together")
        return self
```

`katrain/web/interface.py`,Task 2 写的

```python
    def _do_timeout(self):
        """End game due to timeout - current player loses on time"""
        # r1:语义与从前相同,只多了「已经结束过就拒」。带轮次绑定的版本在 Task 6。
        with self.ai_ladder_commit_lock:
            return self._commit_end_state(f"{self.game.current_node.player}+T")
```

整段替换为

```python
    def clock_exhausted(self) -> bool:
        """轮到的一方用时是否已经耗尽 —— 服务端判超时的唯一依据(r1 C1)。

        与前端 `kiosk/components/game/goClock.ts` 的 `isTimedGame` / `readGoClock` 逐条同口径:
          · 暂停 / 不在对局模式 / 没有对局 / 时限不是开局设置写的(`timer_configured`)→ False;
          · 主时间与读秒长度都为 0(不计时)→ False;
          · 主时间还没用完 → False;
          · 只有主时间(读秒长度或次数为 0)→ True —— **不许**借用 `update_timer` 的 `max(1, …)`;
          · 否则读秒次数用完 → True。
        核实不了一律 False(fail-closed):把一个核实不了的「到点」写成输棋,代价不可逆。先 `update_timer()` 结算到此刻。"""
        with self.ai_ladder_commit_lock:
            self.update_timer()
            if (
                self.timer_paused
                or self.play_analyze_mode != MODE_PLAY
                or not self.game
                or not getattr(self, "timer_configured", False)
            ):
                return False
            main_total = self.active_game_timer.get("main_time", 0) * 60
            byo_length = self.active_game_timer.get("byo_length", 0)
            byo_periods = self.active_game_timer.get("byo_periods", 0)
            if main_total <= 0 and byo_length <= 0:
                return False
            if self.main_time_used_by_player.get(self.game.current_node.next_player, 0) < main_total:
                return False
            if byo_length <= 0 or byo_periods <= 0:
                return True
            return self.next_player_info.periods_used >= byo_periods

    def _do_timeout(self, expected_game_id=None, expected_node_id=None, color=None):
        """End game due to timeout - current player loses on time.

        不带绑定(galaxy 旧调用):语义照旧 —— 最后落子的一方胜,不核时钟;只多了「已经结束过就拒」。
        带绑定(kiosk,r1 C1):整段在对局提交锁里按顺序判 ——
          1. 这一手所在的局面线已经结束过 → `already_ended`;
          2. 局 id 不符、`id(current_node)` 不符、轮到的不是 `color`、或当前手不在叶子上 → `stale_turn`
             (服务端已经走过了请求方以为的那一手:人在最后一刻落子、AI 提交在途、翻到了前面);
          3. 服务端时钟没耗尽(`clock_exhausted`)→ `clock_not_expired`;
          4. 都通过 → `color` 一方超时负。
        已知残留:服务端只在叶子上走钟,翻到前面看棋的那段时间不计入任何一方(今天就有的语义,本轮不改);盒上服务重启后会话就没了。"""
        with self.ai_ladder_commit_lock:
            cn = self.game.current_node
            if expected_node_id is None:
                return self._commit_end_state(f"{cn.player}+T")
            if cn.end_state or self.game.ended_at(cn):
                raise EndgameConflict("already_ended")
            if (
                self.game.game_id != expected_game_id
                or id(cn) != expected_node_id
                or cn.next_player != color
                or cn.children
            ):
                raise EndgameConflict("stale_turn")
            if not self.clock_exhausted():
                raise EndgameConflict("clock_not_expired")
            winner = "W" if color == "B" else "B"
            return self._commit_end_state(f"{winner}+T")
```

`katrain/web/server.py` `/api/timeout`(`:2119-2165`,Task 2 / Task 5 改过)整段替换为:

```python
    @app.post("/api/timeout")
    async def timeout(request: TimeoutRequest, current_user: User = Depends(get_current_user_optional)):
        """End game due to timeout - current player loses on time.

        r1 C1:kiosk 带上期望的局 / 手 / 方,`_do_timeout` 在对局提交锁里核对轮次、用服务端时钟核实;核实不了一律拒绝(409),
        不判负。galaxy 的旧调用不带这三个字段,语义照旧(撞上已结束的局是 200 空操作)。"""
        session = _get_session_or_404(manager, request.session_id)
        guard_session_terminator(session, current_user, "timeout")
        guard_ai_ladder_ranked_human_action(session, current_user, "timeout")
        await _guard_ai_ladder_cloud_active(app, session, current_user)

        # For multiplayer games, record the result
        is_multiplayer = session.player_b_id is not None or session.player_w_id is not None
        bound = request.expected_node_id is not None
        wrote = True
        with session.lock:
            guard_ai_ladder_ranked_human_action(session, current_user, "timeout")
            before = _terminal_of(session)
            try:
                if bound:
                    session.katrain(
                        "timeout",
                        expected_game_id=request.expected_game_id,
                        expected_node_id=request.expected_node_id,
                        color=request.color,
                    )
                else:
                    session.katrain("timeout")
            except EndgameConflict as e:
                # 被拒前先刷新 last_state:随后的 GET /api/state 给出此刻的局面与计时基准,前端据此重同步。
                session.last_state = session.katrain.get_state()
                if bound or e.reason != "already_ended":
                    raise
                wrote = False
            end = _new_terminal(session, before) if wrote else None
            state = session.katrain.get_state()
            session.last_state = state

        # Record game result for multiplayer
        if is_multiplayer and current_user and wrote:
            winner_id = session.player_w_id if current_user.id == session.player_b_id else session.player_b_id
            result = f"{'W' if winner_id == session.player_w_id else 'B'}+T"
            try:
                app.state.game_repo.record_multiplayer_game(
                    sgf_content=session.katrain.get_sgf(),
                    result=result,
                    game_type=getattr(session, "game_type", "free"),
                    black_id=session.player_b_id,
                    white_id=session.player_w_id,
                )
            except Exception as e:
                logging.getLogger("katrain_web").error(f"Failed to record game result: {e}")

            # 广播**不在** try 里:它告诉对面「这局结束了」,而 try 守的是落账。
            # 两件事捆在一个 try 里时,落账一失败对面就永远收不到终局 —— 盒上
            # `app.state.game_repo` 恒为 None(`server.py` board 模式那一段),
            # 于是这条路上每一次认输/超时都会静默地把对面挂在「还在等你走」。
            # 数子(`_complete_count`)和退出(forfeit)两处本来就是这么写的,这里对齐。
            manager._schedule_broadcast(
                session,
                {"type": "game_end", "data": {"reason": "timeout", "winner_id": winner_id, "result": result}},
            )
        elif not is_multiplayer and end is not None:
            await _finish_ended_game(session, app, current_user, end)
            state = session.katrain.get_state()
            session.last_state = state

        return {"session_id": session.session_id, "state": state}
```

Run 同上 → Expected: 全 PASS;另跑 `CI=true uv run pytest tests/web_ui/test_ai_ladder_api.py tests/web_ui/test_game_termination_and_chat_identity.py tests/web_ui/test_ai_game_autosave.py -q -k "timeout or terminal"` 仍全绿(它们发的都是只带 `session_id` 的旧请求);`git status --short katrain/config.json` 为空。

- [ ] **Step 2: 计时纯函数(测试 → 实现)**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
for f in src/kiosk/components/game/goClock.ts src/kiosk/components/game/goClock.test.ts src/kiosk/components/game/GameControlPanel.playAi.test.tsx tests/kiosk-screen-05-play-ai.spec.ts; do git ls-files "$f"; ls "$f" 2>/dev/null; done   # 期望:无输出
```

`src/kiosk/components/game/goClock.test.ts`:

```ts
import { describe, expect, test } from 'vitest';
import { readGoClock, type GoClockInput } from './goClock';

const input = (over: Partial<GoClockInput> = {}): GoClockInput => ({
  mainTimeMin: 5, byoLength: 30, byoPeriods: 3, mainUsed: 0, periodsUsed: 0, nodeTimeUsed: 0, active: true, elapsed: 0, ...over,
});

describe('readGoClock —— 与 interface.py update_timer 同一套算法', () => {
  test('主时间里:只扣主时间,读秒还没开始', () => {
    expect(readGoClock(input({ mainUsed: 100, elapsed: 20 }))).toEqual({ mainLeft: 180, byoLeft: null, periodsLeft: 3, expired: false });
  });

  test('不轮到的一方不外推本地流逝', () => {
    expect(readGoClock(input({ mainUsed: 100, elapsed: 20, active: false })).mainLeft).toBe(200);
  });

  test('主时间在这一手里用完:超出的部分才进读秒', () => {
    // 这一手开始时还剩 10 秒主时间,已经想了 25 秒 ⇒ 读秒用掉 15 秒
    expect(readGoClock(input({ mainUsed: 290, elapsed: 25 }))).toEqual({ mainLeft: 0, byoLeft: 15, periodsLeft: 3, expired: false });
  });

  test('每满一次读秒长度记一次,次数用完即超时', () => {
    expect(readGoClock(input({ mainTimeMin: 0, elapsed: 65 }))).toEqual({ mainLeft: 0, byoLeft: 25, periodsLeft: 1, expired: false });
    expect(readGoClock(input({ mainTimeMin: 0, elapsed: 91 })).expired).toBe(true);
  });

  test('只有主时间、没有读秒:主时间用完即超时', () => {
    expect(readGoClock(input({ byoLength: 0, byoPeriods: 0, mainUsed: 300 })).expired).toBe(true);
  });
});
```

Run: `npx vitest run src/kiosk/components/game/goClock.test.ts` → Expected: FAIL(`Failed to resolve import "./goClock"`)。

`src/kiosk/components/game/goClock.ts`:

```ts
import { useEffect, useRef, useState } from 'react';
import type { GameState } from '../../../api';

/**
 * 对局屏玩家卡的时钟(A18)。
 *
 * 算法与服务端 `interface.py` `update_timer` 一致:主时间先扣;扣完之后,**这一手**里超出主时间的部分才进读秒,
 * 每满一次读秒长度记一次;次数用完即超时。服务端只在换手时结算,两次推送之间由这里按本地流逝时间外推
 * (galaxy `components/PlayerCard.tsx` 同一套 —— 那个文件是 galaxy 的 MUI 卡,kiosk 不引它,只对齐算法)。
 * 已知局限:刷新页面会把「这一手已想了多久」清零(服务端不在手中途结算),与 galaxy 相同。
 */
export interface GoClockReading {
  /** 主时间还剩几秒;用完或没有主时间时为 0。 */
  mainLeft: number;
  /** 本次读秒还剩几秒;还在主时间里时为 null。 */
  byoLeft: number | null;
  /** 还剩几次读秒。 */
  periodsLeft: number;
  expired: boolean;
}

export interface GoClockInput {
  /** 主时间,**分钟**(与 `timer.settings.main_time`、开局设置 `TIME_PRESETS` 同单位)。 */
  mainTimeMin: number;
  byoLength: number;
  byoPeriods: number;
  mainUsed: number;
  periodsUsed: number;
  /** 当前这一手已记的秒数(`timer.current_node_time_used`);只对轮到的一方有意义。 */
  nodeTimeUsed: number;
  active: boolean;
  /** 上一次计时基准变化之后本地流逝的秒数。 */
  elapsed: number;
}

export function readGoClock(i: GoClockInput): GoClockReading {
  const extra = i.active ? i.elapsed : 0;
  const mainTotal = Math.max(0, i.mainTimeMin) * 60;
  const periodsTotal = Math.max(0, i.byoPeriods);
  const mainLeft = Math.max(0, mainTotal - (i.mainUsed + extra));
  if (mainLeft > 0) {
    return { mainLeft, byoLeft: null, periodsLeft: Math.max(0, periodsTotal - i.periodsUsed), expired: false };
  }
  const byoLen = Math.max(0, i.byoLength);
  const mainAvailableAtNodeStart = Math.max(0, mainTotal - i.mainUsed);
  let overflow = Math.max(0, (i.active ? i.nodeTimeUsed : 0) + extra - mainAvailableAtNodeStart);
  let periodsUsed = i.periodsUsed;
  while (byoLen > 0 && overflow > byoLen && periodsUsed < periodsTotal) {
    overflow -= byoLen;
    periodsUsed += 1;
  }
  const periodsLeft = Math.max(0, periodsTotal - periodsUsed);
  if (byoLen <= 0 || periodsLeft <= 0) return { mainLeft: 0, byoLeft: 0, periodsLeft: 0, expired: true };
  return { mainLeft: 0, byoLeft: Math.max(0, byoLen - overflow), periodsLeft, expired: false };
}

/**
 * 这一局计不计时。**两段都要**:服务端说时限是开局设置写的(`configured`),且主时间或读秒至少一样非零。
 * 只看 `settings` 会把星阵 / 大厅局继承的默认「20 分 + 30 秒×5」当成真时限。
 */
export function isTimedGame(timer: GameState['timer']): boolean {
  const s = timer?.settings;
  return timer?.configured === true && !!s && (s.main_time > 0 || s.byo_length > 0);
}

const TICK_MS = 250;

/**
 * 一方的时钟读数;不计时的局返回 null。轮到的一方耗尽时调一次 `onExpired`(由假变真那一刻),
 * 以及计时基准换了(换了一手、服务端结算过)之后仍耗尽时再调一次 —— 服务端判「轮次过期」后前端重同步到新的一手,要能再核。
 */
export function useGoClock(gameState: GameState, color: 'B' | 'W', onExpired?: () => void): GoClockReading | null {
  const timer = gameState.timer;
  const timed = isTimedGame(timer);
  // 只在叶子上、且这一局没有终局事实时走钟 —— 与服务端 `update_timer` 同口径(它在有子节点时不计时)。
  // 翻到前面看棋时还按本地流逝倒数,会在服务端根本不会判的地方显示「超时」并发请求(r1 S6)。
  const active = timed && timer?.paused === false && !gameState.end_result && !gameState.terminal_result
    && (gameState.children?.length ?? 0) === 0 && gameState.player_to_move === color;
  const info = gameState.players_info[color];
  // 计时基准:服务端最近一次给的量。任何一个变了(换手、结算),本地流逝就从 0 重新数。
  const baseKey = `${active}|${info.main_time_used}|${info.periods_used}|${timer?.current_node_time_used ?? 0}|${gameState.current_node_id}`;
  const [tick, setTick] = useState({ key: baseKey, elapsed: 0 });

  useEffect(() => {
    if (!active) return undefined;
    const startedAt = Date.now();
    const id = window.setInterval(() => setTick({ key: baseKey, elapsed: (Date.now() - startedAt) / 1000 }), TICK_MS);
    return () => window.clearInterval(id);
  }, [active, baseKey]);

  const elapsed = tick.key === baseKey ? tick.elapsed : 0;
  const reading = timed && timer
    ? readGoClock({
      mainTimeMin: timer.settings.main_time,
      byoLength: timer.settings.byo_length,
      byoPeriods: timer.settings.byo_periods,
      mainUsed: info.main_time_used,
      periodsUsed: info.periods_used,
      nodeTimeUsed: timer.current_node_time_used,
      active,
      elapsed,
    })
    : null;

  const expired = active && !!reading?.expired;
  const onExpiredRef = useRef(onExpired);
  useEffect(() => { onExpiredRef.current = onExpired; }, [onExpired]);
  useEffect(() => { if (expired) onExpiredRef.current?.(); }, [expired, baseKey]);
  return reading;
}
```

`api.ts` 的 `timer?: { … settings: {…}; };` 里 `settings` 之后加:

```ts
    /** 这一局的时限是开局设置写的(服务端 `timer_configured`)。星阵 / 大厅局没有,别把它们当计时局。 */
    configured?: boolean;
```

`api.ts` 中 `timeout` 改为（第三参可选，galaxy / 共享 hook 旧两参调用兼容）：

```ts
  timeout: (sessionId: string, token?: string, expect?: {
    expected_game_id: string; expected_node_id: number; color: 'B' | 'W';
  }): Promise<SessionResponse> =>
    apiPost("/api/timeout", { session_id: sessionId, ...expect }, token),
```

Run: `npx vitest run src/kiosk/components/game/goClock.test.ts` → Expected: 5 条 PASS。

- [ ] **Step 3: 玩家卡接时钟(测试 → 实现)**

`src/kiosk/components/game/GameControlPanel.playAi.test.tsx`:

```tsx
import { act, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import GameControlPanel from './GameControlPanel';
import type { GameState } from '../../../api';

/** 对弈·AI/升降级赛道的右栏行为测试。只证 DOM 结构与文案;几何在 tests/kiosk-screen-05-play-ai.spec.ts。 */

const seat = (type: string, name: string, over: Record<string, number> = {}) => ({
  player_type: type, player_subtype: '', name, calculated_rank: null, periods_used: 0, main_time_used: 0, ...over,
});

const base = (over: Partial<GameState> = {}): GameState => ({
  game_id: 'g', board_size: [19, 19], komi: 7.5, handicap: 0, ruleset: 'chinese',
  current_node_id: 7, current_node_index: 7, history: [{ node_id: 0, score: null, winrate: null }],
  player_to_move: 'B', stones: [], last_move: null, prisoner_count: { B: 0, W: 0 }, analysis: null, commentary: '',
  is_root: false, is_pass: false, end_result: null, children: [], ghost_stones: [], note: '',
  game_type: 'free', count_min_moves: 100,
  ui_state: {
    show_children: false, show_dots: false, show_hints: false, show_policy: false,
    show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false,
  },
  players_info: { B: seat('player:human', '我'), W: seat('player:ai', 'KataGo') },
  ...over,
} as GameState);

const timer = (settings: { main_time: number; byo_length: number; byo_periods: number }, configured = true) => ({
  paused: false, main_time_used: 0, current_node_time_used: 0, next_player_periods_used: 0, configured,
  settings: { minimal_use: 0, sound: false, ...settings },
});

const panel = (gs: GameState, props: Record<string, unknown> = {}) => render(
  <GameControlPanel
    gameState={gs}
    onAction={() => {}}
    onNavigate={() => {}}
    analysisToggles={{}}
    onToggleAnalysis={() => {}}
    {...props}
  />,
);

const clockOf = (color: 'B' | 'W') => {
  const card = screen.getByTestId(`player-card-${color}`);
  return { value: card.querySelector('.clock b')?.textContent, label: card.querySelector('.clock span')?.textContent };
};

describe('A18 · 玩家卡时钟', () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  test('主时间阶段:两张卡都写剩余,只有轮到的一方在走', () => {
    panel(base({
      timer: timer({ main_time: 5, byo_length: 30, byo_periods: 3 }),
      players_info: { B: seat('player:human', '我', { main_time_used: 12 }), W: seat('player:ai', 'KataGo', { main_time_used: 30 }) },
    }));
    expect(clockOf('B')).toEqual({ value: '4:48', label: '剩余' });
    expect(clockOf('W')).toEqual({ value: '4:30', label: '剩余' });
    act(() => { vi.advanceTimersByTime(2000); });
    expect(clockOf('B').value).toBe('4:46');
    expect(clockOf('W').value).toBe('4:30');
  });

  test('仅读秒:写本次读秒剩余与剩几次', () => {
    panel(base({
      timer: timer({ main_time: 0, byo_length: 30, byo_periods: 3 }),
      players_info: { B: seat('player:human', '我', { periods_used: 1 }), W: seat('player:ai', 'KataGo') },
    }));
    expect(clockOf('B')).toEqual({ value: '0:30', label: '读秒 · 剩 2 次' });
    expect(clockOf('W')).toEqual({ value: '0:30', label: '读秒 · 剩 3 次' });
  });

  test('耗尽:写「超时」,并对轮到的那一方回调一次 onTimeout', () => {
    const onTimeout = vi.fn();
    panel(base({ timer: timer({ main_time: 0, byo_length: 30, byo_periods: 1 }) }), { onTimeout });
    act(() => { vi.advanceTimersByTime(31_000); });
    expect(clockOf('B')).toEqual({ value: '0:00', label: '超时' });
    expect(onTimeout).toHaveBeenCalledTimes(1);
    expect(onTimeout).toHaveBeenCalledWith('B');
  });

  test('没配过时限的局(星阵 / 大厅)不倒计时,仍写「第 N 手 · 不限时」', () => {
    panel(base({ timer: timer({ main_time: 20, byo_length: 30, byo_periods: 5 }, false) }));
    expect(clockOf('B')).toEqual({ value: '第 8 手', label: '不限时' });
  });

  test('r1 S6:翻到了前面(有子节点)或这一局已有终局事实 —— 时钟不走、不回调', () => {
    const onTimeout = vi.fn();
    const timed = timer({ main_time: 0, byo_length: 30, byo_periods: 1 });
    const props = { onAction: () => {}, onNavigate: () => {}, analysisToggles: {}, onToggleAnalysis: () => {}, onTimeout };
    const { rerender } = render(<GameControlPanel gameState={base({ timer: timed, children: [['W', [3, 3]]] })} {...props} />);
    act(() => { vi.advanceTimersByTime(31_000); });
    expect(onTimeout).not.toHaveBeenCalled();
    rerender(<GameControlPanel gameState={base({ timer: timed, terminal_result: 'W+R' })} {...props} />);
    act(() => { vi.advanceTimersByTime(31_000); });
    expect(onTimeout).not.toHaveBeenCalled();
  });

  test('r1 C1:换了一手、仍然耗尽 —— 再回调一次(服务端判轮次过期后,前端重同步到新的一手要能再核)', () => {
    const onTimeout = vi.fn();
    const timed = timer({ main_time: 0, byo_length: 30, byo_periods: 1 });
    const props = { onAction: () => {}, onNavigate: () => {}, analysisToggles: {}, onToggleAnalysis: () => {}, onTimeout };
    const exhausted = { B: seat('player:human', '我', { periods_used: 1 }), W: seat('player:ai', 'KataGo') };
    const { rerender } = render(<GameControlPanel gameState={base({ timer: timed, players_info: exhausted })} {...props} />);
    expect(onTimeout).toHaveBeenCalledTimes(1);
    rerender(<GameControlPanel gameState={base({ timer: timed, players_info: exhausted, current_node_id: 9 })} {...props} />);
    expect(onTimeout).toHaveBeenCalledTimes(2);
  });
});
```

Run: `npx vitest run src/kiosk/components/game/GameControlPanel.playAi.test.tsx` → Expected: 前三条 FAIL(时钟仍是「第 8 手 · 不限时」),第四条 PASS;
r1 两条在「只加了 SeatRow、`useGoClock` 用的是本 Task 最初那版」的实现下各自红:`active` 缺叶子 / 终局事实两个条件 ⇒ 31 秒后回调了;
`useEffect` 依赖只有 `[expired]` ⇒ 换手后回调次数仍是 1。本步实现(Step 2 的 `goClock.ts`)已含这两处,Step 3 实现完两条应 PASS。

实现 —— `GameControlPanel.tsx`:

1. 第 1 行改为 `import { useCallback, useEffect, useRef } from 'react';`,并在 import 区加 `import { useGoClock } from './goClock';`。
2. `Props` 里 `hardwareFault?: string | null;` 之后加:

```tsx
  /**
   * A18:轮到的一方时间耗尽。GamePage 决定发不发 `/api/timeout`(升降级 AI 回合、引擎停摆时不发)。
   * 只在开局设置配过时限的局里会被调用(`timer.configured`)。
   */
  onTimeout?: (color: 'B' | 'W') => void;
```

3. 组件参数解构里加上 `onTimeout`(接在 `hardwareFault = null,` 之后)。
4. `formatTime` 之后、`PlayerRow` 之前加:

```tsx
/**
 * 一方的玩家卡 + 时钟(A18)。时钟跟着本地时间走,所以 hook 挂在每张卡自己身上 ——
 * 放在父组件里算,每 250ms 一次的重渲会把胜率图、棋谱一起带着重画。
 */
function SeatRow({ gameState, color, turn, state, untimed, lang, t, onTimeout }: {
  gameState: GameState;
  color: 'B' | 'W';
  turn: boolean;
  state: string;
  /** 这一局不计时时那一格写什么(原来的「第 N 手 · 不限时」/「本局已下」)。 */
  untimed: { value: string; label: string } | null;
  lang: string;
  t: (key: string, fallback?: string) => string;
  onTimeout?: (color: 'B' | 'W') => void;
}) {
  const onExpired = useCallback(() => onTimeout?.(color), [onTimeout, color]);
  const reading = useGoClock(gameState, color, onExpired);
  const clock = reading === null ? untimed
    : reading.expired ? { value: '0:00', label: t('game:time_up', '超时') }
    : reading.byoLeft === null ? { value: formatTime(reading.mainLeft), label: t('game:time_left', '剩余') }
    : {
      value: formatTime(reading.byoLeft),
      label: t('game:byo_left', '读秒 · 剩 {n} 次').replace('{n}', String(reading.periodsLeft)),
    };
  return (
    <PlayerRow
      color={color} info={gameState.players_info[color]} captures={gameState.prisoner_count[color]}
      turn={turn} state={state} clock={clock} lang={lang} t={t}
    />
  );
}
```

5. `clockFor` 上面那段注释开头的「kiosk 的局**不设时限**(开局设置里没有时间控件)」改为
   「**不计时的局**(开局选了「不限时」,或星阵 / 大厅这类没配过时限的局 —— 计时局由 `SeatRow` 的 `useGoClock` 接管)」,其余不动。
6. 返回值里两处 `<PlayerRow color="W" …/>`、`<PlayerRow color="B" …/>` 换成:

```tsx
      <SeatRow
        gameState={gameState} color="W" turn={toMove === 'W' && !isGameOver} state={stateWord('W')}
        untimed={clockFor('W')} lang={lang} t={t} onTimeout={onTimeout}
      />
      <SeatRow
        gameState={gameState} color="B" turn={toMove === 'B' && !isGameOver} state={stateWord('B')}
        untimed={clockFor('B')} lang={lang} t={t} onTimeout={onTimeout}
      />
```

Run: `npx vitest run src/kiosk/components/game/GameControlPanel.playAi.test.tsx src/kiosk/components/game/GameControlPanel.test.tsx` → Expected: 全 PASS。

- [ ] **Step 4: GamePage 发绑定超时、重同步与退避(测试 → 实现)**

测试文件补 `act`、`ApiError` import。A18 describe 内每条先 stub `API.timeout` 与 `API.getState`，不要真实请求；断言 API 调用，不再断言 `handleAction('timeout')`。补以下用例：

```tsx
describe('A18 · 时间耗尽判超时', () => {
  beforeEach(() => {
    vi.spyOn(API, 'timeout').mockResolvedValue({ state: makeState({ terminal_result: 'W+T' }) });
    vi.spyOn(API, 'getState').mockResolvedValue({ state: makeState() });
  });

  it('到点带局/手/方；同一帧回调两次只发一次；盒上 token 为 null 仍发', () => {
    sessionMock.gameState = makeState();
    renderPage();
    fireEvent.click(screen.getByText('MOCK_TIMEOUT_B'));
    fireEvent.click(screen.getByText('MOCK_TIMEOUT_B'));
    expect(API.timeout).toHaveBeenCalledExactlyOnceWith('play-ai-s1', undefined, {
      expected_game_id: 'g', expected_node_id: 5, color: 'B',
    });
    expect(sessionMock.handleAction).not.toHaveBeenCalled();
  });

  it.each(['stale_turn', 'already_ended'])('409 %s 只重同步，不上红条', async (reason) => {
    vi.mocked(API.timeout).mockRejectedValue(new ApiError(409, `timeout rejected: ${reason}`));
    const fresh = makeState({ current_node_id: 6 });
    vi.mocked(API.getState).mockResolvedValue({ state: fresh });
    sessionMock.gameState = makeState();
    renderPage();
    fireEvent.click(screen.getByText('MOCK_TIMEOUT_B'));
    await waitFor(() => expect(sessionMock.setGameState).toHaveBeenCalledWith(fresh));
    expect(API.getState).toHaveBeenCalledWith('play-ai-s1', undefined);
    fireEvent.click(screen.getByText('MOCK_TIMEOUT_B'));
    expect(API.timeout).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/超时判定没有送达|Request failed/)).toBeNull();
  });

  it('clock_not_expired 重同步后同一手只再核一次，不依赖时钟再次从假变真', async () => {
    vi.useFakeTimers();
    try {
      vi.mocked(API.timeout).mockRejectedValue(new ApiError(409, 'timeout rejected: clock_not_expired'));
      sessionMock.gameState = makeState();
      renderPage();
      fireEvent.click(screen.getByText('MOCK_TIMEOUT_B'));
      await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
      expect(API.timeout).toHaveBeenCalledTimes(2);
      fireEvent.click(screen.getByText('MOCK_TIMEOUT_B'));
      await act(async () => { await vi.advanceTimersByTimeAsync(30_000); });
      expect(API.timeout).toHaveBeenCalledTimes(2);
    } finally { vi.useRealTimers(); }
  });

  it.each([
    { children: [['W', [3, 3]]] },
    { terminal_result: 'W+R' },
    { player_to_move: 'W' },
    { last_ladder_error: true },
    { game_type: 'ai_ladder_ranked', players_info: { B: seat('player:ai', 'AI'), W: seat('player:human', '我') } },
  ])('翻手/终局/非回合/引擎停摆/升降级 AI 回合不发超时 %j', (over) => {
    sessionMock.gameState = makeState(over as Partial<GameState>);
    renderPage();
    fireEvent.click(screen.getByText('MOCK_TIMEOUT_B'));
    expect(API.timeout).not.toHaveBeenCalled();
  });

  it('503 等失败按 2/5/10 秒退避，三次重发后显示未送达', async () => {
    vi.useFakeTimers();
    try {
      vi.mocked(API.timeout).mockRejectedValue(new ApiError(503, 'unavailable'));
      sessionMock.gameState = makeState();
      renderPage();
      fireEvent.click(screen.getByText('MOCK_TIMEOUT_B'));
      await act(async () => { await vi.advanceTimersByTimeAsync(1999); });
      expect(API.timeout).toHaveBeenCalledTimes(1);
      for (const [ms, count] of [[1, 2], [5000, 3], [10000, 4]]) {
        await act(async () => { await vi.advanceTimersByTimeAsync(ms); });
        expect(API.timeout).toHaveBeenCalledTimes(count);
      }
      expect(screen.getByText('超时判定没有送达，请检查连接后重新进入这一局')).toBeInTheDocument();
      await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
      expect(API.timeout).toHaveBeenCalledTimes(4);
    } finally { vi.useRealTimers(); }
  });
});
```

再加一个假时钟用例：第一次 503 后 `rerender(pageTree())` 到另一手，推进 20 秒，旧轮次不再发；卸载也清理重试。恢复成功时 `setGameState` 收到结果，提示消失。403 同样重同步，401/网络错误走有限退避。错误实现下：旧 handleAction 路径不带字段，缺叶子闸会发请求，吞掉失败无重试，无限重试超出四次。

Run: `npx vitest run src/kiosk/pages/GamePage.playAi.test.tsx -t A18` → 确认上述失败来自缺功能。

实现：状态声明区增加以下 ref/state；清理 effect **放在所有早退之前**。`timeoutScope` 同时含 session / game / node / color 及可发送条件，换轮次、终局、翻手、引擎停摆或卸载即取消旧请求后续操作。

```tsx
  const [timeoutError, setTimeoutError] = useState<string | null>(null);
  const timeoutAttemptRef = useRef<{
    key: string; checks: number; retries: number; timer: number | null;
  } | null>(null);
  const timeoutState = session.gameState;
  const timeoutScope = `${sessionId}|${timeoutState?.game_id}|${timeoutState?.current_node_id}|${timeoutState?.player_to_move}|${timeoutState?.end_result}|${timeoutState?.terminal_result}|${timeoutState?.children?.length}|${timeoutState?.last_ladder_error}`;
  useEffect(() => () => {
    const attempt = timeoutAttemptRef.current;
    if (attempt?.timer != null) window.clearTimeout(attempt.timer);
    timeoutAttemptRef.current = null;
  }, [timeoutScope]);
```

`humanColor` 之后增加（API import 加 `ApiError`；token 与数子取同源的 `token ?? undefined`，**不以 token 真值作闸**）：

```tsx
  const handleClockExpired = (color: 'B' | 'W') => {
    if (!sessionId || isGameOver || gameState.player_to_move !== color || gameState.children.length > 0) return;
    if (gameState.last_ladder_error || (isRanked && humanColor !== color)) return;
    const key = `${gameState.game_id}|${gameState.current_node_id}|${color}`;
    if (timeoutAttemptRef.current?.key === key) return;
    const attempt = { key, checks: 1, retries: 0, timer: null as number | null };
    timeoutAttemptRef.current = attempt;
    const expect = { expected_game_id: gameState.game_id, expected_node_id: gameState.current_node_id, color };
    const current = () => timeoutAttemptRef.current === attempt;
    const later = (ms: number) => {
      attempt.timer = window.setTimeout(() => { if (current()) void send(); }, ms);
    };
    const retryDelivery = () => {
      if (!current()) return;
      const delay = [2000, 5000, 10000][attempt.retries++];
      if (delay !== undefined) later(delay);
      else setTimeoutError(t('game:timeout_not_delivered', '超时判定没有送达，请检查连接后重新进入这一局'));
    };
    const send = async (): Promise<void> => {
      if (!current()) return;
      try {
        const res = await API.timeout(sessionId, token ?? undefined, expect);
        if (!current()) return;
        if (res?.state) session.setGameState(res.state);
        setTimeoutError(null);
      } catch (e) {
        if (!current()) return;
        if (e instanceof ApiError && (e.status === 409 || e.status === 403)) {
          try {
            const fresh = await API.getState(sessionId, token ?? undefined);
            if (!current()) return;
            if (fresh?.state) session.setGameState(fresh.state);
            if (e.message.includes('clock_not_expired') && attempt.checks < 2) {
              attempt.checks += 1;
              later(1000);
            }
          } catch { retryDelivery(); }
        } else retryDelivery();
      }
    };
    setTimeoutError(null);
    void send();
  };
```

`GameControlPanel` 传 `onTimeout={handleClockExpired}`；增加独立的 `Snackbar` / `Alert` 展示 `timeoutError`，可关闭。换局后旧请求结果不覆盖新局（`current()`）；同轮次最多两次服务端核实，每次发送遇网络等失败最多额外三次退避。Task 11 的通用错误条不接管这个专用提示。

Run: `npx vitest run src/kiosk/pages/GamePage.playAi.test.tsx src/kiosk/pages/GamePage.test.tsx` → 全 PASS。

- [ ] **Step 5: 真实运行时证据(Playwright,打构建产物)**

`katrain/web/ui/tests/kiosk-screen-05-play-ai.spec.ts`:

```ts
import { expect, test, type Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * 对弈·AI/升降级赛道(superpowers/tracks/kiosk-go-play-ai)的真浏览器实测,1024×600,打构建产物。
 * 只放 jsdom 作不了证的东西:时钟真的在走、右栏承重链(Task 9 追加)。
 * 不改 kiosk-screen-05-game.spec.ts —— 那个文件跨平台赛道也在改。
 */
test.use({ viewport: { width: 1024, height: 600 } });

const SHOTS = resolve(process.cwd(), '../../../superpowers/tracks/kiosk-go-play-ai/visual');
mkdirSync(SHOTS, { recursive: true });

const seat = (name: string, type: string, over: Record<string, number> = {}) => ({
  player_type: type, player_subtype: '', name, calculated_rank: -4, periods_used: 0, main_time_used: 0, ...over,
});

const baseState = (over: Record<string, unknown> = {}) => ({
  game_id: 'play-ai', board_size: [19, 19], komi: 7.5, handicap: 0, ruleset: 'chinese',
  game_type: 'free', count_min_moves: 100, current_node_id: 0, current_node_index: 0,
  history: [{ node_id: 0, score: null, winrate: null, move: null, player: null }],
  player_to_move: 'B', stones: [], last_move: null, prisoner_count: { B: 0, W: 0 },
  analysis: null, commentary: '', is_root: true, is_pass: false, end_result: null, children: [], ghost_stones: [],
  players_info: { B: seat('访客（你）', 'player:human'), W: seat('KataGo', 'player:ai') },
  note: '',
  ui_state: {
    show_children: false, show_dots: false, show_hints: false, show_policy: false,
    show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false,
  },
  ...over,
});

const open = async (page: Page, state: Record<string, unknown>) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'play-ai');
    localStorage.setItem('katrain_language', 'cn');
  });
  // 造的 token 是假的,不接住 WS 屏上会盖一条「实时连接被拒绝」(那一态归 kiosk-screen-05-game.spec.ts 量)
  await page.routeWebSocket('**/ws/**', () => { /* 连上就行,不推任何东西 */ });
  await page.route('**/api/state**', (route) => route.fulfill({ json: { state } }));
  await page.route('**/api/analysis/current', (route) => route.fulfill({ json: { state } }));
  await page.route('**/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/me') return route.fulfill({ json: { id: 1, username: '访客', rank: '5段', credits: 0 } });
    if (path === '/api/v1/vision/status') {
      return route.fulfill({ json: { enabled: false, camera_connected: false, pose_locked: false,
        sync_state: 'unbound', recognition_ready: false, led_connected: null, bound_session_id: null } });
    }
    if (path === '/api/v1/geometry/status') return route.fulfill({ status: 404, json: { detail: 'geometry disabled' } });
    return route.fulfill({ json: {} });
  });
  await page.goto('/kiosk/play/ai/game/play-ai');
  await page.waitForSelector('[data-testid="game-board"] canvas');
};

test('A18 计时局:轮到的一方时钟真的在走,另一方停着,时钟格没被玩家卡裁掉', async ({ page }) => {
  await open(page, baseState({
    timer: {
      paused: false, main_time_used: 12, current_node_time_used: 0, next_player_periods_used: 0, configured: true,
      settings: { main_time: 5, byo_length: 30, byo_periods: 3, minimal_use: 0, sound: false },
    },
    players_info: {
      B: seat('访客（你）', 'player:human', { main_time_used: 12 }),
      W: seat('KataGo', 'player:ai', { main_time_used: 30 }),
    },
  }));
  const clock = (c: 'B' | 'W') => page.locator(`[data-testid="player-card-${c}"] .clock b`);
  await expect(page.locator('[data-testid="player-card-B"] .clock span')).toHaveText('剩余');
  const b0 = await clock('B').textContent();
  const w0 = await clock('W').textContent();
  await expect.poll(() => clock('B').textContent(), { timeout: 3000, message: '轮到的一方时钟没在走' }).not.toBe(b0);
  expect(await clock('W').textContent(), '没轮到的一方时钟在走').toBe(w0);

  const g = await page.evaluate(() => {
    const card = document.querySelector('[data-testid="player-card-B"]')!.getBoundingClientRect();
    const c = document.querySelector('[data-testid="player-card-B"] .clock')!.getBoundingClientRect();
    return { cardRight: Math.round(card.right), clockRight: Math.round(c.right) };
  });
  expect(g.clockRight, '时钟格溢出了玩家卡').toBeLessThanOrEqual(g.cardRight);
  await page.screenshot({ path: `${SHOTS}/a18-timed-game-1024x600.png` });
});
```

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
npm run build
cp ~/.katrain/config.json /tmp/kgpa-katrain-config.json 2>/dev/null || true
lsof -nP -iTCP:8002 -sTCP:LISTEN   # 若被别的 worktree 占着,先协调,不要杀
npx playwright test tests/kiosk-screen-05-play-ai.spec.ts
cp /tmp/kgpa-katrain-config.json ~/.katrain/config.json 2>/dev/null || true
```
Expected: 1 passed;截图 `superpowers/tracks/kiosk-go-play-ai/visual/a18-timed-game-1024x600.png` 生成。**交 Fan 单图确认**(稿子没有计时态参考图)。

- [ ] **Step 6: 两套构建 + 四图 + 提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
npx tsc -b && echo TSC_OK
npx eslint src/kiosk/components/game/goClock.ts src/kiosk/components/game/GameControlPanel.tsx src/kiosk/pages/GamePage.tsx src/api.ts
npm run build && npm run build:kiosk-2d          # api.ts 是共享领地:两套都要绿
lsof -nP -iTCP:5173 -sTCP:LISTEN
npx playwright test --config=playwright.visual.config.ts tests/kiosk-screen-05-game.fourup.spec.ts   # 只跑屏 05;`npm run fourup` 会跑全部 27 屏
git -C /Users/fan/Repositories/katrain-kiosk-go-play-ai status --short superpowers/tracks/kiosk-go-shell-align/visual/05-game
```
Expected: `TSC_OK`;两套构建绿;屏 05 的 fixture 没有 `timer` ⇒ 右栏时钟格文案不变,四图应只有抖动级差异(`<canvas>` 盘,地板约 4500 像素)——
跑第二次 diff 两次结果确认是抖动,**不提交**这一屏的图(`git checkout HEAD -- superpowers/tracks/kiosk-go-shell-align/visual/05-game`,之前先确认该目录没有你要留的未提交改动)。

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
# 基线 diff(后端 + 前端)，两个 comm -13 均须为空
CI=true uv run pytest tests --continue-on-collection-errors -q -rfE -p no:cacheprovider 2>&1 | tee /tmp/kgpa-now-pytest.log
grep -E '^(FAILED|ERROR) tests/' /tmp/kgpa-now-pytest.log | sed -E 's/ - .*//' | LC_ALL=C sort -u > /tmp/kgpa-now-pytest-failed.txt
LC_ALL=C comm -13 /tmp/kgpa-baseline/pytest-failed.txt /tmp/kgpa-now-pytest-failed.txt   # 期望:无输出
git restore --source=HEAD -- katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json
rm -f test_user_data.db
git status --short katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json test_user_data.db   # 期望:空
cd katrain/web/ui
npx vitest run --reporter=verbose 2>&1 | tee /tmp/kgpa-now-vitest.log
grep -E '^\s+×' /tmp/kgpa-now-vitest.log | sed -E 's/^\s+×\s+//; s/ [0-9]+ms$//' | LC_ALL=C sort -u > /tmp/kgpa-now-vitest-failed.txt
LC_ALL=C comm -13 /tmp/kgpa-baseline/vitest-failed.txt /tmp/kgpa-now-vitest-failed.txt   # 期望:无输出
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
git add katrain/web/models.py katrain/web/server.py tests/web_ui/test_play_ai_endgame_api.py \
  katrain/web/interface.py katrain/web/ui/src/api.ts katrain/web/ui/src/kiosk/components/game/goClock.ts \
  katrain/web/ui/src/kiosk/components/game/goClock.test.ts katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx \
  katrain/web/ui/src/kiosk/components/game/GameControlPanel.playAi.test.tsx katrain/web/ui/src/kiosk/pages/GamePage.tsx \
  katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx katrain/web/ui/tests/kiosk-screen-05-play-ai.spec.ts \
  tests/test_play_ai_endgame.py superpowers/tracks/kiosk-go-play-ai/visual/a18-timed-game-1024x600.png
git diff --cached --stat
git commit -m "feat(kiosk): 开局选了用时,对局屏却不倒计时、不读秒、到点不判负 —— 玩家卡接上时钟

A18(P1)。08-22 重画屏 05 时按「kiosk 没有时间控件」的错误前提撤了计时。服务端新增 timer.configured
(星阵 / 大厅局继承默认时限但没人配过,不能当计时局);玩家卡按 update_timer 同一算法外推剩余与读秒,
轮到的一方耗尽调 /api/timeout(升降级 AI 回合与引擎停摆时不发)。
超时绑定局/手/方，提交锁内核轮次与服务端时钟；核实不了不判负。409/403 重同步，网络等失败 2/5/10 秒退避后提示未送达。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```
**必须上板**(记进 Task 12 清单):RK3562 上一局「仅读秒 30秒×3」让读秒走完,确认判负且结果落账。

---

### Task 7: A3 「实地」「厚势」开局 500;五个策略各有一句核过实现的说明

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx:32-46`(`AI_STRATEGY_HINT` 与其注释)、`:506-512`(策略选项的 `value`)
- Test: `katrain/web/ui/src/kiosk/pages/AiSetupPage.test.tsx`(**文件末尾追加一个顶层 `describe`**,复用文件里既有的桩 `gameSetup` / `renderPage`)

**Interfaces:**
- Consumes: 既有 `/api/game/setup`(`ai_strategy` 原样交给 `update_player(player_subtype=…)`,再由 `core/ai.py` `STRATEGY_REGISTRY` 与 `ai_rank_estimation` 查表)
- Produces: 开局设置送出的策略 id 集合 = `ai:human` / `ai:default` / `ai:p:territory` / `ai:p:influence` / `ai:policy`(全部是 `core/constants.py` 里真实存在的 id)

- [ ] **Step 1: 写失败的测试(追加到 `AiSetupPage.test.tsx` 末尾)**

```tsx
// ── A3 · AI 策略(kiosk-go-play-ai)──────────────────────────────────────────
// 2026-09-14 本机复现:「实地」「厚势」送的是 `ai:territory` / `ai:influence`,真实 id 是
// `ai:p:territory` / `ai:p:influence`(core/constants.py:50-51)。`update_player` → `ai_rank_estimation`
// → `AI_STRENGTH['ai:territory']` 抛 KeyError,开局 500。
describe('A3 · AI 策略', () => {
  beforeEach(() => {
    localStorage.removeItem(PLAY_ON_BOARD_KEY);
    createSession.mockClear();
    gameSetup.mockClear();
    mockNavigate.mockReset();
  });

  it.each([
    ['实地', 'ai:p:territory'],
    ['厚势', 'ai:p:influence'],
  ])('选「%s」开局,送出的是真实策略 id %s', async (name, id) => {
    renderPage('free');
    const user = userEvent.setup();
    await user.click(within(screen.getByTestId('setup-strategy')).getByRole('button', { name }));
    await user.click(screen.getByRole('button', { name: /开始对局|开始计分局/i }));
    await waitFor(() => expect(gameSetup).toHaveBeenCalledWith('s1', 'free', expect.objectContaining({ ai_strategy: id })));
  });

  it.each([
    ['拟人', '拟人:按所选棋力下出该水平的棋,包括那个水平会犯的错'],
    ['KataGo', 'KataGo:每手都下引擎搜索后的第一选择,不放水'],
    ['实地', '实地:偏爱三线及以下的低位,在随机抽出的一批候选里按这个偏好挑,不是全力'],
    ['厚势', '厚势:偏爱四线及以上的高位,在随机抽出的一批候选里按这个偏好挑,不是全力'],
    ['策略', '策略:不看搜索结果,直接下策略网络的第一直觉;开局前 22 手随机一些'],
  ])('选中「%s」时说明行说它真在干什么', async (name, hint) => {
    renderPage('free');
    const user = userEvent.setup();
    await user.click(within(screen.getByTestId('setup-strategy')).getByRole('button', { name }));
    expect(screen.getByText(hint)).toBeInTheDocument();
  });
});
```

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui && npx vitest run src/kiosk/pages/AiSetupPage.test.tsx -t "A3"`
Expected: 两条 id 用例 FAIL(收到 `ai:territory` / `ai:influence`);说明行除「拟人」外 4 条 FAIL。

- [ ] **Step 2: 实现**

`AiSetupPage.tsx` 把 `AI_STRATEGY_HINT` 上面那段注释与函数整段替换为:

```tsx
/**
 * `.kiosk-opthint` 写的是**当前选中项**的大白话(规范 §11 v1.21)。
 *
 * 每一句都是对产品行为的断言,所以每一句都对着 `core/ai.py` 核过(2026-09-14):
 *   · KataGo `ai:default` → `DefaultStrategy`:等分析完,下 `candidate_moves[0]`;
 *   · 实地 `ai:p:territory` → `TerritoryStrategy`:`generate_influence_territory_weights` 按离边距离加权,
 *     `threshold 3.5` ⇒ 三线及以内满权、往里衰减;走 `PickBasedStrategy`(`pick_n 5` + `pick_frac 0.3` 随机抽候选);
 *   · 厚势 `ai:p:influence` → `InfluenceStrategy`:同一个函数反过来,三线及以内按 `line_weight 10` 压权;
 *   · 策略 `ai:policy` → `PolicyStrategy`:照常等分析回来,但只取 `policy_ranking[0]`(不看搜索结果);`opening_moves 22` 手内改走 `WeightedStrategy`。
 * `.kiosk-opthint` 定高(`--opthint-h`),说明换一句不会让下面那些组跳。
 */
const AI_STRATEGY_HINT = (t: (en: string, zh: string) => string): Record<string, string> => ({
  'ai:human': t(
    'Human-like: plays at the chosen strength, mistakes of that level included',
    '拟人:按所选棋力下出该水平的棋,包括那个水平会犯的错',
  ),
  'ai:default': t('setup:strategy_hint_default', 'KataGo:每手都下引擎搜索后的第一选择,不放水'),
  'ai:p:territory': t('setup:strategy_hint_territory', '实地:偏爱三线及以下的低位,在随机抽出的一批候选里按这个偏好挑,不是全力'),
  'ai:p:influence': t('setup:strategy_hint_influence', '厚势:偏爱四线及以上的高位,在随机抽出的一批候选里按这个偏好挑,不是全力'),
  'ai:policy': t('setup:strategy_hint_policy', '策略:不看搜索结果,直接下策略网络的第一直觉;开局前 22 手随机一些'),
});
```

策略选项两行改为:

```tsx
                        // ⚠️ id 必须是 core/constants.py 里真实存在的那个:`ai:territory` 这种假 id 在
                        // update_player → ai_rank_estimation 里 KeyError,开局直接 500(A3,2026-09-14 复现)。
                        { value: 'ai:p:territory', label: t('setup:style_territory', '实地') },
                        { value: 'ai:p:influence', label: t('Influence', '厚势') },
```

- [ ] **Step 3: 验证**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
npx vitest run src/kiosk/pages/AiSetupPage.test.tsx src/kiosk/__tests__/AiSetupPage.test.tsx
npx tsc -b && echo TSC_OK
npx eslint src/kiosk/pages/AiSetupPage.tsx
```
Expected: 全 PASS;`TSC_OK`。

真实运行时一张图(说明行定高、最长那句不溢出):`npm run dev -- --host 127.0.0.1 --port 5173`(先 `lsof` 看端口),`/browse` 打开 `http://127.0.0.1:5173/kiosk/play/ai/setup/free`,1024×600,点「实地」,
截图存 `superpowers/tracks/kiosk-go-play-ai/visual/a3-strategy-hint-territory-1024x600.png`。
Expected: 说明行一行或两行内放下,下面的组没有被推动。交 Fan 单图确认。屏 02 四图默认选中「拟人」,那一帧不变,不重跑。

- [ ] **Step 4: 基线 diff(后端 + 前端)后提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
# 基线 diff(后端 + 前端)，两个 comm -13 均须为空
CI=true uv run pytest tests --continue-on-collection-errors -q -rfE -p no:cacheprovider 2>&1 | tee /tmp/kgpa-now-pytest.log
grep -E '^(FAILED|ERROR) tests/' /tmp/kgpa-now-pytest.log | sed -E 's/ - .*//' | LC_ALL=C sort -u > /tmp/kgpa-now-pytest-failed.txt
LC_ALL=C comm -13 /tmp/kgpa-baseline/pytest-failed.txt /tmp/kgpa-now-pytest-failed.txt   # 期望:无输出
git restore --source=HEAD -- katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json
rm -f test_user_data.db
git status --short katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json test_user_data.db   # 期望:空
cd katrain/web/ui
npx vitest run --reporter=verbose 2>&1 | tee /tmp/kgpa-now-vitest.log
grep -E '^\s+×' /tmp/kgpa-now-vitest.log | sed -E 's/^\s+×\s+//; s/ [0-9]+ms$//' | LC_ALL=C sort -u > /tmp/kgpa-now-vitest-failed.txt
LC_ALL=C comm -13 /tmp/kgpa-baseline/vitest-failed.txt /tmp/kgpa-now-vitest-failed.txt   # 期望:无输出
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
git add katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx katrain/web/ui/src/kiosk/pages/AiSetupPage.test.tsx \
  superpowers/tracks/kiosk-go-play-ai/visual/a3-strategy-hint-territory-1024x600.png
git diff --cached --stat
git commit -m "fix(kiosk): 开局选「实地」「厚势」直接 500 —— 策略 id 用真实的 ai:p:*,五个策略各补一句核过实现的说明

A3(核实后升为 P1)。条目原写「四个策略都能选、能下」不成立:ai:territory / ai:influence 不存在,
update_player 查 AI_STRENGTH 抛 KeyError。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: A2(文案)+ A15 升降级 503 按原因说话

**Files:**
- Create: `katrain/web/ui/src/features/aiLadder/startErrors.ts`、`startErrors.test.ts` —— **共享领地**(不许 import kiosk/galaxy/pages)
- Modify: `katrain/web/ui/src/features/aiLadder/useAiLadderStatus.ts:16-22`(`aiLadderStatusErrorMessage` 的 503 分支)
- Modify: `katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx:178-182`(`handleStart` 的 503 分支)+ import
- Test: `katrain/web/ui/src/kiosk/pages/AiSetupPage.test.tsx`(末尾追加)

**Interfaces:**
- Consumes: `i18n.t(key, fallback)`(`src/i18n.ts`,与 `features/aiLadder/copy.ts` 同一用法);`AiLadderApiError.message` = 服务端 `detail` 原文(`features/aiLadder/api.ts:55-62`)
- Produces: `type AiLadderUnavailableReason = 'offline' | 'not_authoritative' | 'engine_cannot_serve' | 'cloud_unconfirmed' | 'unknown'`;
  `aiLadderUnavailableReason(detail: string): AiLadderUnavailableReason`;`aiLadderStatusUnavailableMessage(detail: string): string`;`aiLadderStartUnavailableMessage(detail: string): string`

- [ ] **Step 1: 写失败的测试**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
git ls-files src/features/aiLadder/startErrors.ts src/features/aiLadder/startErrors.test.ts; ls src/features/aiLadder/startErrors.ts 2>/dev/null   # 期望:无输出
```

`src/features/aiLadder/startErrors.test.ts`:

```ts
import { describe, expect, test } from 'vitest';
import {
  aiLadderStartUnavailableMessage,
  aiLadderStatusUnavailableMessage,
  aiLadderUnavailableReason,
} from './startErrors';

describe('升降级 503 按服务端 detail 分原因(A15 / A2)', () => {
  test.each([
    ['Remote server unavailable', 'offline'],
    ['Ranked AI ladder authority is unavailable on this node', 'not_authoritative'],
    ['Ranked engine cannot serve the seated rung', 'engine_cannot_serve'],
    ['Ranked game reservation is awaiting cloud expiry', 'cloud_unconfirmed'],
    ['Ranked game activation is awaiting cloud reconciliation', 'cloud_unconfirmed'],
    // kiosk 开局页的桩把整段 `Request failed 503: {...}` 塞进 message —— 包含判定对两种形状都成立
    ['Request failed 503: {"detail":"Ranked engine cannot serve the seated rung"}', 'engine_cannot_serve'],
    ['Could not create game session', 'unknown'],
  ])('%s → %s', (detail, reason) => {
    expect(aiLadderUnavailableReason(detail)).toBe(reason);
  });

  test('断网时状态接口不再说「本机不记升降级成绩」', () => {
    const msg = aiLadderStatusUnavailableMessage('Remote server unavailable');
    expect(msg).toContain('连不上云端');
    expect(msg).not.toContain('本机不记');
  });

  test('节点确实不记成绩时原句不变', () => {
    expect(aiLadderStatusUnavailableMessage('Ranked AI ladder authority is unavailable on this node'))
      .toBe('本机不记升降级成绩，暂时无法开始升降级对弈');
  });

  test('引擎带不动这一档:说没开局、段位没动,不叫人「稍后再试」—— 顶端 6 档在盒上不会自己好', () => {
    const msg = aiLadderStartUnavailableMessage('Ranked engine cannot serve the seated rung');
    expect(msg).toContain('本次没有开局');
    expect(msg).not.toContain('稍后再试');
  });

  test('云端未确认:不许说「本次没有开局」—— 那一局可能已经在云端开出来了', () => {
    expect(aiLadderStartUnavailableMessage('Ranked game activation is awaiting cloud reconciliation')).not.toContain('本次没有开局');
  });
});
```

追加到 `src/kiosk/pages/AiSetupPage.test.tsx` 末尾:

```tsx
// ── A15 · 升降级开局 503 分原因(kiosk-go-play-ai)────────────────────────────
describe('A15 · 升降级开局 503 分原因', () => {
  beforeEach(() => {
    startRanked.mockReset();
    mockNavigate.mockReset();
    // 必须清:排在前面的「升降级挡局面板」组最后一条把 blocking_game 设成 reserved 且不还原,
    // 带着它渲染 ranked,右栏是挡局面板、没有开始按钮,这条会因为找不到按钮而红(红得不对)。
    withBlocking(null);
  });

  it('盒子断网:说「连不上云端」,不说引擎不可用', async () => {
    const err: Error & { status?: number } = new Error('Remote server unavailable');
    err.status = 503;
    startRanked.mockRejectedValueOnce(err);
    renderPage('ranked');
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /开始对局|开始计分局/i }));
    expect(await screen.findByText(/连不上云端/)).toBeInTheDocument();
    expect(screen.queryByText(/升降级引擎暂时不可用/)).not.toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
```

Run: `npx vitest run src/features/aiLadder/startErrors.test.ts src/kiosk/pages/AiSetupPage.test.tsx -t "503|按服务端"`
Expected: `startErrors.test.ts` 整个 FAIL(模块不存在);A15 那条 FAIL(屏上是「升降级引擎暂时不可用…」)。

- [ ] **Step 2: 实现**

`src/features/aiLadder/startErrors.ts`:

```ts
import { i18n } from '../../i18n';

/**
 * 升降级的 503 按服务端 `detail` 分原因(A15 / A2)。
 *
 * 同一个 503 背着几件不同的事(`katrain/web/api/v1/endpoints/ai_ladder.py`):
 *   · `Remote server unavailable` —— 盒子连不上云端(`_remote`);
 *   · `Ranked AI ladder authority is unavailable on this node` —— 这个节点不记升降级成绩(`_require_authority`);
 *   · `Ranked engine cannot serve the seated rung` —— 本机引擎带不动这一档(`_preflight_ladder_engine`;
 *     顶端 6 个 b18 档在只宣告 b6c96 的盒子上必然如此,怎么修待 Fan 拍板);
 *   · `…awaiting cloud expiry` / `…awaiting cloud reconciliation` —— 云端还没确认这一局。
 * 从前一律翻成「本机不记成绩」或「引擎暂时不可用,请稍后再试」:断网的人以为这台盒子不支持升降级,
 * 顶端档位的人被叫去「稍后再试」一件永远不会自己好的事。
 * 判定用「包含」:真 `AiLadderApiError.message` 是 detail 原文,旧桩里是整段 `Request failed 503: {...}`。
 */
export type AiLadderUnavailableReason = 'offline' | 'not_authoritative' | 'engine_cannot_serve' | 'cloud_unconfirmed' | 'unknown';

export function aiLadderUnavailableReason(detail: string): AiLadderUnavailableReason {
  if (detail.includes('Remote server unavailable')) return 'offline';
  if (detail.includes('authority is unavailable')) return 'not_authoritative';
  if (detail.includes('cannot serve the seated rung')) return 'engine_cannot_serve';
  if (detail.includes('awaiting cloud')) return 'cloud_unconfirmed';
  return 'unknown';
}

/** `/ai-ladder/status` 503 时屏上那句话。 */
export function aiLadderStatusUnavailableMessage(detail: string): string {
  return aiLadderUnavailableReason(detail) === 'offline'
    ? i18n.t('ladder:status_offline', '连不上云端。升降级对弈要联网，检查网络后点「重试」')
    : i18n.t('ladder:load_error_not_authoritative', '本机不记升降级成绩，暂时无法开始升降级对弈');
}

/** `/ai-ladder/start` 503 时屏上那句话。除「云端未确认」外,每一句都说清局没开成、段位没动。 */
export function aiLadderStartUnavailableMessage(detail: string): string {
  switch (aiLadderUnavailableReason(detail)) {
    case 'offline':
      return i18n.t('ladder:start_offline', '连不上云端。升降级对弈要联网，本次没有开局，也不影响你的段位；检查网络后再试');
    case 'engine_cannot_serve':
      return i18n.t('ladder:start_engine_cannot_serve', '这台盒子的引擎现在带不动这一档对手。本次没有开局，也不影响你的段位');
    case 'cloud_unconfirmed':
      return i18n.t('ladder:start_cloud_unconfirmed', '云端还没确认这一局的状态，先别重复开局；回到这一屏会显示它的状态');
    case 'not_authoritative':
      return i18n.t('ladder:load_error_not_authoritative', '本机不记升降级成绩，暂时无法开始升降级对弈');
    default:
      return i18n.t('ladder:engine_unavailable_start', '升降级引擎暂时不可用，本次没有开局，也不影响你的段位。请稍后再试。');
  }
}
```

`useAiLadderStatus.ts`:import 区加 `import { aiLadderStatusUnavailableMessage } from './startErrors';`,
`if (error.status === 503) return AI_LADDER_COPY.loadErrorNotAuthoritative;` 改为
`if (error.status === 503) return aiLadderStatusUnavailableMessage(error.message);`。

`AiSetupPage.tsx`:import 区加 `import { aiLadderStartUnavailableMessage } from '../../features/aiLadder/startErrors';`,503 分支整段替换为:

```tsx
      } else if (status === 503 && isRanked) {
        /* 开局前的 503 背着几件不同的事(断网 / 引擎带不动这一档 / 云端未确认),按服务端 detail 分开说,
           见 features/aiLadder/startErrors.ts。 */
        setAuthPrompt('');
        setError(aiLadderStartUnavailableMessage(typeof e?.message === 'string' ? e.message : ''));
```

- [ ] **Step 3: 验证(共享领地 ⇒ 两套构建)并提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
npx vitest run src/features/aiLadder/startErrors.test.ts src/features/aiLadder/useAiLadderStatus.test.tsx src/kiosk/pages/AiSetupPage.test.tsx src/galaxy/pages/AiSetupPage.test.tsx
npx tsc -b && echo TSC_OK
npx eslint src/features/aiLadder/startErrors.ts src/features/aiLadder/useAiLadderStatus.ts src/kiosk/pages/AiSetupPage.tsx
npm run build && npm run build:kiosk-2d
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
# 基线 diff(后端 + 前端)，两个 comm -13 均须为空
CI=true uv run pytest tests --continue-on-collection-errors -q -rfE -p no:cacheprovider 2>&1 | tee /tmp/kgpa-now-pytest.log
grep -E '^(FAILED|ERROR) tests/' /tmp/kgpa-now-pytest.log | sed -E 's/ - .*//' | LC_ALL=C sort -u > /tmp/kgpa-now-pytest-failed.txt
LC_ALL=C comm -13 /tmp/kgpa-baseline/pytest-failed.txt /tmp/kgpa-now-pytest-failed.txt   # 期望:无输出
git restore --source=HEAD -- katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json
rm -f test_user_data.db
git status --short katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json test_user_data.db   # 期望:空
cd katrain/web/ui
npx vitest run --reporter=verbose 2>&1 | tee /tmp/kgpa-now-vitest.log
grep -E '^\s+×' /tmp/kgpa-now-vitest.log | sed -E 's/^\s+×\s+//; s/ [0-9]+ms$//' | LC_ALL=C sort -u > /tmp/kgpa-now-vitest-failed.txt
LC_ALL=C comm -13 /tmp/kgpa-baseline/vitest-failed.txt /tmp/kgpa-now-vitest-failed.txt   # 期望:无输出
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
git add katrain/web/ui/src/features/aiLadder/startErrors.ts katrain/web/ui/src/features/aiLadder/startErrors.test.ts \
  katrain/web/ui/src/features/aiLadder/useAiLadderStatus.ts katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx katrain/web/ui/src/kiosk/pages/AiSetupPage.test.tsx
git diff --cached --stat
git commit -m "fix(ladder): 升降级 503 一律说成「本机不记成绩 / 引擎暂时不可用」—— 按服务端 detail 分原因

A15(P2)+ A2 文案。断网说连不上云端;引擎带不动这一档不再叫人稍后再试(顶端 6 个 b18 档在盒上不会自己好,
怎么修待 Fan 拍板);云端未确认不说「本次没有开局」。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```
Expected: 全 PASS;`TSC_OK`;两套构建绿(`verify:kiosk-2d` exit 0)。

---

## Phase 2 · P2 / P3

### Task 9: N14 + A11(+ A9 与拍板无关的一半)右栏按对局类型摆对

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/game/gameKinds.ts`
- Modify: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx`(`TWO_HUMAN_GAME_TYPES` 常量移走、`freeVsAi`、`analysisActions`、`moveRows`、棋谱折叠块的渲染条件与注释)
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx:291`(`wantAnalysis`)
- Modify: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.test.tsx`(改一条已被 A11 推翻的用例:「棋谱只在星阵屏出现」)
- Test: `GameControlPanel.playAi.test.tsx`、`GamePage.playAi.test.tsx`、`tests/kiosk-screen-05-play-ai.spec.ts`(追加)

**Interfaces:**
- Consumes: Task 1 的页面测试桩；Task 6 的 `GameControlPanel.playAi.test.tsx` 的 `panel` / `base`； Task 6 的 `SeatRow` 改动(同文件,先做 Task 6);Task 6 spec 的 `open` / `baseState` / `seat` / `SHOTS`
- Produces: `gameKinds.ts` 导出 `TWO_HUMAN_GAME_TYPES: Set<string>` 与
  `isFreeVsAi({ gameType, engineMode, isRanked }: { gameType: string | null | undefined; engineMode?: boolean; isRanked?: boolean }): boolean`

- [ ] **Step 1: 写失败的测试**

追加到 `src/kiosk/components/game/GameControlPanel.playAi.test.tsx` 末尾:

```tsx
describe('N14 + A11 · 右栏按对局类型', () => {
  const hist = [
    { node_id: 0, score: null, winrate: null, move: null, player: null },
    { node_id: 1, score: null, winrate: null, move: 'Q16', player: 'B' },
    { node_id: 2, score: null, winrate: null, move: 'D4', player: 'W' },
  ] as GameState['history'];
  const labels = () => Array.from(screen.getByTestId('game-actions').querySelectorAll('button'))
    .map((b) => b.textContent?.trim());

  test('升降级局:不渲染「领地」「AI支招」(规范 §8:禁的时候整块不渲染)', () => {
    panel(base({ game_type: 'ai_ladder_ranked' }), { isRanked: true });
    expect(labels()).toEqual(['数子', '停一手', '认输']);
  });

  test.each([
    ['升降级', { game_type: 'ai_ladder_ranked' }, { isRanked: true, analysisToggles: { score: true } }],
    ['本地对局', { game_type: 'pvp_local' }, { analysisToggles: { score: true } }],
    ['关掉图表的自由对弈', { game_type: 'free' }, { analysisToggles: { score: false } }],
  ])('%s:胜率块不在时,右栏中段是棋谱', (_name, over, props) => {
    panel(base({ ...(over as Partial<GameState>), history: hist, current_node_index: 2 }), props);
    expect(screen.getByTestId('game-moves-fold')).toBeInTheDocument();
    expect(document.querySelector('.kiosk-fold[data-fold="eval"]')).toBeNull();
  });

  test('开着图表的自由对弈:胜率块在、棋谱不在(屏 05 不变)', () => {
    panel(base({ history: hist, current_node_index: 2 }), { analysisToggles: { score: true } });
    expect(screen.queryByTestId('game-moves-fold')).toBeNull();
    expect(document.querySelector('.kiosk-fold[data-fold="eval"]')).not.toBeNull();
  });
});
```

追加到 `src/kiosk/pages/GamePage.playAi.test.tsx` 末尾:

```tsx
describe('A9(与拍板无关的一半)· 不渲染胜率块的局不白算分析', () => {
  it('本地对局:「图表」开关默认开着,也不请求按需分析', () => {
    const spy = vi.spyOn(API, 'analyzeCurrent').mockResolvedValue({});
    sessionMock.gameState = makeState({
      game_type: 'pvp_local',
      players_info: { B: seat('player:human', '小明'), W: seat('player:human', '小红') },
    });
    renderPage();
    expect(spy).not.toHaveBeenCalled();
  });

  it('人机自由对弈照旧请求(默认开还是关等 Fan 定,本轮不动)', () => {
    const spy = vi.spyOn(API, 'analyzeCurrent').mockResolvedValue({});
    sessionMock.gameState = makeState();
    renderPage();
    expect(spy).toHaveBeenCalledWith('play-ai-s1');
  });
});
```

`src/kiosk/components/game/GameControlPanel.test.tsx` 里把

```tsx
  test('棋谱只在星阵屏出现 —— 屏 05 那块地方归胜率图', () => {
    panel({ history: hist([['Q16', 'B'], ['D4', 'W']]) });
    expect(screen.queryByTestId('game-moves-fold')).toBeNull();
  });
```

改为

```tsx
  // A11(kiosk-go-play-ai,2026-09-14)推翻了「棋谱只在星阵屏」:scope §27 那条概念债说的就是
  // 「没有哪种对局原则上拿不到自己下过的手」。现在胜率块不在的局中段都是棋谱;只有胜率块开着时那块地方归胜率图。
  test('胜率块开着时棋谱不出现 —— 屏 05 那块地方归胜率图', () => {
    panel({ history: hist([['Q16', 'B'], ['D4', 'W']]) }, { analysisToggles: { score: true } });
    expect(screen.queryByTestId('game-moves-fold')).toBeNull();
  });
```

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui && npx vitest run src/kiosk/components/game/GameControlPanel.playAi.test.tsx src/kiosk/components/game/GameControlPanel.test.tsx src/kiosk/pages/GamePage.playAi.test.tsx`
Expected: N14 标签那条 FAIL(多了「领地」「AI支招」);三条「中段是棋谱」FAIL;「本地对局不请求」FAIL;其余 PASS。

- [ ] **Step 2: 实现**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
git ls-files src/kiosk/components/game/gameKinds.ts; ls src/kiosk/components/game/gameKinds.ts 2>/dev/null   # 期望:无输出
```

`src/kiosk/components/game/gameKinds.ts`:

```ts
import { isRankedGameType } from '../../../features/aiLadder/gameType';

/** 两个人面对面下的局:胜率图整块不渲染、没有悔棋(规范 §8「按对弈方式判」那张表)。 */
export const TWO_HUMAN_GAME_TYPES = new Set(['pvp_local', 'pvp_online']);

/**
 * 这一局是不是**人机自由对弈**。规范 §8 那张表只有一句话:自由对弈能用的,另外四种(升降级 / 本地两人 /
 * 在线大厅 / 星阵人机)一概不能。胜率块、悔棋、「图表」触发的按需分析都认这一个判据 —— 从前 GamePage 的按需分析
 * 只认开关、不认局,本地对局不渲染胜率块却每手照样请求一次(A9)。
 * 升降级两个操作数都读:`isRanked` 是调用方给的,`gameType` 是这一局自己带的 —— 少传一次 prop 不该把闸打开。
 */
export function isFreeVsAi({ gameType, engineMode = false, isRanked = false }: {
  gameType: string | null | undefined;
  engineMode?: boolean;
  isRanked?: boolean;
}): boolean {
  return !engineMode && !isRanked && !isRankedGameType(gameType) && !TWO_HUMAN_GAME_TYPES.has(gameType ?? 'free');
}
```

`GameControlPanel.tsx`:

1. 删掉文件里的 `const TWO_HUMAN_GAME_TYPES = new Set(['pvp_local', 'pvp_online']);`(连同它上面那行注释),import 区加 `import { isFreeVsAi } from './gameKinds';`。
2. `const freeVsAi = !engineMode && !rankedGame && !TWO_HUMAN_GAME_TYPES.has(gameState.game_type ?? 'free');` 改为
   `const freeVsAi = isFreeVsAi({ gameType: gameState.game_type, engineMode, isRanked: rankedGame });`。
3. `const moveRows = engineMode ? toMoveRows(gameState.history) : [];` 改为:

```tsx
  // A11:棋谱是**无条件**的 —— 没有哪种对局原则上拿不到自己下过的手(scope §27 那条概念债)。
  // 胜率块不在的局(星阵 / 升降级 / 本地对局 / 关掉图表),中段那块高度归棋谱;胜率块开着时归胜率块。
  const showMoves = engineMode || !showScore;
  const moveRows = showMoves ? toMoveRows(gameState.history) : [];
```

4. `const analysisActions: KioskAction[] = engineMode ? [] : [` 改为 `const analysisActions: KioskAction[] = engineMode || rankedGame ? [] : [`,并在这一行上面加注释:

```tsx
  // N14:升降级局**整块不渲染**「领地」「AI支招」(规范 §8;实体对弈 PRD「升降级:支招按钮不可见」)。
  // 从前领地能按亮、盘上永远不出色块 —— 按需分析对升降级是关的(GamePage 早退 + 服务端拒)。
```

5. 棋谱折叠块的 `{engineMode && (` 改为 `{showMoves && (`;它上面那段注释第一句「棋谱 —— 只有星阵屏有(稿子 `:1833`)」改为「棋谱 —— 胜率块不在的局都有(星阵屏稿子 `:1833`;A11 扩到升降级 / 本地对局 / 关掉图表)」。

`GamePage.tsx`:import 区加 `import { isFreeVsAi } from '../components/game/gameKinds';`,`const wantAnalysis = analysisToggles.ownership || analysisToggles.score;` 改为:

```tsx
  // 「图表」只在胜率块真的会渲染的局里触发按需分析 —— 本地对局等两人局不渲染胜率块,
  // 从前照样每手请求一次,结果无处显示、白占本机引擎(A9 与拍板无关的那一半;默认开还是关等 Fan 定)。
  const wantAnalysis = analysisToggles.ownership
    || (analysisToggles.score && isFreeVsAi({ gameType: session.gameState?.game_type, engineMode }));
```

Run: 同 Step 1 的命令 → Expected: 全 PASS。另跑 `npx vitest run src/kiosk/__tests__/GamePageLedBadge.test.tsx src/kiosk/__tests__/GamePageEngine.test.tsx src/kiosk/pages/GamePage.test.tsx` → 全 PASS。

- [ ] **Step 3: 承重实测(真浏览器)—— 追加到 `tests/kiosk-screen-05-play-ai.spec.ts` 末尾**

判据先写死:① 满态棋谱 body 自己溢出(数据造到装不下,否则这一轮的数不算);② 右栏不滚;③ 棋谱块不被右栏裁;
④ 动作区贴右栏底;⑤ **中段没有洞**:显示开关排的底 + 12(`--rail-gap`)= 动作区的顶(没有 `grow` 时洞就出在这两者之间,
这是 A11 要消灭的那块空白);⑥ 真滚轮拨得动。最空态(0 手)再量 ④⑤ —— 塌陷类缺陷只在最空状态下现形。

```ts
// ── Task 9 · N14 + A11:胜率块不在的局,右栏中段是棋谱 ───────────────────────────────
const COLS = 'ABCDEFGHJKLMNOPQRST';
const longHistory = (n: number) => [
  { node_id: 0, score: null, winrate: null, move: null, player: null },
  ...Array.from({ length: n }, (_, i) => ({
    node_id: i + 1, score: null, winrate: null,
    move: `${COLS[i % 19]}${(Math.floor(i / 19) % 19) + 1}`, player: i % 2 === 0 ? 'B' : 'W',
  })),
];

const railChain = (page: Page) => page.evaluate(() => {
  const rail = document.querySelector('.kiosk-rail') as HTMLElement;
  const fold = document.querySelector('[data-testid="game-moves-fold"]') as HTMLElement | null;
  const body = fold?.querySelector('.kiosk-fold__body') as HTMLElement | null;
  const toggles = document.querySelector('.kiosk-rail .gtoggles') as HTMLElement;
  const acts = document.querySelector('[data-testid="game-actions"]') as HTMLElement;
  const rb = rail.getBoundingClientRect();
  const fb = fold?.getBoundingClientRect();
  return {
    hasFold: !!fold,
    hasEval: !!document.querySelector('.kiosk-fold[data-fold="eval"]'),
    labels: Array.from(acts.querySelectorAll('button')).map((b) => b.textContent?.trim()),
    bodyOverflow: body ? body.scrollHeight - body.clientHeight : null,
    foldH: fb ? Math.round(fb.height) : null,
    foldInsideRail: fb ? fb.top >= rb.top - 0.5 && fb.bottom <= rb.bottom + 0.5 : null,
    railOverflow: rail.scrollHeight - rail.clientHeight,
    togglesBottom: Math.round(toggles.getBoundingClientRect().bottom),
    actionsTop: Math.round(acts.getBoundingClientRect().top),
    actionsBottom: Math.round(acts.getBoundingClientRect().bottom),
    railBottom: Math.round(rb.bottom),
    docScrollHeight: document.documentElement.scrollHeight,
    innerHeight: window.innerHeight,
  };
});

const KINDS = [
  ['ranked', { game_type: 'ai_ladder_ranked' }],
  ['pvp-local', { game_type: 'pvp_local', players_info: { B: seat('小明', 'player:human'), W: seat('小红', 'player:human') } }],
] as const;

for (const [kind, over] of KINDS) {
  test(`承重 · ${kind}:200 手时棋谱自己滚、右栏不滚、中段没有洞、动作区贴底`, async ({ page }) => {
    await open(page, baseState({ ...over, history: longHistory(200), current_node_id: 200, current_node_index: 200 }));
    await page.waitForSelector('[data-testid="game-moves-fold"] .mvrows .mv');
    const g = await railChain(page);
    console.log(`[play-ai/${kind}/full]`, JSON.stringify(g));

    expect(g.hasEval, '胜率块不该在').toBe(false);
    expect(g.hasFold, '棋谱块没出来').toBe(true);
    expect(g.bodyOverflow, '棋谱没溢出 —— 数据没造够,这一轮量出来的数一概不算').toBeGreaterThan(0);
    expect(g.railOverflow, '右栏被棋谱顶破了').toBeLessThanOrEqual(0);
    expect(g.foldInsideRail, '棋谱块被右栏裁掉一截').toBe(true);
    expect(g.actionsBottom, '动作区没贴右栏底').toBe(g.railBottom);
    expect(g.actionsTop - g.togglesBottom, '显示开关与动作区之间有洞 —— 棋谱没把中段吃满').toBeLessThanOrEqual(13);
    expect(g.docScrollHeight, '整页纵向溢出').toBeLessThanOrEqual(g.innerHeight);

    const body = page.locator('[data-testid="game-moves-fold"] .kiosk-fold__body');
    await body.evaluate((el) => { el.scrollTop = 0; });
    const box = (await body.boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.wheel(0, 300);
    // Chromium 的滚轮滚动是异步的,派完立刻读 scrollTop 还是 0 —— 用 poll
    await expect.poll(() => body.evaluate((el) => el.scrollTop), { message: '真滚轮拨不动' }).toBeGreaterThan(0);
    await page.screenshot({ path: `${SHOTS}/n14-a11-${kind}-rail-1024x600.png` });
  });

  test(`承重 · ${kind}:0 手时空态说话、中段没有洞、动作区贴底`, async ({ page }) => {
    await open(page, baseState({ ...over }));
    await page.waitForSelector('[data-testid="game-moves-fold"]');
    const g = await railChain(page);
    console.log(`[play-ai/${kind}/empty]`, JSON.stringify(g));

    await expect(page.locator('[data-testid="game-moves-fold"] .kiosk-fold__body')).toHaveText('这一局还没有着法');
    expect(g.actionsBottom, '动作区没贴右栏底').toBe(g.railBottom);
    expect(g.actionsTop - g.togglesBottom, '最空态下中段塌出一个洞').toBeLessThanOrEqual(13);
    expect(g.railOverflow, '右栏溢出').toBeLessThanOrEqual(0);
  });
}

test('升降级局动作区:没有领地、AI支招、图表、悔棋', async ({ page }) => {
  await open(page, baseState({ game_type: 'ai_ladder_ranked' }));
  expect((await railChain(page)).labels).toEqual(['数子', '停一手', '认输']);
});
```

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
npm run build
cp ~/.katrain/config.json /tmp/kgpa-katrain-config.json 2>/dev/null || true
lsof -nP -iTCP:8002 -sTCP:LISTEN
npx playwright test tests/kiosk-screen-05-play-ai.spec.ts tests/kiosk-screen-05-game.spec.ts
cp /tmp/kgpa-katrain-config.json ~/.katrain/config.json 2>/dev/null || true
```
Expected: 全 passed(含既有 `kiosk-screen-05-game.spec.ts` —— 屏 05 / 屏 10 的几何闸不许红)。
**变异自检(一次,不提交)**:把 `KioskFold fold="moves"` 的 `grow` 删掉、重新 build、只跑本 spec,预期「中段没有洞」两态都红;红了再恢复。没红说明判据选错了,停下来重想。

- [ ] **Step 4: 四图 + 视觉确认 + 提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
npx tsc -b && echo TSC_OK
npx eslint src/kiosk/components/game/gameKinds.ts src/kiosk/components/game/GameControlPanel.tsx src/kiosk/pages/GamePage.tsx
lsof -nP -iTCP:5173 -sTCP:LISTEN
npx playwright test --config=playwright.visual.config.ts tests/kiosk-screen-05-game.fourup.spec.ts tests/kiosk-screen-10-platform-game.fourup.spec.ts
npx playwright test --config=playwright.visual.config.ts tests/kiosk-screen-05-game.fourup.spec.ts tests/kiosk-screen-10-platform-game.fourup.spec.ts   # 第二次:两次结果 diff 得本屏抖动地板
git -C /Users/fan/Repositories/katrain-kiosk-go-play-ai status --short superpowers/tracks/kiosk-go-shell-align/visual
```
Expected: 屏 05(开着图表的自由对弈)与屏 10(星阵)这两帧的内容不该变;两屏都是 `<canvas>` 盘,变化若是散在全图、与两次运行之间的差同量级(约 4500 像素)即抖动 ⇒
`git checkout HEAD -- superpowers/tracks/kiosk-go-shell-align/visual/05-game superpowers/tracks/kiosk-go-shell-align/visual/10-platform-game`(先确认这两个目录没有要留的未提交改动)。
若变化聚在右栏,停下来查,不要提交。

把 `superpowers/tracks/kiosk-go-play-ai/visual/n14-a11-ranked-rail-1024x600.png`、`n14-a11-pvp-local-rail-1024x600.png` 交 Fan 视觉确认(稿子没有这两态的参考图),**确认前本 Task 不算完成**。

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
# 基线 diff(后端 + 前端)，两个 comm -13 均须为空
CI=true uv run pytest tests --continue-on-collection-errors -q -rfE -p no:cacheprovider 2>&1 | tee /tmp/kgpa-now-pytest.log
grep -E '^(FAILED|ERROR) tests/' /tmp/kgpa-now-pytest.log | sed -E 's/ - .*//' | LC_ALL=C sort -u > /tmp/kgpa-now-pytest-failed.txt
LC_ALL=C comm -13 /tmp/kgpa-baseline/pytest-failed.txt /tmp/kgpa-now-pytest-failed.txt   # 期望:无输出
git restore --source=HEAD -- katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json
rm -f test_user_data.db
git status --short katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json test_user_data.db   # 期望:空
cd katrain/web/ui
npx vitest run --reporter=verbose 2>&1 | tee /tmp/kgpa-now-vitest.log
grep -E '^\s+×' /tmp/kgpa-now-vitest.log | sed -E 's/^\s+×\s+//; s/ [0-9]+ms$//' | LC_ALL=C sort -u > /tmp/kgpa-now-vitest-failed.txt
LC_ALL=C comm -13 /tmp/kgpa-baseline/vitest-failed.txt /tmp/kgpa-now-vitest-failed.txt   # 期望:无输出
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
git add katrain/web/ui/src/kiosk/components/game/gameKinds.ts katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx \
  katrain/web/ui/src/kiosk/components/game/GameControlPanel.test.tsx katrain/web/ui/src/kiosk/components/game/GameControlPanel.playAi.test.tsx \
  katrain/web/ui/src/kiosk/pages/GamePage.tsx katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx \
  katrain/web/ui/tests/kiosk-screen-05-play-ai.spec.ts \
  superpowers/tracks/kiosk-go-play-ai/visual/n14-a11-ranked-rail-1024x600.png superpowers/tracks/kiosk-go-play-ai/visual/n14-a11-pvp-local-rail-1024x600.png
git diff --cached --stat
git commit -m "fix(kiosk): 升降级局领地键按亮盘上不出色块;胜率块不在的局右栏中段空一块 —— 右栏按对局类型摆

N14(P2):升降级局整块不渲染领地 / AI支招。A11(P3):胜率块不在的局中段显示棋谱(承重实测:满态自滚、
最空态不塌、动作区贴底)。A9 与拍板无关的一半:本地对局不再每手白算一次分析。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: A20 + A21(前端部分)实体盘降级后关掉实体盘 UI;重标定弹层说真话、不在进局时闪

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx:204-208`(`physicalPlay`)、`:406`(`recalOpen`)、`:421-425`(`hardwareFault`)、`:840-845`(`<PhysicalSyncEscalationDialog>`)
- Modify: `katrain/web/ui/src/kiosk/components/physical/PhysicalSyncEscalationDialog.tsx`(`onScreenPlay` prop)
- Modify: `katrain/web/ui/src/kiosk/components/game/RecalibrationModal.tsx:63`(正文)
- Modify: `katrain/web/ui/src/kiosk/components/vision/VisionSyncOverlay.tsx:295`(「横幅中的重新定位」那一句)
- Test: `katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx`(追加)

**Interfaces:**
- Consumes: Task 1 测试文件的 `vision` / `sessionMock` / `pageTree` / `renderPage` / `makeState`
- Produces: `PhysicalSyncEscalationDialog` 新 prop `onScreenPlay?: () => void`;sessionStorage 键 `kiosk_screen_fallback:<sessionId>` = `'1'` 表示本局已降级为屏幕落子

- [ ] **Step 1: 写失败的测试(追加到 `GamePage.playAi.test.tsx` 末尾)**

```tsx
describe('A20 + A21 · 实体盘降级与重标定弹层', () => {
  const physical = () => {
    vision.enabled = true;
    localStorage.removeItem('kiosk_play_on_board');   // 偏好默认开(utils/playInput.ts)
    sessionMock.gameState = makeState();
  };

  it('进局头几秒还没锁定过位姿:不弹「棋盘可能被移动」', () => {
    physical();
    vision.poseLocked = false;
    renderPage();
    expect(screen.queryByText('棋盘可能被移动')).toBeNull();
  });

  it('锁定过之后又丢了才弹,而且说真话:要亮灯、要先清空棋盘', () => {
    physical();
    vision.poseLocked = true;
    const view = renderPage();
    vision.poseLocked = false;
    view.rerender(pageTree());
    expect(screen.getByText('棋盘可能被移动')).toBeInTheDocument();
    expect(screen.getByText(/要先把棋盘上的子全部拿走/)).toBeInTheDocument();
    expect(screen.queryByText(/无需 LED/)).toBeNull();
  });

  it('「改用屏幕落子」之后:解绑一次,实体盘那一串 UI 撤掉;同一局重挂载仍是屏幕模式', async () => {
    physical();
    sessionMock.physicalReminder = { kind: 'escalation', to_place: [], to_remove: [] };
    const unbind = vi.spyOn(API, 'visionUnbind').mockResolvedValue(undefined);
    const view = renderPage();
    // `hidden: true` 是承重的:升级弹窗开着时 MUI 给页面根挂 `aria-hidden`,默认的 ByRole 查不到页控条上的键 ——
    // 不加它,第一条会误红;后面几条 `toBeNull()` 会在弹窗退场期间「因为被藏了」而误绿。
    expect(screen.getByRole('button', { name: /重置识别/, hidden: true })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '改用屏幕落子' }));
    expect(unbind).toHaveBeenCalledTimes(1);
    vision.poseLocked = false;   // 解绑后识别状态机回到未绑定
    view.rerender(pageTree());

    await waitFor(() => expect(screen.queryByRole('button', { name: /重置识别/, hidden: true })).toBeNull());
    expect(screen.queryByText('棋盘可能被移动')).toBeNull();
    expect(sessionStorage.getItem('kiosk_screen_fallback:play-ai-s1')).toBe('1');

    view.unmount();
    sessionMock.physicalReminder = null;
    renderPage();
    expect(screen.queryByRole('button', { name: /重置识别/, hidden: true })).toBeNull();
  });
});
```

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui && npx vitest run src/kiosk/pages/GamePage.playAi.test.tsx -t "A20"`
Expected: 第一条 FAIL(弹层出现了);第二条 FAIL(文案是「无需 LED,对齐外框即可」);第三条 FAIL(重置识别键还在)。

- [ ] **Step 2: 实现**

`PhysicalSyncEscalationDialog.tsx`:`Props` 里 `onClose: () => void;` 之后加

```tsx
  /**
   * A20:用户选了「改用屏幕落子」。GamePage 据此把**本局**降级为屏幕模式 —— 只调后端解绑的话,
   * 前端仍按挂载时读的偏好当自己在实体盘上,1–4 秒后弹「棋盘可能被移动」、常驻「标定丢失」。
   */
  onScreenPlay?: () => void;
```

组件参数解构加 `onScreenPlay`,`screenPlay` 改为:

```tsx
  const screenPlay = () => {
    API.visionUnbind().catch(() => undefined);
    onScreenPlay?.();
    onClose();
  };
```

`GamePage.tsx`,把

```tsx
  const [playOnBoard] = useState(readPlayOnBoard);
  const physicalPlay = isVisionEnabled
    && playOnBoard
    && (session.gameState?.board_size?.[0] ?? 19) === 19;
```

替换为

```tsx
  const [playOnBoard] = useState(readPlayOnBoard);
  // A20:本局已从实体盘降级为屏幕落子(`PhysicalSyncEscalationDialog` 的「改用屏幕落子」)。
  // 按 sessionId 记在 sessionStorage:同一局刷新 / 从「继续上一局」回来仍是屏幕模式,换一局不受影响。
  const screenFallbackKey = `kiosk_screen_fallback:${sessionId ?? ''}`;
  const [screenFallback, setScreenFallback] = useState(() => {
    try { return sessionStorage.getItem(screenFallbackKey) === '1'; } catch { return false; }
  });
  const fallBackToScreen = useCallback(() => {
    try { sessionStorage.setItem(screenFallbackKey, '1'); } catch { /* 隐私模式:本页照样降级,只是刷新后记不住 */ }
    setScreenFallback(true);
  }, [screenFallbackKey]);
  const physicalPlay = !screenFallback
    && isVisionEnabled
    && playOnBoard
    && (session.gameState?.board_size?.[0] ?? 19) === 19;
  // A21:「棋盘可能被移动」只在**本页锁定过位姿之后又丢了**时才算数。进局头几秒识别还没绑定 / 刚绑定,
  // `poseLocked` 本来就是假 —— 那不是棋盘被挪了。(渲染中按条件调整 state 的写法,不走 effect。)
  const [poseEverLocked, setPoseEverLocked] = useState(false);
  if (physicalPlay && visionStatus.poseLocked && !poseEverLocked) setPoseEverLocked(true);
```

`const recalOpen = physicalPlay && !visionStatus.poseLocked && !isGameOver;` 改为
`const recalOpen = physicalPlay && poseEverLocked && !visionStatus.poseLocked && !isGameOver;`。

`hardwareFault` 里 `: visionStatus.poseLocked === false ? t('vision:pose_lost', '标定丢失 · 请重新标定')` 改为
`: poseEverLocked && visionStatus.poseLocked === false ? t('vision:pose_lost', '标定丢失 · 请重新标定')`。

`<PhysicalSyncEscalationDialog` 那一段加一个 prop:`onScreenPlay={fallBackToScreen}`。

`RecalibrationModal.tsx` 第 63 行那句正文改为:

```tsx
          {/* A21:「重新标定」跑的是 LED 13 点标定(geometry_calibration_service.py 要 LED、
              led_geometry_calibrator.py 的空盘基线检查盘上有子即失败)。无 LED 外框重定位(V1)接进对局主链之前,
              这里只能说它真会做的事。 */}
          {t('game:recalibrate_needs_empty_board', '重新标定会亮灯，而且要先把棋盘上的子全部拿走；棋盘没被挪过的话，点「仍要继续」')}
```

`VisionSyncOverlay.tsx:295` 改为:

```tsx
            {t('vision:board_lost_hint', '看一下摄像头有没有被挡住、棋盘有没有被挪动；挪动过的话要重新标定')}
```

- [ ] **Step 3: 验证并提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
npx vitest run src/kiosk/pages/GamePage.playAi.test.tsx src/kiosk/pages/GamePage.test.tsx src/kiosk/__tests__/GamePageLedBadge.test.tsx src/kiosk/__tests__/GamePage.test.tsx
npx tsc -b && echo TSC_OK
npx eslint src/kiosk/pages/GamePage.tsx src/kiosk/components/physical/PhysicalSyncEscalationDialog.tsx src/kiosk/components/game/RecalibrationModal.tsx src/kiosk/components/vision/VisionSyncOverlay.tsx
```
Expected:`GamePage.playAi.test.tsx` 全 PASS;`TSC_OK`;eslint 无新增 error(若 `if (…) setPoseEverLocked(true)` 被 `react-hooks` 规则判为 error,
先停下来在报告里说明,不要加 `eslint-disable`)。
**既有 `src/kiosk/pages/GamePage.test.tsx` 的 `State B — RecalibrationModal` 组里有两条会红,而且红得对**(它们从 `mockPoseLocked = false` 起步,
按 A21 的新判据「没锁定过就不是棋盘被挪」本就不该弹)。按下面改,其余不动:

`opens when pose is lost mid-game, and 重新标定 calls GeometryAPI.calibrate("manual")` 的开头

```tsx
      mockIsVisionEnabled = true;
      mockPoseLocked = false;
      mockGameState = makeGameState({ players_info: aiVsHuman, end_result: null });
      renderPage();
```

改为

```tsx
      mockIsVisionEnabled = true;
      // A21(kiosk-go-play-ai):先锁定过、再丢失,才算「棋盘可能被移动」。
      mockPoseLocked = true;
      mockGameState = makeGameState({ players_info: aiVsHuman, end_result: null });
      const view = renderPage();
      mockPoseLocked = false;
      view.rerender(pageTree());
```

`re-opens on a fresh pose-loss after being dismissed and the board regaining lock` 的开头

```tsx
      mockIsVisionEnabled = true;
      mockPoseLocked = false;
      mockGameState = makeGameState({ players_info: aiVsHuman, end_result: null });
      const view = renderPage();
```

改为

```tsx
      mockIsVisionEnabled = true;
      // A21(kiosk-go-play-ai):先锁定过、再丢失,才算「棋盘可能被移动」。
      mockPoseLocked = true;
      mockGameState = makeGameState({ players_info: aiVsHuman, end_result: null });
      const view = renderPage();
      mockPoseLocked = false;
      view.rerender(pageTree());
```

改完再跑一遍上面的 vitest 命令 → Expected: 全 PASS。

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
git add katrain/web/ui/src/kiosk/pages/GamePage.tsx katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx \
  katrain/web/ui/src/kiosk/components/physical/PhysicalSyncEscalationDialog.tsx katrain/web/ui/src/kiosk/components/game/RecalibrationModal.tsx \
  katrain/web/ui/src/kiosk/components/vision/VisionSyncOverlay.tsx
# 基线 diff(后端 + 前端)，两个 comm -13 均须为空
CI=true uv run pytest tests --continue-on-collection-errors -q -rfE -p no:cacheprovider 2>&1 | tee /tmp/kgpa-now-pytest.log
grep -E '^(FAILED|ERROR) tests/' /tmp/kgpa-now-pytest.log | sed -E 's/ - .*//' | LC_ALL=C sort -u > /tmp/kgpa-now-pytest-failed.txt
LC_ALL=C comm -13 /tmp/kgpa-baseline/pytest-failed.txt /tmp/kgpa-now-pytest-failed.txt   # 期望:无输出
git restore --source=HEAD -- katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json
rm -f test_user_data.db
git status --short katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json test_user_data.db   # 期望:空
cd katrain/web/ui
npx vitest run --reporter=verbose 2>&1 | tee /tmp/kgpa-now-vitest.log
grep -E '^\s+×' /tmp/kgpa-now-vitest.log | sed -E 's/^\s+×\s+//; s/ [0-9]+ms$//' | LC_ALL=C sort -u > /tmp/kgpa-now-vitest-failed.txt
LC_ALL=C comm -13 /tmp/kgpa-baseline/vitest-failed.txt /tmp/kgpa-now-vitest-failed.txt   # 期望:无输出
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
git add katrain/web/ui/src/kiosk/pages/GamePage.test.tsx
git diff --cached --stat
git commit -m "fix(kiosk): 改用屏幕落子后页面仍当自己在实体盘上;重标定弹层说「无需 LED」而实际要亮灯清盘

A20(P2):本局降级记在 sessionStorage,关掉识别绑定与整串实体盘 UI。A21 前端部分:弹层只在锁定过又丢失时出现,
文案改成它真会做的事;「棋盘检测异常」不再指向不存在的横幅。无 LED 外框重定位(V1)归视觉/标定模块。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```
**必须上板**(记进 Task 12 清单):RK3562 上实体盘对局制造一次长时间跟不上 → 「改用屏幕落子」→ 10 秒内无弹层、可继续屏幕落子。

---

### Task 11: N25 对局屏红条可关、不印后端原文;断线给盒上真能做的出口

**Files:**
- Modify: `katrain/web/ui/src/hooks/useGameSession.ts`(`connectionLost` 状态、`ws.onopen`、`ws.onclose` 两个分支、`clearError`、返回值)—— **共享领地,纯增量**
- Create: `katrain/web/ui/src/hooks/useGameSession.connection.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx:607-609`(那个 `Snackbar` 替换为两个)+ 一个状态
- Test: `katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx`(追加)

**Interfaces:**
- Consumes: Task 1 测试文件的 `sessionMock` / `pageTree`、Task 2 的退出确认框；`connectionLost` 测试桩已按本 Task 的类型建好
- Produces: `useGameSession()` 额外返回 `connectionLost: 'rejected' | 'dropped' | null`(1008 被拒 / 意外断开 / 连着)与 `clearError(): void`;`error` 的文案与写入时机不变；退出框在 dropped / rejected 时提供 `exit-leave-keep`（只导航，不认输、不清指针）

- [ ] **Step 1: 写失败的测试**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
git ls-files src/hooks/useGameSession.connection.test.tsx; ls src/hooks/useGameSession.connection.test.tsx 2>/dev/null   # 期望:无输出
```

`src/hooks/useGameSession.connection.test.tsx`:

```tsx
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useGameSession } from './useGameSession';

vi.mock('../api', () => ({
  API: {
    getState: vi.fn().mockResolvedValue({ session_id: 'session-123', state: {} }),
    undo: vi.fn().mockRejectedValue(new Error('Request failed 409: {"detail":"nope"}')),
  },
}));

const sockets: MockWebSocket[] = [];
class MockWebSocket {
  static OPEN = 1;
  readyState = MockWebSocket.OPEN;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onopen: (() => void) | null = null;
  onclose: ((event: { code: number; reason: string; wasClean: boolean }) => void) | null = null;
  close = vi.fn();
  send = vi.fn();
  constructor() { sockets.push(this); }
}

describe('useGameSession · 断线与一次性错误分开记(N25)', () => {
  beforeEach(() => {
    sockets.length = 0;
    vi.stubGlobal('WebSocket', MockWebSocket);
  });
  afterEach(() => { vi.unstubAllGlobals(); });

  const connected = async () => {
    const hook = renderHook(() => useGameSession());
    act(() => { hook.result.current.setSessionId('session-123'); });
    await waitFor(() => expect(sockets.length).toBe(1));
    return hook;
  };

  it('意外断开:connectionLost = dropped,error 文案不变(galaxy 照旧)', async () => {
    const { result } = await connected();
    act(() => { sockets[0].onclose?.({ code: 1006, reason: '', wasClean: false }); });
    expect(result.current.connectionLost).toBe('dropped');
    expect(result.current.error).toContain('实时连接已断开');
  });

  it('被服务端拒(1008):connectionLost = rejected', async () => {
    const { result } = await connected();
    act(() => { sockets[0].onclose?.({ code: 1008, reason: 'Invalid token', wasClean: true }); });
    expect(result.current.connectionLost).toBe('rejected');
  });

  it('一次性操作失败不算断线,clearError 能清掉', async () => {
    const { result } = await connected();
    await act(async () => { await result.current.handleAction('undo').catch(() => undefined); });
    expect(result.current.connectionLost).toBeNull();
    expect(result.current.error).toContain('409');
    act(() => { result.current.clearError(); });
    expect(result.current.error).toBeNull();
  });
});
```

追加到 `src/kiosk/pages/GamePage.playAi.test.tsx` 末尾:

```tsx
describe('N25 · 对局屏错误条', () => {
  it('一次性操作失败:一句人话,不印后端原文,× 能关', () => {
    sessionMock.gameState = makeState();
    sessionMock.error = 'Request failed 409: {"detail":"Not your turn"}';
    renderPage();
    expect(screen.getByText('这一步没有成功，请再试一次')).toBeInTheDocument();
    expect(screen.queryByText(/Request failed/)).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /close/i }));
    expect(sessionMock.clearError).toHaveBeenCalled();
  });

  it('连接意外断开:给盒上真能做的出口,不叫人「刷新页面」', () => {
    sessionMock.gameState = makeState();
    sessionMock.error = '实时连接已断开，棋盘不会自动更新，请刷新页面';
    sessionMock.connectionLost = 'dropped';
    renderPage();
    expect(screen.getByText(/再从「继续上一局」回来/)).toBeInTheDocument();
    expect(screen.queryByText(/请刷新页面/)).toBeNull();
  });

  it('被服务端拒:原句照旧(带原因与「请重新登录」,屏 05 几何闸认的就是它)', () => {
    sessionMock.gameState = makeState();
    sessionMock.error = '实时连接被拒绝（Invalid token），棋盘不会自动更新，请重新登录后重试';
    sessionMock.connectionLost = 'rejected';
    renderPage();
    expect(screen.getByText(/实时连接被拒绝/)).toBeInTheDocument();
  });
});
```

N25 describe 追加下面测试；imports 加 `within`、`Link`，`sessionMock` 增加稳定的 `setSessionId: vi.fn()` 并让 hook 桩返回它。
为证明「继续上一局」用的是真指针，activeSession mock 用 `vi.importActual` 包装真实 read/write/clear，保留 spy；beforeEach 清 localStorage。
`pageTree` 的 `/kiosk/play` 测试页读取 `readActiveSession('game')` 并把其 `route` 渲染成「继续上一局」Link，不硬编码返回路由。

```tsx
  it.each(['dropped', 'rejected'] as const)('断线 %s：从退出框先离开，不认输，回来仍是同一局', (reason) => {
    const original = makeState();
    sessionMock.gameState = original;
    sessionMock.connectionLost = reason;
    renderPage();
    const saved = readActiveSession('game');
    expect(saved?.route).toBe('/kiosk/play/ai/game/play-ai-s1');
    fireEvent.click(screen.getByRole('button', { name: '退出对局' }));
    const dialog = screen.getByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: '先离开，不认输' }));
    expect(screen.getByText('PLAY_PAGE')).toBeInTheDocument();
    expect(sessionMock.handleAction).not.toHaveBeenCalledWith('resign');
    expect(clearActiveSession).not.toHaveBeenCalled();
    expect(readActiveSession('game')).toEqual(saved);
    sessionMock.setSessionId.mockClear();
    fireEvent.click(screen.getByRole('link', { name: '继续上一局' }));
    expect(sessionMock.setSessionId).toHaveBeenCalledWith('play-ai-s1');
    expect(screen.getByTestId('game-control-panel')).toBeInTheDocument();
    expect(sessionMock.gameState).toBe(original);
  });

  it('连着时退出框没有先离开', () => {
    sessionMock.gameState = makeState();
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: '退出对局' }));
    expect(within(screen.getByRole('dialog')).queryByText('先离开，不认输')).toBeNull();
  });
```

两种断线分别运行。hook 文件另加真实连接生命周期测试：挂载→`setSessionId('session-123')`→1006→卸载→重新挂载并设置同一 id，断言 `API.getState` 再请求该 id、创建第二条 WS，未调用 resign/newGame；用来补足页面桩不能证明的重新取状态与建连。
旧实现下没有按钮或复用认输回调都会红；清掉真实指针会让继续链接消失，回来换局会让 setSessionId 断言红。

Run: `npx vitest run src/hooks/useGameSession.connection.test.tsx src/kiosk/pages/GamePage.playAi.test.tsx -t "N25|断线"`
Expected: hook 三条 FAIL(`connectionLost` 为 undefined / `clearError is not a function`);GamePage 前两条 FAIL(印的是原文),第三条 PASS。

- [ ] **Step 2: 实现**

`useGameSession.ts`:

1. `const [error, setError] = useState<string | null>(null);` 之后加:

```ts
    // N25:连接断了是**持续状态**(Fan 2026-08-21),与一次性操作失败分开记;调用方据此决定哪种自己消失、给什么出口。
    // 'rejected' = 服务端 1008 拒绝(凭据问题),'dropped' = 意外断开。只增不改:`error` 的写法与文案原样保留。
    const [connectionLost, setConnectionLost] = useState<'rejected' | 'dropped' | null>(null);
```

2. `wsRef.current = ws;` 之后加:

```ts
                    ws.onopen = () => { if (wsRef.current === ws) setConnectionLost(null); };
```

3. `ws.onclose` 里 1008 分支的 `setError(…)` 之前加 `setConnectionLost('rejected');`;`!event.wasClean` 分支的 `setError(…)` 之前加 `setConnectionLost('dropped');`。

4. `const initNewSession = useCallback(…)` 之前加:

```ts
    // N25:一次性错误由调用方在显示过之后清掉(kiosk 的错误条 6 秒自己走、× 可关)。
    const clearError = useCallback(() => setError(null), []);
```

5. 返回对象里 `error,` 之后加 `connectionLost, clearError,`。

`GamePage.tsx`:状态声明区(`resyncError` 之后)加:

```tsx
  // N25:断线提示被用户关掉之后,本页不再弹同一条(持续状态不自动消失,但可以手动关)。
  const [connectionNoticeDismissed, setConnectionNoticeDismissed] = useState(false);
```

把 `<Snackbar open={!!session.error} anchorOrigin={{ vertical: 'top', horizontal: 'center' }}>…</Snackbar>`(连同它上面那段注释保留)整段替换为:

```tsx
      {/* N25:一次性操作失败 —— 一句人话,6 秒自己走,× 可关。后端原文(`Request failed 409: {...}`)不上屏:
          它说的是给运维看的事,盒上用户按不出任何东西。 */}
      <Snackbar
        open={!!session.error && !session.connectionLost}
        autoHideDuration={6000}
        onClose={() => session.clearError()}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <Alert severity="error" onClose={() => session.clearError()}>
          {t('game:action_failed', '这一步没有成功，请再试一次')}
        </Alert>
      </Snackbar>

      {/* N25:连接断了是持续状态(Fan 2026-08-21)—— 不自动消失,× 可关。意外断开时盒上全屏 chromium 没有刷新键,
          给真能做的出口:退出对局 → 先离开，不认输，再从「继续上一局」回来重新建连。被拒(1008)也提供该按钮，照旧显示 hook 的原句
          (带原因与「请重新登录」;`kiosk-screen-05-game.spec.ts` 的几何闸量的就是那一态)。 */}
      <Snackbar
        open={!!session.connectionLost && !connectionNoticeDismissed}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <Alert severity="error" onClose={() => setConnectionNoticeDismissed(true)}>
          {session.connectionLost === 'dropped'
            ? t('game:connection_dropped', '实时连接断了，棋盘不会自动更新。点「退出对局」→「先离开，不认输」，再从「继续上一局」回来就会重新连上')
            : session.error}
        </Alert>
      </Snackbar>
```

Task 2 修改过的退出确认框 `DialogActions` 中，在「取消」与认输退出之间加：

```tsx
{session.connectionLost && (
  <Button data-testid="exit-leave-keep" onClick={() => {
    setShowExitConfirm(false);
    navigate('/kiosk/play');
  }}>
    {t('game:leave_keep_game', '先离开，不认输')}
  </Button>
)}
```

这条出口不调用 `handleAction('resign')`、`clearActiveSession` 或 `clearPhysicalEngineError`。`rejected` 同样给出口，因为凭据失效时认输也可能被拒。返回仍使用持久化的原 session 路由，重新挂载 hook 拉状态；服务重启导致会话消失时由 Task 1 兜底。

- [ ] **Step 3: 验证(共享领地 ⇒ 两套构建;e2e 几何闸)并提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
npx vitest run src/hooks/useGameSession.connection.test.tsx src/hooks/useGameSession.navigation.test.tsx src/kiosk/pages/GamePage.playAi.test.tsx src/kiosk/pages/GamePage.test.tsx src/galaxy/pages/GameRoomPage.test.tsx
npx tsc -b && echo TSC_OK
npx eslint src/hooks/useGameSession.ts src/kiosk/pages/GamePage.tsx
npm run build && npm run build:kiosk-2d
cp ~/.katrain/config.json /tmp/kgpa-katrain-config.json 2>/dev/null || true
lsof -nP -iTCP:8002 -sTCP:LISTEN
npx playwright test tests/kiosk-screen-05-game.spec.ts -g "布局 A 的外框"
cp /tmp/kgpa-katrain-config.json ~/.katrain/config.json 2>/dev/null || true
```
Expected: 全 PASS;`TSC_OK`;两套构建绿;「布局 A 的外框」那条仍绿(1008 那一态显示原句、不占流内高度)。

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
# 基线 diff(后端 + 前端)，两个 comm -13 均须为空
CI=true uv run pytest tests --continue-on-collection-errors -q -rfE -p no:cacheprovider 2>&1 | tee /tmp/kgpa-now-pytest.log
grep -E '^(FAILED|ERROR) tests/' /tmp/kgpa-now-pytest.log | sed -E 's/ - .*//' | LC_ALL=C sort -u > /tmp/kgpa-now-pytest-failed.txt
LC_ALL=C comm -13 /tmp/kgpa-baseline/pytest-failed.txt /tmp/kgpa-now-pytest-failed.txt   # 期望:无输出
git restore --source=HEAD -- katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json
rm -f test_user_data.db
git status --short katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json test_user_data.db   # 期望:空
cd katrain/web/ui
npx vitest run --reporter=verbose 2>&1 | tee /tmp/kgpa-now-vitest.log
grep -E '^\s+×' /tmp/kgpa-now-vitest.log | sed -E 's/^\s+×\s+//; s/ [0-9]+ms$//' | LC_ALL=C sort -u > /tmp/kgpa-now-vitest-failed.txt
LC_ALL=C comm -13 /tmp/kgpa-baseline/vitest-failed.txt /tmp/kgpa-now-vitest-failed.txt   # 期望:无输出
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
git add katrain/web/ui/src/hooks/useGameSession.ts katrain/web/ui/src/hooks/useGameSession.connection.test.tsx \
  katrain/web/ui/src/kiosk/pages/GamePage.tsx katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx
git diff --cached --stat
git commit -m "fix(kiosk): 对局屏红条一出现就关不掉、印后端原文;断线让盒上用户「刷新页面」

N25(P3)。useGameSession 纯增量加 connectionLost / clearError:一次性失败说人话、6 秒自走、可关;
断线时退出框多一个「先离开，不认输」，保留继续上一局；意外断开持续提示这条出口;1008 被拒仍显示原句。WS 自动重连不在本轮。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: 收尾验证与上板清单

**Files:**
- Create: `superpowers/tracks/kiosk-go-play-ai/board-checklist.md`(上板要验的项,给真机那一轮用)
- 无源码改动

**Interfaces:**
- Consumes: Task 1–11 的全部提交
- Produces: 一份可以直接照着上板的清单;本轮完成判据的证据(基线 diff、两套构建、四图/承重结论、Fan 视觉确认记录)

- [ ] **Step 1: 全量回归(基线 diff)**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
git status --short        # 期望:前序 Task 均已提交，无待提交源码或测试；不硬编码文档未提交状态
CI=true uv run pytest tests --continue-on-collection-errors -q -rfE -p no:cacheprovider 2>&1 | tee /tmp/kgpa-final-pytest.log
grep -E '^(FAILED|ERROR) tests/' /tmp/kgpa-final-pytest.log | sed -E 's/ - .*//' | LC_ALL=C sort -u > /tmp/kgpa-final-pytest-failed.txt
LC_ALL=C comm -13 /tmp/kgpa-baseline/pytest-failed.txt /tmp/kgpa-final-pytest-failed.txt      # 期望:无输出
git restore --source=HEAD -- katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json
rm -f test_user_data.db
git status --short katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json test_user_data.db   # 期望:空
cd katrain/web/ui
npx vitest run --reporter=verbose 2>&1 | tee /tmp/kgpa-final-vitest.log
grep -E '^\s+×' /tmp/kgpa-final-vitest.log | sed -E 's/^\s+×\s+//; s/ [0-9]+ms$//' | LC_ALL=C sort -u > /tmp/kgpa-final-vitest-failed.txt
LC_ALL=C comm -13 /tmp/kgpa-baseline/vitest-failed.txt /tmp/kgpa-final-vitest-failed.txt      # 期望:无输出
npx tsc -b && echo TSC_OK
npm run build && npm run build:kiosk-2d
```
Expected: 两个 `comm -13` 都无输出;`TSC_OK`;两套构建绿。有输出就逐条查:是本轮造的就修,是进程级共享状态污染(落在无关文件里)也算本轮造的。

**源码闸（先排除注释行，逐行确认所在函数）：**

```bash
sed '/^[[:space:]]*#/d' katrain/web/server.py | grep -n "end_state *="       # 期望:无
sed '/^[[:space:]]*#/d' katrain/web/interface.py | grep -n "end_state *="    # 期望:只在 _commit_end_state
sed '/^[[:space:]]*#/d' katrain/web/server.py | grep -n "_record_ai_game(\|_record_platform_engine_game("  # 定义 + _finish_ended_game 内唯一终局调用
CI=true uv run pytest tests/web_ui/test_play_ai_endgame_api.py --continue-on-collection-errors -q -k resign_writes_one_ledger_row_or_none
```

grep 绿不代表落账没丢；本分支平台 / 大厅认输的写入 1/0 行行为测试必须绿。
**合并指引（仅记录，当前任务不合并、不改 PRD §6.0）：**跨平台 helper 将来合入时，在 `_finish_ended_game` 的多人局早退之前插入：

```python
        if is_platform_engine_session(session):
            await _record_platform_engine_game(session, app, current_user, end.result)
            return
```

保持该 helper 为薄适配，overrides 由它构造；不预加本分支没有调用方的参数。
`_do_end_without_result` 改走 `_commit_end_state("Void")`；仅当前手已有双停待补分事实且尚无 end_state 时传 `fill_pending=True`。
本分支不带 guard 的平台双停不会产生该事实。合并后还须单独跑 `tests/platforms/test_engine_game_ledger_e2e.py` 三条行为测试；与 web_ui 拆命令。

- [ ] **Step 2: e2e(打构建产物)**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
cp ~/.katrain/config.json /tmp/kgpa-katrain-config.json 2>/dev/null || true
lsof -nP -iTCP:8002 -sTCP:LISTEN
npx playwright test tests/kiosk-screen-05-play-ai.spec.ts tests/kiosk-screen-05-game.spec.ts tests/kiosk-ai-ladder-blocking-panel.spec.ts
cp /tmp/kgpa-katrain-config.json ~/.katrain/config.json 2>/dev/null || true
```
Expected: 全 passed。

- [ ] **Step 3: 视觉确认记录**

产出以下截图与对比，统一标注「待 Fan 确认」；不自行判视觉通过，也不因尚未确认停止本轮已授权实施：
`superpowers/tracks/kiosk-go-play-ai/visual/` 下 `n17-game-unavailable-1024x600.png`、`a18-timed-game-1024x600.png`、
`a3-strategy-hint-territory-1024x600.png`、`n14-a11-ranked-rail-1024x600.png`、`n14-a11-pvp-local-rail-1024x600.png`;
屏 05 / 屏 02 四图参考、实现、并排、叠加/差异与两次截图抖动比较；屏 10 仅按受影响的既有测试验证。

- [ ] **Step 4: 写上板清单**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
git ls-files superpowers/tracks/kiosk-go-play-ai/board-checklist.md; ls superpowers/tracks/kiosk-go-play-ai/board-checklist.md 2>/dev/null   # 期望:无输出
```

`superpowers/tracks/kiosk-go-play-ai/board-checklist.md`:

```markdown
# kiosk-go-play-ai · 上板清单(RK3562)

> 一次只跑一家(2G 内存)。盒子树可能落后本分支,先确认板上代码的提交号与本分支一致再验(板上没有 git:比对文件 `git hash-object`)。
> 每项记:日期、板上提交、结果、耗时/截图路径。

| # | 条目 | 步骤 | 通过判据 |
|---|---|---|---|
| 1 | A12 数子补分 | 自由对弈,关掉「领地」「图表」,下满 100 手后点「数子」 | 屏上先出「正在数子…」,15 秒内出 `黑+x`/`白+x` 结果卡;记录点击到出结果的秒数 |
| 2 | N22 AI 跟停 | 自由对弈(已登录),人先停一手、AI 跟停 | 结果卡是胜负而不是「终局」;屏 01「全部对局」里出现这一局 |
| 3 | N22 升降级双停 | 升降级局人先停、AI 跟停 | 对局结束;回升降级开局页没有挡局面板(「继续」按钮消失),能开下一局 |
| 4 | N21 AI 思考中认输 | 自由对弈人落子后立刻「退出对局 → 认输并退出」 | 「全部对局」里这一局记为 AI 胜;回到这一局不再出现 AI 新落的子 |
| 5 | A18 读秒判负 | 自由对弈选「仅读秒 30秒×3」,轮到自己时不下 | 时钟从「读秒 · 剩 3 次」数到「超时」,结果卡为对方超时胜 |
| 6 | A20 改用屏幕落子 | 实体盘对局,制造一次长时间跟不上(不摆 AI 的子)→ 弹层「改用屏幕落子」 | 10 秒内没有「棋盘可能被移动」弹层、开关排没有「标定丢失」;屏幕点子能继续下 |
| 7 | N17 失效的继续上一局 | 开一局后重启 katrain 服务,回屏 01 点「继续上一局」 | 对局屏显示「这一局已经打不开了」+「回到对弈」;回屏 01 后「继续上一局」消失 |
| 8 | 终局后翻手 | 已登录自由对弈认输/双停结束，立刻上一手、最后一手 | 结果卡与打谱键始终在；屏 01 无继续上一局；全部对局只有一局 |
| 9 | 断线出口 | 对局中重启服务，断线红条 → 退出对局 → 先离开，不认输 → 继续上一局 | 看到打不开与回到对弈；全程无认输、无卡死；仅断连接未重启时回来仍是同一局 |

## 视觉证据

屏 05/02 的参考、实现、并排、叠加/差异与相关状态截图：待 Fan 确认。记录实际路径与观察，不自行判通过。

## 本轮登记的后续项（非上板）

1. 本地对局连点停一手可能把两人的停都按掉：共享 `/api/move` 需带 expected_node_id，与 galaxy 一起验收。
2. galaxy 的超时仍不带绑定；前端尚不读 terminal_result。本轮服务端仅冻结终局所在局面线，悔棋另开分支仍兼容；kiosk 前端整局冻结。
3. 视觉 orchestrator 缺终局暂停原因：结束后识别仍在跑，提交被拒再布防。
4. 大厅多人局：leave/登出判负可能重复落账、认输不清 pending_count_request、timeout 胜方按请求者而盘面按轮次；终局后导航另开分支再认输可再记一行。归人人对弈模块。
5. 本地认输框点名方来自浏览器，请求未绑定该方。
6. 服务端翻手期间不计时，盒上服务重启后计时状态丢失；本轮保持现有语义。

```

- [ ] **Step 5: 提交清单**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
git add superpowers/tracks/kiosk-go-play-ai/board-checklist.md
git diff --cached --stat
git commit -m "docs(play-ai): 本轮上板清单 —— 数子补分、AI 跟停落账、认输判方、读秒判负、实体盘降级、失效续局

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage(PRD §3 逐条)**

| PRD 条目 | 任务 |
|---|---|
| N17 加载失败出口 + 清指针 | Task 1 |
| N21 认输判方 / 终局后不落子 / 本地对局确认框 / 大厅按座位 | Task 2 |
| N23 数子门槛按路数 | Task 3 |
| A12 数子补分 + 在途 + 原因 | Task 4 |
| N22 收尾函数 + AI 收尾落账 / 双停补分 / 串行 / 升降级不补 | Task 5 |
| A18 `timer.configured` + 时钟 + 超时 + 截图 | Task 6 |
| A3 策略 id + 五句说明 + 截图 | Task 7 |
| A2(文案)+ A15 503 分原因 | Task 8 |
| N14 + A11 + A9 一半 + 承重实测 + 截图 | Task 9 |
| A20 + A21 前端部分 | Task 10 |
| N25 错误条 + 断线出口 | Task 11 |
| §7 必须上板的四项(另加 N21/N17 两项) | Task 12 清单 |

PRD §4(A12-R、A2 修法、A9 默认值、A7、A14、A17、A19、Z6)与 §5 均未进任务 —— 符合「待拍板不进计划」。

**2. 片段自查**：核心并发与超时路径给出具体代码；改动位置对照真实源码。环境或源码差异在本计划与提交中说明，除 PRD §4 待拍板事项外继续处理。

**3. Type consistency（r1 已核）**：

- 对局提交锁统一为 `WebKaTrain.ai_ladder_commit_lock`（RLock），锁序 `session.lock → ai_lock → 提交锁 → Game._lock`；协程收尾另用 `end_game_lock`，不以它代替线程互斥。
- `GameEnd(game, node, result)`；`WebGame.ended_at(node)` 按局面线；`record_two_pass_end(node)` 只由 guarded 本地落子和 AI 提交调用。
- `_commit_end_state(result, *, node=None, fill_pending=False) -> GameEnd`；同局面线先写者胜，待补分例外。
- `_do_resign(loser: Optional[str] = None) -> GameEnd`；`_do_play(coords, guard=False, expected_player=None)`；Task 2 的无绑定 `_do_timeout` 由 Task 6 扩为 `_do_timeout(expected_game_id=None, expected_node_id=None, color=None)`。
- `ensure_current_score(timeout_s=None, node=None) -> Optional[float]`：Task 4 端点与 Task 5 补分均带 `node=`；默认当前手只给兼容的直接调用使用。
- `_terminal_of(session) -> Optional[GameEnd]` / `_count_result(score)` 在 Task 4 产出；`_new_terminal(session, before)` / `_score_two_pass_end(session, end)` 在 Task 5 产出。
- `_complete_count(session, app, current_user, node=None)`：Task 4 返回 `(result, needs_record)`，Task 5 明确替换为 `result: str` 并移除旧调用解包。
- `_FINISH_ENDED_GAME_FN(session, app, current_user, end)` 对应 `_finish_ended_game`，`end` 必填；`game_ended_callback(end)` → `_on_game_ended(sid, end)` → `on_game_ended(session, end)` → `_on_game_ended_off_request(session, end)`。
- `API.timeout(sessionId, token?, expect?)`；`GameState.terminal_result?: string | null`；`timer.configured?: boolean`；`useGoClock(gameState, color, onExpired)` / `onTimeout(color)` 在 Task 6 内一致，Task 9 不改签名。
- `isFreeVsAi({ gameType, engineMode, isRanked })` 在 Task 9 定义，两处调用字段一致。
- `connectionLost: 'rejected' | 'dropped' | null` / `clearError(): void`，Task 11 产出；前端测试桩预先兼容。离开按钮只导航，真实 activeSession 指针测试证明回来仍取原会话。
- 明确列文件运行时，根目录真实类测试与 `tests/web_ui` 始终拆命令；全量只传 `tests`，继续收集错误；所有 Task 的后端/前端失败名称集合都用 `comm -13`，全量后清三处污染。

**4. 本次一致性自查**：补齐 Task 2/4/9 Consumes 与 Task 5 返回类型变化；修正 Task 5 本地 resign 捕获锁范围及提交说明重复尾行。旧接口若作为明确的替换前片段出现不代表保留；源码实作以实际定义为准，差异更新计划并记入对应 Task 中文提交。
