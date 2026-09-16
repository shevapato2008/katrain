# 围棋 kiosk · 跨平台对弈（本轮）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让盒上（token 恒为 null）的星阵人机这条路从对弈首页到存谱真的走得通、屏上每句话都成立，并把 OGS 挑战与实体盘恢复框里两处「说不出口 / 走不出去」补上。

**Architecture:** 三块互不依赖的前端小修（token 判别位、首页状态请求、挑战文案）先行；然后撤掉星阵局两颗注定被拒的键。后端切片分三步：AI 回停一手 / 认输时本地局以 `Void` 结束、`/api/move` 回 200，而迟到的隧道回复先确认「还是被提交的那一盘、而且还没结束」才落子 / 结束（Task 5）；星阵会话的平台上下文一旦在终局时被摘掉，这盘就是终态——落子 / 停一手 / 认输都不再落到本地树上，判别位是建局时写下的 `platform_engine_color`（Task 5b）；星阵局在认输 / AI 终局 / 实体盘 AI 终局 / 恢复框「重试」四处经 `_record_ai_game` 落账到 `user_games`（Task 6）。最后前端把 `Void` 说成人话，并给实体盘等待态加出口（8a）、编排器终局时释放恢复暂停（8b）。数据契约只新增既有字段的取值（`end_result` / `user_games.result` = `"Void"`；恢复框重试响应在终局时是 `{"ok": true, "game_ended": true}`），不加字段。三条泳道可在各自 worktree 并行（见「并行泳道」），全量闸、真浏览器与四图在合并回本分支后串行（Task 9）。

**Tech Stack:** React 19 + TypeScript + Vite + vitest（`katrain/web/ui`）；FastAPI + pytest（`asyncio_mode = auto`）；Playwright（`playwright.visual.config.ts`，vite dev :5173）。

**Spec:** `superpowers/tracks/kiosk-go-cross-platform/prd.md`

## Global Constraints

> **开工前先读 `prd.md` §6.0**：五条赛道的共享文件归属与合并顺序（尤其第 1 条：`server.py` 终局落账只留一条入口、后合并方怎么机械地适配）。与本 plan 冲突时以 §6.0 为准。

- 在 worktree `/Users/fan/Repositories/katrain-kiosk-go-cross-platform`（分支 `feature/kiosk-go-cross-platform`）里开发；**不 push、不合并 develop**，合并由 Fan 决定；**不在别的赛道的 worktree 里 checkout**。所有命令用绝对路径或先 `cd` 到本 worktree（并行执行时换成泳道目录，规则见「并行泳道」）。
- 本 worktree 的 `.venv` 与 `node_modules` 已装好，Task 0 先核实；若缺包，后端依赖**必须带 extras**：`uv sync --extra web --extra vision --extra board`，再 `uv pip install boto3 fonttools brotli moto`。只 `uv sync` 会缺 fastapi、pytest 收集中止，旧 grep 闸可能假绿。
- 改了共享领地（`src/components`、`hooks`、`api`、`features`、`context`、`utils` 等）或共享消费链上的 kiosk 页面，必须 `npm run build` 与 `npm run build:kiosk-2d` **都绿**；`verify:kiosk-2d`（kiosk 边界）不许破。
- 类型检查用 `npx tsc -b`（`npx tsc --noEmit` 检查 0 个文件，无效）；`*.test.tsx` 不在 tsc 范围内——mock 漏字段不会有类型错，只会运行时变 `undefined`；测试文件导入一个不存在的模块也不会有类型错，只会让整个文件在 vitest 里进「Failed Suites」（全量闸认这个形状，见 Task 0 Step 3）。
- 盒上 `token` 恒为 `null`：任何「发不发请求 / 渲不渲染」的判别位用 `isAuthenticated`，不用 `token`；`token` 只当凭据原样往下传（`api.ts` 的 `platform*` 已接受 `null`）。
- 「这是不是星阵人机局」后端只认 `katrain.web.platforms.gateway.is_platform_engine_session(session)`（`session.katrain.platform_engine_color in ("B", "W")`，Task 5b 定义）。**不许**用 `gateway.is_engine_game` / `is_platform_game`（终局那一刻平台上下文已被摘）、**不许**用 `player_*_id == -1`（OGS 真人局同形）、**不许**按真值判（MagicMock 属性恒为真值）。
- 新文案一律 `t('ns:key', '中文默认')`；**不往 PO 里加 key**（补不补 PO 待 Fan 裁定）。
- Python 用 `uv run black -l 120 <文件>`；前端单测 `cd katrain/web/ui && npx vitest run <文件>`；后端 `uv run pytest <文件>`（pytest 配置在 `pyproject.toml`，`asyncio_mode = "auto"`，async 测试不必加 marker）。**`tests/web_ui/` 下的文件不和根目录 / `tests/platforms/` 的文件放进同一条 pytest 命令**：`tests/web_ui/conftest.py` 在收集时把 `sys.modules["katrain.web.interface"]` 换成 MagicMock（`:90`），同一进程里真栈用例拿到的就是替身。
- 全量测试的判据是 **Task 0 写下的闸脚本 `${TMPDIR}/kgcp-gate.py`**：读结构化报告（vitest JSON / pytest junit XML）+ 退出码 + 汇总行；报告缺失、退出码不是 0/1、收集 / 导入失败、未处理异常一律红；非基线的那一轮比「失败用例名集合」「基线有而这次没跑到的用例」与「这次没执行而基线里不是这样的用例」（skip / todo / pending / xfail；只有 passed / failed 算执行），**不比条数**，也不 grep 日志里的失败行（旧写法对「整个测试文件导入失败」「conftest 导入失败」「进程中断」都读出 0 条失败，而且 `grep '^(FAILED|ERROR) '` 会把日志里 `ERROR    katrain_web:…` 的捕获行也当成用例名）。
- 全量 pytest 会改写两份**提交进仓库**的文件：`katrain/config.json`、`katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json`（写它的是 `tests/platforms/test_engine_manager.py:435` `test_dump_engine_game_state_fixture`，内容随本机语言变；`GamePageEngine.test.tsx` 读它），并可能改 `~/.katrain/config.json`。每次全量跑完 `git status --porcelain` 只许出现这两个文件，`git checkout --` 还原；出现别的就停下查。全量跑之前先 `ps -axo pid,command | grep -E '[p]ytest tests|[v]itest run'`：别的赛道在跑全量时等它结束（共享 `~/.katrain`，不许杀别人的进程）。
- Playwright e2e（`playwright.config.ts`，:8002）打的是**构建产物**：改源码后先 `npm run build` 再跑。本计划用到的 `tests/kiosk-screen-05-game.spec.ts`、`Void` 终局卡预览与四图走 `playwright.visual.config.ts`（vite dev :5173，自动起服务），打的是源码。⚠️ 该配置是 `reuseExistingServer: true`（`playwright.visual.config.ts:14`）：另外四条赛道各有 worktree、也会起 :5173，**端口上已有别人的 dev server 时 Playwright 会静默复用它、量的是别人的树**。所以每条 Playwright 命令都**在同一条命令里**先查端口（写法见 Task 9 Step 4：监听者的 cwd 不是本树就不跑）；不许杀别人的进程。**:5173 上的一切只在合并回本分支后、在 Task 9 里串行跑**。
- 视觉 / 布局改动走 CLAUDE.md 的四图对比（`npx playwright test --config=playwright.visual.config.ts tests/kiosk-screen-XX-*.fourup.spec.ts`，jsdom 不作布局证据）；每屏**跑两次并真比两次的实现图**取自己的抖动底（屏 10 是 canvas 盘，抖动约 4500 像素），只提交内容真变了的屏、四张图一起提交；**视觉通过需 Fan 确认**。本计划判定不触发承重实测（理由见 prd §7）。
- 共享文件与其它四条赛道重叠（prd §6）：只改计划里点名的行段，不顺手重排 / 重命名周边代码。
- 提交时删掉旧模板里的 Claude `Co-Authored-By` 行，使用实际提交者署名。

## File Structure

| 文件 | 责任 | Task |
|---|---|---|
| `katrain/web/ui/src/kiosk/pages/GamePage.tsx` | 道具两处判别位（X7）；终局卡 `Void` 说明行（X9-b） | 1, 7 |
| `katrain/web/ui/src/kiosk/__tests__/GamePageEngine.test.tsx` | auth mock 可变 + 盒端用例；停一手用例改写；Void 说明行用例 | 1, 4, 7 |
| `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx`（+ `.test.tsx`） | engineMode 只留认输 + `.ghint`（X9-a） | 4 |
| `katrain/web/ui/tests/kiosk-screen-05-game.spec.ts`、`katrain/web/ui/tests/kiosk-screen-10-platform-game.fourup.spec.ts` | 屏 10 动作区断言与取图等待条件（Task 4 改，Task 9 跑） | 4 |
| `katrain/web/ui/src/kiosk/components/report/reviewPresentation.ts`（+ `.test.ts`） | `Void` 念成人话 | 7 |
| `katrain/web/ui/src/kiosk/pages/PlayPage.tsx`（+ `.test.tsx`） | 状态请求判别位（X8）；野狐卡徽标（X1） | 2 |
| `katrain/web/ui/src/kiosk/pages/PlatformLobbyPage.tsx`（+ `.test.tsx`） | 挑战 toast / 确认框说实话（X4-a） | 3 |
| `katrain/web/ui/src/kiosk/components/physical/EngineMoveErrorDialog.tsx`、`katrain/web/ui/src/kiosk/__tests__/EngineMoveErrorDialog.test.tsx` | 等待态加「认输」（M2） | 8a |
| `katrain/web/interface.py` | 新命令 `end_without_result` | 5 |
| `katrain/web/platforms/gateway.py` | AI 终局结束本地局 + 迟到回复闸 `_submitted_position_status`（5）；判别位 `is_platform_engine_session` + 「上下文没了的星阵局即终局」（5b） | 5, 5b |
| `tests/platforms/test_engine_gateway.py`、`tests/platforms/test_engine_integration.py` | 上两行的单测与真栈用例 | 5, 5b |
| `katrain/web/server.py` | `/api/move` game_ended→200（5）；`/api/move`、`/api/resign`、视觉入口按判别位路由 + 再认输幂等（5b）；`data_overrides`、`_session_owner` / `_record_platform_engine_game` / `_record_platform_engine_game_off_request`、resign / move / 视觉三处落账（6） | 5, 5b, 6 |
| `tests/platforms/test_engine_game_ledger.py`（新建；`git ls-files` 无同名、`git check-ignore` 不吞） | move / resign 端点分支与落账 helper | 5, 5b, 6 |
| `tests/platforms/test_engine_game_ledger_e2e.py`（新建；同上已核） | 真端点 → 真 gateway → 真写库调用（prd §6.0 第 1 条的合并验收） | 6 |
| `katrain/web/core/repository.py`、`katrain/web/core/sync_worker.py`、`katrain/web/core/remote_client.py`、`tests/web_ui/test_user_game_cloud_owner.py`（新） | 云端会话与棋谱主人不同时，本机落账并延迟补传；401 换人不重试 / 污染 token；双用户真链路测试 | 6b |
| `tests/test_vision_move_poller.py` | 视觉入口路由（5b）、视觉路径落账（6） | 5b, 6 |
| `katrain/web/api/v1/endpoints/vision.py`、`tests/test_vision_engine_move_recovery_endpoints.py` | 恢复框「重试」遇 game_ended：关恢复、经 off-request helper 落账 | 6 |
| `katrain/web/core/physical_play_orchestrator.py`、`tests/test_physical_play_orchestrator.py`、`tests/test_engine_physical_integration.py` | 终局释放恢复暂停并熄灯（M4）+ 等待态认输后残子不复活的真栈用例 | 8b |
| `superpowers/tracks/kiosk-go-shell-align/visual/01-play/`、`visual/10-platform-game/` | 四图重取 | 9 |

## 并行泳道

三条泳道**文件互不相交**（上表逐行、下面每个 Task 的 Files 段逐条核过：同一个文件出现在两个 Task 里，这两个 Task 必在同一泳道——`GamePage.tsx` 1/7、`GamePageEngine.test.tsx` 1/4/7 ⇒ A；`gateway.py`、`server.py`、两份 platforms 测试、`test_engine_game_ledger.py`、`test_vision_move_poller.py` 都跨 5/5b/6 ⇒ C），可以各开一个 git worktree 同时做；泳道内部按列出的顺序串行。也可以不开泳道，在本 worktree 按 0 → 1 → 2 → 3 → 4 → 5 → 5b → 6 → 7 → 8a → 8b → 9 串行做完——两种走法的产物一样。

| 泳道 | Task（泳道内顺序） | 独占的文件 |
|---|---|---|
| **A 对局屏前端** | 1 → 4 → 7 | `katrain/web/ui/` 下：`src/kiosk/pages/GamePage.tsx`、`src/kiosk/__tests__/GamePageEngine.test.tsx`、`src/kiosk/components/game/GameControlPanel.tsx`（+ `.test.tsx`）、`src/kiosk/components/report/reviewPresentation.ts`（+ `.test.ts`）、`tests/kiosk-screen-05-game.spec.ts`、`tests/kiosk-screen-10-platform-game.fourup.spec.ts` |
| **B 其它前端页** | 2 → 3 → 8a | `katrain/web/ui/` 下：`src/kiosk/pages/PlayPage.tsx`（+ `.test.tsx`）、`src/kiosk/pages/PlatformLobbyPage.tsx`（+ `.test.tsx`）、`src/kiosk/components/physical/EngineMoveErrorDialog.tsx`、`src/kiosk/__tests__/EngineMoveErrorDialog.test.tsx` |
| **C 后端** | 5 → 5b → 6 → 6b → 8b | `katrain/web/interface.py`、`katrain/web/platforms/gateway.py`、`katrain/web/server.py`、`katrain/web/api/v1/endpoints/vision.py`、`katrain/web/core/repository.py`、`katrain/web/core/sync_worker.py`、`katrain/web/core/remote_client.py`、`katrain/web/core/physical_play_orchestrator.py`、`tests/platforms/test_engine_gateway.py`、`tests/platforms/test_engine_integration.py`、`tests/platforms/test_engine_game_ledger.py`（新）、`tests/platforms/test_engine_game_ledger_e2e.py`（新）、`tests/web_ui/test_user_game_cloud_owner.py`（新）、`tests/test_vision_move_poller.py`、`tests/test_vision_engine_move_recovery_endpoints.py`、`tests/test_physical_play_orchestrator.py`、`tests/test_engine_physical_integration.py` |
| **合并后串行**（本 worktree） | 9 | 两屏四图目录；以及所有 :5173 / 构建 / 全量的步骤：两套构建、全量 vitest / pytest 闸、`kiosk-screen-05-game.spec.ts` 真浏览器、`Void` 终局卡预览、四图 |

**泳道之间没有代码依赖**，只有数据契约：C 产出 `end_result` / `user_games.result` = `"Void"`，A 的 Task 7 只在 mock 里消费这个字符串；C 的恢复框重试在终局时回 `{"ok": true, "game_ended": true}`，B 不读 `game_ended`（弹层按既有的 `ok: true` 关闭，`EngineMoveErrorDialog.tsx:88-90`，`EngineMoveErrorDialog.test.tsx:64` 已守）。泳道 C 内部有依赖：5b 消费 5 的 `/api/move` game_ended→200 分支；6 消费 5b 的 `is_platform_engine_session` 与路由；8b 的真栈用例消费 5b 的视觉路由（故 8b 排在 C 的最后）。

**开泳道**（Task 0 做完、任何 Task 开始之前；Task 0 不提交，所以 `$BASE` 就是当前 HEAD）。**前提是本计划与 prd 的修订已经提交**：泳道从 `$BASE` 开出，没提交的修订进不了泳道，泳道里那份 `plan.md` 就是旧版（没有 5b、没有闸、Task 8 没拆）——Task 0 Step 1 要求 `status --porcelain` 为空，查的就是这件事，不为空就先把文档修订单独提交。派任务给泳道时，计划一律给绝对路径 `$R/superpowers/tracks/kiosk-go-cross-platform/plan.md`，不读泳道里的副本：

```bash
R=/Users/fan/Repositories/katrain-kiosk-go-cross-platform
LANES="${TMPDIR:-/tmp}/kgcp-lanes"
BASE=$(git -C $R rev-parse HEAD) && echo "$BASE" > "${TMPDIR:-/tmp}/kgcp-base.sha"
for l in a b c; do git -C $R worktree add -b "kgcp-lane-$l" "$LANES/$l" "$BASE"; done
cd "$LANES/a/katrain/web/ui" && npm ci
cd "$LANES/b/katrain/web/ui" && npm ci
```

- 前端泳道各自 `npm ci`，**不要把 `node_modules` 软链到本 worktree**：`tsconfig.app.json:3` / `tsconfig.node.json:3` 的 `tsBuildInfoFile` 是 `./node_modules/.tmp/…`，软链会让几条泳道的 `tsc -b` 共用同一份增量状态。
- 后端泳道不建自己的 `.venv`：泳道里 `uv run` 会按 lockfile 另建一个**不带 extras** 的环境（fastapi 缺失）。一律用本 worktree 的解释器、**在泳道根目录下**跑：`python -m` 把当前目录放在 `sys.path` 首位，导入的是泳道里的 `katrain`（审查时在临时 worktree 里就是这么实跑的，报错栈里的路径是临时树的 `katrain/web/server.py`）。

**泳道里执行 Task 步骤时的两条机械替换**（其余照抄）：

1. 步骤里的 `cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform` 换成 `cd "$LANES/<a|b|c>"`。
2. 泳道 C：`uv run pytest <文件> …` 换成 `$R/.venv/bin/python -m pytest <文件> … -p no:cacheprovider`；`uv run black …` 换成 `$R/.venv/bin/python -m black …`。

**泳道里不做的**：Playwright / :5173、`npm run build`、全量 vitest / pytest（都在 Task 9）。泳道 C 只跑各步骤点名的文件——跑整个 `tests/platforms/` 会多出两条只在「这棵树没有自己的 `.venv`」时才红的用例（`test_golaxy_alignment_campaign.py::test_direct_cli_pins_current_repo_katrain_before_poisoned_pythonpath_and_disables_kivy_args`、`test_golaxy_sampling_campaign.py::test_sampling_direct_cli_pins_current_repo_before_poisoned_pythonpath`；审查时在未改动源码的临时树上实跑同样红）。

**合回本分支**（三条泳道都提交完；按 A → B → C 的顺序，文件不相交所以不会有冲突——有冲突就说明越界改了别的泳道的文件，停下查）：

```bash
R=/Users/fan/Repositories/katrain-kiosk-go-cross-platform
LANES="${TMPDIR:-/tmp}/kgcp-lanes"
BASE=$(cat "${TMPDIR:-/tmp}/kgcp-base.sha")
cd $R && git status --porcelain && for l in a b c; do git cherry-pick "$BASE..kgcp-lane-$l" || break; done
git -C $R log --oneline "$BASE..HEAD" | wc -l
for l in a b c; do git -C "$LANES/$l" status --short --ignored; done
```

Expected：`git status --porcelain` 为空；cherry-pick 全部成功；提交数恰好 **11**（A：1、4、7；B：2、3、8a；C：5、5b、6、6b、8b）；三个泳道的 `--ignored` 里只剩 `node_modules/`、`.pytest_cache/`、`__pycache__/` 这类可重装的东西（有别的就先挪走再删泳道——`worktree remove` 会静默删掉 gitignored 文件）。然后：

```bash
R=/Users/fan/Repositories/katrain-kiosk-go-cross-platform
LANES="${TMPDIR:-/tmp}/kgcp-lanes"
for l in a b c; do git -C $R worktree remove --force "$LANES/$l" && git -C $R branch -D "kgcp-lane-$l"; done
```

之后在本 worktree 做 Task 9。

---

### Task 0: 环境与基线

**Files:** 无代码改动、不提交。闸脚本、日志与报告只写到 `${TMPDIR:-/tmp}/kgcp-*`。

**Interfaces:**
- Produces（Task 9 消费）：`${TMPDIR}/kgcp-gate.py`；`${TMPDIR}/kgcp-vitest-before.{exit,log,json,ids,bad,skip}`、`${TMPDIR}/kgcp-pytest-before.{exit,log,xml,ids,bad,skip}`、`${TMPDIR}/kgcp-eslint-before.json`、`${TMPDIR}/kgcp-user-config.json`。

- [ ] **Step 1: 确认起点**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && git rev-parse --abbrev-ref HEAD && git log --oneline -1 && git status --porcelain
```
Expected: `feature/kiosk-go-cross-platform`；HEAD 是 develop `bad0c1fb` 之上只含 `superpowers/tracks/kiosk-go-cross-platform/` 文档的提交；`status --porcelain` 无输出。

- [ ] **Step 2: 核实依赖（缺了才装），并确认 pytest 收得齐**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && .venv/bin/python -c 'import fastapi, boto3, fontTools, brotli, moto, cv2; print("deps-ok")'
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && test -x node_modules/.bin/vitest && echo node-ok
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && CI=true uv run pytest tests --collect-only -q > "${TMPDIR:-/tmp}/kgcp-collect.log" 2>&1; echo "exit=$?"; tail -3 "${TMPDIR:-/tmp}/kgcp-collect.log"
```
Expected: 前两条打印 `deps-ok` / `node-ok`；第三条打印 `exit=0`，末行是 `N tests collected in …s`，**没有** `error` / `Interrupted`（2026-09-15 实跑 N = 3980）。缺包时才跑 `uv sync --extra web --extra vision --extra board && uv pip install boto3 fonttools brotli moto` 或在 `katrain/web/ui` 跑 `npm ci`，然后重跑核实命令。
- 只 `uv sync` 不带 extras：`tests/conftest.py:73` 导入 `katrain.web` → `server.py` 导入 fastapi 失败，conftest 加载即中止（实跑：`ModuleNotFoundError: No module named 'fastapi'`，退出码 4）。
- 带 extras 但不补那 4 个包：`tests/test_storage_s3.py`（boto3）、`tests/web_ui/test_build_galaxy_fonts.py`（fontTools）收集失败，`Interrupted: 2 errors during collection`（实跑）。
- 有人跑过裸 `uv sync`（它会删掉多装的包）就重做本步。

- [ ] **Step 3: 写全量测试闸**

Run:
```bash
cat > "${TMPDIR:-/tmp}/kgcp-gate.py" <<'EOF'
"""kgcp 全量测试闸。用法：python3 kgcp-gate.py {vitest|pytest} <phase> [允许消失 / 不执行的用例名清单文件]
phase = before（基线）或任意别的名字（after / after2 …，都与 before 比）。
读 $TMPDIR/kgcp-<tool>-<phase>.{exit,log,json|xml}；写 .ids（报告里的用例）、.bad（失败）、.skip（在报告里但没执行）、.new（比 before 新增的失败）。
退出码 0 = 绿，1 = 红。判据落在「这一轮完整跑完了没有」上，不只落在失败名字上：报告缺失、没有汇总行、
退出码不是 0/1、收集 / 导入失败、未处理异常都是红；非 before 另比名字集合（新增失败、基线有而这次没了的用例、
这次没执行而基线里不是这样的用例——只有 passed / failed 算执行：skip / todo / pending / xfail 报不出失败）。"""
import json, os, re, sys
import xml.etree.ElementTree as ET

tool, phase = sys.argv[1], sys.argv[2]
allowed = set(open(sys.argv[3], encoding="utf-8").read().splitlines()) - {""} if len(sys.argv) > 3 else set()
K = os.path.join(os.environ.get("TMPDIR", "/tmp"), "kgcp")
base, red, ids, bad, skip = f"{K}-{tool}-{phase}", [], set(), set(), set()
text = lambda p: open(p, encoding="utf-8", errors="replace").read() if os.path.exists(p) else ""
code = text(base + ".exit").strip()
code = int(code) if code.isdigit() else None
log = text(base + ".log")

if tool == "vitest":
    try:
        report = json.loads(text(base + ".json"))
    except json.JSONDecodeError:
        report = None
        red.append("没有可解析的 JSON 报告（运行没跑完）")
    for f in (report or {}).get("testResults", []):
        name = os.path.relpath(f["name"])
        for a in f["assertionResults"]:
            tid = " > ".join([name, *a["ancestorTitles"], a["title"]])
            ids.add(tid)
            if a["status"] == "failed":
                bad.add(tid)
            elif a["status"] != "passed":  # skipped / todo / pending
                skip.add(tid)
        if f["status"] == "failed" and not any(a["status"] == "failed" for a in f["assertionResults"]):
            bad.add(f"SUITE {name}: {(f.get('message') or '').splitlines()[:1]}")  # 导入失败 / beforeAll 抛错 / 空文件
    m = re.search(r"^\s*Errors\s+(\d+) errors?", log, re.M)  # 未处理异常：JSON 的 success 看不见它
    if m:
        bad.add(f"UNHANDLED {m.group(1)} error(s)，见 log 的 Unhandled Errors 段")
    if not re.search(r"^\s*Test Files\s+", log, re.M):
        red.append("log 里没有 `Test Files` 汇总行（运行没跑完）")
else:
    try:
        root = ET.fromstring(text(base + ".xml"))
    except ET.ParseError:
        root = None
        red.append("没有 junit XML（conftest / 插件导入失败、进程被杀时就是这样）")
    for tc in root.iter("testcase") if root is not None else []:
        if not tc.get("classname"):  # 收集失败：整个模块没进来
            bad.add(f"COLLECT {tc.get('name')}")
            continue
        tid = f"{tc.get('classname')}::{tc.get('name')}"
        ids.add(tid)
        if tc.find("failure") is not None or tc.find("error") is not None:
            bad.add(tid)
        elif tc.find("skipped") is not None:  # skip / skipif / xfail
            skip.add(tid)
    if re.search(r"Interrupted:|INTERNALERROR", "\n".join(log.splitlines()[-5:])):
        red.append("log 末尾有 Interrupted / INTERNALERROR")

if not ids:
    red.append("一条用例都没跑")
if code not in (0, 1):
    red.append(f"退出码 {code}（0/1 以外 = 中断、内部错误、用法错误或没收集到用例）")
if (code == 1) != bool(bad):
    red.append(f"退出码 {code} 与解析出的失败数 {len(bad)} 对不上 —— 有闸不认识的形状，去读 log")
structural = sorted(b for b in bad if b.startswith(("SUITE ", "COLLECT ", "UNHANDLED ")))
for ext, rows in ((".ids", ids), (".bad", bad), (".skip", skip)):
    open(base + ext, "w", encoding="utf-8").write("".join(r + "\n" for r in sorted(rows)))
print(f"[{tool} {phase}] exit={code} 用例={len(ids)} 失败={len(bad) - len(structural)} 结构性={len(structural)} 未执行={len(skip)}")

if phase == "before" and structural:
    red.append("基线里有结构性失败（环境没装齐），基线不可用：\n    " + "\n    ".join(structural))
if phase != "before":
    before_ids = set(text(f"{K}-{tool}-before.ids").splitlines())
    new_bad = sorted(bad - set(text(f"{K}-{tool}-before.bad").splitlines()))
    vanished = sorted(before_ids - ids - allowed)
    new_skip = sorted(skip - set(text(f"{K}-{tool}-before.skip").splitlines()) - allowed)
    open(base + ".new", "w", encoding="utf-8").write("".join(r + "\n" for r in new_bad))
    print("--- 新增失败 ---", *new_bad, "--- 基线有、这次没了的用例（不在允许清单里）---", *vanished,
          "--- 这次没执行、基线里不是这样的用例（不在允许清单里）---", *new_skip, sep="\n")
    if not before_ids or not os.path.exists(f"{K}-{tool}-before.skip"):
        red.append("找不到 before 基线（Task 0 没跑、TMPDIR 被清，或基线是改版前的闸写的、没有 .skip）")
    if new_bad:
        red.append(f"新增失败 {len(new_bad)} 条")
    if vanished:
        red.append(f"{len(vanished)} 条基线用例这次没跑到")
    if new_skip:
        red.append(f"{len(new_skip)} 条用例这次没执行（基线跑过的改成了 skip / todo / xfail，或新增的用例没执行）")

if red:
    print("闸红：", *red, sep="\n  - ")
    sys.exit(1)
print("闸绿")
EOF
shasum -a 256 "${TMPDIR:-/tmp}/kgcp-gate.py"
python3 "${TMPDIR:-/tmp}/kgcp-gate.py" vitest __nobase__; echo "exit=$?"; rm -f "${TMPDIR:-/tmp}"/kgcp-vitest-__nobase__.*
```
Expected:
- `shasum` 打印 `2e4c3b05575b334d0c68274bf6855a16f2630be750c9db125fd87197b8172366`（与审查时逐分支回放过的那份逐字节相同；对不上就是抄错了，重抄，别往下走）。
- 探针那条打印 `[vitest __nobase__] exit=None 用例=0 失败=0 结构性=0 未执行=0`，`闸红：` 下面含 `一条用例都没跑`，最后 `exit=1`。它证明文件里是能跑的闸，而不只是能被解析的 Python——上一版这里用 `ast.parse` 检查，对一个没替换的模板占位符（双花括号包一个名字，恰好是合法的 Python 表达式）也打印 `gate ok`。

这个闸的每条分支审查时都执行过一次（用 2026-09-15 真实运行留下的产物回放，结论是实跑得出的）：真基线 vitest 1730 条 / pytest 3980 条（85 条既有失败）→ 绿；同一份 pytest 基线当 after → 绿；某测试文件导入改名后的模块 → `SUITE …: Failed to resolve import` 红，且该文件 20 条用例进「没跑到」；`setTimeout` 里抛错 → `UNHANDLED 1 error(s)` 红；空测试文件、`beforeAll` 抛错 → `SUITE` 红；普通断言失败 → 「新增失败 1 条」红；`tests/` 下一个模块收集失败 → `COLLECT …` + 退出码 2 红；conftest 导入失败（没有 XML、退出码 4）→ 红；进程被杀（没有 JSON、没有汇总行、退出码 137）→ 红；找不到 before 基线 → 红；允许清单里的用例消失 → 不算「没跑到」。它替掉的旧写法 `grep '^\s+×'` / `grep '^(FAILED|ERROR) '` + `;` 对上面「导入失败 / conftest 失败 / 中断」三种都读出 0 条失败。

- [ ] **Step 4: 前端基线**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && K="${TMPDIR:-/tmp}/kgcp" && rm -f "$K-vitest-before.exit" "$K-vitest-before.log" "$K-vitest-before.json" && npx vitest run --reporter=default --reporter=json --outputFile.json="$K-vitest-before.json" > "$K-vitest-before.log" 2>&1; echo $? > "$K-vitest-before.exit"; python3 "$K-gate.py" vitest before
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx eslint --format json src/kiosk/pages/GamePage.tsx src/kiosk/pages/PlayPage.tsx src/kiosk/pages/PlatformLobbyPage.tsx src/kiosk/components/game/GameControlPanel.tsx src/kiosk/components/report/reviewPresentation.ts src/kiosk/components/physical/EngineMoveErrorDialog.tsx > "${TMPDIR:-/tmp}/kgcp-eslint-before.json"; python3 -c "import json,os; r=json.load(open(os.path.join(os.environ.get('TMPDIR','/tmp'),'kgcp-eslint-before.json'))); print(sum(f['errorCount'] for f in r), 'errors', sum(f['warningCount'] for f in r), 'warnings')"
```
Expected: 闸打印 `[vitest before] exit=0 用例=… 失败=0 结构性=0 未执行=…` 与 `闸绿`（2026-09-15 实跑 1730 条、0 失败、5 条既有 skip）；eslint 打印 `1 errors 4 warnings`（error 是 `PlayPage.tsx:49` 状态 effect 开头 `setPlatforms(defaultPlatforms())` 的 `react-hooks/set-state-in-effect`，4 条 warning 是 `GamePage.tsx` 既有的 `exhaustive-deps`；不在本轮修）。闸红就停下修环境，不许带着红闸往下走。**闸要在 `katrain/web/ui` 下跑**：用例名里的文件路径是相对当前目录算的，Task 9 在同一目录跑才对得上。

- [ ] **Step 5: 后端基线**

Run（先看有没有别的赛道在跑全量，有就等它结束）:
```bash
ps -axo pid,command | grep -E '[p]ytest tests|[v]itest run'
```
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && K="${TMPDIR:-/tmp}/kgcp" && cp ~/.katrain/config.json "$K-user-config.json" && rm -f "$K-pytest-before.exit" "$K-pytest-before.log" "$K-pytest-before.xml" && CI=true uv run pytest tests -q -rfE --junitxml="$K-pytest-before.xml" > "$K-pytest-before.log" 2>&1; echo $? > "$K-pytest-before.exit"; python3 "$K-gate.py" pytest before; git status --porcelain; cmp -s ~/.katrain/config.json "$K-user-config.json" && echo user-config-unchanged
```
Expected:
- 闸打印 `[pytest before] exit=1 用例=… 失败=… 结构性=0 未执行=…` 与 `闸绿`（2026-09-15 两次实跑：3980 条用例，失败 83 / 85 条、8 条既有 skip / xfail——基线本身有抖动；其中含 `tests/platforms/test_engine_move_guards.py` 的 20 条既有失败，它守的是 undo / redo / nav / ai-move 的 pending 闸，本轮不改那几个端点）。
- `git status --porcelain` 只可能列出 `katrain/config.json` 与 `katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json`：对列出的执行 `git checkout -- <文件>` 还原；列出别的文件就停下查。
- 没打印 `user-config-unchanged`：全量 pytest 改了 `~/.katrain/config.json`。第一条 `ps` 没有别的赛道在跑时，`cp "$K-user-config.json" ~/.katrain/config.json` 还原；有别人在跑就不还原（会覆盖别人的写入），把 `diff` 记进最终回报。

---

### Task 1: X7 —— 对局屏付费道具的两道 token 闸换 `isAuthenticated`

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx:142`（解构）、`:334-341`（`refreshItemCounts`）、`:501`（`handleEngineAnalysis` 早退）
- Test: `katrain/web/ui/src/kiosk/__tests__/GamePageEngine.test.tsx:68-71`（auth mock）、`:187-190`（beforeEach）、`:340` 之后（新用例）

**Interfaces:**
- Consumes: `useAuth(): { token: string | null; isAuthenticated: boolean; user; … }`（`src/context/AuthContext.tsx`）；`API.platformEngineItems(platform: string, token: string | null | undefined)`、`API.platformEngineAnalysis(platform, sessionId, kind, token: string | null | undefined)`（`src/api.ts`，a979132a 已放宽）。
- Produces: 无新接口。

- [ ] **Step 1: 把 auth mock 改成可变，写两条盒端用例（先红）**

`GamePageEngine.test.tsx` 把

```tsx
// Mock auth
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'mock-token', isAuthenticated: true, user: { id: 1, username: 'test' }, login: vi.fn(), logout: vi.fn() }),
}));
```

替换为

```tsx
// Mock auth —— token 与 isAuthenticated 是**两个量**:严格盒端 token 恒 null 而人是登录的,
// 所以夹具必须能分别置位,不能让一个推另一个(a979132a 的 LobbyPage 夹具同一条)。
const authMock = vi.hoisted(() => ({ token: 'mock-token' as string | null, isAuthenticated: true }));
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({
    token: authMock.token, isAuthenticated: authMock.isAuthenticated,
    user: { id: 1, username: 'test' }, login: vi.fn(), logout: vi.fn(),
  }),
}));
```

`describe('GamePage engine mode')` 的 `beforeEach` 开头 `vi.clearAllMocks();` 之后加两行：

```tsx
    authMock.token = 'mock-token';
    authMock.isAuthenticated = true;
```

在 `describe('星阵隧道分析 (领地/支招/变化图)')` 里、`it('clicking 支招 calls API.platformEngineAnalysis(golaxy, sessionId, options, token)')` 之后插入：

```tsx
    // X7:盒上 token 恒为 null 而人是登录的。闸判 token 时这两条一个请求都不发 ——
    // 角标永远「—」、按下去没反应、实体盘支招白灯也不亮(白灯是后端在分析端点里点的)。
    // 变异记录:把 GamePage 里两处 `!isAuthenticated` 改回 `!token` → 这两条各红一次。
    it('盒端(token=null 但已登录):挂载时照样拉余次,凭据位传 null', async () => {
      authMock.token = null;
      renderPage(true);
      await waitFor(() => expect(API.platformEngineItems).toHaveBeenCalledWith('golaxy', null));
    });

    it('盒端(token=null 但已登录):按支招照样发分析请求', async () => {
      authMock.token = null;
      (API.platformEngineAnalysis as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: false, reason: 'insufficient', kind: 'options',
      });
      renderPage(true);

      fireEvent.click(screen.getByText('支招'));

      await waitFor(() => {
        expect(API.platformEngineAnalysis).toHaveBeenCalledWith('golaxy', 'test-session', 'options', null);
      });
    });
```

- [ ] **Step 2: 跑，确认两条新用例红、其余不变**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx vitest run src/kiosk/__tests__/GamePageEngine.test.tsx`
Expected: 恰好 2 条 FAIL（「盒端(token=null 但已登录)…」两条，`platformEngineItems` / `platformEngineAnalysis` 未被调用），其余 PASS。

- [ ] **Step 3: 改 `GamePage.tsx`**

`:142`

```tsx
  const { token, user } = useAuth();
```

替换为

```tsx
  // token 只当**凭据**用（严格盒端恒为 null，身份在 HttpOnly sb_go_token cookie 里）；
  // 「发不发请求」一律判 isAuthenticated —— a979132a 同一判据，这一页当时漏了（X7）。
  const { token, user, isAuthenticated } = useAuth();
```

`refreshItemCounts`（`:334-341`）

```tsx
  const refreshItemCounts = useCallback(async () => {
    if (!engineMode || !token) return;
    try {
      setEngineItemCounts(await API.platformEngineItems(platform, token));
    } catch (e) {
      console.error(e);
    }
  }, [engineMode, token]);
```

替换为

```tsx
  const refreshItemCounts = useCallback(async () => {
    if (!engineMode || !isAuthenticated) return;
    try {
      setEngineItemCounts(await API.platformEngineItems(platform, token));
    } catch (e) {
      console.error(e);
    }
  }, [engineMode, isAuthenticated, token]);
```

`handleEngineAnalysis` 里（`:501`）

```tsx
    if (!sessionId || !token) return;
```

替换为

```tsx
    if (!sessionId || !isAuthenticated) return;
```

- [ ] **Step 4: 跑测试与类型检查**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx vitest run src/kiosk/__tests__/GamePageEngine.test.tsx src/kiosk/pages/GamePage.test.tsx && npx tsc -b
```
Expected: 全 PASS；`tsc -b` 无输出退出 0。

- [ ] **Step 5: 变异验证（不提交）**

把 Step 3 的两处 `!isAuthenticated` 临时改回 `!token`，重跑 `npx vitest run src/kiosk/__tests__/GamePageEngine.test.tsx`，Expected：两条盒端用例红；`git diff` 确认后还原，再跑一次全绿。

- [ ] **Step 6: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && git add katrain/web/ui/src/kiosk/pages/GamePage.tsx katrain/web/ui/src/kiosk/__tests__/GamePageEngine.test.tsx && git commit -m "$(cat <<'EOF'
fix(kiosk): 星阵对局屏剩下的两道 token 闸 —— 盒上三颗付费道具按了没反应

a979132a 漏了 GamePage:refreshItemCounts 与 handleEngineAnalysis 仍判 !token,
盒上 token 恒 null ⇒ 角标恒「—」、领地/支招/变化图不发请求、实体盘支招白灯不亮。
判别位换 isAuthenticated,token 只作凭据原样传。新增 2 条盒端用例,变异(改回 !token)各红一次。

EOF
)"
```

---

### Task 2: X8 + X1 —— 对弈首页在盒上拉平台状态；野狐卡与屏 07 同一个词

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/PlayPage.tsx:43`（解构）、`:46-60`（状态 effect）、`:138-148`（野狐卡）
- Test: `katrain/web/ui/src/kiosk/pages/PlayPage.test.tsx:70-76`（`expectAllDisconnected`）、`:265-280`（登出用例夹具）、文件末 `});` 之前（新用例）

**Interfaces:**
- Consumes: `API.platformStatus(token: string | null | undefined): Promise<PlatformStatusResponse>`；`mergePlatformStatus` / `defaultPlatforms`（`kiosk/constants/platforms.ts`，不改）；key `platform:no_play_yet`（屏 07 `PlatformConnectPage.tsx:263` 已在用）。
- Produces: 无新接口。

- [ ] **Step 1: 写测试（先红）**

`PlayPage.test.tsx` 的 `expectAllDisconnected` 把

```tsx
  expect(fox).toHaveTextContent('接口还没通');
  expect(fox).toBeDisabled();
};
```

替换为

```tsx
  expect(fox).toHaveTextContent('接口还没通');
  // X1:屏 07 那一行写的是「暂不能对弈」,并判过「即将上线」是预测不是状态(没人给过日期)。
  // 同一个事实两屏同一个词。
  expect(fox).toHaveTextContent('暂不能对弈');
  expect(fox).not.toHaveTextContent('即将上线');
  expect(fox).toBeDisabled();
};
```

用例 `'keeps disconnected defaults after logout when an older request resolves'` 里把

```tsx
    let auth = { user: { username: '友' }, isAuthenticated: true, token: 'A' as string | null };
    const requestA = deferred<{ platforms: PlatformInfo[] }>();
    useAuthMock.mockImplementation(() => auth);
    platformStatusMock.mockReturnValue(requestA.promise);
    const view = renderPage();

    auth = { ...auth, token: null };
```

替换为

```tsx
    let auth: { user: { username: string } | null; isAuthenticated: boolean; token: string | null } =
      { user: { username: '友' }, isAuthenticated: true, token: 'A' };
    const requestA = deferred<{ platforms: PlatformInfo[] }>();
    useAuthMock.mockImplementation(() => auth);
    platformStatusMock.mockReturnValue(requestA.promise);
    const view = renderPage();

    // 登出的真形状:AuthContext.logout 把 user 置 null ⇒ isAuthenticated 为假,token 也清掉。
    // 只把 token 置 null 在盒上**不是**登出(盒上 token 本来就恒为 null)。
    auth = { user: null, isAuthenticated: false, token: null };
```

在文件末尾 `describe('PlayPage')` 的最后一个 `it` 之后、收尾 `});` 之前插入：

```tsx
  // X8:盒上 token 恒为 null 而人是登录的。判 token 时这一屏永远停在全未连接的默认名单 ——
  // 已连上星阵的人看到「点击登录 · 手机号 + 验证码」,点卡先绕到屏 07。
  // 变异记录:把 PlayPage 的 `if (isAuthenticated)` 改回 `if (token)` → 这条红。
  it('盒端(token=null 但已登录):照样拉平台状态,已连接的星阵卡直达人机开局', async () => {
    useAuthMock.mockReturnValue({ user: { username: '友' }, isAuthenticated: true, token: null });
    platformStatusMock.mockResolvedValue({ platforms: [platformRecord('golaxy', true)] });

    renderPage();

    const golaxy = await screen.findByRole('button', { name: /^星阵围棋，已连接/ });
    expect(platformStatusMock).toHaveBeenCalledWith(null);
    fireEvent.click(golaxy);
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/cross-platform/engine/golaxy');
  });
```

- [ ] **Step 2: 跑，确认红**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx vitest run src/kiosk/pages/PlayPage.test.tsx`
Expected: 新用例 FAIL（找不到「星阵围棋，已连接」）；调用了 `expectAllDisconnected` 的用例 FAIL（没有「暂不能对弈」）。

- [ ] **Step 3: 改 `PlayPage.tsx`**

`:43`

```tsx
  const { user, token } = useAuth();
```

替换为

```tsx
  // token 只当**凭据**用（严格盒端恒为 null）；「发不发这次请求」判 isAuthenticated。
  // 判 token 时盒上每个已登录用户都停在全未连接的默认名单上（X8，a979132a 同一判据，这一页当时漏了）。
  const { user, token, isAuthenticated } = useAuth();
```

状态 effect（`:46-60`）

```tsx
  useEffect(() => {
    let current = true;
    setPlatforms(defaultPlatforms());

    if (token) {
      API.platformStatus(token).then((d) => {
        if (current) setPlatforms(mergePlatformStatus(d.platforms));
      }).catch(() => {
        if (current) setPlatforms(defaultPlatforms());
      });
    }

    return () => { current = false; };
  }, [token]);
```

替换为

```tsx
  useEffect(() => {
    let current = true;
    setPlatforms(defaultPlatforms());

    if (isAuthenticated) {
      API.platformStatus(token).then((d) => {
        if (current) setPlatforms(mergePlatformStatus(d.platforms));
      }).catch(() => {
        if (current) setPlatforms(defaultPlatforms());
      });
    }

    return () => { current = false; };
  }, [isAuthenticated, token]);
```

野狐卡（`:138-148`）

```tsx
            // 「即将上线」不是「锁定」:锁定意味着东西在、满足条件就给。接口没通的平台
            // 不许摆成锁着的样子 —— `comingSoon` 是 PLATFORM_META 里就有的真标记,不是这里现编的。
            if (meta.comingSoon) {
              return (
                <KioskCard
                  key={p.platform}
                  title={t(meta.label, meta.labelCn)}
                  sub={t('Not wired up yet', '接口还没通')}
                  icon={PLATFORM_ICON[p.platform] ?? 'globe-hemisphere-west'}
                  soon={t('Coming soon', '即将上线')}
                />
```

替换为

```tsx
            // 接口没通的平台不许摆成锁着的样子(锁定意味着东西在、满足条件就给)——
            // `comingSoon` 是 PLATFORM_META 里就有的真标记,不是这里现编的。
            // 徽标也不写「即将上线」:没人给过日期,那是预测不是状态。屏 07 同一行写的是
            // 「暂不能对弈」(`PlatformConnectPage.tsx` 头注释),同一个事实两屏共用同一个 key(X1)。
            if (meta.comingSoon) {
              return (
                <KioskCard
                  key={p.platform}
                  title={t(meta.label, meta.labelCn)}
                  sub={t('Not wired up yet', '接口还没通')}
                  icon={PLATFORM_ICON[p.platform] ?? 'globe-hemisphere-west'}
                  soon={t('platform:no_play_yet', '暂不能对弈')}
                />
```

- [ ] **Step 4: 跑测试与类型检查**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx vitest run src/kiosk/pages/PlayPage.test.tsx && npx tsc -b
```
Expected: 全 PASS；`tsc -b` 退出 0。

- [ ] **Step 5: 变异验证（不提交）**

把 `if (isAuthenticated)` 临时改回 `if (token)`，重跑 `PlayPage.test.tsx`，Expected：「盒端(token=null 但已登录)…」红；还原后全绿。

- [ ] **Step 6: Commit**（屏 01 四图在 Task 9 统一重取）

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && git add katrain/web/ui/src/kiosk/pages/PlayPage.tsx katrain/web/ui/src/kiosk/pages/PlayPage.test.tsx && git commit -m "$(cat <<'EOF'
fix(kiosk): 对弈首页在盒上拉不到平台状态 —— 已连上的星阵也写「点击登录」

PlayPage 只在 token 为真时请求 /platforms/status,盒上 token 恒 null ⇒ 三张平台卡永远是
全未连接默认名单。判别位换 isAuthenticated。登出用例的夹具改成真形状(isAuthenticated=false),
只清 token 在盒上不是登出。

顺手统一野狐卡徽标:屏 07 早判过「即将上线」是预测不是状态,屏 01 改用同一个 key「暂不能对弈」。

EOF
)"
```

---

### Task 3: X4-a —— 屏 08 挑战那两句说实话

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/PlatformLobbyPage.tsx:109`（toast）、`:295`（确认框尾句）
- Test: `katrain/web/ui/src/kiosk/pages/PlatformLobbyPage.test.tsx:95-108`（用例「挑战先确认一次…」）

**Interfaces:**
- Consumes: `interpolate(template: string, vars: Record<string, string>)`（`kiosk/utils/interpolate`，本文件已 import）；`meta`（本组件内 `PLATFORM_META[platform]`）。
- Produces: 无。

- [ ] **Step 1: 写测试（先红）**

`PlatformLobbyPage.test.tsx` 用例 `'挑战先确认一次,发出去的条件和屏上那行读数同源'` 整条替换为：

```tsx
  it('挑战先确认一次,发出去的条件和屏上那行读数同源', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('platform-user')).toHaveLength(3));
    await userEvent.click(within(rowOf('stone_walker')).getByRole('button', { name: '挑战' }));

    const dlg = await screen.findByTestId('platform-challenge-confirm');
    expect(within(dlg).getByText('向 stone_walker 发起挑战？')).toBeInTheDocument();
    // X4-a:对方接受后盒子既不建局也不跳转(OGS `active_game` 事件没人接)。
    // 发之前就要说清 —— 同屏自动匹配那句早就这么说了。
    expect(dlg).toHaveTextContent('不会回到这台盒子');
    expect(platformSendChallenge, '还没确认就发出去了').not.toHaveBeenCalled();

    await userEvent.click(within(dlg).getByRole('button', { name: '发出挑战' }));
    await waitFor(() => expect(platformSendChallenge).toHaveBeenCalledWith(
      'ogs', { user_id: '1', board_size: 19, rules: 'chinese', ranked: true }, 'tok',
    ));
    // 发出之后那句 toast 也不许再暗示「接下来会在这边下」。
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('不会回到这台盒子'));
  });
```

- [ ] **Step 2: 跑，确认红**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx vitest run src/kiosk/pages/PlatformLobbyPage.test.tsx`
Expected: 该用例 FAIL 于 `expect(dlg).toHaveTextContent('不会回到这台盒子')`；其余 PASS。

- [ ] **Step 3: 改 `PlatformLobbyPage.tsx`**

`:109`

```tsx
      setToast({ text: t('platform:challenge_sent', '挑战已发出 —— 接下来在对面那边'), bad: false });
```

替换为

```tsx
      // X4-a:对方接受之后这台盒子不会建局、不会跳转(适配器的 `active_game` 事件没人接,
      // 见文件头「那条诚实债」)。这句原来写「接下来在对面那边」,读起来像是会回来。
      setToast({
        text: interpolate(
          t('platform:challenge_sent', '挑战已发出。对方接受后要去 {name} 上下，不会回到这台盒子。'),
          { name: t(meta.label, meta.labelCn) },
        ),
        bad: false,
      });
```

`:295`

```tsx
              <b>{t('platform:challenge_ask_tail', '发出去就在对方那边了。')}</b>
```

替换为

```tsx
              <b>
                {interpolate(
                  t('platform:challenge_ask_tail', '发出去撤不回来；对方接受后要去 {name} 上下，不会回到这台盒子。'),
                  { name: t(meta.label, meta.labelCn) },
                )}
              </b>
```

- [ ] **Step 4: 跑测试与类型检查**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx vitest run src/kiosk/pages/PlatformLobbyPage.test.tsx && npx tsc -b
```
Expected: 全 PASS；`tsc -b` 退出 0。

- [ ] **Step 5: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && git add katrain/web/ui/src/kiosk/pages/PlatformLobbyPage.tsx katrain/web/ui/src/kiosk/pages/PlatformLobbyPage.test.tsx && git commit -m "$(cat <<'EOF'
fix(kiosk): 屏 08 挑战文案不再暗示对局会回到盒子

OGS 对方接受挑战后盒子不建局也不跳转(active_game 没人接,X4 主体待拍板)。
确认框与发出后的 toast 都说清「要去 OGS 上下,不会回到这台盒子」,与同屏自动匹配那句同口径。

EOF
)"
```

---

### Task 4: X9-a —— 星阵人机局撤掉「停一手」「数子」

**Files:**
- Modify: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx:309-322`（`actions` 的 engineMode 分支）、`:413-428`（`.ghint` 注释与三元）
- Test: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.test.tsx`（悔棋 `test.each` 之后新增一条）
- Test: `katrain/web/ui/src/kiosk/__tests__/GamePageEngine.test.tsx:210-222`（改写「停一手/认输 stay enabled」用例）
- Test: `katrain/web/ui/tests/kiosk-screen-05-game.spec.ts:400-403`（屏 10 动作区标签）
- Modify: `katrain/web/ui/tests/kiosk-screen-10-platform-game.fourup.spec.ts`（等待条件、两处说明文字）
- 这两份 Playwright spec 本 Task 只改不跑：真浏览器与四图都在 :5173 上，合并回本分支后在 Task 9 Step 4 / Step 6 串行跑（见「并行泳道」）。

**Interfaces:**
- Consumes: `KioskAction`（`kiosk/shell/KioskActions.tsx`）；本组件内 `isGameOver` / `canCount` / `countMin` / `hardwareFault` / `analysisRequiresLogin`。
- Produces: 无。

- [ ] **Step 1: 写测试（先红）**

`GameControlPanel.test.tsx`：在悔棋那条 `test.each([...])('悔棋:%s → %s', …)` 结束之后插入：

```tsx
  // ── 星阵人机:停一手 / 数子撤掉(X9,2026-09-14)──────────────────────────────
  // 两颗在星阵局里**开局就定死按了必被拒**:星阵 PASS 编码没抓到,后端对引擎局恒 409
  // `pass_not_supported`;数子走联机握手,对面是 `-1`,永远 pending。判据同悔棋:
  // 永久不可用 → 撤掉,原因写在开关排右端那一格。
  // 历史给 120 手:证明撤掉不是「还没到 100 手」,右端那句也不是数子手数提示。
  // 变异记录:engineMode 那一支把 pass/count 加回去 → 前两句红;删掉 ghint 的 engineMode 分支 → 最后一句红。
  test('星阵人机:动作区只剩认输,右端写明为什么', () => {
    const history = Array.from({ length: 120 }, (_, i) => ({ node_id: i, score: 0, winrate: 0.5 }));
    const { container } = panel({ game_type: 'free', history } as Partial<GameState>, { engineMode: true });
    expect(screen.queryByText('停一手')).toBeNull();
    expect(screen.queryByText('数子')).toBeNull();
    expect(screen.getByText('认输')).toBeInTheDocument();
    expect(container.querySelector('.gtoggles .ghint')).toHaveTextContent('暂不支持停一手、数子');
  });
```

`GamePageEngine.test.tsx` 把整条

```tsx
  it('停一手/认输 stay enabled in engineMode (galaxy-reference: no blunt engineMode disable)', async () => {
```

（到它的收尾 `});`，`:210-222`）替换为：

```tsx
  // X9(2026-09-14):上一版这里钉的是「engineMode 下停一手照样可按(galaxy 参考)」——
  // 那是 07-08 那次 merge 的写法,把 07-02 `3677f3d1` 的禁用改了回去。galaxy 那边没有星阵人机局,
  // 拿它当判据是量错了对象:星阵局里这两颗按下去一个 409、一个永远 pending。
  it('星阵人机没有停一手和数子;认输照旧走确认框', async () => {
    mockGameState.count_min_moves = 1;   // 手数够了也不该出现数子 —— 撤掉不是「还没到手数」
    renderPage(true);

    expect(screen.queryByText('停一手')).toBeNull();
    expect(screen.queryByText('数子')).toBeNull();
    fireEvent.click(screen.getByText('认输'));
    expect(screen.getByText('确认认输？')).toBeInTheDocument();
  });
```

- [ ] **Step 2: 跑，确认红**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx vitest run src/kiosk/components/game/GameControlPanel.test.tsx src/kiosk/__tests__/GamePageEngine.test.tsx`
Expected: 两条新用例 FAIL（找到了「停一手」）；其余 PASS。

- [ ] **Step 3: 改 `GameControlPanel.tsx` 的动作数组**

`:309-322`

```tsx
  const actions = engineMode
    ? [
      // 悔棋不在这里 —— 跨平台对弈**整局都没有**这颗键(见上面 `undoAllowed`)。
      // 稿子 `:1851` 画的是 `<button disabled>悔棋</button>`,理由「灰在这儿比点了被拒好」;
      // 那条理由只对「等一会儿就回来」成立,而这儿是永久没有。**实现反过来纠正稿子。**
      { key: 'pass', icon: 'hand-pointing' as const, label: t('game:pass', '停一手'), onClick: () => onAction('pass'), disabled: isGameOver },
      {
        key: 'count', icon: 'squares-four' as const, label: t('Score', '数子'),
        onClick: () => onAction('count'), disabled: !canCount,
        reason: t('game:count_min', '数子要下满 {n} 手').replace('{n}', String(countMin)),
      },
      { key: 'resign', icon: 'flag' as const, label: t('Resign', '认输'), onClick: () => onAction('resign'), danger: true, disabled: isGameOver },
    ]
    : [...analysisActions, ...playActions];
```

替换为

```tsx
  const actions = engineMode
    ? [
      // 悔棋不在这里 —— 跨平台对弈**整局都没有**这颗键(见上面 `undoAllowed`)。
      // 稿子 `:1851` 画的是 `<button disabled>悔棋</button>`,理由「灰在这儿比点了被拒好」;
      // 那条理由只对「等一会儿就回来」成立,而这儿是永久没有。**实现反过来纠正稿子。**
      //
      // 停一手 / 数子按同一条判据撤掉(X9,2026-09-14)。星阵的 PASS 编码从没抓到,后端
      // `gateway.pass_move` 对引擎局恒拒(409 `pass_not_supported`);数子走联机局握手,对面是 `-1`,
      // 永远 pending。两颗都是**开局就定死的按了必被拒** ⇒ 撤掉,原因写在开关排右端 `.ghint`。
      // (07-02 `3677f3d1` 灰掉过,07-08 merge 按 galaxy 参考改回可按 —— galaxy 没有星阵人机局,
      //  那条参考量错了对象。)终局时认输照旧灰着:这一排的终局版式不在这次改动里。
      { key: 'resign', icon: 'flag' as const, label: t('Resign', '认输'), onClick: () => onAction('resign'), danger: true, disabled: isGameOver },
    ]
    : [...analysisActions, ...playActions];
```

- [ ] **Step 4: 改 `.ghint`**

`:413-428`（从注释 `{/* 三句话抢同一格` 到 `</i>`）替换为：

```tsx
        {/* 几句话抢同一格,优先级是**按「这句话还会不会自己消失」排的**:
              ① `hardwareFault` —— 故障,最急,而且要用红。
              ② 星阵人机 —— 停一手 / 数子**整局都没有**(X9),这一句是它们不在的唯一解释;
                 这种局里没有分析键也没有数子手数,③④ 两句本来就不适用。
              ③ 游客 —— 三个键**不登录就永远不会亮**;这一句在触屏上是它们唯一的解释
                 (`reason` 落在 `title`/`aria-description` 上,手指够不着)。
              ④ 数子 —— 只关一个键,而且**下满手数它自己就好了**。
            ⚠️ 代价说清楚:游客在前 100 手看不到「数子要下满 N 手」那句。可以接受 ——
            数子键到时候自己会亮,而三个分析键不会。反过来排的话,游客整局都不知道
            那三个键为什么是灰的。 */}
        <i className="ghint" data-fault={hardwareFault ? 'true' : undefined}>
          {hardwareFault
            ?? (engineMode
              ? (isGameOver ? '' : t('game:golaxy_no_pass_count', '暂不支持停一手、数子'))
              : analysisRequiresLogin
                ? t('play:analysis_requires_login_hint', '领地 / 支招 / 图表 登录后可用')
                : !isGameOver && !canCount
                  ? t('game:count_min', '数子要下满 {n} 手').replace('{n}', String(countMin))
                  : '')}
        </i>
```

- [ ] **Step 5: 跑单测与类型检查**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx vitest run src/kiosk/components/game/GameControlPanel.test.tsx src/kiosk/__tests__/GamePageEngine.test.tsx src/kiosk/__tests__/GamePageLedBadge.test.tsx src/kiosk/pages/GamePage.test.tsx && npx tsc -b
```
Expected: 全 PASS（`GamePageLedBadge` 守的是非星阵局的「数子要下满 100 手」与故障优先，不受影响）；`tsc -b` 退出 0。

- [ ] **Step 6: 改真浏览器断言与四图等待条件**

`tests/kiosk-screen-05-game.spec.ts:400-403`

```ts
  // 悔棋不在里面 —— **跨平台对弈整局都没有这颗键**(Fan 2026-08-25 亲裁)。
  // 上一版是四个键,第四个是「悔棋」,只在星阵算招期间撤掉 ⇒ 一局几十次四↔三来回翻,
  // 而这一排是 `grid-auto-columns: 1fr`,翻一次「认输」就在用户手指底下挪一格。
  expect(g.actionLabels, '星阵局的动作区不是三个键').toEqual(['停一手', '数子', '认输']);
```

替换为

```ts
  // 悔棋不在里面 —— **跨平台对弈整局都没有这颗键**(Fan 2026-08-25 亲裁)。
  // 停一手 / 数子也不在(X9,2026-09-14):星阵局里一个恒 409、一个永远 pending,开局就定死按了必被拒。
  // 三颗都是**整局不在**,不是来回翻 ⇒「认输」不会在用户手指底下挪格。
  expect(g.actionLabels, '星阵局的动作区只剩认输').toEqual(['认输']);
```

`tests/kiosk-screen-10-platform-game.fourup.spec.ts`：

(a) 把

```ts
  /**
   * 动作区就是三颗 —— **这一屏现在从第一帧起就是三颗**,不再有「四颗变三颗」那个过程。
   *
   * ⚠️ 所以这一句现在只是「这一排渲染出来了、且不多不少三颗」的守卫,
   * **它不再证明任何时序**;别把它读成「等到了某个状态」。
   * ⚠️ 也别退回去等 `button:disabled`:数子本来就是灰的(第 18 手 < `count_min_moves` 100),
   * 那个选择器立刻命中、测试通过而**什么都没证明** —— 量错了对象。
   */
  await page.waitForFunction(() =>
    document.querySelectorAll('[data-testid="game-actions"] button').length === 3);
```

替换为

```ts
  /**
   * 动作区只有一颗「认输」—— 从第一帧起就是一颗(X9,2026-09-14 撤掉停一手 / 数子)。
   *
   * ⚠️ 这一句只是「这一排渲染出来了、且不多不少一颗」的守卫,**不证明任何时序**。
   */
  await page.waitForFunction(() =>
    document.querySelectorAll('[data-testid="game-actions"] button').length === 1);
```

(b) 把说明注释里

```ts
 *  · **数子:稿子画成可按,实现是灰的 —— 这次是稿子错。** `canCount = !isGameOver && moves >= countMin`,
 *    这一帧第 18 手而 `count_min_moves` 是 100 ⇒ 灰,且开关排右端已经写出「数子要下满 100 手」。
 *    稿子在第 18 手把数子画成能按,和它自己写的中国规则局对不上。归「稿子画错」那一类。
```

替换为

```ts
 *  · **停一手 / 数子:稿子画成可按,实现整局不画(X9,2026-09-14)。** 星阵 PASS 编码没抓到,
 *    后端对引擎局恒 409;数子走联机握手,对面是 `-1`,永远 pending ⇒ 开局就定死按了必被拒,
 *    判据同悔棋(永久不可用 → 撤掉),开关排右端写「暂不支持停一手、数子」。
```

(c) 把 `implementationCaption` 里这一段

```ts
      + '**数子稿子画错**:第 18 手 < count_min_moves 100 ⇒ 该灰，右端也已写出原因 · '
```

替换为

```ts
      + '**停一手 / 数子整局不画**(X9):星阵 PASS 恒 409、数子握手对面是 -1 永远 pending，'
      + '判据同悔棋，右端写「暂不支持停一手、数子」 · '
```

- [ ] **Step 7: Commit**（屏 10 真浏览器与四图在 Task 9）

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && git add katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx katrain/web/ui/src/kiosk/components/game/GameControlPanel.test.tsx katrain/web/ui/src/kiosk/__tests__/GamePageEngine.test.tsx katrain/web/ui/tests/kiosk-screen-05-game.spec.ts katrain/web/ui/tests/kiosk-screen-10-platform-game.fourup.spec.ts && git commit -m "$(cat <<'EOF'
fix(kiosk): 星阵人机局撤掉停一手和数子 —— 一个按了弹 409 红条,一个按了永远没反应

星阵 PASS 编码没抓到,gateway 对引擎局恒拒;数子对 player_w_id=-1 的会话走联机握手,永远 pending。
两颗开局就定死按了必被拒,按本组件自己的判据(永久不可用 → 撤掉)撤掉,开关排右端写
「暂不支持停一手、数子」。07-02 3677f3d1 禁用过,07-08 merge 按 galaxy 参考改回可按 ——
galaxy 没有星阵人机局,那条参考量错了对象;钉住它的用例一并改写。

EOF
)"
```

---

### Task 5: X9-b 后端 —— AI 停手 / 认输时本地局以 `Void` 结束，`/api/move` 回 200；迟到的回复只作用于被提交的那一盘

**Files:**
- Modify: `katrain/web/interface.py:1467-1469`（`_do_timeout` 之后新增 `_do_end_without_result`）
- Modify: `katrain/web/platforms/gateway.py:82-85`（`class PlatformCommandGateway` 之前新增模块级 `_submitted_position_status`）、`:170-175`（B1 注释）、`:184`（位置令牌）、`:205-223`（`GolaxyEngineTerminal` 分支）、`:224-228`（普通隧道异常三态闸）、`:230-240`（成功分支的原子落子闸）
- Modify: `katrain/web/server.py:982-984`（`/api/move` 平台分支的 `except PlatformMoveRejectedError`）
- Test: `tests/platforms/test_engine_gateway.py:71-72`（`MockGame` 补 `end_result`）、`:205-209`（`test_engine_terminal_ends_game` 补断言）
- Test: `tests/platforms/test_engine_integration.py`（文件末追加：AI 终局真栈用例 1 条 + 等待期间认输 / 换局的可控异步真栈用例 3 条）
- Create: `tests/platforms/test_engine_game_ledger.py`（move 端点两条；夹具供 5b / 6 复用）

**Interfaces:**
- Consumes: `GolaxyAdapter._genmove_committing` 对非落点坐标 emit `game_ended` 后抛 `GolaxyEngineTerminal`（`golaxy/adapter.py:787-792`，不改）；`PlatformManager._setup_callbacks` / `_on_game_ended` → `end_platform_game`（`manager.py:283-354`，不改）；`PlatformMoveRejectedError(message, reason)`（`gateway.py:22-32`）；`_do_resign` 只改当前节点的 `end_state`、**节点对象不换**（`interface.py:1464-1465`）；`_do_new_game` 换掉整个 `self.game`（`interface.py:710`）。
- Produces:
  - `WebKaTrain` 命令 `"end_without_result"`：`session.katrain("end_without_result")` 把当前节点 `end_state` 置为 `"Void"`，随后照常 `update_state()`。
  - `gateway.py` 模块级 `_submitted_position_status(session, game, node) -> "live" | "ended" | "replaced"`（调用方持 `session.lock`；`game` / `node` 是提交前在同一把锁下抓住的**对象本身**，不是 `id()`）。
  - 原因码契约：gateway **只在被提交的这一盘确实结束时**抛 `reason="game_ended"`——要么本次以 `Void` 结束了它（主线多出人那一手），要么隧道等待期间它已被认输（结果原样保留、这一手不落）；等待期间换了局 / 换了节点一律 `position_changed`，本地局一子不动。⇒ Task 6 两处「只在 `game_ended` 上落账」读到的 `end_result` 恒是被提交那盘的真结果。
  - `POST /api/move` 契约：gateway 抛 `reason == "game_ended"` 时回 **200** `{"session_id", "state"}`；其它 reason 照旧 409 `{"detail": str(e)}`。Task 6 在这个分支里加落账调用。
  - `tests/platforms/test_engine_game_ledger.py` 里的夹具 `HUMAN`、`_engine_session(end_result=None, human_color="B", engine=True)`、`_gateway(is_engine=True)`、`_app(session, gateway)`、`_client(app)`，Task 5b / 6 复用。`engine=False` 造的是 OGS 真人局形状：座位同为 `(人, -1)`、**故意不设** `platform_engine_color`（留 MagicMock 默认值）。

为什么不只在「AI 回了非落点」那一支加 `end_without_result`：隧道最长等 180 秒，这段时间 gateway **不持锁**（`gateway.py:199-204`）。认输（`/api/resign` 没有 pending 闸，`server.py:1874-1893`；引擎局的认输键在等待期间是亮的）只改节点的 `end_state`，所以只比 `id(current_node)` 的旧闸对它是瞎的：迟到的落点回复会在认输节点后面接上 [人, AI] 两手、局面复活；迟到的非落点回复会先接上人那一手再写 `Void`、把认输盖掉。`/api/new-game`、`/api/sgf/load` 也没有 pending 闸（`server.py:3022-3028` 的 docstring 自认不防），迟到的非落点回复会把**新局**以 `Void` 结束，Task 6 随后还会给它落一行空账。审查时在临时 worktree 里用真栈把这四种时序都跑出来过。

- [ ] **Step 1: 写测试（先红）**

(a) `tests/platforms/test_engine_gateway.py` 的 `MockGame.__init__`（`:71-72`）

```python
        self.current_node = MockNode()
        self.rules = "japanese"  # read (before the length check) by the real suicide-rule branch
```

替换为

```python
        self.current_node = MockNode()
        self.end_result = None  # 真 Game 的 property;gateway 的迟到回复闸(`_submitted_position_status`)读它
        self.rules = "japanese"  # read (before the length check) by the real suicide-rule branch
```

（不补这一行，Step 4 之后 `test_human_then_ai_order`、`test_engine_terminal_ends_game`、`test_local_play_failure_after_ai_move_clears_pending` 三条会报 `AttributeError: 'MockGame' object has no attribute 'end_result'`——夹具跟着真对象的形状补齐，不是为了让测试变绿去改生产代码。）

(b) 同文件 `test_engine_terminal_ends_game` 末尾（`:205-209`）

```python
        assert session.moves == [(3, 3)]  # human's final move IS recorded (D7)
        assert ctx.pending_action is None
        assert exc_info.value.reason == "game_ended"
        reasons = [msg.get("reason") for _, msg in sm.broadcasts if msg["type"] == "platform_move_rejected"]
        assert "game_ended" in reasons
```

替换为

```python
        assert session.moves == [(3, 3)]  # human's final move IS recorded (D7)
        assert ctx.pending_action is None
        assert exc_info.value.reason == "game_ended"
        reasons = [msg.get("reason") for _, msg in sm.broadcasts if msg["type"] == "platform_move_rejected"]
        assert "game_ended" in reasons
        # X9: the LOCAL game ends too, without a result — an AI pass and an AI resign decode
        # identically today, so any winner written here would be a guess. Without this the
        # board sat on "AI to move" forever and every retry failed "not your turn".
        commands = [command for command, _ in session.katrain_calls]
        assert commands[-1] == "end_without_result"
        assert commands.index("play") < commands.index("end_without_result")
```

(c) `tests/platforms/test_engine_integration.py`：先改 `:22` 的 import

```python
from katrain.web.platforms.golaxy.engine_client import GenmoveResult
```

替换为

```python
from katrain.web.platforms.golaxy.engine_client import GenmoveResult, Retryable
```

再在文件末尾追加（其余所需 `EngineGameConfig`、`_build_stack`、`_genmove_for`、`_main_line` 文件里都已有）：

```python
@pytest.mark.asyncio
async def test_ai_special_coord_ends_the_local_game_without_result():
    """X9: genmove 回一个盘外坐标(星阵的停一手 / 认输都解成 UnknownSpecial)。

    真栈上要成立三件事:人那一手落下;本地局以 `Void` 结束(不再停在「轮到 AI」);
    平台上下文被摘掉。`_setup_callbacks` 在生产里由 `connect_platform` 挂上,
    这里 `_build_stack` 没走登录,手动挂 —— 否则 adapter 的 `game_ended` 没人接,
    第三条测的就不是生产里的形状。"""
    from katrain.web.platforms.gateway import PlatformMoveRejectedError

    sm, pm, gateway, adapter = _build_stack(genmove_return=GenmoveResult(coord=361, prob=0.0))
    pm._setup_callbacks(adapter)
    config = EngineGameConfig(level=1100, human_color="B")
    session_id = await pm.start_engine_game("golaxy", config, user_id=1)
    session = sm.get_session(session_id)

    with pytest.raises(PlatformMoveRejectedError) as exc_info:
        await gateway.play_move(session_id, 3, 3, user_id=1)

    assert exc_info.value.reason == "game_ended"
    assert _main_line(session) == [("B", (3, 3))]
    assert session.katrain.game.end_result == "Void"
    assert session.katrain.get_state()["end_result"] == "Void"
    assert not pm.is_platform_game(session_id)


TUNNEL_TIMEOUT = Retryable("Golaxy genmove network error: ReadTimeout")  # `engine_client.py:270` 的形状


async def _human_black_move_waiting_on_the_tunnel(reply):
    """开一盘人执黑的星阵人机局,人在 (3,3) 落子,隧道**停在** genmove 上不返回,直到调用方 `release.set()`。

    `reply` 是异常实例时,放行后隧道**抛出**它而不是回一个坐标 —— 超时 / 断网在生产里就是这个形状
    (`engine_client.engine_genmove` 把 httpx 的超时与传输错误包成 `Retryable`,adapter 原样重试一次后抛出)。

    真栈,只替换网络边界;`_setup_callbacks` 手动挂上(生产里由 `connect_platform` 挂),
    否则认输和 AI 终局的 `game_ended` 没人接、平台上下文不会被摘,测的就不是生产里的形状。"""
    import asyncio

    entered, release = asyncio.Event(), asyncio.Event()

    async def genmove_waits_for_release(**_kwargs):
        entered.set()
        await release.wait()
        if isinstance(reply, Exception):
            raise reply
        return reply

    sm, pm, gateway, adapter = _build_stack(genmove_side_effect=genmove_waits_for_release)
    pm._setup_callbacks(adapter)
    session_id = await pm.start_engine_game("golaxy", EngineGameConfig(level=1100, human_color="B"), user_id=1)
    session = sm.get_session(session_id)
    move_task = asyncio.create_task(gateway.play_move(session_id, 3, 3, user_id=1))
    await entered.wait()  # 人那一手已经过了本地预检、pending 已置、正卡在隧道里
    return gateway, session_id, session, move_task, release


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reply",
    [_genmove_for(15, 3), GenmoveResult(coord=361, prob=0.0), TUNNEL_TIMEOUT],
    ids=["ai_move", "ai_special_coord", "tunnel_timeout"],
)
async def test_resign_during_the_tunnel_wait_stands_against_the_late_reply(reply):
    """X9/N13: 人在 AI 还没回的时候认输(等待期间认输键是亮的,「退出 → 认输并退出」同理)。

    认输不改 `current_node` 的身份 ⇒ 只比节点身份的闸放行迟到的回复:回的是落点,就在已认输的
    节点后面接上 [人, AI] 两手,局面「复活」;回的是非落点,就接上人那一手再写 Void,把认输结果盖掉。
    隧道卡住正是人最想认输的时候 ⇒ 认输之后隧道才超时同样常见(plan 审查第 2 轮):报 `engine_error` 的话
    `/api/move` 回 409、终局卡上弹不会自己消失的「AI 连接出错」,视觉路把它计进恢复 episode,恢复框「重试」
    再发一张新令牌 —— 都是对一盘已经结束的局。
    判据是认输写进节点的 `end_state`(结束流程写下的状态位),不是「有没有收到过终局消息」。"""
    from katrain.web.platforms.gateway import PlatformMoveRejectedError

    gateway, session_id, session, move_task, release = await _human_black_move_waiting_on_the_tunnel(reply)

    await gateway.resign(session_id, user_id=1)
    resigned = session.katrain.game.end_result
    assert resigned and resigned.endswith("+R")

    release.set()
    with pytest.raises(PlatformMoveRejectedError) as exc_info:
        await move_task

    assert exc_info.value.reason == "game_ended"
    assert session.katrain.game.end_result == resigned
    assert _main_line(session) == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reply", [GenmoveResult(coord=361, prob=0.0), TUNNEL_TIMEOUT], ids=["ai_special_coord", "tunnel_timeout"]
)
async def test_new_game_during_the_tunnel_wait_is_not_touched_by_the_late_reply(reply):
    """X9: 等待期间这个会话换了一盘(`/api/new-game`、`/api/sgf/load` 都没有 pending 闸,见 server.py
    `_guard_engine_move_pending` 的 docstring)。迟到的非落点回复结束的是**原来那盘**,不许把新局以 Void 结束;
    也不许回 `game_ended` —— `/api/move` 与视觉路只在 `game_ended` 上落账(Task 6),回了就会给这盘新局落一行空账。
    隧道超时同理:原因码说的是被提交的那一盘,等待期间换了局一律 `position_changed`,不看隧道回了什么。"""
    from katrain.web.platforms.gateway import PlatformMoveRejectedError

    gateway, session_id, session, move_task, release = await _human_black_move_waiting_on_the_tunnel(reply)

    with session.lock:
        session.katrain("new_game")

    release.set()
    with pytest.raises(PlatformMoveRejectedError) as exc_info:
        await move_task

    assert session.katrain.game.end_result is None
    assert _main_line(session) == []
    assert exc_info.value.reason == "position_changed"
```

这组用例没有 sleep、没有轮询：`entered` 保证测试一定卡在隧道里，`release` 决定回复什么时候到。

(d) 新建 `tests/platforms/test_engine_game_ledger.py`：

```python
"""星阵人机局收尾的三件事:AI 结束对局时如实终局(X9),终局之后不再能被接着下(X9),下完的每一盘进棋谱库(N13)。

接线照 `test_engine_move_guards.py`:`create_app()` 不跑 lifespan(真 Kivy 在非主线程初始化会崩),
会话用真 `WebSession` + MagicMock 的 katrain,gateway 用 MagicMock —— 这里测的是 server.py 里
**这几段分支本身**;gateway 的真行为在 test_engine_gateway.py / test_engine_integration.py,
端点一路到写库的真路径在 test_engine_game_ledger_e2e.py。
"""

import threading
from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient

from katrain.web.api.v1.endpoints.auth import get_current_user_optional
from katrain.web.models import User
from katrain.web.platforms.gateway import PlatformMoveRejectedError
from katrain.web.server import create_app
from katrain.web.session import WebSession

HUMAN = User(id=7, username="小明")


def _engine_session(end_result=None, human_color="B", engine=True):
    """星阵人机会话的形状:人坐一边,引擎那一边是合成 id `-1`,`user_id` 是人。

    `engine=False` 是 OGS 真人局:座位同形 `(人, -1)`,**`platform_engine_color` 故意不设**(留 MagicMock 默认值)——
    判别位若写成按真值判,用它的正对照当场红。"""
    katrain = MagicMock()
    katrain.game_type = "free"
    katrain.analysis_allowed = True
    katrain.get_state.return_value = {"end_result": end_result, "player_to_move": human_color, "history": []}
    katrain.game.end_result = end_result
    if engine:
        katrain.platform_engine_color = "W" if human_color == "B" else "B"  # 与 manager.start_engine_game 同一推法
    session = WebSession(session_id="eng-1", katrain=katrain, lock=threading.Lock())
    session.user_id = HUMAN.id
    session.player_b_id = HUMAN.id if human_color == "B" else -1
    session.player_w_id = HUMAN.id if human_color == "W" else -1
    return session


def _gateway(is_engine=True):
    gw = MagicMock()
    gw.is_platform_game.return_value = True
    gw.is_engine_game.return_value = is_engine
    gw.play_move = AsyncMock()
    gw.pass_move = AsyncMock()
    gw.resign = AsyncMock(return_value={"status": "ok"})
    return gw


def _app(session, gateway):
    app = create_app(enable_engine=False)
    app.state.session_manager._sessions[session.session_id] = session
    app.state.session_manager._schedule_broadcast = MagicMock()
    app.state.platform_gateway = gateway
    app.state.game_repo = MagicMock()
    app.dependency_overrides[get_current_user_optional] = lambda: HUMAN
    return app


def _client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class TestMoveWhenTheEngineEndsTheGame:
    async def test_game_ended_returns_the_ended_state_not_409(self):
        """这盘结束了 —— 这次请求不是失败。回 409 的话前端会说「AI 连接出错,请重试落子」,
        而重试只会因为「不是你的回合」继续失败。"""
        session = _engine_session(end_result="Void")
        gw = _gateway()
        gw.play_move.side_effect = PlatformMoveRejectedError("AI returned non-move coord 361", reason="game_ended")
        app = _app(session, gw)

        async with _client(app) as ac:
            r = await ac.post("/api/move", json={"session_id": session.session_id, "coords": [3, 3]})

        assert r.status_code == 200, r.text
        assert r.json()["state"]["end_result"] == "Void"
        assert session.last_state["end_result"] == "Void"

    async def test_other_rejections_are_still_409(self):
        """正对照:只有 game_ended 改成 200,隧道故障等照旧 409(前端靠它弹重试提示)。"""
        session = _engine_session()
        gw = _gateway()
        gw.play_move.side_effect = PlatformMoveRejectedError("tunnel down", reason="engine_error")
        app = _app(session, gw)

        async with _client(app) as ac:
            r = await ac.post("/api/move", json={"session_id": session.session_id, "coords": [3, 3]})

        assert r.status_code == 409
        assert r.json()["detail"] == "tunnel down"
```

- [ ] **Step 2: 跑，确认红**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && uv run pytest tests/platforms/test_engine_gateway.py tests/platforms/test_engine_integration.py tests/platforms/test_engine_game_ledger.py -q`
Expected: `6 failed, 16 passed`（审查时在 HEAD 原树实跑）：
- `test_engine_gateway.py::TestEnginePlayMove::test_engine_terminal_ends_game` —— `AssertionError: assert 'play' == 'end_without_result'`
- `test_engine_integration.py::test_ai_special_coord_ends_the_local_game_without_result` —— `AssertionError: assert None == 'Void'`
- `test_engine_integration.py::test_resign_during_the_tunnel_wait_stands_against_the_late_reply[ai_move]` —— `Failed: DID NOT RAISE <class 'katrain.web.platforms.gateway.PlatformMoveRejectedError'>`（局面复活）
- `…[ai_special_coord]` —— `AssertionError: assert None == 'W+R'`（人那一手接在了认输后面）
- `test_engine_integration.py::test_new_game_during_the_tunnel_wait_is_not_ended_by_the_late_terminal` —— `AssertionError: assert 'game_ended' == 'position_changed'`
- `test_engine_game_ledger.py::TestMoveWhenTheEngineEndsTheGame::test_game_ended_returns_the_ended_state_not_409` —— `AssertionError: {"detail":"AI returned non-move coord 361"}`（409）

`test_other_rejections_are_still_409` PASS（正对照）。

- [ ] **Step 3: `interface.py` 加命令**

`:1467-1469`

```python
    def _do_timeout(self):
        """End game due to timeout - current player loses on time"""
        self.game.current_node.end_state = f"{self.game.current_node.player}+T"
```

替换为

```python
    def _do_timeout(self):
        """End game due to timeout - current player loses on time"""
        self.game.current_node.end_state = f"{self.game.current_node.player}+T"

    def _do_end_without_result(self):
        """对局结束,不判胜负 —— SGF 的 `Void`。

        目前唯一的调用方是星阵人机局:AI 回了一个不是落点的坐标(停一手或认输;星阵这两种
        编码从没抓到过,`golaxy_to_katrain` 统一解成 UnknownSpecial),本地分不出是哪一种。
        记成「谁中盘胜」就是替它选了一个结果 ⇒ 记无胜负。`Game.end_result` 读的就是当前节点的
        `end_state`;`get_sgf` 只在结果带 `+` 时写 RE,存出来的谱不带 RE,与 SGF「无结果」一致。"""
        self.game.current_node.end_state = "Void"
```

- [ ] **Step 4: `gateway.py` —— 迟到回复闸 + AI 终局结束本地局**

(i) `:82-85`（`_check_move_legal` 收尾到 `class PlatformCommandGateway:`）

```python
    _check_moves_legal_sequence(game, [move])


class PlatformCommandGateway:
```

替换为

```python
    _check_moves_legal_sequence(game, [move])


def _submitted_position_status(session, game, node) -> str:
    """Is a tunnel reply still about the game it was asked about? Caller MUST hold `session.lock`.

    `game` / `node` are the Game object and its current node captured (under the same lock)
    before the tunnel call — the objects themselves, not `id()`: holding them keeps them alive,
    so an identity match can never be a recycled address.

    - "replaced": a different Game (new game / SGF load swap `session.katrain.game`) or a
      different node (an undo/nav that raced the pending guard). The reply is about a position
      that no longer exists here — apply nothing, end nothing.
    - "ended":    same Game, same node, but the node now carries a result — a resign landed
      while the tunnel waited. `_do_resign` writes `end_state` onto the SAME node, so node
      identity alone cannot see it. That result stands: no stones after it, no Void over it.
    - "live":     apply the reply.
    """
    current = session.katrain.game
    if current is not game or current.current_node is not node:
        return "replaced"
    if current.end_result:
        return "ended"
    return "live"


class PlatformCommandGateway:
```

(ii) `:170-175`（B1 注释，只改措辞）

```python
        # B1: pre-validate the human's move locally (occupied/ko/suicide) BEFORE
        # spending a ~180s tunnel call on a move that can never land. Also record
        # the current node's identity as a position token: the atomic-apply step
        # below re-checks this token so a tree mutation that races the tunnel wait
        # (B2 — undo/redo/nav bypassing the pending guard) can never make the AI's
        # reply land on the wrong node.
```

替换为

```python
        # B1: pre-validate the human's move locally (occupied/ko/suicide) BEFORE
        # spending a ~180s tunnel call on a move that can never land. Also record
        # the game and its current node (the objects) as the submitted position:
        # both apply steps below re-check it (`_submitted_position_status`) so a tree
        # mutation that races the tunnel wait (B2 — undo/redo/nav bypassing the
        # pending guard, a new game, a resign) can never make the AI's reply land on
        # the wrong node, reopen a resigned game, or end a newer one.
```

(iii) `:184`

```python
            position_token = id(game.current_node)
```

替换为

```python
            submitted_game, submitted_node = game, game.current_node
```

(iv) `:205-223`（`GolaxyEngineTerminal` 分支）

```python
        except GolaxyEngineTerminal as e:
            # D7: the human's move is real and final (the adapter committed it on its
            # side before raising) — play it locally BEFORE the terminal/game_ended
            # broadcast, so the local record doesn't miss the actual last move. Still
            # position-gated: if the tree moved out from under us during the tunnel
            # wait, discard rather than mis-apply it to the wrong node.
            try:
                with session.lock:
                    if id(session.katrain.game.current_node) == position_token:
                        self._local_play(session_id, col, row)
                    else:
                        logger.warning(
                            f"Engine terminal for session {session_id}: position changed "
                            "during tunnel wait, discarding human move instead of misapplying it"
                        )
            finally:
                ctx.clear_pending()
            self._broadcast_rejected(session_id, "game_ended")
            raise PlatformMoveRejectedError(str(e), reason="game_ended")
```

替换为

```python
        except GolaxyEngineTerminal as e:
            # D7: the human's move is real and final (the adapter committed it on its
            # side before raising) — play it locally BEFORE the terminal/game_ended
            # broadcast, so the local record doesn't miss the actual last move.
            # X9: the engine has ended this game on its side (the manager already dropped the
            # platform context via the adapter's game_ended). End the LOCAL game too, without a
            # result: an AI pass and an AI resign decode identically today, so any winner written
            # here would be a guess. Without this the board sat on "AI to move" forever.
            # Both writes are gated on the SUBMITTED game still being live: a resign during the
            # wait keeps its node (only `end_state` changes) and a new game swaps the Game object —
            # either way this reply is not about the game on the board now, and must neither
            # add a stone after a result, overwrite that result with Void, nor end a newer game.
            try:
                with session.lock:
                    status = _submitted_position_status(session, submitted_game, submitted_node)
                    if status == "live":
                        self._local_play(session_id, col, row)
                        session.katrain("end_without_result")
                    else:
                        logger.warning(
                            f"Engine terminal for session {session_id}: game {status} during tunnel wait, "
                            "leaving the local game untouched"
                        )
            finally:
                ctx.clear_pending()
            if status == "replaced":
                # Not "game_ended": /api/move and the vision path record the game on game_ended
                # (N13), and the game on the board now is not the one that ended.
                self._broadcast_rejected(session_id, "position_changed")
                raise PlatformMoveRejectedError(
                    "Position changed while waiting for the engine reply", reason="position_changed"
                )
            self._broadcast_rejected(session_id, "game_ended")
            raise PlatformMoveRejectedError(str(e), reason="game_ended")
```

(v) `:224-228`（普通隧道异常分支：超时 / 断网 / 隧道报错。计划审查第 2 轮 R2-2——上一版只给前后两个出口加了闸，这一支仍无条件回 `engine_error`）

```python
        except Exception as e:
            logger.error(f"Engine move failed: {e}")
            ctx.clear_pending()
            self._broadcast_rejected(session_id, "engine_error")
            raise PlatformMoveRejectedError(str(e), reason="engine_error")
```

替换为

```python
        except Exception as e:
            logger.error(f"Engine move failed: {e}")
            ctx.clear_pending()
            # Same submitted-position gate as the two branches around this one. A tunnel that fails only
            # AFTER the submitted game was resigned (the resign key stays lit through the whole wait, and a
            # stuck tunnel is exactly when people give up) is not a connection problem of any game on the
            # board: engine_error here would make /api/move answer 409 ("AI 连接出错") over the result card,
            # count toward the vision poller's recovery episode, and make the recovery dialog's retry mint a
            # new token for a game that is over.
            with session.lock:
                status = _submitted_position_status(session, submitted_game, submitted_node)
            if status == "ended":
                self._broadcast_rejected(session_id, "game_ended")
                raise PlatformMoveRejectedError("Game ended while waiting for the engine reply", reason="game_ended")
            if status == "replaced":
                self._broadcast_rejected(session_id, "position_changed")
                raise PlatformMoveRejectedError(
                    "Position changed while waiting for the engine reply", reason="position_changed"
                )
            self._broadcast_rejected(session_id, "engine_error")
            raise PlatformMoveRejectedError(str(e), reason="engine_error")
```

(vi) `:230-240`（成功分支的原子落子闸）

```python
        # Success: atomic apply of [human, AI] under a single lock hold, gated on the
        # position token recorded before the tunnel call. Assert failure is defensive
        # (should be unreachable once the server.py pending guards are in) — discard
        # BOTH moves rather than half-commit or mis-apply.
        try:
            with session.lock:
                if id(session.katrain.game.current_node) != position_token:
                    self._broadcast_rejected(session_id, "position_changed")
                    raise PlatformMoveRejectedError(
                        "Position changed while waiting for the engine reply", reason="position_changed"
                    )
```

替换为

```python
        # Success: atomic apply of [human, AI] under a single lock hold, gated on the
        # position submitted before the tunnel call. "replaced" is defensive (should be
        # unreachable once the server.py pending guards are in) — discard BOTH moves
        # rather than half-commit or mis-apply. "ended" is reachable: a resign during the
        # wait is not pending-guarded (the user must always be able to give up a stuck game).
        try:
            with session.lock:
                status = _submitted_position_status(session, submitted_game, submitted_node)
                if status == "ended":
                    # The resign's result stands: playing [human, AI] after it would silently
                    # reopen the game.
                    self._broadcast_rejected(session_id, "game_ended")
                    raise PlatformMoveRejectedError(
                        "Game ended while waiting for the engine reply", reason="game_ended"
                    )
                if status == "replaced":
                    self._broadcast_rejected(session_id, "position_changed")
                    raise PlatformMoveRejectedError(
                        "Position changed while waiting for the engine reply", reason="position_changed"
                    )
```

（其后 `self._local_play` 两手与 `except PlatformMoveRejectedError: raise` 不动。）

- [ ] **Step 5: `server.py` `/api/move`**

`:982-984`（⚠️ `except PlatformMoveRejectedError as e: raise HTTPException(status_code=409, …)` 这两行在 `server.py` 里**出现两次**：`:983` 是 `/api/move`，`:1892` 是 `/api/resign`。old_string 带上它上面那行 `return` 保证唯一；`/api/resign` 那处在 Task 5b 改）

```python
                    return {"session_id": session.session_id, "state": state}
            except PlatformMoveRejectedError as e:
                raise HTTPException(status_code=409, detail=str(e))
```

替换为

```python
                    return {"session_id": session.session_id, "state": state}
            except PlatformMoveRejectedError as e:
                if e.reason != "game_ended":
                    raise HTTPException(status_code=409, detail=str(e))
                # X9: 被提交的这盘已经结束 —— 要么星阵在它那边结束了它(AI 回了停一手或认输,人那一手已落下、
                # gateway 以无胜负结束了本地局),要么 tunnel 等待期间人已经认输(结果原样保留,这一手没落)。
                # 两种都不是失败,回终局态。回 409 的话前端会弹「AI 连接出错,请重试落子」—— 对一盘已结束的局是假话。
                # 等待期间换了局不会走到这里(gateway 抛 position_changed),所以下面读到的 end_result 恒是被提交那盘的。
                state = session.katrain.get_state()
                session.last_state = state
                return {"session_id": session.session_id, "state": state}
```

- [ ] **Step 6: 格式化、跑测试**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && uv run black -l 120 katrain/web/interface.py katrain/web/platforms/gateway.py katrain/web/server.py tests/platforms/test_engine_gateway.py tests/platforms/test_engine_integration.py tests/platforms/test_engine_game_ledger.py && git diff katrain/web/server.py | grep '^@@'
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && uv run pytest tests/platforms/test_engine_gateway.py tests/platforms/test_engine_integration.py tests/platforms/test_engine_game_ledger.py tests/test_vision_move_poller.py tests/test_engine_physical_integration.py tests/platforms/test_engine_rebuild.py tests/platforms/test_gateway.py -q
```
Expected:
- black 报 `1 file reformatted`：`server.py` 在基线上**本来就不是 black 干净的**，black 会顺带把 `:341-343` 的 `app.state.report_settlement_task = asyncio.create_task(` 三行并成一行。那一块不是本 Task 的改动、又在多赛道共享文件里 ⇒ 把它改回三行原样（`app.state.report_settlement_task = asyncio.create_task(` / `        _report_settlement_loop(session_factory)` / `    )`），再 `git diff katrain/web/server.py | grep '^@@'` 应只剩 `/api/move` 那一个 hunk。Task 5b / 6 跑 black 时同样处理。
- pytest `64 passed`（审查时实跑）。
- 这里不再带 `tests/platforms/test_engine_move_guards.py`：它在基线上本来就红 20 条（`_make_mock_session` 是 MagicMock，`session.user_id` 自动是 MagicMock ⇒ `guard_session_reader` 当它有主人 ⇒ 401），守的是本轮不改的 undo / redo / nav / ai-move 端点；它的名字集合由 Task 9 的全量闸比。不许顺手修那个夹具。

- [ ] **Step 7: 变异验证（不提交）**

逐条临时改、跑 Step 2 那条命令、还原（审查时逐条实跑，每条只红它对应的用例）：

| 变异 | 期望变红 |
|---|---|
| 删掉 `_submitted_position_status` 里 `if current.end_result: return "ended"` 两行 | `…[ai_move]` `DID NOT RAISE`；`…[ai_special_coord]` `assert 'Void' == 'W+R'` |
| 终局分支里把 `session.katrain("end_without_result")` 挪到 `if/else` 之后（即计划上一版的写法） | `…[ai_special_coord]` `assert 'Void' == 'W+R'`；`test_new_game_…` `assert 'Void' is None` |
| 终局分支里 `if status == "replaced":` 改成 `if False:` | `test_new_game_…` `assert 'game_ended' == 'position_changed'` |
| 成功分支里 `if status == "ended":` 改成 `if False:` | `…[ai_move]` `DID NOT RAISE` |
| `/api/move` 里 `if e.reason != "game_ended":` 改成 `if True:` | `test_game_ended_returns_the_ended_state_not_409` |

「比对象而不是比 `id()`」这一点变异测不出来（地址复用在测试里造不稳定），靠 docstring 写明理由。

- [ ] **Step 8: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && git add katrain/web/interface.py katrain/web/platforms/gateway.py katrain/web/server.py tests/platforms/test_engine_gateway.py tests/platforms/test_engine_integration.py tests/platforms/test_engine_game_ledger.py && git commit -m "$(cat <<'EOF'
fix(platforms): 星阵 AI 停手/认输时本地局如实结束;迟到的隧道回复不再改写另一盘棋

AI 回非落点坐标时 manager 摘掉了平台上下文,本地局却没有结果:屏上停在「轮到 AI」,
/api/move 一律 409 ⇒ 前端弹「AI 连接出错,请重试落子」,重试因「不是你的回合」继续失败。
星阵的停一手与认输编码没抓到、分不出是哪种 ⇒ 本地局以 SGF「无胜负」Void 结束
(新命令 end_without_result),/api/move 对 game_ended 回 200 + 终局态,其它 reason 仍 409。

隧道等待期间 gateway 不持锁,而旧的位置令牌只比 id(current_node):认输不换节点 ⇒ 迟到的回复
在认输节点后面接着下(复活)或把认输盖成 Void;等待期间换局 ⇒ 迟到的终局把新局结束。
改成锁内比「提交时的 Game 对象与节点对象」并看节点是否已有结果:live 才落子 / 结束;
ended(等待期间已认输)抛 game_ended、结果原样;replaced 抛 position_changed、一子不动。
新增 4 条可控异步真栈用例(认输 × 两种回复、换局、AI 终局),5 个变异各红一次。

EOF
)"
```

---

### Task 5b: X9-b / N13 / X10-a 后端 —— 星阵局结束之后就是终态：落子、停一手、再认输都不再落到本地树上

**为什么有这个 Task**（计划审查第 1 轮 F1 + 同形清扫）：星阵人机局一结束（认输或 AI 终局），`PlatformManager.end_platform_game` 就把平台上下文摘掉（`manager.py:283-289`；它是**唯一**摘上下文的地方，只由 adapter 的 `game_ended` 经 `_on_game_ended` 调用，`manager.py:348-354`）。从那一刻起，所有「上下文不在 ⇒ 这是本地局」的分支都把这盘当本地局接着下：
- 视觉入口 `server.py:3213` 判 `is_platform_game` 为假 ⇒ `:3240-3242` 本地 `play`。Task 8b 让编排器在终局时放掉恢复暂停、识别恢复——而「拿回棋子」等待态存在的前提就是那颗子还在盘上 ⇒ 它被再确认一次、长出新节点、`end_result` 回到 None，屏幕回到对局中，账本却已记了认输（审查时真栈实跑：主线 `[('B', (3, 3))]`、`end_result None`）。
- gateway 的 `play_move` / `pass_move` / `resign` 在 `ctx is None` 时直接走本地（`gateway.py:129-131`、`:281-283`、`:307-309`）⇒ 恢复框「重试」在别处已结束的局上静默复活它（实跑：响应 `{'ok': True}`、genmove 0 次）。
- `/api/move`（`server.py:970`）、`/api/resign`（`:1885`）按 `is_platform_game` 路由 ⇒ 终局后翻回一手再点盘会落进本地分支；上下文已摘后再认输（首个响应丢了重发、旧屏）走本地 `_do_resign` 改写结果、再 `record_multiplayer_game`——服务端多写一行没名字的 `play_human`（实跑：第二次认输后 `record_multiplayer_game` 调用数 1→2）。

修法只有一个判别位 + 一处 gateway 判断：「这曾是一盘星阵人机局」由建局时写下的 `session.katrain.platform_engine_color` 回答（`manager.py:180-190` 经 `edit_game` 写入；`_do_new_game` 清掉，`interface.py:670`；只有 manager 这一个写入者，`/api/edit-game` 的请求模型没有这个字段，`models.py:42-48`）。上下文不在而它还在 ⇒ 这盘已经结束 ⇒ gateway 抛 `game_ended`；server 三个入口的路由认「上下文在，或者是星阵会话」⇒ 仍交给 gateway。视觉入口拿到 `game_ended` 走既有的 `_apply_engine_recovery_outcome` → `engine_recovery.py:107-109`：清 episode、**不重新 arm**（worker 确认时已把残子并进基线；再推期望盘面会让它每 3 帧再确认一次）。

**Files:**
- Modify: `katrain/web/platforms/gateway.py`（Task 5 之后的行号）`:103-108`（`_submitted_position_status` 之后新增模块级 `is_platform_engine_session`）、`:148-154`（`is_engine_move_pending` 之后新增 `_is_ended_engine_game`，`play_move` 的 `ctx is None` 分支）、`:329-331`（`pass_move`）、`:355-357`（`resign`）
- Modify: `katrain/web/server.py`（Task 5 之后的行号）`:968-973`（`/api/move` 路由）、`:1891-1901`（`/api/resign` 路由 + 已结束时幂等）、`:3160-3161`（`_handle_confirmed_move` 的 import）、`:3221-3222`（视觉入口路由）
- Test: `tests/platforms/test_engine_gateway.py`、`tests/platforms/test_engine_integration.py`、`tests/platforms/test_engine_game_ledger.py`、`tests/test_vision_move_poller.py`（各在文件末追加）

**Interfaces:**
- Consumes: Task 5 的 `/api/move` game_ended→200 分支与 `test_engine_game_ledger.py` 夹具；测试文件既有的 `setup` fixture（`test_engine_gateway.py`，产出 `(gateway, pm, sm, adapter, ctx, session)`，会话 id `"s"`、远端局 id `"g"`）、`FakeSession` / `FakeGateway(is_platform=…, outcomes=…)` / `FakeVision` / `_app` / `_move`（`test_vision_move_poller.py`）。
- Produces:
  - `katrain.web.platforms.gateway.is_platform_engine_session(session) -> bool`：`platform_engine_color in ("B", "W")`。星阵人机局的**唯一**判别位（Task 6 落账、prd §6.0 第 1 条合并后对弈·AI 的 `_finish_ended_game` 都认它）。
  - gateway 契约：星阵会话（判别位为真）而上下文不在 ⇒ `play_move` / `pass_move` / `resign` 抛 `PlatformMoveRejectedError(reason="game_ended")`，本地树不动；判别位为假的会话照旧本地（OGS / 本地局不受影响）。
  - `POST /api/resign` 契约：星阵局已结束时再认输回 **200** + 当前局面，不改结果、不落账、不广播 `game_end`。
  - `_handle_confirmed_move` 契约：星阵会话一律交给 gateway；已结束 ⇒ 不落子、不重新 arm、返回 `0.0`。

- [ ] **Step 1: 写测试（先红）**

(a) `tests/platforms/test_engine_gateway.py` 文件末尾追加（`SimpleNamespace`、`MagicMock`、`PlatformMoveRejectedError` 文件里已 import）：

```python
class TestEngineSessionAfterItsContextIsGone:
    """X9 / N13(plan 审查第 1 轮):星阵人机局一结束,manager 就摘掉平台上下文(`end_platform_game` 是唯一摘它的
    地方,只由 adapter 的 `game_ended` 触发)。之后 `ctx is None` 不再意味着「这是本地局」—— 建局时写在会话上的
    `platform_engine_color` 还在。落子 / 停一手 / 认输都不许再落到本地树上。"""

    @staticmethod
    def _ended(setup, engine_color="W"):
        gateway, pm, sm, adapter, ctx, session = setup
        pm._session_to_game.pop("s")
        pm._active_games.pop("g")
        session.katrain.platform_engine_color = engine_color
        return gateway, adapter, session

    @pytest.mark.asyncio
    async def test_play_move_is_rejected_as_game_ended(self, setup):
        gateway, adapter, session = self._ended(setup)

        with pytest.raises(PlatformMoveRejectedError) as exc_info:
            await gateway.play_move("s", 3, 3, user_id=1)

        assert exc_info.value.reason == "game_ended"
        assert session.katrain_calls == []
        adapter.submit_engine_move.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_pass_is_rejected_as_game_ended(self, setup):
        gateway, adapter, session = self._ended(setup)

        with pytest.raises(PlatformMoveRejectedError) as exc_info:
            await gateway.pass_move("s", user_id=1)

        assert exc_info.value.reason == "game_ended"
        assert session.katrain_calls == []

    @pytest.mark.asyncio
    async def test_resign_is_rejected_as_game_ended_and_leaves_the_result_alone(self, setup):
        gateway, adapter, session = self._ended(setup)

        with pytest.raises(PlatformMoveRejectedError) as exc_info:
            await gateway.resign("s", user_id=1)

        assert exc_info.value.reason == "game_ended"
        assert session.resigned is False
        adapter.resign_engine_game.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_session_that_never_was_an_engine_game_still_plays_locally(self, setup):
        """正对照:没有 `platform_engine_color` 的会话照旧本地落子 —— 判别位认的是「建局时写下的颜色」,
        不是「经过了 gateway」。"""
        gateway, adapter, session = self._ended(setup, engine_color=None)

        await gateway.play_move("s", 3, 3, user_id=1)

        assert session.moves == [(3, 3)]


@pytest.mark.parametrize("value, expected", [("B", True), ("W", True), (None, False), (MagicMock(), False)])
def test_is_platform_engine_session_accepts_only_a_colour(value, expected):
    """MagicMock 那一格守的是「按真值判」:测试里的 katrain 大多是 MagicMock,属性恒为真值。"""
    from katrain.web.platforms.gateway import is_platform_engine_session

    session = SimpleNamespace(katrain=SimpleNamespace(platform_engine_color=value))
    assert is_platform_engine_session(session) is expected
```

(b) `tests/platforms/test_engine_integration.py` 文件末尾追加：

```python
@pytest.mark.asyncio
async def test_an_ended_engine_game_cannot_be_played_on_or_resigned_again():
    """X9 / N13(plan 审查第 1 轮):认输之后平台上下文被摘掉。之后再到 gateway 的落子(视觉路径、恢复框重试、
    终局后翻回一手再点盘)与再一次认输(首个响应丢了重发、旧屏)不许把局当本地局接着下,也不许改写结果。"""
    from katrain.web.platforms.gateway import PlatformMoveRejectedError

    sm, pm, gateway, adapter = _build_stack(genmove_return=_genmove_for(15, 3))
    pm._setup_callbacks(adapter)
    session_id = await pm.start_engine_game("golaxy", EngineGameConfig(level=1100, human_color="B"), user_id=1)
    session = sm.get_session(session_id)
    await gateway.resign(session_id, user_id=1)
    resigned = session.katrain.game.end_result
    assert resigned and not pm.is_platform_game(session_id)

    with pytest.raises(PlatformMoveRejectedError) as move_exc:
        await gateway.play_move(session_id, 4, 4, user_id=1)
    with pytest.raises(PlatformMoveRejectedError) as resign_exc:
        await gateway.resign(session_id, user_id=1)

    assert (move_exc.value.reason, resign_exc.value.reason) == ("game_ended", "game_ended")
    assert _main_line(session) == []
    assert session.katrain.game.end_result == resigned
    adapter._rest.engine_genmove.assert_not_awaited()
```

(c) `tests/platforms/test_engine_game_ledger.py` 文件末尾追加：

```python
class TestAfterTheEngineGameEnded:
    """X9 / N13(plan 审查第 1 轮):终局时 manager 摘掉了平台上下文(gateway 的 `is_platform_game` 变假)。
    路由认建局时写下的 `platform_engine_color`:仍交给 gateway(它判「已经结束」),不落进下面的本地分支 ——
    本地落子会把结束了的局接着下;本地认输会改写结果、再走 `record_multiplayer_game`(服务端再写一行没名字的 play_human)。"""

    async def test_a_move_still_goes_to_the_gateway_and_gets_the_ended_state(self):
        session = _engine_session(end_result="W+R")
        gw = _gateway()
        gw.is_platform_game.return_value = False
        gw.play_move.side_effect = PlatformMoveRejectedError("This engine game has already ended", reason="game_ended")
        app = _app(session, gw)

        async with _client(app) as ac:
            r = await ac.post("/api/move", json={"session_id": session.session_id, "coords": [3, 3]})

        assert r.status_code == 200, r.text
        gw.play_move.assert_awaited_once()
        assert [c.args[0] for c in session.katrain.call_args_list] == []

    async def test_resigning_again_changes_nothing_and_records_nothing(self):
        session = _engine_session(end_result="W+R")
        gw = _gateway()
        gw.is_platform_game.return_value = False
        gw.resign.side_effect = PlatformMoveRejectedError("This engine game has already ended", reason="game_ended")
        app = _app(session, gw)

        async with _client(app) as ac:
            r = await ac.post("/api/resign", json={"session_id": session.session_id})

        assert r.status_code == 200, r.text
        assert r.json()["state"]["end_result"] == "W+R"
        gw.resign.assert_awaited_once()
        assert [c.args[0] for c in session.katrain.call_args_list] == []
        app.state.game_repo.record_multiplayer_game.assert_not_called()
        assert app.state.session_manager._schedule_broadcast.call_args_list == []
```

(d) `tests/test_vision_move_poller.py` 文件末尾追加：

```python
class TestEngineGameWhoseContextIsGone:
    """X9 / X10(plan 审查第 1 轮):星阵人机局终局时 manager 摘掉了平台上下文(`is_platform_game` 变假)。之后识别
    再确认出来的子 —— 最典型的是恢复框「拿回棋子」等待态里认输后盘上那颗没拿走的子,Task 8b 放掉暂停后识别恢复 ——
    仍要交给 gateway 判「这盘已经结束」;掉进本地分支就是在终局节点下面接着下(屏回到对局中,账本已记这盘)。"""

    def test_a_move_after_the_engine_game_ended_goes_to_the_gateway_not_the_local_tree(self):
        session = FakeSession(player_to_move="B")
        session.katrain.platform_engine_color = "W"
        gateway = FakeGateway(is_platform=False, outcomes=[PlatformMoveRejectedError("over", reason="game_ended")])
        vision = FakeVision()
        app = _app(FakeSessionManager({"s1": session}), gateway=gateway, tracker=EngineRecoveryTracker())

        delay = asyncio.run(_handle_confirmed_move(app, vision, "s1", _move(color=BLACK), log))

        assert gateway.calls == [("s1", 3, 15)]
        assert session.katrain.plays == []
        assert vision.expected_pushes == []  # 不重新 arm:worker 确认时已把这颗子并进基线
        assert delay == 0.0
```

- [ ] **Step 2: 跑，确认红**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && uv run pytest tests/platforms/test_engine_gateway.py tests/platforms/test_engine_integration.py tests/platforms/test_engine_game_ledger.py tests/test_vision_move_poller.py -q`
Expected: `11 failed, 36 passed`（审查时在 Task 5 之后的树上实跑）：
- `TestEngineSessionAfterItsContextIsGone` 的 `test_play_move_is_rejected_as_game_ended`、`test_pass_is_rejected_as_game_ended`、`test_resign_is_rejected_as_game_ended_and_leaves_the_result_alone` —— 各 `Failed: DID NOT RAISE <class 'katrain.web.platforms.gateway.PlatformMoveRejectedError'>`
- `test_is_platform_engine_session_accepts_only_a_colour` 4 格 —— `ImportError: cannot import name 'is_platform_engine_session' from 'katrain.web.platforms.gateway'`
- `test_engine_integration.py::test_an_ended_engine_game_cannot_be_played_on_or_resigned_again` —— `Failed: DID NOT RAISE …`
- `TestAfterTheEngineGameEnded::test_a_move_still_goes_to_the_gateway_and_gets_the_ended_state` —— `AssertionError: Expected play_move to have been awaited once. Awaited 0 times.`
- `TestAfterTheEngineGameEnded::test_resigning_again_changes_nothing_and_records_nothing` —— `AssertionError: Expected resign to have been awaited once. Awaited 0 times.`
- `TestEngineGameWhoseContextIsGone::test_a_move_after_the_engine_game_ended_goes_to_the_gateway_not_the_local_tree` —— `AssertionError: assert [] == [('s1', 3, 15)]`

正对照 `test_a_session_that_never_was_an_engine_game_still_plays_locally` PASS。

- [ ] **Step 3: `gateway.py`**

(i) `:103-108`

```python
    if current.end_result:
        return "ended"
    return "live"


class PlatformCommandGateway:
```

替换为

```python
    if current.end_result:
        return "ended"
    return "live"


def is_platform_engine_session(session) -> bool:
    """星阵人机局(引擎在对面)的**唯一**判别位 —— 本赛道的路由与落账、对弈·AI 的 `_finish_ended_game` 都认它
    (prd §6.0 第 1 条)。

    `PlatformManager.start_engine_game` 建局时经 `edit_game` 写在 `session.katrain.platform_engine_color` 上;
    平台上下文被摘掉之后它还在(`end_platform_game` 只清 manager 自己的两张表),`_do_new_game` 清掉。
    **不许**换成 `is_engine_game` / `is_platform_game`:终局那一刻 adapter 的 `game_ended` 已经让 manager 摘掉了上下文。
    **不许**换成 `player_*_id == -1`:OGS 真人局同形。**不许**按真值判:测试里的 MagicMock katrain 属性恒为真值。"""
    return getattr(getattr(session, "katrain", None), "platform_engine_color", None) in ("B", "W")


class PlatformCommandGateway:
```

(ii) `:148-154`

```python
        ctx = self._pm.get_game_context(session_id)
        return bool(ctx and ctx.is_engine and ctx.is_pending)

    async def play_move(self, session_id: str, col: int, row: int, user_id: int) -> dict:
        ctx = self._pm.get_game_context(session_id)
        if ctx is None:
            return self._local_play(session_id, col, row)
```

替换为

```python
        ctx = self._pm.get_game_context(session_id)
        return bool(ctx and ctx.is_engine and ctx.is_pending)

    def _is_ended_engine_game(self, session_id: str) -> bool:
        """Called only when the platform context is gone. For an engine session that means the game is
        over: `PlatformManager.end_platform_game` is the only thing that drops a context and only the
        adapter's `game_ended` (AI special coord / resign) calls it. From then on the session must not
        be treated as a local game — a move would grow a node under the result, a resign would overwrite
        it (X9 / N13, plan review round 1)."""
        try:
            session = self._sm.get_session(session_id)
        except KeyError:
            return False
        return is_platform_engine_session(session)

    async def play_move(self, session_id: str, col: int, row: int, user_id: int) -> dict:
        ctx = self._pm.get_game_context(session_id)
        if ctx is None:
            if self._is_ended_engine_game(session_id):
                raise PlatformMoveRejectedError("This engine game has already ended", reason="game_ended")
            return self._local_play(session_id, col, row)
```

(iii) `pass_move`（`:329-331`）

```python
        ctx = self._pm.get_game_context(session_id)
        if ctx is None:
            return self._local_pass(session_id)
```

替换为

```python
        ctx = self._pm.get_game_context(session_id)
        if ctx is None:
            if self._is_ended_engine_game(session_id):
                raise PlatformMoveRejectedError("This engine game has already ended", reason="game_ended")
            return self._local_pass(session_id)
```

(iv) `resign`（`:355-357`）

```python
        ctx = self._pm.get_game_context(session_id)
        if ctx is None:
            return self._local_resign(session_id)
```

替换为

```python
        ctx = self._pm.get_game_context(session_id)
        if ctx is None:
            if self._is_ended_engine_game(session_id):
                raise PlatformMoveRejectedError("This engine game has already ended", reason="game_ended")
            return self._local_resign(session_id)
```

- [ ] **Step 4: `server.py` 三个入口的路由**

(i) `/api/move`（`:968-973`）

```python
        # Route through platform gateway for cross-platform games
        gateway = getattr(app.state, "platform_gateway", None)
        if gateway and gateway.is_platform_game(request.session_id):
            from katrain.web.platforms.gateway import PlatformMoveRejectedError

            try:
```

替换为

```python
        # Route through platform gateway for cross-platform games
        gateway = getattr(app.state, "platform_gateway", None)
        from katrain.web.platforms.gateway import PlatformMoveRejectedError, is_platform_engine_session

        # 星阵人机局终局时平台上下文被摘掉(`is_platform_game` 变假),它仍是星阵局 —— 仍交给 gateway 判「已经结束」;
        # 否则终局后的落子(翻回一手再点盘、识别确认卡)会掉进下面的本地分支,把结束了的局接着下。
        if gateway and (gateway.is_platform_game(request.session_id) or is_platform_engine_session(session)):
            try:
```

(ii) `/api/resign`（`:1891-1901`）

```python
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
```

替换为

```python
        # Route through platform gateway for cross-platform games
        gateway = getattr(app.state, "platform_gateway", None)
        from katrain.web.platforms.gateway import PlatformMoveRejectedError, is_platform_engine_session

        # 星阵人机局终局后平台上下文已被摘掉,仍交给 gateway(它判「已经结束」)—— 落进下面的本地认输会改写已有的结果,
        # 再走 `record_multiplayer_game`(服务端多写一行没名字的 play_human)。
        platform_game = bool(
            not ranked_ai
            and gateway
            and (gateway.is_platform_game(request.session_id) or is_platform_engine_session(session))
        )
        if platform_game:
            try:
                user_id = current_user.id if current_user else 0
                await gateway.resign(request.session_id, user_id)
            except PlatformMoveRejectedError as e:
                if e.reason != "game_ended":
                    raise HTTPException(status_code=409, detail=str(e))
                # 这盘早就结束了:认输幂等 —— 不改结果、不落账、不广播 game_end,回当前局面。
                # 不回 409:「退出 → 认输并退出」遇错就不退出,用户会被困在一盘已经结束的局里。
                state = session.katrain.get_state()
                session.last_state = state
                return {"session_id": session.session_id, "state": state}
```

（其后「`is_multiplayer` / `if not platform_game:` / 落账 / `game_end` 广播」都不动：已结束时上面直接 return 了，走不到它们。）

(iii) `_handle_confirmed_move` 开头的 import（`:3160-3161`）

```python
    from katrain.vision.katrain_bridge import vision_move_to_katrain
    from katrain.web.platforms.gateway import PlatformMoveRejectedError
```

替换为

```python
    from katrain.vision.katrain_bridge import vision_move_to_katrain
    from katrain.web.platforms.gateway import PlatformMoveRejectedError, is_platform_engine_session
```

(iv) 视觉入口路由（`:3221-3222`）

```python
    if gateway and gateway.is_platform_game(session_id):
        game_id = gateway.get_game_id(session_id) or ""
```

替换为

```python
    # 星阵人机局终局后平台上下文已被摘掉,仍交给 gateway 判「已经结束」(X9 / X10,plan 审查第 1 轮):盘上没拿走的子
    # 在识别恢复后会被再确认一次,掉进下面的本地分支就是在终局节点下面接着下。gateway 回 game_ended ⇒ 不重新 arm。
    if gateway and (gateway.is_platform_game(session_id) or is_platform_engine_session(session)):
        game_id = gateway.get_game_id(session_id) or ""
```

- [ ] **Step 5: 格式化、跑测试**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && uv run black -l 120 katrain/web/platforms/gateway.py katrain/web/server.py tests/platforms/test_engine_gateway.py tests/platforms/test_engine_integration.py tests/platforms/test_engine_game_ledger.py tests/test_vision_move_poller.py
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && uv run pytest tests/platforms/test_engine_gateway.py tests/platforms/test_engine_integration.py tests/platforms/test_engine_game_ledger.py tests/test_vision_move_poller.py tests/test_engine_physical_integration.py tests/test_vision_engine_move_recovery_endpoints.py tests/platforms/test_gateway.py -q
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && uv run pytest tests/web_ui/test_game_termination_and_chat_identity.py -q
```
Expected: black 顺带改到的 `:341-343` 那一块照 Task 5 Step 6 改回；第一条 pytest `81 passed`，第二条 `16 passed`（审查时实跑；第二条守的是既有的认输广播与终止身份，确认 `/api/resign` 路由改动没把它改坏）。

- [ ] **Step 6: 变异验证（不提交）**

逐条临时改、跑 Step 2 那条命令、还原（审查时逐条实跑）：

| 变异 | 期望变红 |
|---|---|
| `is_platform_engine_session` 改成 `return bool(getattr(…, "platform_engine_color", None))`（按真值判） | `test_is_platform_engine_session_accepts_only_a_colour[value3-False]`（MagicMock 那一格）`assert True is False` |
| `play_move` 里 `if self._is_ended_engine_game(session_id):` 改成 `if False:` | `test_play_move_is_rejected_as_game_ended`、`test_an_ended_engine_game_cannot_be_played_on_or_resigned_again` |
| `/api/move` 路由退回 `if gateway and gateway.is_platform_game(request.session_id):` | `test_a_move_still_goes_to_the_gateway_and_gets_the_ended_state` |
| `/api/resign` 路由退回只判 `gateway.is_platform_game(request.session_id)` | `test_resigning_again_changes_nothing_and_records_nothing`（`resign` 未被 await） |
| 视觉入口路由退回 `if gateway and gateway.is_platform_game(session_id):` | `test_a_move_after_the_engine_game_ended_goes_to_the_gateway_not_the_local_tree`（Task 8b 之后 Case 7 真栈用例也红，见 8b Step 6） |
| `/api/resign` 里 `if e.reason != "game_ended":` 改成 `if True:` | `test_resigning_again_changes_nothing_and_records_nothing`（`{"detail":"This engine game has already ended"}`） |

- [ ] **Step 7: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && git add katrain/web/platforms/gateway.py katrain/web/server.py tests/platforms/test_engine_gateway.py tests/platforms/test_engine_integration.py tests/platforms/test_engine_game_ledger.py tests/test_vision_move_poller.py && git commit -m "$(cat <<'EOF'
fix(platforms): 星阵局结束后不再被当成本地局接着下 —— 残子复活、再认输改写结果并多写一行账

星阵局一结束 manager 就摘掉平台上下文,而 gateway 与 server 三个入口都按「上下文不在 ⇒ 本地局」分支:
识别恢复后盘上没拿走的子会在终局节点下面长出新节点(屏回到对局中,账本已记这盘);
恢复框重试在别处已结束的局上静默落子;上下文已摘后再认输走本地 _do_resign 改写结果,
服务端再 record_multiplayer_game 多写一行 play_human。
判别位改认建局时写下的 platform_engine_color(is_platform_engine_session,不认上下文、不认 -1 座位、不按真值判):
星阵会话而上下文不在 ⇒ gateway 抛 game_ended;/api/move、/api/resign、视觉入口按判别位仍交给 gateway;
再认输幂等回 200,视觉入口不重新 arm。OGS / 本地局不受影响(正对照)。

EOF
)"
```

---

### Task 6: N13 后端 —— 星阵人机局在四条终局路上落账到 `user_games`

**Files:**
- Modify: `katrain/web/server.py`（Task 5b 之后的行号；括号里是 HEAD 行号）`:1609`（`_record_ai_game_locked` 签名；HEAD `:1599`）、`:1684-1688`（`data` 构造之后合并 overrides；HEAD `:1674-1678`）、`:1874-1880`（`_record_ai_game`；HEAD `:1864-1870`）、`:1948-1960`（`/api/resign` 落账分支；HEAD `:1926-1938`）、`:992-996`（Task 5 加的 `/api/move` game_ended 分支补一行落账）、`:3129` 之前（新增模块级 `_session_owner` / `_record_platform_engine_game` / `_record_platform_engine_game_off_request`；HEAD `:3107`）、`:3241-3244`（`_handle_confirmed_move` 的 `except PlatformMoveRejectedError`；HEAD `:3217-3220`）
- Modify: `katrain/web/api/v1/endpoints/vision.py:346-348`（`retry_engine_move` docstring）、`:359-360`（`except Exception`）
- Test: `tests/platforms/test_engine_game_ledger.py`（import 段 + 文件末追加）
- Create: `tests/platforms/test_engine_game_ledger_e2e.py`（`git ls-files` 无同名、`git check-ignore` 不吞；**prd §6.0 第 1 条的合并验收就是这个文件**）
- Test: `tests/test_vision_move_poller.py`、`tests/test_vision_engine_move_recovery_endpoints.py`（各在文件末追加一个 class）

**Interfaces:**
- Consumes: Task 5 的 `end_without_result` 与 `/api/move` game_ended 分支；Task 5b 的 `is_platform_engine_session` 与三处路由（再认输已在路由层幂等返回，走不到落账）；`test_engine_game_ledger.py` 的夹具；`app.state.user_repo.get_user_by_id(user_id) -> dict | None`（`core/auth.py:219`）；`User`（`katrain/web/models.py:176`，`server.py:34` 已 `import *`）；恢复端点测试文件既有的 `_tripped_tracker`、`FakeGateway`、`_build_app`、`_client`（`app.state.physical_play` 是记录 `entered_error` / `cleared_error` 的替身）。
- Produces:
  - `_record_ai_game(session, app, current_user, result, data_overrides: dict | None = None)`（闭包，经 `server._RECORD_FN` 暴露）：`data_overrides` 在**非升降级**局里合进写库的 `data`。
  - 模块级 `def _session_owner(app, session) -> User | None`：`User(**user_repo.get_user_by_id(session.user_id))`，查不到返回 None（与对弈·AI 的 `_on_game_ended_off_request` 同一种解析，prd §6.0 第 1 条合并后只留这一个）。
  - 模块级 `async def _record_platform_engine_game(session, app, user) -> None`：**参数顺序与对弈·AI 的 `_finish_ended_game(session, app, current_user)` 相同**（合并时只改名）；自带判别位闸——不是星阵人机局、`user` 为 None、`end_result` 为空时不写；否则调 `_RECORD_FN(session, app, user, result, data_overrides={"source": "play_ai", "player_black": …, "player_white": …})`，人那一方（`platform_engine_color` 的对面）写 `user.username`。
  - 模块级 `async def _record_platform_engine_game_off_request(session, app) -> None`：没有 HTTP 请求的两条路（视觉 poller、恢复框重试）**只许**经它落账，它认会话主人。合并时只改它的函数体。
  - `POST /api/v1/vision/engine-move/retry` 契约：gateway 抛 `game_ended` ⇒ 不 `trip_now`、`orchestrator.clear_engine_error()`、经 off-request helper 落账、回 `{"ok": true, "game_ended": true}`（弹层按既有 `ok: true` 关闭，前端不改）；其它失败照旧 `ok: false` + 新令牌。

四条终局路：① `/api/resign` 星阵局（用户认输）；② `/api/move` 遇 `game_ended`（AI 在这一手之后结束、或等待期间已认输）；③ 视觉 poller 遇 `game_ended`（实体盘上这一手之后 AI 结束 / 这盘早已结束）；④ 恢复框「重试」遇 `game_ended`（`vision.py:358` 直接 `await gateway.play_move`，不经 `/api/move` 与 poller——上一版计划漏了它：端点把 `game_ended` 当隧道故障，`trip_now` 发新令牌、弹层继续写「星阵连接出错」、这盘不落账，审查时实跑复现）。同一局重复到这里由 `_record_ai_game` 的 `_recorded` 标记 + `record_game_lock` 挡住（`server.py:1603-1608`、`:1839`）。

- [ ] **Step 1: 写测试（先红）**

(a) `tests/platforms/test_engine_game_ledger.py` 的 import 段

```python
import threading
from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient

from katrain.web.api.v1.endpoints.auth import get_current_user_optional
```

替换为

```python
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient

import katrain.web.server as server
from katrain.web.api.v1.endpoints.auth import get_current_user_optional
```

文件末尾追加：

```python
class TestMoveLedger:
    async def test_ai_terminal_move_is_recorded_for_the_requesting_user(self, monkeypatch):
        session = _engine_session(end_result="Void")
        gw = _gateway()
        gw.play_move.side_effect = PlatformMoveRejectedError("AI returned non-move coord 361", reason="game_ended")
        app = _app(session, gw)
        recorder = AsyncMock()
        monkeypatch.setattr(server, "_record_platform_engine_game", recorder)

        async with _client(app) as ac:
            r = await ac.post("/api/move", json={"session_id": session.session_id, "coords": [3, 3]})

        assert r.status_code == 200, r.text
        recorder.assert_awaited_once()
        assert recorder.await_args.args[0] is session
        assert recorder.await_args.args[2].id == HUMAN.id


class TestResignLedger:
    async def test_engine_resign_goes_through_the_ai_game_ledger(self, monkeypatch):
        """N13:星阵人机局只有一个 KaTrain 用户、对手是外部引擎 —— 走人机局那条两种部署都通的落账路。
        原来的 `record_multiplayer_game` 在盒上一次都没写进去过(`game_repo` 恒为 None),
        在服务端写进去的是一局没名字的 `play_human`。"""
        session = _engine_session(end_result="W+R")
        gw = _gateway(is_engine=True)

        async def _resign_drops_context(*_args, **_kwargs):
            # 真 gateway.resign 会经 adapter → manager 摘掉平台上下文 ⇒ 之后再问上下文就不是引擎局了。
            # 判别位不许取自上下文;这一行让取自上下文的实现当场红。
            gw.is_engine_game.return_value = False
            gw.is_platform_game.return_value = False
            return {"status": "ok"}

        gw.resign.side_effect = _resign_drops_context
        app = _app(session, gw)
        recorder = AsyncMock()
        monkeypatch.setattr(server, "_record_platform_engine_game", recorder)

        async with _client(app) as ac:
            r = await ac.post("/api/resign", json={"session_id": session.session_id})

        assert r.status_code == 200, r.text
        recorder.assert_awaited_once()
        assert recorder.await_args.args[0] is session
        assert recorder.await_args.args[2].id == HUMAN.id
        app.state.game_repo.record_multiplayer_game.assert_not_called()
        sent = [call.args[1] for call in app.state.session_manager._schedule_broadcast.call_args_list]
        assert any(m.get("type") == "game_end" for m in sent), "引擎局认输也要照旧广播 game_end"

    async def test_non_engine_platform_resign_still_uses_the_multiplayer_repo(self, monkeypatch):
        """正对照:OGS 这类真人平台局(座位同形 `(人, -1)`,但没有 `platform_engine_color`)不改路。"""
        session = _engine_session(end_result="W+R", engine=False)
        app = _app(session, _gateway(is_engine=False))
        recorder = AsyncMock()
        monkeypatch.setattr(server, "_record_platform_engine_game", recorder)

        async with _client(app) as ac:
            r = await ac.post("/api/resign", json={"session_id": session.session_id})

        assert r.status_code == 200, r.text
        recorder.assert_not_awaited()
        app.state.game_repo.record_multiplayer_game.assert_called_once()


class TestRecordPlatformEngineGame:
    @staticmethod
    def _session(end_result, human_color="B", engine=True):
        session = _engine_session(end_result=end_result, human_color=human_color, engine=engine)
        me = SimpleNamespace(name="Me", human=False, ai=False, calculated_rank=None, sgf_rank=None)
        bot = SimpleNamespace(name="[golaxy] 星铠虾", human=False, ai=False, calculated_rank="2段", sgf_rank=None)
        session.katrain.players_info = {"B": me, "W": bot} if human_color == "B" else {"B": bot, "W": me}
        return session

    async def test_human_seat_gets_the_account_name_and_source_is_play_ai(self, monkeypatch):
        """会话上人那一方叫占位的 "Me";复盘列表认「你是哪一方」靠的正是存进去的名字。"""
        record = AsyncMock()
        monkeypatch.setattr(server, "_RECORD_FN", record, raising=False)
        session, app = self._session("W+R"), MagicMock()

        await server._record_platform_engine_game(session, app, HUMAN)

        record.assert_awaited_once()
        assert record.await_args.args == (session, app, HUMAN, "W+R")
        assert record.await_args.kwargs["data_overrides"] == {
            "source": "play_ai",
            "player_black": "小明",
            "player_white": "[golaxy] 星铠虾",
        }

    async def test_human_on_white_gets_the_name_on_white(self, monkeypatch):
        record = AsyncMock()
        monkeypatch.setattr(server, "_RECORD_FN", record, raising=False)

        await server._record_platform_engine_game(self._session("B+R", human_color="W"), MagicMock(), HUMAN)

        overrides = record.await_args.kwargs["data_overrides"]
        assert (overrides["player_black"], overrides["player_white"]) == ("[golaxy] 星铠虾", "小明")

    async def test_nothing_is_written_without_a_result_or_a_user(self, monkeypatch):
        record = AsyncMock()
        monkeypatch.setattr(server, "_RECORD_FN", record, raising=False)

        await server._record_platform_engine_game(self._session(None), MagicMock(), HUMAN)
        await server._record_platform_engine_game(self._session("W+R"), MagicMock(), None)

        record.assert_not_awaited()

    async def test_a_non_engine_platform_session_is_not_written(self, monkeypatch):
        """OGS 真人局落到这里(比如将来有人在别处复用它)也不许写成人机局 —— helper 自己判,不靠调用点。"""
        record = AsyncMock()
        monkeypatch.setattr(server, "_RECORD_FN", record, raising=False)

        await server._record_platform_engine_game(self._session("W+R", engine=False), MagicMock(), HUMAN)

        record.assert_not_awaited()

    async def test_the_real_record_fn_writes_the_overrides_into_the_row(self):
        """不 mock `_RECORD_FN`:overrides 真的进了盒上那条 `repository_dispatcher.user_games_create` 的 data。"""
        create_app(enable_engine=False)  # `_RECORD_FN` 由 create_app 填上
        session = self._session("Void")
        session.katrain.get_sgf.return_value = "(;GM[1])"
        session.katrain.get_state.return_value = {
            "board_size": [19, 19],
            "history": [1, 2],
            "komi": 7.5,
            "ruleset": "chinese",
        }
        app = MagicMock()
        app.state.repository_dispatcher.user_games_create = AsyncMock(return_value={"id": "g1"})

        await server._record_platform_engine_game(session, app, HUMAN)

        app.state.repository_dispatcher.user_games_create.assert_awaited_once()
        kwargs = app.state.repository_dispatcher.user_games_create.await_args.kwargs
        assert kwargs["user_id"] == HUMAN.id
        data = kwargs["data"]
        assert data["source"] == "play_ai"
        assert (data["player_black"], data["player_white"]) == ("小明", "[golaxy] 星铠虾")
        assert data["result"] == "Void"


class TestRecordOffRequest:
    """视觉 poller 与恢复框「重试」这两条路没有请求可取 `current_user`:认**会话主人**,不认按键的人。
    prd §6.0 第 1 条:合并时只改 `_record_platform_engine_game_off_request` 的函数体 —— 这一组测试随之改。"""

    async def test_records_for_the_session_owner(self, monkeypatch):
        session, app = _engine_session(end_result="Void"), MagicMock()
        app.state.user_repo = SimpleNamespace(
            get_user_by_id=lambda uid: {"id": uid, "username": "小明"} if uid == HUMAN.id else None
        )
        recorder = AsyncMock()
        monkeypatch.setattr(server, "_record_platform_engine_game", recorder)

        await server._record_platform_engine_game_off_request(session, app)

        recorder.assert_awaited_once()
        recorded_session, recorded_app, owner = recorder.await_args.args
        assert recorded_session is session and recorded_app is app
        assert (owner.id, owner.username) == (HUMAN.id, "小明")

    async def test_an_unknown_owner_is_passed_as_none(self, monkeypatch):
        session, app = _engine_session(end_result="Void"), MagicMock()
        app.state.user_repo = SimpleNamespace(get_user_by_id=lambda uid: None)
        recorder = AsyncMock()
        monkeypatch.setattr(server, "_record_platform_engine_game", recorder)

        await server._record_platform_engine_game_off_request(session, app)

        assert recorder.await_args.args[2] is None
```

(b) 新建 `tests/platforms/test_engine_game_ledger_e2e.py`（**不许** mock 任何中间层，这是它存在的意义）：

```python
"""N13 × N22 合并契约的验收:真端点 → 真 gateway → 真 GolaxyAdapter → 真 WebKaTrain → 真 `_record_ai_game` → 写库调用。

只 mock 两个边界:星阵网络(`adapter._rest.engine_genmove`)和最外层写库(`repository_dispatcher.user_games_create`)。
**不许** monkeypatch `_finish_ended_game` / `_FINISH_ENDED_GAME_FN` / `_record_platform_engine_game` /
`_record_platform_engine_game_off_request` / `_RECORD_FN` / `_record_ai_game` —— 这条测试存在的意义就是证明终局真的走到了
写库;把中间任何一层换成桩,它就只剩「调用了某个名字」,和 grep 一样能被合并骗过(prd §6.0 第 1 条)。

终局那一刻平台上下文已被 manager 摘掉(`gateway.is_engine_game` 为假),会话座位是 (用户, -1),与 OGS 真人局同形;
能认出「这是星阵人机局」的只有建局时写在 `session.katrain.platform_engine_color` 上的判别位。
"""

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient

from katrain.vision.ipc import ConfirmedMove
from katrain.web.api.v1.endpoints.auth import get_current_user_optional
from katrain.web.models import User
from katrain.web.platforms.gateway import PlatformCommandGateway
from katrain.web.platforms.golaxy.adapter import EngineGameConfig, GolaxyAdapter
from katrain.web.platforms.golaxy.coords import katrain_to_golaxy
from katrain.web.platforms.golaxy.engine_client import GenmoveResult
from katrain.web.platforms.manager import PlatformManager
from katrain.web.server import _handle_confirmed_move, create_app

HUMAN = User(id=7, username="小明")
AI_SPECIAL = GenmoveResult(coord=361, prob=0.0)  # 盘外坐标:星阵的停一手 / 认输都解成它


async def _real_engine_game(genmove, human_color="B"):
    app = create_app(enable_engine=False)
    sm = app.state.session_manager
    pm = PlatformManager(sm)
    gateway = PlatformCommandGateway(pm, sm)
    adapter = GolaxyAdapter()
    pm.register_adapter(adapter)
    adapter._rest.set_tokens("tok", "refresh")
    adapter._rest.engine_genmove = AsyncMock(return_value=genmove)
    pm._setup_callbacks(adapter)  # 生产里由 connect_platform 挂上;不挂的话 game_ended 没人接、上下文不会被摘
    app.state.platform_gateway = gateway
    app.state.game_repo = None  # 盒上形状(server.py board 模式)
    app.state.repository_dispatcher = MagicMock()
    app.state.repository_dispatcher.user_games_create = AsyncMock(return_value={"id": "g1"})
    app.dependency_overrides[get_current_user_optional] = lambda: HUMAN
    session_id = await pm.start_engine_game(
        "golaxy", EngineGameConfig(level=1100, human_color=human_color), user_id=HUMAN.id
    )
    return app, sm.get_session(session_id), gateway


def _client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _the_one_row(app):
    create = app.state.repository_dispatcher.user_games_create
    assert create.await_count == 1, f"星阵人机局终局应写 1 行 user_games,实际 {create.await_count} 行"
    kwargs = create.await_args.kwargs
    assert kwargs["user_id"] == HUMAN.id
    return kwargs["data"]


async def test_ai_ending_the_game_over_http_writes_one_row():
    app, session, gateway = await _real_engine_game(AI_SPECIAL)

    async with _client(app) as ac:
        r = await ac.post("/api/move", json={"session_id": session.session_id, "coords": [3, 3]})

    assert r.status_code == 200, r.text
    assert not gateway.is_engine_game(session.session_id)  # 前提:落账那一刻上下文确实已经没了
    data = _the_one_row(app)
    assert (data["source"], data["result"]) == ("play_ai", "Void")
    assert data["player_black"] == "小明" and data["player_white"].startswith("[golaxy] ")


async def test_resigning_over_http_writes_one_row_and_resigning_again_writes_none():
    app, session, gateway = await _real_engine_game(GenmoveResult(coord=katrain_to_golaxy(15, 3, 19), prob=0.5), "W")

    async with _client(app) as ac:
        first = await ac.post("/api/resign", json={"session_id": session.session_id})
        again = await ac.post("/api/resign", json={"session_id": session.session_id})  # 首个响应丢了重发 / 旧屏

    assert (first.status_code, again.status_code) == (200, 200), (first.text, again.text)
    assert not gateway.is_engine_game(session.session_id)
    data = _the_one_row(app)
    assert (data["source"], data["result"]) == ("play_ai", "B+R")
    assert data["player_white"] == "小明" and data["player_black"].startswith("[golaxy] ")
    assert again.json()["state"]["end_result"] == "B+R"


async def test_ai_ending_the_game_on_the_physical_board_writes_one_row_for_the_owner():
    app, session, gateway = await _real_engine_game(AI_SPECIAL)
    app.state.user_repo = SimpleNamespace(
        get_user_by_id=lambda uid: {"id": uid, "username": "小明"} if uid == HUMAN.id else None
    )
    vision = SimpleNamespace(set_expected_from_stones=lambda *a, **k: None)

    await _handle_confirmed_move(
        app, vision, session.session_id, ConfirmedMove(col=3, row=3, color=1), logging.getLogger("e2e")
    )

    assert not gateway.is_engine_game(session.session_id)
    data = _the_one_row(app)
    assert (data["source"], data["result"], data["player_black"]) == ("play_ai", "Void", "小明")
```

(c) `tests/test_vision_move_poller.py` 文件末尾追加：

```python
class TestGameEndedIsRecordedOffRequest:
    """N13:实体盘上那一手之后星阵结束了这盘。这条路没有 HTTP 请求 ⇒ 经 `_record_platform_engine_game_off_request`
    落账(它认会话主人,见 tests/platforms/test_engine_game_ledger.py `TestRecordOffRequest`)。"""

    def test_game_ended_is_recorded_off_request(self, monkeypatch):
        from unittest.mock import AsyncMock

        import katrain.web.server as server

        session = FakeSession()
        gateway = FakeGateway(outcomes=[PlatformMoveRejectedError("over", reason="game_ended")])
        app = _app(FakeSessionManager({"s1": session}), gateway=gateway, tracker=EngineRecoveryTracker())
        recorder = AsyncMock()
        monkeypatch.setattr(server, "_record_platform_engine_game_off_request", recorder)

        delay = asyncio.run(_handle_confirmed_move(app, FakeVision(), "s1", _move(), log))

        assert delay == 0.0
        recorder.assert_awaited_once_with(session, app)

    def test_other_rejections_record_nothing(self, monkeypatch):
        """正对照:隧道故障不是终局,不落账。"""
        from unittest.mock import AsyncMock

        import katrain.web.server as server

        gateway = FakeGateway(outcomes=[PlatformMoveRejectedError("boom", reason="engine_error")])
        app = _app(FakeSessionManager({"s1": FakeSession()}), gateway=gateway, tracker=EngineRecoveryTracker())
        recorder = AsyncMock()
        monkeypatch.setattr(server, "_record_platform_engine_game_off_request", recorder)

        asyncio.run(_handle_confirmed_move(app, FakeVision(), "s1", _move(), log))

        recorder.assert_not_awaited()
```

(d) `tests/test_vision_engine_move_recovery_endpoints.py` 文件末尾追加（正对照不另写：既有 `TestRetryFailsAgain` 两条守着「非 game_ended 照旧 `ok:false` + 新令牌」，Step 7 的变异证明它们会红）：

```python
class TestRetryThatEndsTheGame:
    """X9 / N13:重试那一手之后星阵结束了这盘(AI 回了停一手或认输),或者这盘早在别处结束了。gateway 回 game_ended ⇒
    没有东西可恢复:不再发新令牌、不再暂停识别,回 ok 让弹层照「重试成功」那条路关掉;这盘经
    `_record_platform_engine_game_off_request` 进棋谱库(它认会话主人 —— 共用盒子上按「重试」的不一定是开这局的人)。
    原来这里把 game_ended 当成又一次隧道故障:回 ok:false + 新令牌,弹层继续写「星阵连接出错」,这盘不落账。"""

    @pytest.mark.asyncio
    async def test_game_ended_closes_the_recovery_and_records_the_game(self, monkeypatch):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock

        import katrain.web.server as server

        tracker = _tripped_tracker(coords=(3, 15), token="tok-1")
        gateway = FakeGateway(
            outcomes=[PlatformMoveRejectedError("AI returned non-move coord 361", reason="game_ended")]
        )
        app = _build_app(tracker=tracker, gateway=gateway)
        session = SimpleNamespace(session_id="s1", user_id=7)
        app.state.session_manager = SimpleNamespace(get_session=lambda sid: {"s1": session}[sid])
        recorder = AsyncMock()
        monkeypatch.setattr(server, "_record_platform_engine_game_off_request", recorder)

        async with _client(app) as ac:
            r = await ac.post("/api/v1/vision/engine-move/retry", json={"session_id": "s1", "recovery_token": "tok-1"})

        assert r.status_code == 200
        assert r.json() == {"ok": True, "game_ended": True}
        assert tracker.active_episode is None
        assert app.state.physical_play.entered_error == []
        assert app.state.physical_play.cleared_error == 1
        recorder.assert_awaited_once_with(session, app)
```

- [ ] **Step 2: 跑，确认红**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && uv run pytest tests/platforms/test_engine_game_ledger.py tests/platforms/test_engine_game_ledger_e2e.py tests/test_vision_move_poller.py tests/test_vision_engine_move_recovery_endpoints.py -q`
Expected: `16 failed, 30 passed`（审查时在 Task 5b 之后的树上实跑）：
- 13 条 `AttributeError: … 'katrain.web.server' … has no attribute '_record_platform_engine_game'`（或 `_record_platform_engine_game_off_request`）：`TestMoveLedger` 1、`TestResignLedger` 2（**含正对照**——monkeypatch 在断言之前就炸）、`TestRecordPlatformEngineGame` 5、`TestRecordOffRequest` 2、`TestGameEndedIsRecordedOffRequest` 2、`TestRetryThatEndsTheGame` 1。这 13 条的红只证明「helper 还不存在」。
- 3 条 e2e `AssertionError: 星阵人机局终局应写 1 行 user_games,实际 0 行`（move：Task 5 已回 200 但不落账；resign：仍走 `record_multiplayer_game`，盒上形状 `game_repo=None` 被吞，日志 `Failed to record game result: 'NoneType' object has no attribute 'record_multiplayer_game'`；视觉：不落账）。**这 3 条才证明「终局没走到写库」**；「判别位取自上下文」「端点把终局当故障」这类错由 Step 7 的变异来证。

- [ ] **Step 3: `_record_ai_game(_locked)` 接受 `data_overrides`**

`:1609`

```python
    async def _record_ai_game_locked(session, app, current_user, result):
```

替换为

```python
    async def _record_ai_game_locked(session, app, current_user, result, data_overrides=None):
```

`data = {...}` 字典收尾处（`:1684-1688`）

```python
                "game_type": game_type,
                "game_date": game_date,
            }

            if game_type == "ai_ladder_ranked":
```

替换为

```python
                "game_type": game_type,
                "game_date": game_date,
            }

            # 调用方替这一局说清「它是什么局、谁坐哪边」—— 星阵人机局的两个座位都是 bare "human"、
            # 人那一方叫占位的 "Me",上面那段推不出来(`_record_platform_engine_game`)。
            # 升降级那一支自己校验 source,不接受外来覆盖。
            if data_overrides and game_type != "ai_ladder_ranked":
                data.update(data_overrides)

            if game_type == "ai_ladder_ranked":
```

`_record_ai_game`（`:1874-1880`）

```python
    async def _record_ai_game(session, app, current_user, result):
        record_lock = getattr(session, "record_game_lock", None)
        if not isinstance(record_lock, asyncio.Lock):
            record_lock = asyncio.Lock()
            session.record_game_lock = record_lock
        async with record_lock:
            await _record_ai_game_locked(session, app, current_user, result)
```

替换为

```python
    async def _record_ai_game(session, app, current_user, result, data_overrides=None):
        record_lock = getattr(session, "record_game_lock", None)
        if not isinstance(record_lock, asyncio.Lock):
            record_lock = asyncio.Lock()
            session.record_game_lock = record_lock
        async with record_lock:
            await _record_ai_game_locked(session, app, current_user, result, data_overrides=data_overrides)
```

- [ ] **Step 4: 模块级 helper**

在 `def _apply_engine_recovery_outcome(`（`:3129`，全文唯一）之前插入——即把

```python
def _apply_engine_recovery_outcome(
```

替换为

```python
def _session_owner(app: FastAPI, session):
    """会话主人,形状与 `current_user` 相同(`User`)。

    视觉 poller 与恢复框「重试」两条路没有请求可取 `current_user`,替会话落账时只能认主人。盒上的主人是
    shadow user,`user_repo` 里查得到。查不到返回 None —— 调用方就不写,不猜一个名字出来。
    与对弈·AI 的 `_on_game_ended_off_request` 同一种解析(`User(**row)`):prd §6.0 第 1 条合并后只留这一个。"""
    user_id = getattr(session, "user_id", None)
    repo = getattr(app.state, "user_repo", None)
    if user_id is None or repo is None:
        return None
    row = repo.get_user_by_id(user_id)
    if not row:
        return None
    return User(**row)


async def _record_platform_engine_game(session, app: FastAPI, user) -> None:
    """N13 —— 星阵人机局落账。盒上与服务端两种部署都走 `_record_ai_game` 那条路。

    它只有**一个** KaTrain 用户、对手是外部引擎,语义就是人机局 ⇒ 不走 `record_multiplayer_game`
    (盒上 `app.state.game_repo` 恒为 None,一次都没写进去过;服务端写进去的是一局没名字的 `play_human`)。
    也因此它**不依赖**「跨盒人人对弈 / 盒上账本」的裁定 —— 那两条管的是两个 KaTrain 用户的局。

    自己判是不是星阵人机局(`is_platform_engine_session`),调用点不必、也不许各自先判一次。参数顺序与对弈·AI 的
    `_finish_ended_game` 相同:prd §6.0 第 1 条合并后,它是那个函数第一个分支里的薄 helper,调用点只改名。

    替会话说清两件 `_record_ai_game` 自己推不出来的事:
      · `source` 写 `play_ai` —— 两个座位的 player_type 都是 bare "human";
      · 人那一方(`platform_engine_color` 的对面)写**账号名** —— 会话上是占位的 "Me",而复盘列表认「你是哪一方」
        靠的正是存进去的名字(`kiosk/components/report/reviewPresentation.ts` `yourColor`)。
    局还没有结果、或者认不出是谁时不写;同一局重复调用由 `_record_ai_game` 的 `_recorded` 挡住。"""
    from katrain.web.platforms.gateway import is_platform_engine_session

    if not is_platform_engine_session(session) or user is None:
        return
    result = session.katrain.game.end_result
    if not result:
        return
    record = globals().get("_RECORD_FN")
    if record is None:
        return
    players = session.katrain.players_info
    names = {"B": players["B"].name or "", "W": players["W"].name or ""}
    names["W" if session.katrain.platform_engine_color == "B" else "B"] = user.username
    await record(
        session,
        app,
        user,
        result,
        data_overrides={"source": "play_ai", "player_black": names["B"], "player_white": names["W"]},
    )


async def _record_platform_engine_game_off_request(session, app: FastAPI) -> None:
    """N13 —— 终局不是由人发的 `/api/move`、`/api/resign` 触发的两条路落账:视觉 poller(`_handle_confirmed_move`)
    与实体盘恢复框的「重试」(`api/v1/endpoints/vision.py` `retry_engine_move`)。认**会话主人**,不认发请求的人:
    poller 没有请求;重试在共用盒子上按下去的不一定是开这局的人。

    prd §6.0 第 1 条:合并时**只改这个函数体**(改成经 `_FINISH_ENDED_GAME_FN` 收尾),两个调用点跟着走 ——
    所以 `vision.py` 与 `_handle_confirmed_move` **只许**经这里落账。"""
    await _record_platform_engine_game(session, app, _session_owner(app, session))


def _apply_engine_recovery_outcome(
```

- [ ] **Step 5: 四处调用**

(a) `/api/resign` 落账分支（`:1948-1960`）

```python
        if is_multiplayer and current_user:
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
```

替换为

```python
        if is_multiplayer and current_user:
            winner_id = session.player_w_id if current_user.id == session.player_b_id else session.player_b_id
            result = f"{'W' if winner_id == session.player_w_id else 'B'}+R"
            if is_platform_engine_session(session):
                # N13: 星阵人机局按人机局落账(见 `_record_platform_engine_game`)。判别位建局时写下、
                # 摘平台上下文之后仍在 ⇒ 不依赖「在 gateway.resign 之前判」。
                await _record_platform_engine_game(session, app, current_user)
            else:
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
```

（其后的 `game_end` 广播块不动。）

(b) `/api/move` —— Task 5 加的 `game_ended` 分支（`:992-996`；old_string 带上下面的 `analysis_context = (` 保证只命中 except 里那一份，try 块里同形的三行不动）

```python
                state = session.katrain.get_state()
                session.last_state = state
                return {"session_id": session.session_id, "state": state}

        analysis_context = (
```

替换为

```python
                state = session.katrain.get_state()
                session.last_state = state
                await _record_platform_engine_game(session, app, current_user)  # N13
                return {"session_id": session.session_id, "state": state}

        analysis_context = (
```

(c) `_handle_confirmed_move`（`:3241-3244`）

```python
        except PlatformMoveRejectedError as e:
            log.warning("Platform gateway rejected vision move: %s", e)
            rearm = _apply_engine_recovery_outcome(app, manager, session_id, game_id, coords, e.reason, str(e))
            if rearm:
```

替换为

```python
        except PlatformMoveRejectedError as e:
            log.warning("Platform gateway rejected vision move: %s", e)
            rearm = _apply_engine_recovery_outcome(app, manager, session_id, game_id, coords, e.reason, str(e))
            if e.reason == "game_ended":
                # N13: 这盘结束了(实体盘上这一手之后星阵结束了它,或者它早就结束了)。这条路没有请求 ⇒ 认会话主人落账;
                # 同一局重复到这里由 `_recorded` 挡住。
                await _record_platform_engine_game_off_request(session, app)
            if rearm:
```

(d) `api/v1/endpoints/vision.py` `retry_engine_move`：docstring（`:346-348`）

```python
      paused throughout — never resumed mid-retry), HTTP 200 {"ok": false, "detail",
      "recovery_token": <new>}.
    """
```

替换为

```python
      paused throughout — never resumed mid-retry), HTTP 200 {"ok": false, "detail",
      "recovery_token": <new>}.
    - game_ended (X9 / N13) -> the game is over (the AI ended it on this very retry, or it had
      already ended elsewhere): no new token, clear_engine_error, record the game for the session
      OWNER via server._record_platform_engine_game_off_request, HTTP 200 {"ok": true, "game_ended": true}.
    """
```

`except Exception`（`:359-360`）

```python
    except Exception as e:
        new_episode = tracker.trip_now(game_id=episode.game_id, coords=episode.coords, detail=str(e))
```

替换为

```python
    except Exception as e:
        from katrain.web.platforms.gateway import PlatformMoveRejectedError

        if isinstance(e, PlatformMoveRejectedError) and e.reason == "game_ended":
            # X9 / N13: 这盘已经结束 —— 这一手之后星阵结束了它(AI 回了停一手或认输;gateway 已落下人那一手、以 `Void`
            # 结束本地局),或者它早在别处结束了(平台上下文已摘)。没有东西可恢复:不 trip_now(`consume` 已摘掉旧 episode)、
            # 放掉识别暂停,回 ok 让弹层走「重试成功」那条路关掉;终局卡由 gateway 那次 update_state 推过去。
            # 当成又一次隧道故障的话,弹层会继续写「星阵连接出错」、令牌一直是活的、这盘也不进棋谱库。
            # 函数内 import:`katrain/web/__init__.py` 导入包时就加载 server,放模块顶层会循环导入。
            from katrain.web.server import _record_platform_engine_game_off_request

            if orchestrator is not None:
                orchestrator.clear_engine_error()
            manager = getattr(request.app.state, "session_manager", None)
            try:
                session = manager.get_session(body.session_id) if manager is not None else None
            except KeyError:
                session = None
            if session is not None:
                await _record_platform_engine_game_off_request(session, request.app)
            return {"ok": True, "game_ended": True}
        new_episode = tracker.trip_now(game_id=episode.game_id, coords=episode.coords, detail=str(e))
```

- [ ] **Step 6: 格式化、跑测试**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && uv run black -l 120 katrain/web/server.py katrain/web/api/v1/endpoints/vision.py tests/platforms/test_engine_game_ledger.py tests/platforms/test_engine_game_ledger_e2e.py tests/test_vision_move_poller.py tests/test_vision_engine_move_recovery_endpoints.py
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && uv run pytest tests/platforms/test_engine_game_ledger.py tests/platforms/test_engine_game_ledger_e2e.py tests/test_vision_move_poller.py tests/test_vision_engine_move_recovery_endpoints.py tests/platforms/test_engine_gateway.py tests/platforms/test_engine_integration.py tests/test_local_play_recording.py tests/test_engine_physical_integration.py -q
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && uv run pytest tests/web_ui/test_ai_game_autosave.py tests/web_ui/test_game_termination_and_chat_identity.py -q
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && CI=true uv run pytest tests/web_ui/test_ai_ladder_api.py -q -k vision
```
Expected: black 顺带改到的 `:341-343` 那一块照 Task 5 Step 6 改回（`vision.py` 在基线上 black 干净，不会有别的顺带改动）；三条 pytest 依次 `91 passed`、`22 passed`、`12 passed, 240 deselected`（审查时实跑；后两条守既有的人机局落账、认输广播与升降级视觉落子，确认 `data_overrides` 与路由没把它们改坏）。

- [ ] **Step 7: 变异验证（不提交）**

逐条临时改、跑 Step 2 那条命令、还原（审查时逐条实跑）：

| 变异 | 期望变红 |
|---|---|
| helper 的判别位改取自上下文：`if not is_platform_engine_session(session) or user is None:` → `_gw = getattr(app.state, "platform_gateway", None)` / `if not (_gw and _gw.is_engine_game(session.session_id)) or user is None:` | e2e **3 条全红** `实际 0 行`（终局那一刻上下文已被摘）；另 `test_a_non_engine_platform_session_is_not_written` 与 poller 两条（`FakeGateway` 没有 `is_engine_game`）。**只有 e2e 守得住「判别位取自上下文」这一类错**——单测里 MagicMock gateway 的 `is_engine_game` 恒为真 |
| helper 去掉判别位闸（只留 `if user is None: return`） | `test_a_non_engine_platform_session_is_not_written` |
| 删掉 (b) 那一行落账 | `TestMoveLedger`、e2e move |
| (a) 里 `if is_platform_engine_session(session):` 改成 `if False:` | `test_engine_resign_goes_through_the_ai_game_ledger`、e2e resign |
| (c) 里落账那一行改成 `pass` | `test_game_ended_is_recorded_off_request`、e2e 实体盘 |
| off-request helper 传 `None` 代替 `_session_owner(app, session)` | `test_records_for_the_session_owner`、e2e 实体盘 |
| (d) 里 `if isinstance(e, PlatformMoveRejectedError) and e.reason == "game_ended":` 改成 `if False:` | `test_game_ended_closes_the_recovery_and_records_the_game`（`{'ok': False} != {'ok': True}`） |
| (d) 里删掉 `orchestrator.clear_engine_error()` 两行 | 同上（`assert 0 == 1`） |
| (d) 里判别改成 `if True:`（所有失败都当终局） | 既有 `TestRetryFailsAgain` 两条（`assert True is False`） |
| (d) 里落账那一行改成 `pass` | `test_game_ended_closes_the_recovery_and_records_the_game`（`Awaited 0 times`） |

- [ ] **Step 8: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && git add katrain/web/server.py katrain/web/api/v1/endpoints/vision.py tests/platforms/test_engine_game_ledger.py tests/platforms/test_engine_game_ledger_e2e.py tests/test_vision_move_poller.py tests/test_vision_engine_move_recovery_endpoints.py && git commit -m "$(cat <<'EOF'
fix(platforms): 星阵人机局下完进棋谱库 —— 盒上一盘都没存进去过

认输走联机局分支调 app.state.game_repo.record_multiplayer_game,盒上 game_repo 恒为 None,
AttributeError 被吞;AI 终局那条路完全不落账;服务端写进去的是一局没名字的 play_human。
星阵人机局只有一个 KaTrain 用户、对手是外部引擎,改走人机局那条两种部署都通的
_record_ai_game(新增 data_overrides):source=play_ai,人那一方写账号名(会话上是占位 "Me")。
四处调用:/api/resign(按建局时写下的 platform_engine_color 判)、/api/move 的 game_ended、
视觉 poller 的 game_ended、实体盘恢复框「重试」的 game_ended(原来当成又一次隧道故障:
新令牌、弹层继续写连接出错、不落账;现在关恢复、回 ok)。没有请求的两条路经同一个 helper 认会话主人。
helper 参数顺序与对弈·AI 的 _finish_ended_game 相同,prd §6.0 第 1 条合并时只改名;
新增端到端验收 test_engine_game_ledger_e2e.py(真端点 → 真 gateway → 真写库调用,不 mock 中间层)。

EOF
)"
```

---

### Task 6b: N13 × X11 后端 —— 已绑定云端会话的棋谱按主人写库

**为什么有这个 Task**（计划审查第 2 轮 R2-1）：Task 6 让没有请求的两条路（视觉 poller、恢复框「重试」）以**会话主人**落账，传进 `_record_ai_game` 再到 `dispatcher.user_games_create(user_id=…)` 的是主人没错（`server.py:1836`）；但盒上写库这一层按**云端 bearer** 认人：在线时 `remote_user_games.create_game(data)` 根本不带 `user_id`（`repository.py:273-278`），云端 `POST /api/v1/user-games/` 把这一行记进当前 bearer 的账号。盒子上云端会话只有一份——launcher 换人时 `box_sso_bootstrap` 换 token 并 `bind_user` 新的人（`api/v1/endpoints/auth.py:210-214`），**不结束**上一个人的对局会话。甲开的星阵实体盘局在换成乙之后才结束 ⇒ 甲的这盘进了**乙**的云端棋谱库（审查时实跑：真 `RepositoryDispatcher` + 真 `RemoteAPIClient` + 真本机库与队列 + 真 `SyncWorker`，只有云端是按 bearer 记账的 `httpx.MockTransport`：`{'乙': ['甲']}`）。离线那一半是同一件事：落本机、入队的 `create_user_game` 重放时不看主人（`sync_worker.py:106-113` 只替升降级结算查 `_may_send_for`），谁的会话在就发进谁的库——这一半对今天所有盒上人机局都成立（甲断网下完、乙联网后补传），不是本轮引入的，但判据相同、改在同一处。

判据照搬既有的 `_may_send_for`（`sync_worker.py:209-234`：「盒子是共用的，云端会话只有一份」）：云端会话**绑定的是另一个本机用户**时，这一行当离线处理——本机记在 `user_id` 名下并入队；队列项只在云端会话绑定的是它主人时发出，不挡别人的。与 `_may_send_for` 只差一处：**没有绑定（`None`）不算「别人」**，照今天的行为发。严格盒端每次 bootstrap 都绑人（`auth.py:214`），退出时 `clear_tokens` 同时清掉 token 与绑定、队列整个暂停（`remote_client.py:73-81`、`sync_worker.py:101-103`）；没有绑定而仍发得出去的只有非严格部署重启后恢复出来的整机凭据（`server.py:456-465`）——既有问题，改成「没绑定就等」会让非严格盒子上的离线棋谱一直停在队列里，记入 prd §5，本轮不动。

**Files:**
- Modify: `katrain/web/core/repository.py:273-279`（`user_games_create` 在线分支的判断）
- Modify: `katrain/web/core/sync_worker.py:27`（`ORDERED_OPERATIONS` 之后新增 `OWNER_BOUND_OPERATIONS`）、`:111-113`（`_process_queue` 里 `ORDERED_OPERATIONS` 那一支之后加一支）
- Modify: `katrain/web/core/remote_client.py:97-144`（401 刷新期间云端会话换人时，不用后来者凭据重试、不覆盖后来者 token）
- Create: `tests/web_ui/test_user_game_cloud_owner.py`（`git ls-files` 无同名、`git check-ignore` 不吞；在 `tests/web_ui/` 下，按 Global Constraints 单独一条 pytest 命令跑）

**Interfaces:**
- Consumes: `RemoteAPIClient.bound_user_id`（`remote_client.py:69-71`，`str | None`）、`set_tokens` / `bind_user`（`:53-67`）；`RepositoryDispatcher(..., remote_client=…)`（`repository.py:165-183`；`server.py:483-492` 传入同一个 `remote_client`）；`enqueue_sync_item`（`repository.py:410`）；`SyncWorker.run_sync`（`sync_worker.py:73`）；`UserGameRepository`（`user_game_repo.py:22`）。
- Produces:
  - `RepositoryDispatcher.user_games_create(user_id, data)` 契约：在线且云端会话绑定的是**另一个**本机用户（`bound_user_id` 非 None 且 `!= str(user_id)`）⇒ 不发云端，本机写在 `user_id` 名下并入队 `create_user_game`；绑定是本人或没有绑定 ⇒ 照旧在线直发。
  - `katrain.web.core.sync_worker.OWNER_BOUND_OPERATIONS = frozenset({"create_user_game"})`：云端会话绑定的是另一个本机用户时，这类队列项跳过（保持 `pending`、不计重试、不挡别人的项）。
  - 已发出的 POST 如果在 401 / 刷新等待期间换人，仍用发出时的 bearer；401 后不再用后来者的凭据重试，在线写转本机队列，队列项恢复 `pending`。普通同一人的 401 仍刷新重试。
  - 同步只在断网恢复时触发（`connectivity.py:122-128`）⇒ 被挡住的那一行在「主人的云端会话在」时的下一次同步发出，不是主人一登录就发（prd §5 记为后续项）。
- 与 Task 5 / 5b / 6 没有代码依赖；排在泳道 C 只因为是后端文件。

- [ ] **Step 1: 写测试（先红）**

新建 `tests/web_ui/test_user_game_cloud_owner.py`（**不许** mock dispatcher / `SyncWorker` / `RemoteAPIClient` / 本机库与队列——假的只有云端那一头，它按 bearer 记账，与真云端同一条规则；换成桩就只剩「调用了某个名字」）：

```python
"""共用盒子只有一份云端会话，棋谱 POST 按 bearer 记账。测试在线、队列和 401 换人。

真 dispatcher / client / 本机库 / 队列；仅云端用 MockTransport 按 bearer 记账。
"""

import asyncio
import json
from functools import partial
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db
from katrain.web.core.remote_client import RemoteAPIClient
from katrain.web.core.repository import RemoteUserGameRepository, RepositoryDispatcher, enqueue_sync_item
from katrain.web.core.sync_worker import SyncWorker
from katrain.web.core.user_game_repo import UserGameRepository

JIA, YI = 7, 8
CLOUD_ACCOUNT_BY_BEARER = {"tok-jia": "甲", "tok-jia-new": "甲", "tok-yi": "乙", "tok-yi-new": "乙"}


def _box(cloud_handler=None):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    library = {}  # 云端:账号 -> 那个账号棋谱库里各盘的黑方名

    def cloud(request: httpx.Request) -> httpx.Response:
        if request.url.path != "/api/v1/user-games/":
            return httpx.Response(404)
        account = CLOUD_ACCOUNT_BY_BEARER.get(request.headers.get("authorization", "").removeprefix("Bearer "))
        if account is None:
            return httpx.Response(401, json={"detail": "Not authenticated"})
        library.setdefault(account, []).append(json.loads(request.content)["player_black"])
        return httpx.Response(200, json={"id": f"cloud-{sum(map(len, library.values()))}"})

    remote = RemoteAPIClient(base_url="http://cloud.test", device_id="box-1")
    remote._client = httpx.AsyncClient(
        base_url="http://cloud.test", transport=httpx.MockTransport(cloud_handler or cloud)
    )
    connectivity = SimpleNamespace(is_online=True)
    dispatcher = RepositoryDispatcher(
        connectivity_manager=connectivity,
        remote_tsumego=None,
        remote_kifu=None,
        remote_user_games=RemoteUserGameRepository(remote),
        local_user_game_repo=UserGameRepository(factory),
        sync_enqueue_fn=partial(enqueue_sync_item, factory, device_id="box-1"),
        remote_client=remote,
    )
    return SimpleNamespace(
        factory=factory,
        library=library,
        remote=remote,
        connectivity=connectivity,
        dispatcher=dispatcher,
        worker=SyncWorker(factory, remote),
    )


def _sign_in(box, token, user_id):
    """与 `auth.py` `box_sso_bootstrap` 同样两步:换上这个人的云端 token,再说清它替哪个本机用户说话。"""
    box.remote.set_tokens(token, f"refresh-{token}")
    box.remote.bind_user(user_id)


def _game(black):
    return {"sgf_content": f"(;GM[1]PB[{black}])", "source": "play_ai", "player_black": black, "result": "W+R"}


def _local_blacks(box, user_id):
    return [g["player_black"] for g in box.dispatcher._local_user_game_repo.list(user_id=user_id)["items"]]


def _queue(box):
    with box.factory() as db:
        rows = db.query(models_db.SyncQueueEntry).order_by(models_db.SyncQueueEntry.id).all()
        return [(r.operation, r.user_id, r.status) for r in rows]


async def test_a_game_that_ends_after_the_box_switched_to_yi_stays_out_of_yis_cloud_library():
    box = _box()
    _sign_in(box, "tok-yi", YI)  # 甲开的局还在盘上,launcher 已经换成乙

    await box.dispatcher.user_games_create(user_id=JIA, data=_game("甲"))

    assert box.library == {}, "甲的棋谱进了乙的云端棋谱库"
    assert _local_blacks(box, JIA) == ["甲"]  # 留在本机、记在甲名下
    assert _queue(box) == [("create_user_game", str(JIA), "pending")]  # 等甲的云端会话


async def test_a_queued_game_waits_for_its_owner_without_holding_up_anyone_else():
    box = _box()
    _sign_in(box, "tok-jia", JIA)
    box.connectivity.is_online = False
    await box.dispatcher.user_games_create(user_id=JIA, data=_game("甲"))  # 甲断网时下完
    _sign_in(box, "tok-yi", YI)  # 还没联网,launcher 换成了乙
    await box.dispatcher.user_games_create(user_id=YI, data=_game("乙"))  # 乙也断网下完一盘
    box.connectivity.is_online = True

    synced = await box.worker.run_sync()

    assert box.library == {"乙": ["乙"]}, "重放把甲的棋谱发进了乙的云端棋谱库"
    assert synced == 1
    assert _queue(box) == [("create_user_game", str(JIA), "pending"), ("create_user_game", str(YI), "completed")]

    _sign_in(box, "tok-jia", JIA)  # 甲回来:那盘不是丢了,是在等他
    assert await box.worker.run_sync() == 1
    assert box.library == {"乙": ["乙"], "甲": ["甲"]}


async def test_the_owners_own_session_still_goes_straight_to_the_cloud():
    """正对照:主人就是当前云端会话时照旧在线直发,不落本机、不进队列(`bound_user_id` 是字符串、`user_id` 是整数)。"""
    box = _box()
    _sign_in(box, "tok-jia", JIA)

    await box.dispatcher.user_games_create(user_id=JIA, data=_game("甲"))

    assert box.library == {"甲": ["甲"]}
    assert _local_blacks(box, JIA) == [] and _queue(box) == []


@pytest.mark.parametrize("pause_at", ["first_post", "refresh"])
async def test_switching_cloud_user_during_401_keeps_both_games_with_their_owners(pause_at):
    """初次 POST 返回 401、或旧人的 refresh 等待时切换身份,都不能用新人的 bearer 补发旧谱或污染新 token。"""
    entered, release = asyncio.Event(), asyncio.Event()
    box = None

    async def cloud(request):
        path = request.url.path
        if path == "/api/v1/auth/refresh":
            refresh = json.loads(request.content)["refresh_token"]
            if pause_at == "refresh" and refresh == "refresh-tok-jia":
                entered.set()
                await release.wait()
            return httpx.Response(
                200, json={"access_token": "tok-jia-new" if refresh == "refresh-tok-jia" else "tok-yi-new"}
            )
        if path != "/api/v1/user-games/":
            return httpx.Response(404)
        bearer = request.headers.get("authorization", "").removeprefix("Bearer ")
        if bearer == "tok-jia":
            if pause_at == "first_post":
                entered.set()
                await release.wait()
            return httpx.Response(401)
        account = CLOUD_ACCOUNT_BY_BEARER[bearer]
        box.library.setdefault(account, []).append(json.loads(request.content)["player_black"])
        return httpx.Response(200, json={"id": "cloud-1"})

    box = _box(cloud_handler=cloud)
    _sign_in(box, "tok-jia", JIA)
    pending = asyncio.create_task(box.dispatcher.user_games_create(user_id=JIA, data=_game("甲")))
    await asyncio.wait_for(entered.wait(), timeout=2)
    _sign_in(box, "tok-yi", YI)
    release.set()
    await pending
    assert box.remote._access_token == "tok-yi" and box.remote.bound_user_id == str(YI)
    assert not box.remote.auth_required
    assert _local_blacks(box, JIA) == ["甲"] and _queue(box) == [("create_user_game", str(JIA), "pending")]
    await box.dispatcher.user_games_create(user_id=YI, data=_game("乙"))
    assert box.library == {"乙": ["乙"]}, "身份切换时用后来者 bearer 重试旧谱,或把旧 token 覆盖到新会话"


async def test_queued_game_returns_to_pending_when_owner_changes_during_401():
    entered, release = asyncio.Event(), asyncio.Event()
    box = None

    async def cloud(request):
        if request.url.path == "/api/v1/auth/refresh":
            return httpx.Response(200, json={"access_token": "tok-yi-new"})
        bearer = request.headers.get("authorization", "").removeprefix("Bearer ")
        if bearer == "tok-jia":
            entered.set()
            await release.wait()
            return httpx.Response(401)
        box.library.setdefault("乙", []).append(json.loads(request.content)["player_black"])
        return httpx.Response(200, json={"id": "cloud-1"})

    box = _box(cloud_handler=cloud)
    _sign_in(box, "tok-jia", JIA)
    box.connectivity.is_online = False
    await box.dispatcher.user_games_create(user_id=JIA, data=_game("甲"))
    box.connectivity.is_online = True
    pending = asyncio.create_task(box.worker.run_sync())
    await asyncio.wait_for(entered.wait(), timeout=2)
    _sign_in(box, "tok-yi", YI)
    release.set()
    assert await pending == 0
    assert box.library == {} and _queue(box) == [("create_user_game", str(JIA), "pending")]
    with box.factory() as db:
        assert db.query(models_db.SyncQueueEntry).one().retry_count == 0


async def test_same_owner_401_still_refreshes_and_writes_directly():
    box = None

    async def cloud(request):
        if request.url.path == "/api/v1/auth/refresh":
            return httpx.Response(200, json={"access_token": "tok-jia-new"})
        bearer = request.headers.get("authorization", "").removeprefix("Bearer ")
        if bearer == "tok-jia":
            return httpx.Response(401)
        box.library.setdefault("甲", []).append(json.loads(request.content)["player_black"])
        return httpx.Response(200, json={"id": "cloud-1"})

    box = _box(cloud_handler=cloud)
    _sign_in(box, "tok-jia", JIA)
    await box.dispatcher.user_games_create(user_id=JIA, data=_game("甲"))
    assert box.library == {"甲": ["甲"]} and _queue(box) == []
```

- [ ] **Step 2: 跑，确认红**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && uv run pytest tests/web_ui/test_user_game_cloud_owner.py -q`
Expected：原有的两条跨用户用例在未改代码时红（审查时实跑 2 failed, 1 passed）；401 竞态新用例在旧版 6b 守卫树 `wt-e3` 上实跑为 3 failed, 4 passed：
- `test_a_game_that_ends_after_the_box_switched_to_yi_stays_out_of_yis_cloud_library` —— `AssertionError: 甲的棋谱进了乙的云端棋谱库`（`assert {'乙': ['甲']} == {}`）
- `test_a_queued_game_waits_for_its_owner_without_holding_up_anyone_else` —— `AssertionError: 重放把甲的棋谱发进了乙的云端棋谱库`
- `test_switching_cloud_user_during_401_keeps_both_games_with_their_owners[first_post]` —— 旧请求刷新并重试时用了乙的 bearer。
- `test_switching_cloud_user_during_401_keeps_both_games_with_their_owners[refresh]` —— 甲的刷新结果覆盖乙的 access token。
- `test_queued_game_returns_to_pending_when_owner_changes_during_401` —— 甲的队列项写到乙库并标 `completed`。

正对照 `test_the_owners_own_session_still_goes_straight_to_the_cloud` 与 `test_same_owner_401_still_refreshes_and_writes_directly` PASS。红必须是断言失败，不是收集 / import 错误。

- [ ] **Step 3: `repository.py` 在线分支认云端会话绑定的人**

`:273-279`

```python
    async def user_games_create(self, user_id: int, data: Dict) -> Dict:
        if self.is_online:
            try:
                return await self.remote_user_games.create_game(data)
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
                logger.warning("user_games_create remote failed, falling back to local: %s", e)
        # Offline or remote failed — write locally
```

替换为

```python
    async def user_games_create(self, user_id: int, data: Dict) -> Dict:
        # Cloud POST attributes the game to its bearer, not user_id. A session bound to
        # someone else must use the existing local+queue path; unbound keeps old behavior (prd §5).
        bound = getattr(self._remote_client, "bound_user_id", None)
        if self.is_online and (bound is None or str(bound) == str(user_id)):
            try:
                return await self.remote_user_games.create_game(data)
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
                logger.warning("user_games_create remote failed, falling back to local: %s", e)
        elif self.is_online:
            logger.info("user_games_create: cloud session is user %s, keeping user %s's game local", bound, user_id)
        # Offline, remote failed, or the cloud session speaks for someone else — write locally
```

（其后「本机写 + 入队」那一段不动：`user_id` 本来就是调用方传进来的主人。）

- [ ] **Step 4: `sync_worker.py` 补传认主人**

(i) `:27`

```python
ORDERED_OPERATIONS = frozenset({"settle_ai_ladder_ranked"})
```

替换为

```python
ORDERED_OPERATIONS = frozenset({"settle_ai_ladder_ranked"})

#: Cloud attributes these requests to the bearer. Wait when bound to another user;
#: unlike ORDERED_OPERATIONS, one held game does not block anyone else's items.
OWNER_BOUND_OPERATIONS = frozenset({"create_user_game"})
```

(ii) `:111-113`（`_process_queue` 循环里 `ORDERED_OPERATIONS` 那一支的收尾）

```python
                    if not self._may_send_for(item):
                        blocked_users.add(item.user_id)
                        continue
```

替换为

```python
                    if not self._may_send_for(item):
                        blocked_users.add(item.user_id)
                        continue
                elif item.operation in OWNER_BOUND_OPERATIONS:
                    bound = getattr(self._remote_client, "bound_user_id", None)
                    if bound is not None and item.user_id is not None and str(bound) != str(item.user_id):
                        logger.info(
                            "Holding %s [%s]: queued for user %s, cloud session is user %s",
                            item.operation,
                            item.idempotency_key[:8],
                            item.user_id,
                            bound,
                        )
                        continue
```

(iii) `_process_queue` 的执行结果：

```python
                    await self._execute_item(item)
                    item.status = "completed"
```

替换为

```python
                    outcome = await self._execute_item(item)
                    if outcome == "owner_changed":
                        item.status = "pending"
                        item.locked_at = None
                        db.commit()
                        continue
                    item.status = "completed"
```

(iv) `_execute_item` 在 `item.last_http_status = resp.status_code` 后、判断 2xx 之前插入：

```python
            if resp.status_code == 401 and item.operation in OWNER_BOUND_OPERATIONS and item.user_id is not None:
                bound = self._remote_client.bound_user_id
                if bound is None or str(bound) != str(item.user_id):
                    return "owner_changed"
```

身份在 POST 等待时变了，原请求的 401 不表示主人永久拒绝；这项保持 `pending`，不占重试预算。

- [ ] **Step 4b: `remote_client.py` 的 401 刷新只作用于发出请求时的云端会话**

`_refresh_access_token` 在首次 await 前记录刷新凭据与本机主人；等待期间换人就不覆盖后来者的 access token。`:99-113`：

```python
        if not self._refresh_token:
            return False
        try:
            resp = await self._client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": self._refresh_token},
            )
            if resp.status_code == 200:
                data = resp.json()
                self._access_token = data["access_token"]
                self._auth_required = False
```

替换为

```python
        refresh_token, bound_user_id = self._refresh_token, self._bound_user_id
        if not refresh_token:
            return False
        try:
            resp = await self._client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": refresh_token},
            )
            if resp.status_code == 200:
                if (self._refresh_token, self._bound_user_id) != (refresh_token, bound_user_id):
                    return False  # another user's session replaced this one while refresh waited
                data = resp.json()
                self._access_token = data["access_token"]
                self._auth_required = False
```

`_request` 首次 POST 的 headers 已在 await 前取好；401 后不能再读后来者的 refresh/bearer 来补发旧请求，也不能把后来者标为 `auth_required`。`:126-142`：

```python
        headers = self._auth_headers() if auth else {}
        resp = await self._client.request(method, path, json=json, params=params, headers=headers)

        if resp.status_code == 401 and auth and self._refresh_token:
            refreshed = await self._refresh_access_token()
            if refreshed:
                headers = self._auth_headers()
                resp = await self._client.request(method, path, json=json, params=params, headers=headers)
            else:
                self._auth_required = True
                logger.warning("Auth required: both access and refresh tokens invalid")
```

替换为

```python
        session = (self._refresh_token, self._bound_user_id)
        headers = self._auth_headers() if auth else {}
        resp = await self._client.request(method, path, json=json, params=params, headers=headers)

        if resp.status_code == 401 and auth and session[0]:
            if (self._refresh_token, self._bound_user_id) != session:
                return resp
            refreshed = await self._refresh_access_token()
            if (self._refresh_token, self._bound_user_id) != session:
                return resp
            if refreshed:
                headers = self._auth_headers()
                resp = await self._client.request(method, path, json=json, params=params, headers=headers)
            else:
                self._auth_required = True
                logger.warning("Auth required: both access and refresh tokens invalid")
```

`auth.py:315` 直接调用 `_refresh_access_token()` 的 no-arg / bool 接口不变；没有换人的 401 仍照常刷新重试。

- [ ] **Step 5: 格式化、跑测试**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && uv run black -l 120 katrain/web/core/repository.py && uv run black -l 120 tests/web_ui/test_user_game_cloud_owner.py && echo "remote_client.py hunks=$(uv run black -l 120 --diff katrain/web/core/remote_client.py | grep -c '^@@')" && echo "sync_worker.py hunks=$(uv run black -l 120 --diff katrain/web/core/sync_worker.py | grep -c '^@@')"
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && uv run pytest tests/web_ui/test_user_game_cloud_owner.py tests/web_ui/test_ladder_settlement_sync.py tests/web_ui/test_user_games_authority.py tests/web_ui/test_tsumego_offline.py tests/web_ui/test_ai_ladder_api.py -q
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && uv run pytest tests/test_user_game_repo.py tests/test_local_play_recording.py -q
```
Expected:
- 两次 black 各报 `1 file left unchanged`；`remote_client.py hunks=1`（基线 `end_ai_ladder_game` 的旧折行）、`sync_worker.py hunks=1`（基线 409 旧折行）。这两个文件有非本 Task 的旧格式差异，不许不带 `--diff` 全文件重排；多于 1 时只修本 Task hunk。
- 第一条 pytest 应有 7 条 `test_user_game_cloud_owner.py` 用例全绿（原三条在审查时实跑；新四格须本 Task 实跑），其它点名用例仍绿；第二条原有 27 条全绿。新增用例数量按参数化展开计。

- [ ] **Step 6: 变异验证（不提交）**

逐条临时改、跑 Step 2 那条命令、还原（审查时逐条实跑）：

| 变异 | 期望变红 |
|---|---|
| `repository.py` 判断改回 `if self.is_online:`（不看绑定） | `test_a_game_that_ends_after_the_box_switched_to_yi_stays_out_of_yis_cloud_library`（`甲的棋谱进了乙的云端棋谱库`） |
| `sync_worker.py` 删掉 `elif item.operation in OWNER_BOUND_OPERATIONS:` 那一支 | `test_a_queued_game_waits_for_its_owner_without_holding_up_anyone_else`（`重放把甲的棋谱发进了乙的云端棋谱库`） |
| `repository.py` 里 `str(bound) == str(user_id)` 改成 `bound == user_id`（`bound_user_id` 是字符串、`user_id` 是整数） | 正对照 `test_the_owners_own_session_still_goes_straight_to_the_cloud`（`assert {} == {'甲': ['甲']}`：本人的会话也被当成了别人） |
| `_request` 删「首次 POST 后会话已换就回原 401」闸 | `test_switching_cloud_user_during_401_keeps_both_games_with_their_owners[first_post]` |
| `_refresh_access_token` 删刷新等待后的快照比较 | `test_switching_cloud_user_during_401_keeps_both_games_with_their_owners[refresh]` |
| `sync_worker.py` 删 `owner_changed` 回 pending 分支 | `test_queued_game_returns_to_pending_when_owner_changes_during_401` |
| `_request` 对同一人的 401 也停止刷新 | `test_same_owner_401_still_refreshes_and_writes_directly` |

「没有绑定不算别人」这一格**故意不写测试**：它守的是今天的行为（非严格部署的既有问题，见 prd §5），写成断言等于把一个已知缺陷钉成契约。

- [ ] **Step 7: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && git add katrain/web/core/repository.py katrain/web/core/sync_worker.py katrain/web/core/remote_client.py tests/web_ui/test_user_game_cloud_owner.py && git commit -m "$(cat <<'EOF'
fix(board-sync): 共用盒子棋谱按主人写云库

在线直发和离线补传遇别人的云端会话时留本机 pending；401 等待期间换人不拿后来者凭据重试，也不覆盖后来者 token。双用户真链路和身份切换测试先红后绿、变异再红。未绑定整机凭据沿用既有行为，归 X11 后续裁定。

EOF
)"
```

---

### Task 7: X9-b / N13 前端 —— 把 `Void` 说成人话

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx:122-123`（`EndgameCard` 结果徽标之后）
- Modify: `katrain/web/ui/src/kiosk/components/report/reviewPresentation.ts:96-101`（`outcomeLine`）
- Test: `katrain/web/ui/src/kiosk/__tests__/GamePageEngine.test.tsx:202-208`（afterEach）、`:620` 之前（新 describe）
- Test: `katrain/web/ui/src/kiosk/components/report/reviewPresentation.test.ts:98-101`
- `Void` 终局卡的真运行时预览（:5173）不在本 Task 跑，合并回本分支后在 Task 9 Step 5 取。

**Interfaces:**
- Consumes: Task 5 起 `GameState.end_result` 可能为 `"Void"`（只由「AI 结束了**被提交的这一盘**」写入；等待期间已认输的局保留 `X+R`）；Task 6 起 `UserGameSummary.result` 可能为 `"Void"`（泳道 A 只在 mock 里用这个字符串，不依赖泳道 C 的代码）；`GameState.platform_engine_color?: 'B' | 'W' | null`（`api.ts:113`）。
- Produces: 无。

- [ ] **Step 1: 写测试（先红）**

`GamePageEngine.test.tsx` 主 `afterEach`（`:202-208`）的 `mockGameState.count_min_moves = undefined;` 之后加：

```tsx
    mockGameState.end_result = null;
    mockGameState.platform_engine_color = undefined;
```

在 `describe('G2: engine-aware humanColor / aiTurn derivation (platform_engine_color)')` 之前插入：

```tsx
  // X9:星阵 AI 回了停一手或认输(编码没抓到,分不出是哪一种),后端以无胜负 `Void` 结束了这盘。
  // 结果徽标那一格只会写「?」—— 不补这一句,用户会以为结果丢了。
  describe('星阵 AI 结束对局(无胜负)', () => {
    it('星阵局以 Void 结束:终局卡说清为什么没有胜负', () => {
      mockGameState.end_result = 'Void';
      mockGameState.platform_engine_color = 'W';
      renderPage(true);
      expect(screen.getByTestId('endgame-no-result')).toHaveTextContent('星阵 AI 停手或认输了');
    });

    it('普通终局不出这一行(正对照)', () => {
      mockGameState.end_result = 'W+R';
      mockGameState.platform_engine_color = 'W';
      renderPage(true);
      expect(screen.getByTestId('endgame-card')).toBeInTheDocument();
      expect(screen.queryByTestId('endgame-no-result')).toBeNull();
    });
  });
```

`reviewPresentation.test.ts:98-101`

```ts
  it('后端存了别的写法就原样念,不猜', () => {
    expect(outcomeLine(game({ result: 'Void' }), 'B', t)).toBe('Void');
  });
```

替换为

```ts
  // `Void` 是 SGF 规范里定义好的「不判胜负」,今天由星阵人机局写进来(AI 停手或认输,分不出是哪种)。
  // 照它的意思念,不是猜;规范之外的写法仍原样念。
  it('Void 念成「这盘没有判出胜负」', () => {
    expect(outcomeLine(game({ result: 'Void' }), 'B', t)).toBe('这盘没有判出胜负');
    expect(outcomeLine(game({ result: 'void' }), null, t)).toBe('这盘没有判出胜负');
  });

  it('后端存了别的写法就原样念,不猜', () => {
    expect(outcomeLine(game({ result: 'Unknown' }), 'B', t)).toBe('Unknown');
  });
```

- [ ] **Step 2: 跑，确认红**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx vitest run src/kiosk/__tests__/GamePageEngine.test.tsx src/kiosk/components/report/reviewPresentation.test.ts`
Expected: 「星阵局以 Void 结束…」与「Void 念成…」FAIL；其余 PASS。

- [ ] **Step 3: 改 `GamePage.tsx` `EndgameCard`**

```tsx
      <KioskResultBadge result={gameState.end_result!} rules={gameState.ruleset} />
```

替换为

```tsx
      <KioskResultBadge result={gameState.end_result!} rules={gameState.ruleset} />
      {/* X9:星阵 AI 回了停一手或认输(编码没抓到,分不出是哪一种),后端以无胜负 `Void` 结束了这盘。
          徽标那一格只会写「?」—— 这一句说清为什么没有胜负,而不是让人以为结果丢了。 */}
      {gameState.end_result === 'Void' && gameState.platform_engine_color && (
        <Typography
          variant="caption"
          data-testid="endgame-no-result"
          sx={{ color: 'text.secondary', textAlign: 'center', maxWidth: 320 }}
        >
          {t('game:engine_ended_no_result', '星阵 AI 停手或认输了 · 本终端还分不出是哪一种，这盘不判胜负')}
        </Typography>
      )}
```

- [ ] **Step 4: 改 `reviewPresentation.ts`**

```ts
  const m = raw.match(/^([BW])\+(.+)$/i);
  if (!m) return raw;                       // 后端存了别的写法就原样念,不猜
```

替换为

```ts
  // SGF 的 `Void` = 不判胜负。今天只由星阵人机局写进来(AI 停手或认输,本终端分不出是哪种,
  // server.py `_record_platform_engine_game`)。规范里有定义的值,照它的意思念,不算猜。
  if (/^void$/i.test(raw)) return t('review:no_result_line', '这盘没有判出胜负');
  const m = raw.match(/^([BW])\+(.+)$/i);
  if (!m) return raw;                       // 后端存了别的写法就原样念,不猜
```

- [ ] **Step 5: 跑测试与类型检查**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx vitest run src/kiosk/__tests__/GamePageEngine.test.tsx src/kiosk/components/report/reviewPresentation.test.ts src/kiosk/pages/GamePage.test.tsx && npx tsc -b
```
Expected: 全 PASS；`tsc -b` 退出 0。

- [ ] **Step 6: Commit**（这一态设计稿里没有，真运行时预览截图在 Task 9 Step 5 取）

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && git add katrain/web/ui/src/kiosk/pages/GamePage.tsx katrain/web/ui/src/kiosk/__tests__/GamePageEngine.test.tsx katrain/web/ui/src/kiosk/components/report/reviewPresentation.ts katrain/web/ui/src/kiosk/components/report/reviewPresentation.test.ts && git commit -m "$(cat <<'EOF'
feat(kiosk): 星阵 AI 结束对局时终局卡与复盘列表说清「这盘不判胜负」

后端以 SGF 的 Void 结束这类局(AI 停手或认输,分不出是哪种)。终局卡徽标只会写「?」,
补一句原因;复盘列表把 Void 念成「这盘没有判出胜负」,规范之外的写法仍原样念。

EOF
)"
```

---

### Task 8a: X10-a 前端 —— 实体盘「等待拿回棋子」弹层给出口（M2）

**Files:**
- Modify: `katrain/web/ui/src/kiosk/components/physical/EngineMoveErrorDialog.tsx:172-182`（waiting 分支）
- Test: `katrain/web/ui/src/kiosk/__tests__/EngineMoveErrorDialog.test.tsx`（`describe` 收尾 `});` 之前追加）

**Interfaces:**
- Consumes: 对话框既有的 `onResign` prop 与 `handleResign`（`EngineMoveErrorDialog.tsx:134-136`）；测试文件既有的 `base`、`baseError`、`cancel` mock。
- Produces: 无新接口。等待态认输之后后端怎么收尾（放暂停、熄灯、残子不复活）在 Task 8b，两个 Task 文件不相交。

- [ ] **Step 1: 写测试（先红）**

`EngineMoveErrorDialog.test.tsx` 最后一个 `it` 之后、`describe` 收尾 `});` 之前插入：

```tsx
  // M2(2026-07-11 登记):等待态原来一颗键都没有、点背景也关不掉,而解除条件是「识别盘面与数字盘面
  // 整盘一致连续 N 帧」—— 反光、手影、识别不到盘面时会一直挂住,只能离开围棋应用。
  it('等待拿回棋子时也有出口:认输走页面的确认流,弹层自己不关', async () => {
    cancel.mockResolvedValueOnce({ ok: true, awaiting_removal: true });
    const onResign = vi.fn();
    render(<EngineMoveErrorDialog {...base} onResign={onResign} error={baseError} />);

    fireEvent.click(screen.getByText('拿回棋子'));
    expect(await screen.findByText('等待拿回棋子')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '认输' }));
    expect(onResign).toHaveBeenCalledTimes(1);
    expect(screen.getByText('等待拿回棋子')).toBeInTheDocument();
  });
```

- [ ] **Step 2: 跑，确认红**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx vitest run src/kiosk/__tests__/EngineMoveErrorDialog.test.tsx`
Expected: 「等待拿回棋子时也有出口…」FAIL（`getByRole('button', { name: '认输' })` 找不到按钮）；其余 PASS。

- [ ] **Step 3: 改 `EngineMoveErrorDialog.tsx` waiting 分支**

`:172-182`

```tsx
        ) : (
          <>
            <DialogTitle>{t('Waiting for stone removal', '等待拿回棋子')}</DialogTitle>
            <DialogContent sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <CircularProgress size={20} />
              <Typography variant="body2" color={emphasized ? 'warning.main' : 'text.primary'}>
                {t('Please remove the stone at {coord}', '请拿回 {coord} 处的棋子').replace('{coord}', coordLabel)}
              </Typography>
            </DialogContent>
          </>
        )}
```

替换为

```tsx
        ) : (
          <>
            <DialogTitle>{t('Waiting for stone removal', '等待拿回棋子')}</DialogTitle>
            <DialogContent sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <CircularProgress size={20} />
              <Typography variant="body2" color={emphasized ? 'warning.main' : 'text.primary'}>
                {t('Please remove the stone at {coord}', '请拿回 {coord} 处的棋子').replace('{coord}', coordLabel)}
              </Typography>
            </DialogContent>
            {/* M2(2026-07-11 登记):等待态原来一颗键都没有、点背景也关不掉,而解除条件是
                「识别盘面与数字盘面整盘一致连续 N 帧」—— 反光、手影、识别不到盘面时会一直挂住。
                给一个始终成立的出口:认输,走页面既有的确认流(与出错态同一个 handleResign,
                同样不自行关弹层 —— 确认之后由 GamePage 清掉)。 */}
            <DialogActions>
              <Button onClick={handleResign} color="error">
                {t('Resign', '认输')}
              </Button>
            </DialogActions>
          </>
        )}
```

- [ ] **Step 4: 跑测试与类型检查**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx vitest run src/kiosk/__tests__/EngineMoveErrorDialog.test.tsx src/kiosk/__tests__/GamePageEngine.test.tsx && npx tsc -b
```
Expected: 全 PASS；`tsc -b` 退出 0。

- [ ] **Step 5: 变异验证（不提交）**

把 Step 3 新加的 `<DialogActions>…</DialogActions>` 整块临时删掉，重跑 `npx vitest run src/kiosk/__tests__/EngineMoveErrorDialog.test.tsx`，Expected：「等待拿回棋子时也有出口…」红；还原后全绿。

- [ ] **Step 6: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && git add katrain/web/ui/src/kiosk/components/physical/EngineMoveErrorDialog.tsx katrain/web/ui/src/kiosk/__tests__/EngineMoveErrorDialog.test.tsx && git commit -m "$(cat <<'EOF'
fix(kiosk-physical-play): 等待拿回棋子的弹层给出口 —— 识别对不上时永远挂住

M2(2026-07-11 登记):星阵实体盘局网络出错后选「拿回棋子」,等待态没有任何按钮也关不掉,
解除条件是识别盘面与数字盘面整盘一致连续 N 帧,反光 / 手影时会一直挂住。
加一颗「认输」,走页面既有确认流(与出错态同一个 handleResign,弹层不自行关)。

EOF
)"
```

---

### Task 8b: X10-a 后端 —— 终局时释放恢复暂停并熄灯（M4）；等待态认输后盘上残子不复活

**Files:**
- Modify: `katrain/web/core/physical_play_orchestrator.py:293-298`（`_run` 循环开头）、`:407-412`（`_complete_awaiting_removal` 收尾之后新增方法）
- Test: `tests/test_physical_play_orchestrator.py:664`（`def led_calls_for(orch):` 之前插入一个 class）
- Test: `tests/test_engine_physical_integration.py`（文件末追加 Case 7 真栈用例）

**Interfaces:**
- Consumes: 编排器既有的 `clear_engine_error()`、`clear_awaiting_removal()`、`_apply_points(points)`、`_latest_state`、`PAUSE_REASON_ENGINE_ERROR` / `PAUSE_REASON_AWAITING_REMOVAL` / `PAUSE_REASON_LAG`；`tests/test_physical_play_orchestrator.py` 既有的 `_orch(**cfg)`、`state(stones, end_result=None)`、`FakeLed`、`FakeVision`；`tests/test_engine_physical_integration.py` 既有的 `_build_stack(genmove_side_effect=…, engine_recovery_config=…)`、`_vision_move`、`_main_line`、`_wait_until(predicate, timeout=2.0)`（`:297`）、`CommandType`、`EngineRecoveryConfig`、`EngineGameConfig`、`log`；Task 5b 的视觉入口路由（放掉暂停之后残子被再确认 ⇒ gateway 回 `game_ended`、不重新 arm）。
- Produces: `PhysicalPlayOrchestrator._release_recovery_on_game_end(self) -> bool`。

放掉暂停会恢复识别——这正是 Case 7 要钉住的：「拿回棋子」等待态存在的前提就是那颗子还在盘上，认输后 `_apply_points([])` 清掉 remove 灯的遮罩（`vision/worker.py:280-283`）、识别恢复，worker 会把它再确认一次。没有 Task 5b 的路由，它会在终局节点下面长出新节点（Step 6 第 3 条变异实跑证实）。**所以 8b 必须排在泳道 C 的 5b 之后。**

- [ ] **Step 1: 写测试（先红）**

(a) `tests/test_physical_play_orchestrator.py` 在 `def led_calls_for(orch):`（`:664`）之前插入——即把

```python
def led_calls_for(orch):
```

替换为

```python
class TestRecoveryReleasedOnGameEnd:
    """X10 / M4:恢复框里认输(出错态或等待态都能认输)之后,engine_error / awaiting_removal 两个暂停
    会让 `_run` 跳过 `_tick_once` —— 而「终局清灯」只在 `_tick_once` 里 ⇒ 灯一直亮到离开对局页。"""

    @staticmethod
    def _lit(**cfg):
        orch, led, vision, _ = _orch(**cfg)
        orch.on_game_state(state([["B", [3, 15], None, 1]]))  # GTP y=15 -> vision row 3
        orch._tick_once()
        assert led.calls[-1] == ("set_points", [{"row": 3, "col": 3, "color": "black"}])
        return orch, led, vision

    def test_run_loop_releases_engine_error_and_clears_lamps_when_the_game_ends(self):
        """走真的 `_run` 循环 —— 证的是「接进了循环」,不只是那个方法本身对。
        变异记录:删掉 `_run` 里那一段调用 → 这条红(暂停原因还在、最后一次 LED 调用仍是 set_points)。"""
        orch, led, vision = self._lit(tick_interval_s=0.01)
        orch.enter_engine_error((3, 15), "tok-1")
        orch.on_game_state(state([["B", [3, 15], None, 1]], end_result="W+R"))

        async def run():
            task = asyncio.create_task(orch._run())
            loop = asyncio.get_running_loop()
            deadline = loop.time() + 1.0
            while orch._pause_reasons and loop.time() < deadline:  # 轮询到条件,不赌一个固定时长
                await asyncio.sleep(0.01)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        asyncio.run(run())

        assert orch._pause_reasons == set()
        assert orch._suspended is False
        assert vision.paused is False
        assert led.calls[-1] == ("clear",)

    def test_awaiting_removal_is_released_when_the_game_ends(self):
        orch, led, vision = self._lit()
        orch.enter_engine_error((3, 15), "tok-1")
        orch.enter_awaiting_removal((3, 15))
        orch.on_game_state(state([["B", [3, 15], None, 1]], end_result="W+R"))

        assert orch._release_recovery_on_game_end() is True
        assert orch._awaiting_removal_context is None
        # `_lit` 那一 tick 盘上没摆子 ⇒ 已经挂着「欠一手」的 lag。lag 不归这里放:下一次普通 tick
        # 见终局会 `_set_caught_up(True)` 清掉它(上一条走真循环的用例证的正是这一步),
        # 而 lag 单独在时不挂起 tick。直接调方法时它还在 —— 写 `== set()` 会红。
        assert orch._pause_reasons == {PhysicalPlayOrchestrator.PAUSE_REASON_LAG}
        assert orch._suspended is False
        assert led.calls[-1] == ("clear",)

    def test_nothing_is_released_while_the_game_is_still_running(self):
        orch, led, _ = self._lit()
        orch.enter_engine_error((3, 15), "tok-1")

        assert orch._release_recovery_on_game_end() is False
        assert PhysicalPlayOrchestrator.PAUSE_REASON_ENGINE_ERROR in orch._pause_reasons
        assert led.calls[-1] == ("set_points", [{"row": 3, "col": 3, "color": "black"}])


def led_calls_for(orch):
```

(b) `tests/test_engine_physical_integration.py` 文件末尾追加（所需 import 与 helper 文件里都已有）：

```python
# --- Case 7: 等待拿回棋子时认输,那颗子还在盘上 (plan 审查第 1 轮 F1) ------------------------


class TestCase7ResignWhileWaitingForRemoval:
    @pytest.mark.asyncio
    async def test_leftover_stone_after_a_waiting_state_resign_does_not_reopen_the_game(self):
        """真栈走一遍这条路:隧道断 → 恢复框 → 拿回棋子(等待态)→ 认输 → 编排器的真循环放掉暂停、识别恢复 →
        worker 把盘上没拿走的那颗子再确认一次。棋树、终局结果都不许变,也不许重新 arm。
        等待态存在的前提就是那颗子还在盘上 —— 这不是边角。"""

        async def tunnel_down(**kwargs):
            raise RuntimeError("tunnel down")

        stack = _build_stack(
            genmove_side_effect=tunnel_down,
            engine_recovery_config=EngineRecoveryConfig(engine_move_max_attempts=2),
        )
        # 生产里 connect_platform 挂上;没有它 adapter 的 game_ended 没人接,认输后平台上下文不会被摘,测的就不是生产形状。
        stack.pm._setup_callbacks(stack.adapter)
        config = EngineGameConfig(level=1100, human_color="B", handicap=0)
        session_id = await stack.pm.start_engine_game("golaxy", config, user_id=1)
        session = stack.sm.get_session(session_id)
        stack.orch.on_bind(session_id, session)
        stack.vision.bind_session(session_id)
        worker = stack.vision._worker
        stone = _vision_move(3, 3, "B")
        recovery = {
            PhysicalPlayOrchestrator.PAUSE_REASON_ENGINE_ERROR,
            PhysicalPlayOrchestrator.PAUSE_REASON_AWAITING_REMOVAL,
        }
        try:
            for _ in range(2):  # 第二次失败到阈值 → engine_error
                await _handle_confirmed_move(stack.app, stack.vision, session_id, stone, log)
            episode = stack.tracker.consume(stack.tracker.active_episode.recovery_token)  # /engine-move/cancel
            stack.orch.enter_awaiting_removal(episode.coords)

            await stack.gateway.resign(session_id, 1)  # /api/resign 的平台分支
            result = session.katrain.game.end_result
            assert result
            assert not stack.gateway.is_platform_game(session_id)
            stack.orch.on_game_state(session.katrain.get_state())
            await _wait_until(lambda: not (recovery & stack.orch._pause_reasons))  # 真 `_run` 循环放掉暂停
            pause_cmds = [
                c for c in worker.commands if c in (CommandType.PAUSE_DETECTION, CommandType.RESUME_DETECTION)
            ]
            assert pause_cmds[-1] == CommandType.RESUME_DETECTION  # 识别确实恢复了 —— 下面那一手不是凭空造的

            delay = await _handle_confirmed_move(stack.app, stack.vision, session_id, stone, log)

            assert _main_line(session) == []
            assert session.katrain.game.end_result == result
            assert delay == 0.0  # 不重新 arm:重新 arm 的那条分支返回 0.5
        finally:
            await stack.orch.shutdown()
```

- [ ] **Step 2: 跑，确认红**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && uv run pytest tests/test_physical_play_orchestrator.py tests/test_engine_physical_integration.py -q`
Expected: `4 failed, 53 passed`（审查时在 Task 6 之后的树上实跑）：
- `TestRecoveryReleasedOnGameEnd::test_run_loop_releases_engine_error_and_clears_lamps_when_the_game_ends` —— `AssertionError: assert {'engine_error', 'lag'} == set()`
- `…::test_awaiting_removal_is_released_when_the_game_ends`、`…::test_nothing_is_released_while_the_game_is_still_running` —— `AttributeError: 'PhysicalPlayOrchestrator' object has no attribute '_release_recovery_on_game_end'`
- `TestCase7ResignWhileWaitingForRemoval::test_leftover_stone_after_a_waiting_state_resign_does_not_reopen_the_game` —— `AssertionError: condition not met within 2.0s`（真 `_run` 循环没有放掉暂停；这一条红只说明「还没接上」，承重的那一红在 Step 6 第 3 条）

- [ ] **Step 3: 改编排器**

(i) `_run`（`:293-298`）

```python
    async def _run(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.config.tick_interval_s)
                if self._session_id is None:
                    continue
```

替换为

```python
    async def _run(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.config.tick_interval_s)
                if self._session_id is None:
                    continue
                # X10 / M4: 终局要先于两个恢复暂停被看见 —— 下面两支(awaiting_removal 分派、
                # `_suspended` 早退)都不看 end_result,放着不管灯会一直亮到离开对局页。
                try:
                    self._release_recovery_on_game_end()
                except Exception as e:  # defensive: LED problems must not kill the loop
                    logger.warning("physical-play game-end release error: %s", e)
```

(ii) `_complete_awaiting_removal` 收尾（`:407-412`）

```python
        self.resync()
        self.clear_awaiting_removal()
        self._manager.broadcast_to_session(
            self._session_id,
            {"type": "physical_engine_error_resolved"},
        )
```

替换为

```python
        self.resync()
        self.clear_awaiting_removal()
        self._manager.broadcast_to_session(
            self._session_id,
            {"type": "physical_engine_error_resolved"},
        )

    def _release_recovery_on_game_end(self) -> bool:
        """X10 / M4:局已经结束,还挂着引擎出错 / 等待拿回的暂停 ⇒ 放掉并熄灯。

        终局之后这两个恢复流程都没有意义:没有下一手要重试,也没有下一手要等盘面对齐。
        放掉之后普通 tick 接手,它见 `end_result` 会保持熄灯(`_tick_once`)。hint 暂停不归这里
        (它有自己的超时)。返回是否放掉了。

        放掉会恢复识别 ⇒ 盘上没拿走的子会被再确认一次:星阵局由 server 的视觉路由交给 gateway 判「已经结束」
        (`is_platform_engine_session`,Task 5b),不会落进本地树。"""
        state = self._latest_state
        if not state or not state.get("end_result"):
            return False
        if (
            self.PAUSE_REASON_ENGINE_ERROR not in self._pause_reasons
            and self.PAUSE_REASON_AWAITING_REMOVAL not in self._pause_reasons
        ):
            return False
        self.clear_engine_error()
        self.clear_awaiting_removal()
        self._apply_points([])
        return True
```

- [ ] **Step 4: 格式化、跑测试**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && uv run black -l 120 katrain/web/core/physical_play_orchestrator.py tests/test_physical_play_orchestrator.py tests/test_engine_physical_integration.py && uv run pytest tests/test_physical_play_orchestrator.py tests/test_physical_play_recovery.py tests/test_engine_physical_integration.py tests/test_vision_move_poller.py tests/test_vision_engine_move_recovery_endpoints.py -q
```
Expected: black `3 files left unchanged`；pytest `91 passed`（审查时实跑）。

- [ ] **Step 5: 看一眼这条路在真栈上的全貌（不改代码）**

Case 7 走的是：隧道断两次 → `engine_error` → 取消（`consume` + `enter_awaiting_removal`）→ `gateway.resign`（真 adapter 摘掉上下文）→ `on_game_state` 推终局 → 真 `_run` 循环放掉两个恢复暂停、最后一条暂停类命令是 `RESUME_DETECTION` → 再确认同一颗子 → 棋树、`end_result` 都不变，返回 `0.0`（`_handle_confirmed_move` 里拒绝之后重新 arm 的分支都返回 `0.5`，栈上有编排器时成功路径本来就不 arm，所以 `0.0` 就是「没重新 arm」的判据）。**不数** `SET_EXPECTED_BOARD`：建局与认输挨得近，`WebKaTrain.update_state` 的 250 ms 节流（`interface.py:805-822`）会起后台线程补发一次状态，经编排器包过的回调多推一条期望盘面；它落在「数之前」与「断言」之间时用例就红，而且这个计数区分不了是不是重新 arm。若 Step 4 里它是绿的而你看不出它为什么绿，回到 Task 5b 的「为什么有这个 Task」。

- [ ] **Step 6: 变异验证（不提交）**

逐条临时改、跑 Step 2 那条命令、还原（审查时逐条实跑）：

| 变异 | 期望变红 |
|---|---|
| 删掉 `_run` 里新加的 `try: self._release_recovery_on_game_end() …` 四行 | `test_run_loop_releases_engine_error_and_clears_lamps_when_the_game_ends`（`{'engine_error', 'lag'} == set()`）、Case 7（`condition not met within 2.0s`） |
| `_release_recovery_on_game_end` 里删掉 `self._apply_points([])` | `test_awaiting_removal_is_released_when_the_game_ends`（最后一次 LED 调用仍是 `set_points`） |
| `server.py` 视觉入口路由退回 `if gateway and gateway.is_platform_game(session_id):`（撤掉 Task 5b 那一处） | **Case 7 `AssertionError: assert [('B', (3, 3))] == []`** —— 这一红证明的正是「8b 放掉暂停 + 清遮罩」造出了残子复活这条路、而 5b 的路由把它堵住了 |

- [ ] **Step 7: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && git add katrain/web/core/physical_play_orchestrator.py tests/test_physical_play_orchestrator.py tests/test_engine_physical_integration.py && git commit -m "$(cat <<'EOF'
fix(kiosk-physical-play): 终局时释放恢复暂停并熄灯 —— 恢复框里认输后灯一直亮到离开页面

M4:engine_error / awaiting_removal 暂停会让 _run 跳过 _tick_once,而终局清灯只在那里 ⇒
恢复框里认输后灯一直亮到离开页面。每个 tick 先检查「已终局且挂着这两个暂停」→ 放掉并熄灯。
放掉会恢复识别,等待态里没拿走的那颗子会被再确认一次:新增 Case 7 真栈用例钉住它不改棋树、
不改结果、不重新 arm(靠 Task 5b 的视觉路由;撤掉那一处 Case 7 当场红)。
(2026-07-11 登记的 follow-up;M3/I2 需上板,本次不动。)

EOF
)"
```

---

### Task 9: 收口闸 —— 两套构建、全量闸、真浏览器、四图、给 Fan 的确认清单

> 在**本 worktree**、所有 Task（含合并回来的泳道提交）之后串行做。本 Task 里的 :5173、构建与全量测试不许和别的步骤并行。

**Files:**
- 重取：`superpowers/tracks/kiosk-go-shell-align/visual/01-play/1024x600/*`、`superpowers/tracks/kiosk-go-shell-align/visual/10-platform-game/1024x600/*`
- 无源码改动（若这里发现问题，回到对应 Task 修，别在本 Task 里顺手改）。

**Interfaces:**
- Consumes: Task 0 的 `${TMPDIR}/kgcp-gate.py`、`kgcp-vitest-before.*`、`kgcp-pytest-before.*`、`kgcp-eslint-before.json`、`kgcp-user-config.json`；Task 4 改好的两份 Playwright spec；Task 7 的 `data-testid="endgame-no-result"`。
- Produces: 两屏四图存档；`${TMPDIR}/kgcp-void-card.png`；一份贴给 Fan 的确认清单（写在最终回报里，不落文件）。

- [ ] **Step 1: 类型检查、两套构建、lint 与基线同一组**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx tsc -b && npm run build && npm run build:kiosk-2d; echo "build exit=$?"
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && K="${TMPDIR:-/tmp}/kgcp" && npx eslint --format json src/kiosk/pages/GamePage.tsx src/kiosk/pages/PlayPage.tsx src/kiosk/pages/PlatformLobbyPage.tsx src/kiosk/components/game/GameControlPanel.tsx src/kiosk/components/report/reviewPresentation.ts src/kiosk/components/physical/EngineMoveErrorDialog.tsx > "$K-eslint-after.json"; python3 - "$K-eslint-before.json" "$K-eslint-after.json" <<'EOF'
import collections, json, os, sys
def rules(p):
    return collections.Counter((os.path.basename(f["filePath"]), m.get("ruleId")) for f in json.load(open(p)) for m in f["messages"])
before, after = rules(sys.argv[1]), rules(sys.argv[2])
print("新增:", dict(after - before) or "无", "| 消失:", dict(before - after) or "无")
sys.exit(1 if after - before else 0)
EOF
```
Expected: `build exit=0`（`tsc -b` 无输出；`npm run build` 成功；`build:kiosk-2d` 成功且 `verify:kiosk-2d` 报 clean）；eslint 比较打印 `新增: 无 | 消失: 无` 并退出 0。比的是「(文件, 规则) 的多重集合」，不是条数——条数相等挡不住「修掉一条旧的、新增一条新的」。基线那 1 error / 4 warnings（`PlayPage.tsx` 的 `react-hooks/set-state-in-effect`、`GamePage.tsx` 的 `exhaustive-deps`）不在本轮修；`npm run build` 不跑 lint，它不挡构建。

- [ ] **Step 2: 前端全量闸**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && git status --porcelain
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && K="${TMPDIR:-/tmp}/kgcp" && printf '%s\n' 'src/kiosk/__tests__/GamePageEngine.test.tsx > GamePage engine mode > 停一手/认输 stay enabled in engineMode (galaxy-reference: no blunt engineMode disable)' > "$K-vitest-renamed.txt" && rm -f "$K-vitest-after.exit" "$K-vitest-after.log" "$K-vitest-after.json" && npx vitest run --reporter=default --reporter=json --outputFile.json="$K-vitest-after.json" > "$K-vitest-after.log" 2>&1; echo $? > "$K-vitest-after.exit"; python3 "$K-gate.py" vitest after "$K-vitest-renamed.txt"
```
Expected: 第一条无输出（全量 pytest 还没跑，`engine_game_state.json` 夹具是干净的——`GamePageEngine.test.tsx` 读它，被改写过就先 `git checkout --` 再跑）；闸打印「新增失败」「没跑到」「没执行」三段都为空、`闸绿`。允许清单里只有一条：Task 4 把那条用例改写成了「星阵人机没有停一手和数子;认输照旧走确认框」（Task 3、Task 7 改写的用例沿用了原名）。闸红时逐条看是不是本轮造的（进程级共享状态、mock 漏 `isAuthenticated`），回对应 Task 修；不许按「文件名看着无关」放过；「没执行」红的处理同 Step 3。

- [ ] **Step 3: 后端全量闸 + 格式**

Run（先看有没有别的赛道在跑全量，有就等它结束）:
```bash
ps -axo pid,command | grep -E '[p]ytest tests|[v]itest run'
```
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && K="${TMPDIR:-/tmp}/kgcp" && rm -f "$K-pytest-after.exit" "$K-pytest-after.log" "$K-pytest-after.xml" && CI=true uv run pytest tests -q -rfE --junitxml="$K-pytest-after.xml" > "$K-pytest-after.log" 2>&1; echo $? > "$K-pytest-after.exit"; python3 "$K-gate.py" pytest after; git status --porcelain; cmp -s ~/.katrain/config.json "$K-user-config.json" && echo user-config-unchanged
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && uv run black -l 120 --check katrain/web/interface.py katrain/web/platforms/gateway.py katrain/web/api/v1/endpoints/vision.py katrain/web/core/physical_play_orchestrator.py katrain/web/core/repository.py tests/web_ui/test_user_game_cloud_owner.py tests/platforms/test_engine_game_ledger.py tests/platforms/test_engine_game_ledger_e2e.py tests/platforms/test_engine_gateway.py tests/platforms/test_engine_integration.py tests/test_vision_move_poller.py tests/test_vision_engine_move_recovery_endpoints.py tests/test_physical_play_orchestrator.py tests/test_engine_physical_integration.py; echo "black-check exit=$?"; echo "server.py hunks=$(uv run black -l 120 --diff katrain/web/server.py | grep -c '^@@')"; echo "remote_client.py hunks=$(uv run black -l 120 --diff katrain/web/core/remote_client.py | grep -c '^@@')"; echo "sync_worker.py hunks=$(uv run black -l 120 --diff katrain/web/core/sync_worker.py | grep -c '^@@')"
```
Expected:
- 闸 `闸绿`：「新增失败」「没跑到」「没执行」都为空。
- **闸红于「新增失败」**：任一完整运行的 `.new` 非空就保持红；不取 `after` / `after2` 交集。按用例名聚焦重跑，保留原失败日志。只有该用例本来就在 Task 0 的基线失败集合，或在基线提交上同环境聚焦重跑也失败 / 抖动（记录日志与提交号），才可判为基线问题；新用例基线不存在、仅下一轮转绿、聚焦重跑跳过，都不足以放行。解释不了的间歇失败保持未解决，在最终报告如实列出；修完对应 Task 后重跑全量闸。
- **闸红于「没执行」**：单独处理，不按抖动放行。检查本轮的 skip / todo / pending / xfail、`.only` 与环境漂移；恢复真实执行后重跑。允许清单只放 Task 4 改名的那一条，不拿它放行新跳过。
- `git status --porcelain` 只可能列出 `katrain/config.json` 与 `katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json`（它们不属于本轮改动）：`git checkout --` 还原；列出别的就停下查。没打印 `user-config-unchanged` 时照 Task 0 Step 5 的规则处理。
- `black-check exit=0`；`server.py hunks=1`、`remote_client.py hunks=1`、`sync_worker.py hunks=1`，都只落在各自基线旧折行处。**0 也要查**（可能是 black 未运行），多于 1 则检查本轮 hunk。

- [ ] **Step 4: 真浏览器几何（屏 05 / 屏 10 同文件）**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && L=$(lsof -nP -iTCP:5173 -sTCP:LISTEN -t | head -1); if [ -n "$L" ] && [ "$(lsof -a -p "$L" -d cwd -Fn | sed -n 's/^n//p')" != "$PWD" ]; then echo "5173 上是别的树的 dev server(pid $L),等它结束再跑"; else npx playwright test --config=playwright.visual.config.ts tests/kiosk-screen-05-game.spec.ts; echo "playwright exit=$?"; fi
```
Expected: `playwright exit=0`；控制台 `[10-platform-game]` 那行 `actionLabels` 为 `["认输"]`，`actionsBottom === railBottom`，`railOverflow <= 0`。打印「5173 上是别的树…」时不许杀那个进程，等它结束再跑同一条命令。

- [ ] **Step 5: `Void` 终局卡实运行预览（无设计稿参考，给 Fan 看一帧）**

这一态设计稿里没有，四图无参考图可比 ⇒ 按 CLAUDE.md 相称性取**一张真运行时截图**：
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && cat > "${TMPDIR:-/tmp}/kgcp-void-card.spec.ts" <<'EOF'
import { test } from '@playwright/test';
import { KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';
test.use({ viewport: KIOSK_VIEWPORT });
test('屏 10 · 星阵 AI 结束对局(Void)', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'preview');
    localStorage.setItem('katrain_language', 'cn');
    localStorage.setItem('kiosk_play_on_board', 'false');
  });
  const state = {
    game_id: 'void-preview', board_size: [19, 19], komi: 7.5, handicap: 0, ruleset: 'chinese', game_type: 'free',
    count_min_moves: 100, current_node_id: 1, current_node_index: 1,
    history: [{ node_id: 0, winrate: 0.5, score: 0, move: null, player: null }, { node_id: 1, winrate: 0.5, score: 0, move: 'D4', player: 'B' }],
    player_to_move: 'W', stones: [['B', [3, 3], null, 1]], last_move: [3, 3], prisoner_count: { B: 0, W: 0 },
    analysis: null, commentary: '', is_root: false, is_pass: false, end_result: 'Void', children: [], ghost_stones: [],
    platform_engine_color: 'W',
    players_info: {
      B: { player_type: 'player:human', player_subtype: '', name: '访客（你）', calculated_rank: '', periods_used: 0, main_time_used: 0 },
      W: { player_type: 'player:human', player_subtype: '', name: '星皮猴', calculated_rank: '2段', periods_used: 0, main_time_used: 0 },
    },
    note: '', ui_state: { show_children: false, show_dots: false, show_hints: false, show_policy: false,
      show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false },
  };
  await stubBackendStatics(page);
  await page.routeWebSocket('**/ws/**', () => {});
  await page.route('**/api/state**', (r) => r.fulfill({ json: { state } }));
  await page.route('**/api/v1/**', (r) => {
    const path = new URL(r.request().url()).pathname;
    if (path === '/api/v1/auth/me') return r.fulfill({ json: { id: 1, username: '访客', rank: '5段', credits: 0 } });
    // 与屏 10 四图同一套桩(`kiosk-screen-10-platform-game.fourup.spec.ts`):识别关着、几何 404。
    if (path === '/api/v1/vision/status') {
      return r.fulfill({ json: { enabled: false, camera_connected: false, pose_locked: false,
        sync_state: 'unbound', recognition_ready: false, led_connected: null, bound_session_id: null } });
    }
    if (path === '/api/v1/geometry/status') return r.fulfill({ status: 404, json: { detail: 'geometry disabled' } });
    return r.fulfill({ json: {} });
  });
  await page.goto('/kiosk/play/cross-platform/engine/game/void-preview');
  await page.waitForSelector('[data-testid="endgame-no-result"]');
  await page.screenshot({ path: `${process.env.TMPDIR ?? '/tmp'}/kgcp-void-card.png` });
});
EOF
L=$(lsof -nP -iTCP:5173 -sTCP:LISTEN -t | head -1); if [ -n "$L" ] && [ "$(lsof -a -p "$L" -d cwd -Fn | sed -n 's/^n//p')" != "$PWD" ]; then echo "5173 上是别的树的 dev server(pid $L),等它结束再跑"; else cp "${TMPDIR:-/tmp}/kgcp-void-card.spec.ts" tests/zz-kgcp-void-card.preview.spec.ts && npx playwright test --config=playwright.visual.config.ts tests/zz-kgcp-void-card.preview.spec.ts; echo "playwright exit=$?"; rm -f tests/zz-kgcp-void-card.preview.spec.ts; fi
```
Expected: `playwright exit=0`，生成 `${TMPDIR}/kgcp-void-card.png`；用 Read 看图：终局卡里徽标「?」下方有那句说明、没有被截断。截图路径记进 Step 9 给 Fan 的确认清单。**临时 spec 必须删掉、不提交**（`git status` 不应出现它）。

- [ ] **Step 6: 四图 —— 屏 01、屏 10 各跑两次，真比两次的实现图**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui
R=/Users/fan/Repositories/katrain-kiosk-go-cross-platform; V=$R/superpowers/tracks/kiosk-go-shell-align/visual; K="${TMPDIR:-/tmp}/kgcp"
cat > "$K-pxdiff.py" <<'EOF'
import sys
import numpy as np
from PIL import Image
a, b = (np.asarray(Image.open(p).convert("RGB"), dtype=int) for p in sys.argv[1:3])
d = np.abs(a - b).max(axis=2) > 0
ys, xs = d.nonzero()
print(f"{sys.argv[3]}: changed={int(d.sum())} bbox=" + (f"x{xs.min()}-{xs.max()},y{ys.min()}-{ys.max()}" if d.any() else "none"))
EOF
for s in 01-play 10-platform-game; do
  n=${s%%-*}; img="$V/$s/1024x600/$s--implementation.png"
  git -C $R show "HEAD:superpowers/tracks/kiosk-go-shell-align/visual/$s/1024x600/$s--implementation.png" > "$K-head-$s.png"
  for run in 1 2; do
    L=$(lsof -nP -iTCP:5173 -sTCP:LISTEN -t | head -1)
    if [ -n "$L" ] && [ "$(lsof -a -p "$L" -d cwd -Fn | sed -n 's/^n//p')" != "$PWD" ]; then echo "5173 上是别的树的 dev server(pid $L),停下等"; break 2; fi
    npx playwright test --config=playwright.visual.config.ts tests/kiosk-screen-$n-*.fourup.spec.ts > "$K-fourup-$s-$run.log" 2>&1; echo "$s run$run playwright exit=$?"; grep '\[fourup' "$K-fourup-$s-$run.log"
    cp "$img" "$K-run$run-$s.png"
  done
  $R/.venv/bin/python "$K-pxdiff.py" "$K-run1-$s.png" "$K-run2-$s.png" "$s 两次运行之间(抖动底)"
  $R/.venv/bin/python "$K-pxdiff.py" "$K-head-$s.png" "$K-run2-$s.png" "$s 提交前 vs 本轮"
done
cd $R && git status --short superpowers/tracks/kiosk-go-shell-align/visual/
```
Expected: 两屏各两行 `playwright exit=0` 与 `[fourup …] both=… refOnly=… implOnly=…`（那几个数是**与参考图**的边缘计数，不是两次运行之间的差）；每屏两行 pxdiff：「两次运行之间」是本屏自己的抖动底（屏 10 canvas 盘约 4500 级、bbox 散落全图；屏 01 约 200 级以内），「提交前 vs 本轮」对内容真变了的屏要**高出抖动底一个量级且 bbox 聚在改动处**（屏 01 在野狐卡徽标，屏 10 在右栏动作区与开关排）。打印「5173 上是别的树…」时整段停下，等它结束再从头跑。

- [ ] **Step 7: 逐屏看四张图，判「内容变了」还是「只是抖动」**

用 Read 工具看每屏的 `--side-by-side.png`、`--diff.png` 与 `${TMPDIR}/kgcp-head-<屏>.png`（提交前的实现图）。逐项记：构图 · 几何间距 · 组件层级 · 字体 / 色彩 · 图标 · 文案 · 状态语义。
Expected（写死的期望，先写再看）：
- 屏 01：**只有**野狐卡徽标文字由「即将上线」变「暂不能对弈」；徽标没有溢出卡片右缘、没有换行；其余像素差为散落抖动。
- 屏 10：动作区由三颗变**一颗横跨整行的「认输」**（描边 + `--bad` 字色，不是实心红）；开关排右端由「数子要下满 100 手」变「暂不支持停一手、数子」，一行放得下、不被截断；动作区仍贴右栏底；其余不变。
- 任何一屏若「提交前 vs 本轮」与「两次运行之间」同量级、bbox 分散全图，`git checkout HEAD -- <该屏目录>` 还原，不提交。

- [ ] **Step 8: 提交四图（只提交内容真变了的屏，四张一起）**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && git add superpowers/tracks/kiosk-go-shell-align/visual/01-play/1024x600 superpowers/tracks/kiosk-go-shell-align/visual/10-platform-game/1024x600 && git commit -m "$(cat <<'EOF'
chore(kiosk-go): 重取屏 01 / 屏 10 四图 —— 野狐徽标文案、星阵局动作区只剩认输

屏 01 野狐卡徽标「即将上线」→「暂不能对弈」(与屏 07 同一个 key);屏 10 动作区撤掉停一手 / 数子,
开关排右端改写「暂不支持停一手、数子」。各跑两次、真比两次的实现图取抖动底,只提交内容变化的屏。

EOF
)"
```

- [ ] **Step 9: 回报给 Fan 的确认清单（不落文件，写进最终回报）**

逐条列出，等 Fan 明确确认；未确认前不得宣称视觉通过、不得合并：
1. 屏 01 四图：`superpowers/tracks/kiosk-go-shell-align/visual/01-play/1024x600/01-play--side-by-side.png`（野狐徽标文案）。
2. 屏 10 四图：`…/10-platform-game/1024x600/10-platform-game--side-by-side.png`——**一颗「认输」横跨动作区是否可接受**；不接受的备选是「停一手 / 数子留着但灰 + 同一句右端说明」（改 Task 4 Step 3 一处即可）。
3. 星阵 AI 无胜负终局卡：`${TMPDIR}/kgcp-void-card.png`（设计稿无此态，只有实现截图）；以及「以 `Void` 记无胜负」这条裁定本身（备选：记成人中盘胜）。
4. 两条随审查补上的行为（工程裁定，Fan 可推翻）：① 隧道等待期间人已认输、AI 的回复迟到时，认输结果保留、那一手不落，`/api/move` 回 200 + 认输后的终局态（不回 409——409 在对局屏上是一句不会自动消失的「AI 连接出错」）；② 恢复框「重试」时星阵结束了这盘，弹层按「重试成功」静默关闭、由终局卡上的无胜负说明行说明原因，这盘记在**会话主人**名下（共用盒子上按「重试」的不一定是开局的人，归属规则挂在 X11 下）。
5. Task 6b 的 X11 临时行为：平台连接仍全局；棋谱按会话主人保护，盒子换人时不往后来者云库写，先存主人本机库并等待主人会话下次同步。仅换回主人不立即触发同步，在线云端列表此前可能暂看不到这盘；非严格部署里仍有未绑定整机凭据直发的既有风险（prd §5）。Fan 是否接受这段临时口径，以及平台账号最终归谁，均待确认。
6. 合并提示（给之后做合并的人，见 prd §6.0 第 1 条）：本分支与对弈·AI 谁后合并，谁就按那条规则把星阵落账收进 `_finish_ended_game`，并以 `tests/platforms/test_engine_game_ledger_e2e.py` 三条全绿为验收。
7. 上板清单（严格盒端构建部署到 RK3562 后，一次只跑一家）：
   - X7：星阵人机局角标出数字；按支招出候选圈；实体盘模式下支招白灯亮。
   - X8：连星阵后回屏 01，星阵卡绿点亮、写「已连接 · 人机对弈」，一步进人机开局。
   - N13：下一盘星阵人机并认输 → 屏 19 历史对局出现「vs [golaxy] …」、结果「你(黑)中盘负」，能送复盘；断网认输 → 本地有行、联网后同步上云。
   - X10-a：拔网线造出恢复框 → 拿回棋子 → 等待态认输 → 弹层关、终局卡出、盘上灯灭；**不拿走那颗子，等 5 秒，屏上仍是终局卡**。
   - X9-b：观察项（需星阵 AI 真的停手 / 认输，无法按需触发）。

---

## Self-Review

**1. Spec 覆盖（prd §3 逐条）**

| PRD 条目 | 验收要点 | Task |
|---|---|---|
| X7 | 盒端两条请求照发；变异红；上板 | 1（上板在 9 Step 9） |
| X8 | 盒端拉状态、直达人机开局；登出夹具真形状；上板 | 2 |
| X1 | 野狐卡「暂不能对弈」；屏 01 四图 | 2、9 |
| X4-a | 确认框 + toast 含「不会回到这台盒子」 | 3 |
| X9-a | 面板无停一手 / 数子、`.ghint` 说明；屏 05 spec 屏 10 用例；屏 10 四图 | 4、9 |
| X9-b | 真栈 `Void`；`/api/move` 200 / 409 正对照；等待期间认输或换局后，迟到坐标、非落点、超时都不改终局 / 新局；结束之后落子 / 停一手 / 再认输都不落到本地树；终局卡说明行；上板观察 | 5、5b、7、9 |
| N13 | resign / move / 视觉 poller / 恢复框重试四处落账；OGS 正对照；helper 名字、source、判别位闸；真 `_RECORD_FN` 写入；端到端「真端点 → 写库恰好 1 行」3 条；共用盒子换人时在线与离线棋谱不串账，401 竞态不拿后来者 bearer 重试；`Void` 念成人话；上板 | 5b、6、6b、7、9 |
| X10-a | 等待态认输（8a）；编排器循环级释放 + 熄灯、未终局不释放、等待态认输后残子不复活的真栈用例（8b）；上板（含「不拿走那颗子，屏上仍是终局卡」） | 8a、8b、9 |

prd §4 的 X11 平台账号归属仍待 Fan 拍板；本轮只做 6b 的棋谱写库主人保护（另有未绑定凭据与身份切换竞态限制，见 X11 临时行为）。X4 主体 / X6 / X2 与 §5 后续条目没有任务。

**2. 占位与实跑证据**：全文扫描 `@@名字@@`、双花括号、TBD / TODO，片段无模板占位符。Task 5 / 5b / 6 / 8b 的第 1 轮片段在临时树实跑过；第 2 轮补的 Task 5 超时格是 8 failed → 24 passed，变异 `m5-6` / `m5-7` 各让目标格红。Task 6b 原三格是 2 failed / 1 passed → 3 passed，三种变异各红；401 身份切换新四格在旧 6b 守卫树先 3 failed / 4 passed，新闸后 7 passed，四个变异各红。闸脚本从 plan 正文提取 sha256 `2e4c3b05…2366`，真实报告与同形坏报告回放。源代码变动前要按各 Task 再留本次红绿与变异日志；本计划是权威文本，不再用旧生成脚本重写。

**3. 类型 / 命名一致性**：
- `end_without_result`（interface 命令，Task 5）↔ gateway 终局分支 `session.katrain("end_without_result")`（只在 `status == "live"` 时）↔ 测试 `commands[-1] == "end_without_result"`。
- `_submitted_position_status(session, game, node) -> "live" | "ended" | "replaced"`（Task 5）↔ gateway 成功、终局、普通异常三处调用都在 `with session.lock:` 内 ↔ 真栈迟到坐标 / 非落点 / 超时用例。
- `is_platform_engine_session(session)`（Task 5b，`gateway.py` 模块级）↔ `_is_ended_engine_game` ↔ server 三处路由 ↔ Task 6 helper 自闸与 `/api/resign` 落账分支 ↔ 参数化测试（含 MagicMock 格）↔ prd §6.0 第 1 条。
- `_record_platform_engine_game(session, app, user)`（Task 6；参数顺序同对弈·AI `_finish_ended_game(session, app, current_user)`）↔ `/api/move`、`/api/resign` 两处调用 ↔ 测试 `recorder.await_args.args[0] is session`、`args[2]` 是用户。
- `_record_platform_engine_game_off_request(session, app)`（Task 6）↔ `_handle_confirmed_move`、`vision.py` `retry_engine_move` 两处调用 ↔ 测试 `assert_awaited_once_with(session, app)`。
- `_session_owner(app, session) -> User | None` ↔ off-request helper ↔ 测试 `owner.id / owner.username`。
- `_record_ai_game(..., data_overrides=None)` ↔ helper 以关键字 `data_overrides=` 传 ↔ 测试读 `record.await_args.kwargs["data_overrides"]`。
- `_release_recovery_on_game_end()`（Task 8b）↔ `_run` 调用 ↔ 单测方法名、Case 7 经真 `_run` 循环。
- 前端 key：`platform:no_play_yet`（Task 2，复用屏 07）、`platform:challenge_sent` / `platform:challenge_ask_tail`（Task 3，改默认文案）、`game:golaxy_no_pass_count`（Task 4）、`game:engine_ended_no_result`（Task 7）、`review:no_result_line`（Task 7）——都不进 PO。
- `data-testid="endgame-no-result"`（Task 7 实现）↔ 单测与 Task 9 Step 5 预览 spec 同名。
- 恢复框重试的终局响应 `{"ok": true, "game_ended": true}`（Task 6）↔ 前端既有 `if (res.ok)` 关弹层（`EngineMoveErrorDialog.tsx:88-90`），前端不读 `game_ended`。

**4. 泳道不相交核对**：把 File Structure 表每一行与每个 Task 的 Files 段逐条对过——跨 Task 出现的文件只有 `GamePage.tsx`（1、7）、`GamePageEngine.test.tsx`（1、4、7）、`gateway.py` / `test_engine_gateway.py` / `test_engine_integration.py`（5、5b）、`server.py`（5、5b、6）、`test_engine_game_ledger.py`（5、5b、6）、`test_vision_move_poller.py`（5b、6），全部落在同一泳道（A 或 C）内；6b 的 repository / sync_worker / remote_client / 新测试都只在 C。B 的文件不出现在别的 Task 里；8a / 8b 拆开分别进 B / C。只「跑」不「改」的文件不影响不相交。

**5. 计划审查第 1 轮的发现落在哪**（逐条理由见文末「审查记录」）：F1 → 5b（路由 + gateway）+ 8b（Case 7）；F2 → 5（`_submitted_position_status` + 4 条可控异步真栈用例）；F3 → 6 (d)（重试端点）+ 5b（别处已结束后再重试）；F4 → 5b 判别位 + 6（参数顺序、off-request 单一漏斗、e2e）+ prd §6.0 第 1 条；F5 → 0（extras、结构化闸、还原）+ 9（同一个闸、基线聚焦对照规则、eslint 集合比较、black hunk 数、真比两次四图）；第 2 轮 R2-1 → 6b，R2-2 → 5，R2-3 → 0 / 9，R2-4 → 9 / prd §7。

---

## 审查记录(Codex 第 1 轮)

五条发现都判为成立（REAL），**没有 NOT_REAL**；下面是每条的去向、没照核验建议原样做的地方，以及同形清扫里没纳入本轮的条目。「实跑」= 在从 HEAD 开出的临时 worktree 里跑过；其余是读码。

**发现的去向**
- F1（等待态认输后恢复识别，残子重新开局）—— 实跑复现（真栈：主线 `[('B', (3, 3))]`、`end_result None`）。修在 5b（星阵会话按 `platform_engine_color` 路由给 gateway，gateway 在上下文已摘时回 `game_ended`、不重新 arm）+ 8b Case 7。**没采用**核验建议的 `_handle_confirmed_move` 内 `_game_is_over` 闸：它只堵视觉一个入口，而同一形状还出现在 gateway 三个 `ctx is None ⇒ 本地` 分支（`gateway.py:129-131`、`:281-283`、`:307-309`，恢复框重试就走这里）与 `/api/move`（`server.py:970`）、`/api/resign`（`:1885`）的路由上；5b 一处判别位把它们一起收掉，且不改非星阵实体盘局的双停语义（核验报告 §5.1 的风险）。F1 探针 A 说的「任何已绑定实体盘的本地局认输后多一颗子就复活」是既有缺陷、不经过本计划的改动（`engine_error` / `awaiting_removal` 只由平台 gateway 失败进入：`server.py:3126`、`api/v1/endpoints/vision.py:362`、`:389`），列入 prd §5。
- F2（迟到的终局回复结束另一盘 / 覆盖认输）—— 实跑复现四种时序。照核验建议并入 Task 5：锁内比「提交时的 Game 对象与节点对象」+ 节点是否已有结果，三态 `live / ended / replaced`，`game_ended` 只在被提交那盘确实结束时抛。
- F3（恢复框「重试」的终局漏账）—— 实跑复现（`{'ok': False, …, 'recovery_token': 'tok-fallback-1'}`）。并入 Task 6 (d)。与核验建议的差别：落账漏斗 `_record_platform_engine_game_off_request` 参数顺序定为 `(session, app)`（与其余 helper 一致把 session 放第一位）；核验报告 §6 的「别处已结束后再点重试 ⇒ 静默复活」不另写 6 行预检，由 5b 的 gateway 判断自动覆盖（重试端点拿到 `game_ended` 走同一个关弹层分支）。PRD §5 原来押后的 M1 因此两种形状都在本轮做掉。
- F4（统一收尾入口排除了所有星阵会话）—— 实跑复现（按 §6.0 字面合并 ⇒ e2e 3 条「实际 0 行」）。修在 prd §6.0 第 1 条（判别位、后合并方的机械适配规则、以 e2e 为合并验收、给对弈·AI 的同步清单）+ 本计划 5b / 6。与核验建议的差别：判别位放在 `gateway.py` 模块级（5b 的路由与 6 的落账共用一个，不在 `server.py` 另起一个 `_is_platform_engine_session`）；`_session_owner` 返回 `User(**row)` 而不是 `SimpleNamespace`——与对弈·AI `_on_game_ended_off_request` 的解析同形，合并后留一个即可，且 `_record_ai_game_locked` 的升降级分支会把 `current_user` 整个传给 `_enqueue_ladder_settlement_sync`（`server.py:1815-1817`），只带两个字段的替身不该流进共享收尾函数；e2e 的认输用例另断言「再认输一次不多写」。
- F5（失败集合比较会把收集失败判为通过）—— 核验报告 `verify-F5-baseline-gate.md` 在给定路径不存在；改由本轮编辑者用 2026-09-15 真实运行留下的产物回放闸的每条分支（见 Task 0 Step 3 的清单，实跑），并据控制方跑 Task 0 的实录补 extras 与两份被改写的已提交文件。修在 Task 0 / Task 9。

**同形清扫里没纳入本轮的条目**（清扫评为 high / medium 而本轮已覆盖的，见 Self-Review 第 5 条与 prd 各条验收，这里不重复）
- C1-8 开局第一手 AI 就回非落点：会话还没建，端点 500（`golaxy/adapter.py:755-758`、`manager.py:158`）——low，无局可记，不改。
- C1-11 / C1-12 / C2-7 `/api/timeout`、`/api/multiplayer/leave` 打到星阵会话：kiosk 不调，星阵人机局只由 kiosk 开（`platformEngineStart` 唯一调用者是 `src/kiosk/pages/PlatformEngineSetupPage.tsx`）——low，不改。
- C1-13 / C5-7 非严格部署的 `/api/v1/auth/logout` 对坐着的会话一律判负并 `record_multiplayer_game`（`auth.py:418-468`；严格盒端在 `:383-384` 直接 403）：只影响服务端网页登出时手上还有星阵会话的人，既有缺陷——列入 prd §5 后续项。
- C1-14 盒端换人后视觉仍绑着上一个人的会话：归 X11，已在 prd §4 X11 行说明本轮落账认会话主人。
- C1-15 / C1-16 / C1-17 会话过期、未下完就离开、局中登出星阵：弃局不是「下完的一盘」，不落账是对的。
- C2-10 / C2-11 / C3-9 终局后按「上一手 / 第一手」屏上看起来回到对局中：后端写入已由 5b 兜住（落子 / 再认输都回 `game_ended`、不改树不落账）；前端是否把终局后的翻看做成只读回看是 UI 决定——列入 prd §5。
- C2-12 / C2-13 / C2-14 `sgf/load`、`new-game`、`node/*`、`selfplay` 在星阵会话上：kiosk 星阵 UI 不暴露（`server.py:3022-3028` 同一裁决），迟到回复一侧已由 Task 5 的 `replaced` 兜住——不改。
- C2-19 编排器终局后不暂停识别：5b 之后残子被 gateway 拒绝且不重新 arm；改所有实体盘局的暂停语义与对弈·AI A20 相邻、还要定义终局后悔棋怎么解除——不改。
- C3-8 终局后按道具键弹连接出错类提示（`manager.py:272-277` 查不到上下文 404）——low，不改，记入 prd §5 同一行后续项。
- C3-12 `session.game_ended` 被节流回调延后置位：本轮的判据都读树（`end_result` / `end_state`）与建局判别位，不读它——不适用。
- C4-5 `test_engine_move_guards.py` 基线红 20 条，遮住 undo / redo / nav / ai-move 的回归：本轮不改这几个端点（`server.py:1005-1033`、`:1279-1339`），不修那个夹具。
- C4-14 / C4-17 / C5-3 / C5-9 / C5-10 / C5-12：清扫自己判为正对照或不可达。

---

## 审查记录(Codex 第 2 轮)

四条发现均成立，本轮修订到此收束；后续以本 plan 开发，不再开 plan 审查轮。

- R2-1（只传会话主人仍会把棋谱写进后来者云库）—— Task 6b 保护在线直发与 `create_user_game` 队列补传，身份不匹配时本机记主人名下并留 `pending`，不挡别人的项。真实 dispatcher / remote client / 本机库 / sync worker 的双用户测试在旧代码上 2 红 / 1 绿、加两处守卫后 3 绿，三种静态守卫变异各红。复核又实跑发现 401 等待中换人会拿后来者 bearer 重试，刷新途中换人会污染后来者 token；因此同 Task 加云端会话快照与队列回 `pending`，新四格在仅有静态守卫的 `wt-e3` 上 3 红 / 4 绿，补闸后 7 绿，四种变异各红。生产改动只在写库、队列与共用客户端的这条真实跨用户边界；X11 平台账号归属仍待 Fan 决定。未绑定整机凭据与主人重登不立即同步的限制写进 prd §4 / §5 与 Task 9 确认清单。
- R2-2（认输 / 换局后迟到隧道超时误报 `engine_error`）—— Task 5 普通异常出口也在锁内走 `live / ended / replaced` 三态闸。新增可控 `Retryable(ReadTimeout)` 格，在旧异常分支上随 Task 5 测试 8 红 / 16 绿，补闸后 24 绿；删「已认输」或「已换局」闸分别让 `m5-6` / `m5-7` 目标格红。已结束回 `game_ended`，换局回 `position_changed`，仅原局仍活着回 `engine_error`。
- R2-3（skip / todo 被结构化闸当作执行）—— Task 0 闸只把 passed / failed 算作执行，写 `.skip`；非基线轮新增未执行者红，旧闸基线缺 `.skip` 也红。新脚本正文 sha256 `2e4c3b05575b334d0c68274bf6855a16f2630be750c9db125fd87197b8172366`，从 plan 提取后校验；真实 pytest 3980 项 / Vitest 1730 项基线、同报告 after 为绿，旧执行项改 skip/todo 与新增未执行项为红；普通新增失败、suite 错、未处理异常、报告缺失 / 收集中断的同形报告也红。Global Constraints、Task 9 和 prd §7 同步三段闸口径。
- R2-4（`after ∩ after2` 放过新间歇回归）—— Task 9 与 prd §7 改为任一轮相对基线新增失败即保持红。仅「本来就在基线失败集合」或「基线提交同环境聚焦重跑也失败 / 抖动」可判为基线问题；下一轮转绿不构成证据。无法解释的间歇失败保持未解决并如实报告；skip / xfail 另走 R2-3 闸，不借抖动规则放行。
