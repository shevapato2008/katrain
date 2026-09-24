# 管理后台 Codex 跨 session 交接（2026-09-24）

## 2026-09-25 Git 集成更新（覆盖下文的旧 Git 状态描述）

Fan 已明确要求将当前教程后台工作树改动作为**单独一次提交**合入并推送 `develop`。该提交包含教程后台代码、设计与验收资料、计划/交接更新及 `/output/` 忽略规则；`.playwright-cli` 临时快照不入库。下文“教程草稿未提交/未推送”的句子是这次集成前的历史状态，不再作为后续操作指令。**合入代码不等于教程模块验收或部署**：测试/生产运行服务仍未部署，生产旧 `admin` 尚未处置，cron 尚未开始。`smartbox-software` 父仓的 push 不在本次授权范围。

## 停点

Fan 已恢复按计划开发。现在停在**切片 0 的下一条逐项写库／部署授权关卡**：测试机旧 `admin` 已获单独批准并撤权、随机化口令，本机和生产仍未处理。切片 0 已按 Fan 的新指令合入并推送 `develop`，但**代码推送不是部署**，测试/生产的运行服务仍待单独批准。教程管理 T4/T5 已有本机隔离数据库的真实 HTTP 浏览器检查，但尚未做测试／生产验收，不继续开发 cron。教程草稿的 Git 状态以本报告顶部更新为准。

后续新增了非绿色主题设计稿 `tutorial-admin-design-v2.html`。Fan 已选 **B「石墨铜」作夜间版、C「雾白蓝」作白天版、楷体作后台界面字体**。这套主题已在本地 `AdminApp.css` 实现，依系统深浅模式自动切换；Mac 优先 `Kaiti SC`，Windows 用 `KaiTi`，其他环境回退仓内 `LXGW WenKai`。本地 React 登录、详情、编辑态的 1440×900 预览及同视口并排/叠加/差异记录见 `tutorial-theme-visual-review.md`；详情/编辑预览用 `output/playwright/admin-theme-preview.mjs` 的临时模拟响应，未写入生产代码或真实数据库。聚焦前端测试 13 passed、`build:admin` 和 ESLint 均通过。**Fan 已确认新版 React 外观，但教程模块尚未验收**；此次确认不授权远程连接、写库、push 或部署。
设计自检：工作台采用 Operate／Inspect 构图，没有营销 hero、假指标、功能卡片网格、玻璃模糊或装饰性渐变；`claude-design` 的十项俗套特征评分 0/10。当前 B/C＋楷体的设计参考及本地 React 登录、详情、编辑三态均在 Chromium 1440×900 检查；详情/编辑使用测试响应，不是实际后端集成验收。

工作树：`/Users/fan/Repositories/katrain-admin-console`；分支：`feature/admin-console`。保留工作树中未跟踪的 `.playwright-cli` 临时快照；不能用 `stash`、`reset --hard` 或 `checkout --` 清掉。

## 计划覆盖与顺序

1. `plan-2026-09-24-tutorial-admin-guard.md`：切片 0，公开入口安全修复与旧 `admin` 撤权/发布。顶部 2026-09-24 修订优先于旧 Task 6–7 的“提升公开用户”文字。
2. `plan-2026-09-24-admin-tutorial-first.md`：后台专用账号与**首个完整模块：教程管理**，T0→T6。它覆盖旧 spec 的共享 `users.is_admin` 鉴权及旧 cron 计划的先后顺序。
3. `plan-2026-09-24-admin-console-cron.md`：旧的后台骨架 + cron 计划；顶部修订注明不得照原 Task 顺序和鉴权部分直接执行。教程完成后只复用 cron 记录器、健康判定、只读接口及仍有效的视觉/发布关卡，按当前基础重排。

三份计划**不覆盖全部未来后台模块**。spec §10 的性能监控、金镜像制品、用户/计费及审计查看、YOLO 数据集、设备页、配置体检、报错/告警仍需各自单独设计和计划；教程已从旧的“后续模块”提前。

依赖链：切片 0 安全发布及旧管理员处置 → 教程专用身份/共享后台骨架/真实集成与验收 → cron 完整垂直切片。三个窗口若共用一个 worktree/分支，会同时改后台 app、模型、前端、compose 和 Git 暂存区/HEAD，也可能把未完成教程代码随切片 0 推上去；**不要并行实施**。可以分三个顺序交接的 CLI session。若只读研究/设计要并行，使用独立 worktree，不越过每个模块的设计稿与四图确认 🛑，也不提前改共享基础。

## 已有成果

- 切片 0 安全提交已通过合并提交 `f0a0b4a9` 追上 `develop`，`origin/feature/admin-console` 与 `origin/develop` 均指向它；合并无文本冲突，相对原 `develop` 仅 20 个切片 0 文件，没有教程后台 Fixture、设计稿或代码。合并结果的聚焦 Python 31 项、前端 5 项、Galaxy 与 kiosk 2D 构建及 kiosk 边界检查通过；预期的 `tests/deploy` 在此仓版本中不存在，未宣称通过。Task 1–5b 已完成；Task 6 中测试机旧 `admin` 已撤权并随机化口令，本机和生产未执行；Task 7 仅代码 push 完成，测试/生产部署和验收均未执行。
- `smartbox-software/vendor/katrain` 已在父仓本地 `main` 上更新到 `f0a0b4a9`，提交 `e9d93193`；没有推送 `smartbox-software`，其原有的 `vendor/hermes-agent` 工作树改动未进提交。教程草稿另有仅本地恢复锚点 `wip/admin-tutorial-handoff-20260924` 的 `4fa7aeb3`，未推送；草稿已重新应用回原工作目录的 `feature/admin-console`，保持未提交。根目录 `/output/` 已加入 `.gitignore`，只影响本地验收产物，不影响服务启动；`.playwright-cli` 的已有临时快照仍未跟踪。
- 教程 Galaxy 风格设计稿、Fixture 的 1440×900 四图已获 Fan 确认；`tutorial-admin-contract.md` 已冻结本地契约。它们和教程计划、代码/截图仅在本地 WIP 恢复锚点中保存，**尚未提交到 feature/admin-console 或推送**。
- 本地教程后台实现了独立管理进程/专用 `admin:fan` 身份、登录与写入审计、真实教程读写、并发版本检查、音频/训练样本状态、前端真实 API 集成、Fixture 删除及公开管理员写路由退役。Docker/compose 的本地配置也已调整；没有运行真实数据库迁移或任何远程操作。
- 先前聚焦验证记录为后台及相关公开路由 Python **158 passed**。本次新跑：后台 Python **40 passed**，公开鉴权／教程／计费回归 **122 passed**；并发修正后管理前端 **19 passed**、教程写接口 **13 passed**、`build:admin`、管理前端 ESLint、改动 Python 文件 Black 检查和 `git diff --check` 通过。原 Galaxy 构建、kiosk 构建及隔离校验曾在本次前半程通过，最新修正后未重跑这些非直接相关项。全量 web suite 未宣称通过；本地环境缺 `cv2`，训练导出的正向 OpenCV 路径未实跑。
- 接入新版 `develop` 后，教程工作区的后台 Python **36 passed**、公开鉴权／教程／设备／计费重点回归 **23 passed**、后台前端 **19 passed**，后台、Galaxy、kiosk 2D 三套构建和 kiosk 边界检查通过；这些检查只证明本机组合结果，不构成教程模块验收。
- 本次用 `output/playwright/admin-local-smoke.py` 在临时 SQLite 中建立独立教材，`127.0.0.1:8010` 独立进程提供已构建后台，并在 Chromium 1440×900 真实 HTTP 中验证专用账号登录、读教材和讲解保存；双标签实测 409 后草稿保留、读取服务器版本、核对后重试成功；无效令牌的写请求返回 401 并回到登录。冲突态截图在 `output/playwright/admin-runtime-local-conflict-1440x900.png`。这是隔离测试数据，不是真实环境验收；浏览器尚未做实际 TTS 和音视频播放。
- 由这些检查发现并修复：409 后原无读取服务器版本入口；`board_payload=NULL` 时工作台不显示；空小节无提示；旧视频在棋图／讲解／语音更新后仍被当作成品显示；原“预检查”并未实际检查。后续聚焦复核又发现三项数据风险，均经测试先红后绿：409 刷新后整份旧草稿可能覆盖另一会话独立修改的字段，现按字段重基，双方改同一字段时保存被阻止直到显式确认；仅编辑空棋盘图的讲解可能误创建空盘，现仅显式“编辑棋图”可初始化；失效视频引用时旧时长和大小仍残留，现同事务清空。
- Fan 先明确授权**一次测试机只读 SSH 复核**；`home-ubuntu` 的 `katrain_db` 当时返回 `1|admin|t`。随后 Fan 单独确认了测试机这一条写库命令：在 `katrain-web` 容器内先核对 `current_database()='katrain_db'`、`users.id=1`、用户名 `admin` 与 `is_admin=True`，再在同一事务中将 `is_admin=False`、密码哈希换为不可恢复随机口令。命令退出码 0，写后打印 `katrain_db 1 admin False password_hash_changed`；没有打印口令或哈希。没有连接生产机，下一条远程／写库命令仍须单独批准。
- 发现 `.agents`、`.claude`、`.gemini` 的 `tutorial-data-sync` 旧流程会 `TRUNCATE` 教程表和棋图历史，覆盖后台编辑，而原备份不含历史、计数核对不检测内容差异。三份技能已一致标注停用并移除可直接执行的全表导入命令；未来新增教材须另定按范围核差、冲突拒绝及完整备份恢复演练。不曾执行旧同步。

## 下一 session 的安全起点

1. 先读 `CLAUDE.md`、`codex-handoff.md` 顶部修订、三份计划顶部修订、`tutorial-admin-contract.md` 和本报告；对比 `git status` 与 HEAD，保留工作树中的教程改动。
2. 先处理 T0 的 🛑：切片 0 代码已进入 `develop`，但测试机旧 `admin` 仅已撤权并重置，**安全补丁尚未部署**；本机与生产的目标核对和逐条写库命令、每次远程连接及测试/生产部署都须 Fan 当场明确批准。不要把 Git push 或本报告当部署/写库授权。
3. 教程本机浏览器登录／编辑／401／409 已做；下一步补真实媒体生成／播放验收及目标环境数据差异、备份恢复、替代同步方案。每个真实数据写入及发布步骤单独请 Fan 批准。教程切片只有实际集成、Fixture 已删、Fan 验收通过才算完成。
4. 教程完成后再开 cron session：以既有后台基础重写过时的 cron 执行顺序，先用 `ui-ux-pro-max` 设计并取得 Fan 确认，再做 Fixture 和同视口四图确认；未获四图确认不得写 cron 后端。

除分别获批的测试机只读 SSH 与单条测试库更新、Fan 明确要求的 katrain Git push 外，没有连接运行主机、写本机／生产库或部署。教程代码的 Git 集成状态以本报告顶部更新及实际远端引用为准；`smartbox-software` 的子模块指针仅本地提交，尚未获该父仓 push 指令。
