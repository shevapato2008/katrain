# 围棋 kiosk · 训练营（kiosk-go-tsumego）交接说明

- 日期：2026-09-15
- 交接方：Claude Code 会话（额度用尽）→ 接手方：Codex
- 分支 / worktree：`feature/kiosk-go-tsumego` @ `/Users/fan/Repositories/katrain-kiosk-go-tsumego`
- 当前 HEAD：`99c72334`，基于 develop `bad0c1fb`。**未 push、未合并**，合并由 Fan 决定。
- 需求：同目录 `prd.md`。计划：同目录 `plan.md`（末尾 `## 修订记录` 记着两轮 Codex 对抗审查怎么改的）。

---

## 1. 做到哪了

`plan.md` 的 9 个任务全部实现、提交，每个任务都过了任务复审；整条分支又过了一次 Opus 代码审核，审出的中级问题已修。

| 提交 | 内容 | PRD 条目 |
|---|---|---|
| `0ea816e1` | 做题路由不再无条件套标定守卫（新 `TsumegoInputGuard`）；页内实体开关要求「几何本次开机确认过」，开关开着时几何失效也说原因 + 「去标定」 | T9 |
| `59925403` | 后端：盒上题库读取连不上云端回 503、云端 4xx 原样转回；盒上 `GET /progress` 带响应头 `X-Data-Authority: cloud / local_cache` | N9 后端、T1 |
| `a80d7345` | 前端：503 说「连不上云端题库」，空态不再说「随云端同步」；共享 hook `useTsumegoProblem` 非 404 抛 `HTTP <status>` | N9 前端 |
| `d8497362` | 「上次那一档 / 那一类 / 接着上次」按账号存（`kiosk_tsumego_*:u<id>`），旧不分人的钥匙不再读写 | N10 |
| `1b66df1c` | 三句文案改真：问候副标、整级「按分类排好」、实体模式退一手原因 | N26③、N8、T4 |
| `1e60d182` | 摆题引导删掉永远按不动的「开始答题」；拿除标签写棋盘坐标（`xyToCoord`） | T8、N12 |
| `68d4ccc4` + `fbbae8f2` | 「只做错过的」接通：屏 12 卡 / 屏 13 行可点，错题页（屏 13 骨架），错题快照按账号存；共享 `TsumegoProgressContext` 的进度回答换账号 / 过期作废，退回本机缓存算没读到；错题页真浏览器承重闸 | T1 |
| `47b83432` | 做题屏认 `?set=wrong`：只在错题快照里翻页、返回错题页，快照对不上退回整类 | T1 |
| `9c065ab8` + `bd289e09` | 屏 11–13 四图重取、错题页 / 做题屏错题模式四图、屏 12 滚到底补图 | 视觉关卡 |
| `99c72334` | 代码审核修复：没有重试键的两屏不再叫人「再点重试」（选择题型屏加真重试键；做题屏文案改成「返回再进来」） | N9 |

最后一次全量验证（`99c72334`）：vitest 全量与基线比无新增失败；pytest `tests/web_ui` 与基线比无新增失败；`npx tsc -b` 干净；`npm run build` 与 `npm run build:kiosk-2d` 都绿（`verify:kiosk-2d` 退出 0）；Playwright 承重闸 6/6、`kiosk-copy-placeholders.spec.ts` 5/5。

---

## 2. 还没做完的（按先后）

### 2.1 等 Fan 视觉确认（硬关卡）

确认单（私有 artifact）：https://claude.ai/code/artifact/0a5be6dd-2ed7-482a-a19a-c9eb2ca54575

图在仓里：`superpowers/tracks/kiosk-go-shell-align/visual/{11-training,12-units,13-problems}/1024x600/`、`superpowers/tracks/kiosk-go-tsumego/visual/{13w-wrong,14w-puzzle-wrong,12s-units-scrolled}/1024x600/`。

Fan 确认前本赛道**不算完成、不合并**。Fan 要改哪屏就改哪屏，改完只重取那一屏（见 §5 四图规则）。

### 2.2 上板走查（RK3562，board 模式，token=null）

**部署到板子是对外动作，先问 Fan。** 板上 2G 内存，一次只跑一家的测试。清单：

1. 重启 katrain 服务：实体开关**关着**时点进任意一题直接出题，开关灰、旁边写「物理棋盘需先确认棋盘标定…」、页控条有「去标定」；开关**开着**时进题被带去标定台，「沿用上次标定」后回到题。无摄像头的盒子行为不变。
2. 断网进训练营写「连不上云端题库」；恢复网络点「重试」出题。
3. 甲做两题后退出，乙登录看不到甲的「接着上次」和高亮；甲再登录，自己的都还在。
4. 实体做题：摆题引导里没有「开始答题」；故意答错，右栏写「拿除 Q16」这类坐标、且与蓝灯位置一致；「退一手」灰且原因是新句。
5. 做错两题后回屏 12，「现在有 2 道」可点；进去做对一道，回错题页只剩 1 道。
6. 顺带走一次 kiosk-physical-tsumego PRD §6 全项并留记录（T10）。

### 2.3 待 Fan 拍板（本轮都没做，不要自己动手）

- **D1** 实体盘「退一手」做真流程，还是停在「想重来，按重摆」（推荐 B：加一句「盘面和屏幕对不上」的提示，不改状态机）。见 `prd.md` §4。
- **D2** 「选择题型」「全部题目」两屏要不要按壳重画、整级要不要真混排（推荐先出 B / C 并排草图）。
- **D3** 实体开关开着、标定又修不好时的出口（推荐 A：标定台加「改在屏幕上做」）。
- **F2（代码审核低级，已停放）** 错题模式下「接着上次」存 localStorage（带 `?set=wrong`、写「错题第 n 道」），错题快照存 sessionStorage。在普通浏览器里关标签页再开，点「继续」会静默落回整类。盒上 chromium 无痕、两种存储一起清，遇不到。静默退回整类是 PRD 规定的；要根治得改快照的存法（按账号放 localStorage，或进题时按进度重算错题单），这是改需求决定。

### 2.4 合并协调（Fan 放行之后才做）

按 `prd.md` §6.0 的默认顺序，训练营第 3 个合：复盘 → 棋谱 → **训练营** → 跨平台 → 对弈·AI。训练营 rebase 到棋谱之上，要解的是：

- `katrain/web/ui/src/kiosk/KioskApp.tsx`：本赛道改了做题路由（`TsumegoInputGuard`）并加了 `tsumego/:level/:category/wrong`；棋谱赛道改摆谱路由。hunk 相邻，两边都留。
- `katrain/web/core/repository.py`：本赛道改 `tsumego_*` 四个方法与 `RemoteTsumegoRepository.get_all_problems`；棋谱改 `kifu_*`。都只**调用** `_remote_only`，不改它。
- **本赛道比原计划多动了的共享文件**（合并时要对别家查语义冲突）：`src/context/TsumegoProgressContext.tsx`（`fetchAndMerge`）、`src/api/tsumegoApi.ts`（`getProgress` 返回 `{ progress, degraded }`，galaxy 也经这个 Provider）、`src/hooks/useTsumegoProblem.ts`、`katrain/web/api/v1/endpoints/tsumego.py` 的 `get_progress`。

每次合并前：`git merge develop`（或 rebase）→ `npm run build` + `npm run build:kiosk-2d` + `npx tsc -b` → 按基线 diff 跑测试。git 报「合得干净」不等于合得对，对照 §6.0 查语义冲突。

### 2.5 i18n（合并后统一做，补不补由 Fan 定）

本赛道所有新文案都是 `t('tsumego:<key>', '中文默认')`，**没改任何 `.po`**。新增、且 cn PO 里没有的 key：

`backToWrong` `bankEmpty` `cloudUnreachable` `cloudUnreachableBody` `cloudUnreachableBodyNoRetry` `dao` `greetSub` `noWrong` `progressUnread` `progressUnreadBody` `removeAt` `setupExtra` `setupMatched` `setupSkip` `setupStageBlack` `setupStageWhite` `solvedInCategory` `undoPhysicalReset` `wholeLevelRow` `wholeLevelSub` `wrong_total` `wrongProgress` `wrongResume` `wrongSet` `wrongState` `wrongStatLabel`

（都带 `tsumego:` 前缀。）

### 2.6 复审留下的小项（非阻塞，Fan 没要就不做）

- `BoardSetupGuide` 只剩「跳过设置」一颗键、`flex: 1` 撑满整行（计划要求的写法，重画随上板走查一起做）。
- `TsumegoProblemPage` 的 `geometryConfirmed` 条件照抄自 `PhysicalBoardGuard`（那个文件不许改），两处将来可能漂。
- `endpoints/tsumego.py` 的 `_board_read(call)` 没有类型标注。
- `loadErrorCopy(t, error)` 在错误块里每次渲染调两次。
- `LAST_LEVEL_KEY` / `LAST_CATEGORY_KEY` / `RESUME_KEY` 仍导出但没有外部使用者。
- `wrongSequenceKey / readWrongSequence / writeWrongSequence` 没有直接测 `userId == null ⇒ null`。
- `wrongUnknown`（`serverLoadFailed && 数量 === 0`）在三处各算一遍。
- 做题屏「甲→乙→甲」用例的 `useAuth` mock 恒为 id 7：证明了钥匙分人，但 `useMemo` 依赖里删掉 `user?.id` 它照样绿。
- 没有测「实体模式做对后翻页」在 `?set=wrong` 下的路径（经 `navigateToProblem` 间接覆盖）。
- 错题页承重闸：如果回归导致**零**道错题，页面出空态、没有 `.qgrid`，`waitForSelector('.qgrid button')` 仍会走 30 秒通用超时（60→5 的变异已能红在具名断言上）。
- 选择题型屏新加的「重试」对非 503 错误也显示，连点两下会并发两次请求（与 `TsumegoUnitsPage` 既有写法一致）。

---

## 3. 硬约束（违反就是事故）

- 只在本 worktree 里干活。**不 push、不合并 develop、不在别的 worktree 里 checkout。** katrain 的十几个 worktree 共用一条 stash 栈：不要裸 `git stash` / `git stash pop`，要暂存就打 WIP 提交。
- **不改**：`src/kiosk/utils/activeSession.ts`、`src/kiosk/components/vision/PlayInputGuard.tsx`、`PhysicalBoardGuard.tsx`、`GeometryCalibrationScreen.tsx`、`katrain/web/core/repository.py` 里的 `_remote_only` 本身。
- 盒上 token 恒为 null：判「发不发请求 / 渲不渲染 / 是谁」一律用 `useAuth().user` / `isAuthenticated`，不用 `token`。
- 新文案 `t('tsumego:<camelKey>', '中文默认')`，key 不许与 cn PO 撞名（`grep -o 'msgid "tsumego:[^"]*"' katrain/i18n/locales/cn/LC_MESSAGES/katrain.po`），不改 `.po`。
- 改了共享领地（`src/components`、`src/hooks`、`src/api*`、`src/context`、`src/utils`、`src/features`）必须两套构建都绿。`src/kiosk/**` 不许 import `src/galaxy/**` 等（eslint 管）。
- 布局 / 能不能滚只认真浏览器（Playwright）量出来的数，jsdom 不作布局证据；视觉改动要四图并由 Fan 确认。
- 每个改动一个提交，信息格式 `fix(kiosk-tsumego): …` / `feat(kiosk-tsumego): …` / `test(kiosk-tsumego): …`，正文说清改了什么、为什么。提交前 `git status --short` 只剩本次文件。
- katrain 的 `.gitignore` 有 `log*`，macOS 不分大小写：新建 `Login*.tsx` 之类会被静默忽略。新文件 `git add <路径>` 后用 `git diff --cached --stat` 确认进了暂存区。

---

## 4. 环境与验证命令（踩过的坑都在这）

**装环境（worktree 已装好；新 worktree 才需要）**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego && uv sync --extra web   # 裸 uv sync 不装 fastapi
cd katrain/web/ui && npm ci
```

**类型检查**：`cd katrain/web/ui && npx tsc -b`。`npx tsc --noEmit` 查 0 个文件，不算数；`*.test.ts(x)` 不在 tsc 范围内。

**判据是基线 diff，比失败用例的名字集合，不比条数。** 基线文件在 `/private/tmp/claude-501/kiosk-go-tsumego/`（`vitest-baseline-failed.txt` 1 条、`pytest-baseline-failed.txt` 43 行）。`/private/tmp` 重启会清；不在了就在 `bad0c1fb` 上开一个临时 worktree 重跑（不要在共用树上 checkout 做基线）。

```bash
# 前端全量比较
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego/katrain/web/ui
T=/private/tmp/claude-501/kiosk-go-tsumego
npx vitest run --reporter=json --outputFile=$T/vitest-now.json > $T/vitest-now.log 2>&1 || true
node -e "const r=require('$T/vitest-now.json');for(const f of r.testResults)for(const a of f.assertionResults)if(a.status==='failed')console.log(f.name.replace(/.*\/src\//,'src/')+' :: '+a.fullName)" | sort > $T/vitest-now-failed.txt
comm -13 $T/vitest-baseline-failed.txt $T/vitest-now-failed.txt     # 应无输出

# 后端全量比较（fontTools 没在任何 extra 里声明，不加 --continue-on-collection-errors 会整场中止）
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego
CI=true uv run pytest tests/web_ui -q -rfE -p no:cacheprovider --continue-on-collection-errors > $T/pytest-now.log 2>&1
grep '^FAILED\|^ERROR' $T/pytest-now.log | sed 's/ - .*//' | sort > $T/pytest-now-failed.txt
comm -13 $T/pytest-baseline-failed.txt $T/pytest-now-failed.txt   # 应无输出
git status --short katrain/config.json                              # 测试会改写它；有改动就 git checkout -- katrain/config.json
```

基线里既有的失败（不是本赛道造成的）：`AiSetupPage.test.tsx` 一条偶发；pytest 24 failed / 19 errors（含 `test_tsumego_api.py` 16 条 502、`test_build_galaxy_fonts.py` 收集错误）。新出现的失败一律当作自己造成的，不许按文件名判「看着不相关」；机器忙时先整套重跑一次再下结论。

**Playwright e2e**（`playwright.config.ts`，打 `:8002` 上的**构建产物**）

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego/katrain/web/ui
lsof -nP -iTCP:8002 -sTCP:LISTEN          # 有进程先 lsof -p <pid> | grep cwd，不是本 worktree 就等，不许杀
cp ~/.katrain/config.json /private/tmp/claude-501/kiosk-go-tsumego/katrain-config.bak
npm run build                             # 改源码后必须先构建
KATRAIN_SECRET_KEY=<至少 32 个字符的一次性值> npx playwright test tests/kiosk-tsumego-wrong.spec.ts tests/kiosk-shell-scroll.spec.ts -g "错题页|训练营|单元列表|题目列表"
cp /private/tmp/claude-501/kiosk-go-tsumego/katrain-config.bak ~/.katrain/config.json   # 服务退出会改写它
```

`KATRAIN_SECRET_KEY` 只放命令行，不写进任何文件；短于 32 个字符服务拒绝启动。

**四图**（`playwright.visual.config.ts`，打 `:5173` vite dev server，同样先查端口）

```bash
npx playwright test --config=playwright.visual.config.ts tests/kiosk-screen-12-units.fourup.spec.ts   # 只取改到的屏
```

- 参考图来自另一个仓 `/Users/fan/Repositories/smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots/`，按 `tests/helpers/reference-shots.json` 的 sha256 钉住，不要改那个仓。
- 每屏连取两次、比两次的差异；DOM/SVG 屏抖动地板约 200 像素，canvas 棋盘屏（14 类）约 4500。只是抖动的屏 `git checkout HEAD -- <那一屏目录>` 还原，不提交。
- 按屏整组判断（参考 / 实现 / 并排 / 差异四张），实现图不许不带并排图单独提交。
- 屏 12 在 1024×600 里看不到「整级一起做」那块，改那块要看 `12s-units-scrolled`（`tests/kiosk-tsumego-wrong.fourup.spec.ts` 第三条）。

---

## 5. 资料索引

| 资料 | 位置 | 说明 |
|---|---|---|
| 需求 | `superpowers/tracks/kiosk-go-tsumego/prd.md` | §3 本轮条目、§4 待拍板、§5 不在本轮、§6.0 五赛道协调与合并顺序、§7 验证方式 |
| 计划 | `superpowers/tracks/kiosk-go-tsumego/plan.md` | 每个任务的完整代码与命令；末尾修订记录 |
| 执行台账与各任务报告 | `.superpowers/sdd/plan/`（gitignore，只在这台机器上） | `progress.md` 是台账（含全部裁定）；`task-N-report.md` 是每个任务的 TDD 证据；`review-*.diff` 是复审包 |
| 视觉确认单 | 上面 §2.1 的 artifact 链接 | 私有页，Fan 能看 |
| 其它四条赛道 | worktree `katrain-kiosk-go-{review,kifu,cross-platform,play-ai}` | `git log feature/kiosk-go-<赛道> -- <文件>` 不用 push 就看得见 |
