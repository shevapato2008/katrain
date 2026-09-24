# 交接给 Codex：katrain 管理后台（admin-console）开发

你接手的这条赛道，文档已经完成，代码还没开始。前一个执行者（Claude）额度快用完了，它留下了：
- 设计和两份实施计划；
- 两轮 Codex 对抗评审；
- 计划里的代码已经抽出来实跑过，也做过变异检查。

你的任务是**照计划把代码写出来**。计划里标 🛑 的地方要停下来，等 Fan。

## 0. 位置与铁律

- **工作位置**：worktree `/Users/fan/Repositories/katrain-admin-console`，分支 `feature/admin-console`。主分支是 **develop**；master 是上游，拿它做对照一律无效。
- **动手前先读完这四份**：
  1. `superpowers/tracks/admin-console/spec-2026-09-24-admin-console.md`：设计。
  2. `superpowers/tracks/admin-console/plan-2026-09-24-tutorial-admin-guard.md`：切片 0，安全修复，7 个 Task。
  3. `superpowers/tracks/admin-console/plan-2026-09-24-admin-console-cron.md`：切片 1，后台骨架加 cron 可视化，15 个 Task。
  4. 仓库根目录的 `CLAUDE.md`：虽然是写给 Claude 的，项目规矩对你同样适用，尤其是「SBC 构建边界契约」。
- **照计划原文执行**：
  - 两份计划都按 superpowers writing-plans 格式写。开头的 Global Constraints 对每一步都有效。
  - 每个 Task 都写了文件、接口、逐步命令、完整代码和预期输出。
  - 每做完一步，把 `- [ ]` 改成 `- [x]`，和这个 Task 的代码一起提交。这是下一个接手的人判断进度的唯一依据。
- **计划和源码对不上时**（锚点找不到、基线不一样、命令报错），先读源码弄清原因：
  - 不改设计就能修的（比如行号漂移、import 路径），直接修，在提交信息里写一句。
  - **要动设计、接口契约或安全边界的，停下来问 Fan。**
- 🛑 **不许连接任何远程机器**：
  - `ssh`、`scp`、`rsync` 到 home-ubuntu、ucloud-v100 或盒子都算，只读命令也不行。
  - 唯一例外：计划里标了 🛑 的步骤，而且 Fan 当时明确说了可以。
  - 上一次 Codex 评审就在没有授权的情况下 ssh 进了生产。
- 🛑 **`git push`、部署、写任何环境的数据库，执行之前都要 Fan 当场点头**。计划获批、这份交接说明都不算授权。先部署测试机（home-ubuntu），再部署生产（ucloud-v100）。
- **不要碰别的 worktree**。也不要在共享的主工作树 `~/Repositories/katrain` 里切分支、提交或改文件。例外是计划里的 `git -C /Users/fan/Repositories/katrain fetch / log / worktree add`，它们不动那里的工作文件。
- **不要用 `git stash`**：katrain 的所有 worktree 共用一条 stash 栈，pop 会弹出别人没做完的改动。要暂存就打一个临时的 WIP 提交。
- **不要打印密钥**：`KATRAIN_SECRET_KEY`、`/etc/katrain/*.env` 里的值，以及 `~/.ssh`、`~/.codex` 下的文件内容。要确认某个密钥在不在，只看它的长度。
- **提交署名**：计划里的提交信息结尾写着 `Co-Authored-By: Claude Opus 5.5 …`，那是写给 Claude 的。你提交时删掉这一行，或者换成你自己的署名，不要冒充 Claude。
- **改动要相称**：
  - 计划里写了的测试和变异检查照做。
  - 不要再加测试层、审计脚本或评审轮。两份计划的评审已经结束，Fan 定的上限就是两轮。
- **不要对全仓跑 `black`**，只格式化自己改过的文件。

## 1. 已经定下来的事（都已写进 spec 和计划）

- **放在哪、怎么访问**：代码放在 katrain 仓。后台是一个独立进程，只绑 127.0.0.1:8010，通过 SSH 隧道访问。测试机的隧道映射到本机 8010，生产映射到 8011。
- **顺序**：先做切片 0（安全修复），再做切片 1（cron 可视化）。
- **切片 0 的 Task 3「Bearer 只认 access token」**：Fan 定了保留。
- **后台保持登录**：令牌放在 localStorage，8 小时过期（spec E8、§5.3）。
- **生产上的 `admin/admin`**：撤掉 `is_admin`，口令换成随机值（切片 0 Task 6，执行前要 Fan 点头）。
- **执行方式（Fan 定的）**：
  - **切片 0 在你的主会话里直接做**，因为它的多数步骤要 Fan 当场拍板。
  - **切片 1 一个 Task 派一个子代理，写完就审**，用 superpowers 的 `subagent-driven-development`。
    - 你如果没有 `spawn_agent` 这类工具，就改用 `executing-plans`，在主会话里一个 Task 一个 Task 地做。
    - 派子代理时，把本文件第 0、3、4 节原文附上。
    - 子代理不做任何 🛑 步骤，碰到了就交回给你。

## 2. 顺序与停点

### 切片 0（`plan-2026-09-24-tutorial-admin-guard.md`）

1. **Task 1–4**：写代码。
2. **Task 5**：在真浏览器里量右栏的承重结构，并截图。
   - 🛑 Step 6：把截图和测量结果交给 Fan，他明确确认之后才能进 Task 6。
3. **Task 6** 🛑：清点各环境的管理员账号。
   - Step 1 虽然只是只读查询，但要 ssh 到测试机和生产，所以**也要先问 Fan**。
   - 之后每一条改库命令，执行前 Fan 都要再点一次头。
   - Step 4 要 Fan 在他自己的终端里登录。计划里说的 `! ` 前缀是 Claude Code 的用法，你直接把命令给他就行。
4. **Task 7** 🛑：发布。
   - 每一次 push、每一步部署之前，都要 Fan 点头。
   - 发布预检里的容量闸（看磁盘剩余 `available_bytes`）如果报红，由 Fan 当场决定是否越过；其他预检项红了一律停。

切片 0 推到 develop（Task 7 Step 1）之前，**不要在 `feature/admin-console` 上提交任何切片 1 的东西**。Task 7 会把整个分支快进推到 develop，切片 1 的半成品和假数据会被一起带上去。

### 切片 1（`plan-2026-09-24-admin-console-cron.md`）

1. **Task 1**：设计稿。这一步要换工具，见第 3 节。
   - 🛑 Step 7：Fan 确认设计稿之后，才能进 Task 2。
2. **Task 2**：先接假数据的前端。
3. **Task 3**：四图对比和承重实测。
   - 🛑 Step 6：Fan 明确确认之后，才做 Step 7 的契约定稿，再进 Task 4。
   - **这是 Fan 定的硬性关卡：没有他的确认，任何后端任务都不许做。**
4. **Task 4–13**：后端、前后端集成、删掉 fixture、全量验证，按计划顺序做。
5. **Task 14** 🛑：部署测试机，由 Fan 验收。
6. **Task 15** 🛑：部署生产，每一步都要 Fan 点头。
7. 切片 1 全部做完后，按 `subagent-driven-development` 的收尾流程，对整个切片做一次代码审查。

## 3. 计划里写给 Claude 的步骤，你这样替换

- **切片 1 Task 1 Step 2、3**：这两步要调用 `frontend-design` 和 `ui-ux-pro-max`，都是 Claude 的技能。你有同类技能就用；没有的话，直接按步骤里列出的输入定方向，把取舍写进 `design-notes.md`。
- **切片 1 Task 1 Step 4、7**：计划要求用 Claude 的 Artifact 工具发布设计稿，再「把 Artifact 链接发给 Fan」。你没有这个工具，**跳过发布**：
  - 只做 Step 4 本来就要求的本地设计稿 `slice1/design/admin-cron-design.html`；
  - 在 `design-notes.md` 里写这个文件的路径，代替 Artifact 链接；
  - Step 7 交给 Fan 两样东西：在浏览器里打开设计稿的地址（形如 `file:///Users/fan/Repositories/katrain-admin-console/superpowers/tracks/admin-console/slice1/design/admin-cron-design.html?state=ok`），以及 8 张参考图的路径。
- **`/private/tmp/claude-501/…`**：计划里的备份文件、临时 release worktree、状态文件都放在这下面。它只是个临时目录，照用就行；不存在就先 `mkdir -p`。
- **`.claude/skills/server-deploy/SKILL.md`、`.claude/skills/tutorial-data-sync`**：这是仓库里的文档，当普通文件读。切片 1 Task 11 要修改前者。
- **真浏览器实测和截图**：用计划里写好的 Playwright 脚本跑，不要换成别的浏览器工具。这样测出来的数字和截图才能复现、能对比。

## 4. 已知的坑（都实际踩过，大多已写进计划的 Global Constraints）

- **依赖要按计划的步骤装**。新 worktree 里没有 `.venv`，也没有 `node_modules`：
  - 切片 0 Task 1 Step 1：`uv sync --extra web`；
  - 切片 1 从 Task 8 起：`uv sync --extra web --extra cron`；
  - 前端：`npm ci`。

  只跑 `uv sync` 会缺 fastapi，pytest 在收集阶段就中止，失败名单是空的，看起来却像全过了。
- **全量 pytest 会改写已提交的 `katrain/config.json`**。跑之前确认它是干净的；跑完发现被改了，就用 `git checkout -- katrain/config.json` 还原。不要把它提交进去。
- **`tests/web_ui/` 的 conftest 会把 `katrain.web.interface` 换成 MagicMock**。不要把它和 `tests/platforms/` 或根目录的测试放进同一条 pytest 命令。
- **判断「有没有弄坏」，一律用计划里的 `newfail.sh` / `vitestnewfail.sh`**，按用例名和基线比。有些用例在基线上就是红的，不要求整个文件全绿。
- **类型检查用 `npx tsc -b`**。`npx tsc --noEmit` 实际上检查的是 0 个文件。
- **根目录 `.gitignore` 里的 `log*` 会吞掉新文件**。macOS 文件名不区分大小写，`Login*.tsx` 这类新文件会被静默忽略，所以登录页叫 `SignInPage.tsx`。新文件 `git add` 之后，用 `git diff --cached --stat` 确认它进了暂存区。
- **本机 shell 是 zsh**：它不做词分割，`for f in $FILES` 只循环一次；`$VAR:t…` 会被当成路径修饰符。
- **每次调用 shell 都是新进程**，变量留不到下一步。跨步骤要用的值写进文件。
- **变异检查**：先用 `cp` 备份，全程设 `PYTHONDONTWRITEBYTECODE=1`，最后用备份还原。**不要用 `git checkout` 还原**，那会冲掉本任务还没提交的改动。
- **管道和退出码**：带管道的检查命令先写 `set -o pipefail`；生产上的发布命令一律不接管道。
- **端口**：起 vite 之前先看端口有没有被别的 worktree 占着（计划里写了怎么查），别让截图打到别人的服务上。

## 5. 每个 Task 怎么做

1. 先写测试，确认它是红的。
2. 改代码，直到测试变绿。
3. 做计划要求的变异检查：确认测试会变红，然后还原。
4. 和基线比，新增失败必须是 0。
5. 在计划里勾选完成的步骤，然后提交。

提交前自己审一遍 diff：符合计划，没多做，也没少做。

切片 1 用子代理时，一个 Task 派一个实现者。它交回来以后：
1. 先审它符不符合计划，再审代码质量。
2. 有问题，让同一个实现者去改。
3. 两项都通过了，再派下一个 Task。

## 6. 汇报

**每到一个 🛑**，给 Fan 一段简短的汇报：
- 做完了哪些 Task，各自的提交号；
- 测试和变异检查的结果；
- 需要他确认或决定的具体事项。

**全部做完，或者你的额度、时间快用完时**，把最终报告写进 `superpowers/tracks/admin-console/codex-report.md` 并提交。报告要包括：
- 每个 Task 的提交号，以及测试先红、再变绿、变异后变红的证据摘要；
- 和基线相比新增的失败（必须是 0；如果有抖动，写明判断依据）；
- 两套前端构建、`tsc -b`、eslint 的结果；
- 你偏离计划的地方，以及理由；
- 等 Fan 确认或决定的事项；
- 停在了哪一步，下一步做什么。

**不要宣称视觉通过、验收通过或者可以发布。这些只有 Fan 能说。**
