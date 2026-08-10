# Galaxy 直播页未改版基线

- 采集日期：2026-08-06
- 计划基线 SHA：`5e7dfbf306c777fd13aed97c1d018ef75cd45b58`
- 分支：`feature/galaxy-live-template`
- 真实对局 ID：`yike_184016`
- 真实路径：`/galaxy/live/yike_184016`
- 采集服务：`http://127.0.0.1:8901`
- Sandbox 适配：原计划的相邻 worktree 不在可写范围，经批准将同一个干净 worktree 移至项目内已忽略的 `.worktrees/galaxy-live-template`；分支与基线 SHA 未改变，原工作区及 `/Users/fan/Repositories/katrain-galaxy-s0` 均未修改。

## 基线命令与精确结果

以下命令均从 `katrain/web/ui` 执行：

1. `npm ci --offline`
   - PASS，exit 0。
   - `added 378 packages, and audited 379 packages in 10s`
   - `found 0 vulnerabilities`
2. `npm test -- --run src/galaxy/components/layout/GalaxySidebar.test.tsx`
   - PASS，exit 0。
   - Test Files：`1 passed (1)`；Tests：`5 passed (5)`；Duration：`1.92s`。
3. `npm run build`
   - PASS，exit 0。
   - Vite `v8.0.16`；`12456 modules transformed`；`built in 1.63s`。
   - 存在预存的 Vite `Some chunks are larger than 500 kB after minification` 警告；未在本基线任务扩展范围处理。
4. `npm run build:kiosk-2d`
   - PASS，exit 0。
   - Vite `v8.0.16`；`11840 modules transformed`；`built in 686ms`。
   - verifier：`✅ kiosk boundary clean — no three.js / /galaxy/ / non-board live API in ../static-kiosk-2d ( 22M total)`。

## 真实服务与对局确认

计划命令 `python katrain/web/server.py --host 127.0.0.1 --port 8901` 在该嵌套 worktree 首次运行时 exit 1：脚本入口的 Python 搜索路径命中了另一个 editable 安装，并报 `ModuleNotFoundError: No module named 'katrain.web.core.catalog_cache'`。通过最小诊断确认当前 worktree 内该模块存在；为确保运行的正是本基线代码，最终使用：

`PYTHONPATH=/Users/fan/Repositories/katrain-golaxy-ai-ladder-parity/.worktrees/galaxy-live-template python katrain/web/server.py --host 127.0.0.1 --port 8901`

Sandbox 内首次启动随后因禁止连接本机 PostgreSQL 而 exit 3，精确根因是 `psycopg2.OperationalError: connection to server at localhost, port 5432 failed: Operation not permitted`。按 sandbox 规则以相同命令获得本机服务权限后启动成功。为加载本 worktree 包，启动前使用 `msgfmt` 生成了被 git 忽略的英文 `.mo` 运行时文件；该文件未提交。

- `GET /api/v1/live/matches/yike_184016?fetch_detail=true`：HTTP 200。
- `GET /api/v1/live/matches?limit=50&lang=cn`：HTTP 200。
- 默认对局仍存在且 `status="live"`，采集确认时为 194 手，因此没有修改脚本中的唯一 `matchId`，也没有增加 production fixture。

## 采集结果

从 `katrain/web/ui` 执行：

`node ../../../superpowers/tracks/galaxy-ui-redesign/capture_live_template.mjs reference`

最终结果：PASS，exit 0；`Captured 12 viewports for /galaxy/live/yike_184016 (reference).`

- 共 12 张 `reference.png`，像素尺寸分别与目标 viewport 一致。
- `geometry-reference.json` 含 12 个唯一 viewport、canvas/sidebar/right-rail（存在时）矩形、document 水平 overflow，以及 canvas 上方可见文字和按钮。
- 首轮 one-off 验证暴露了采集器错误地要求 canvas 至少 200px：旧布局在 `901×700` 仅为 `121×121`；移除该错误尺寸门槛后又确认 `430×880` 的 canvas 已挂载但为 `0×0`。等待条件最终修正为 canvas 已挂载，以便如实记录未改版缺陷，没有增加超时。

## 关键未改版问题

- `1024×768`：240px 左栏和 500px 右栏同时固定显示，棋盘被压缩到 `244×244`；页面标题/返回按钮仍占据棋盘上方。
- `900×700`：同样的三列结构把棋盘压缩到 `120×120`，标题被截断。
- `430×880`：240px 左栏仍常驻，右栏被压缩到 158px，棋盘为 `0×0` 而完全不可见；右栏文字和控件严重断行/裁切。
- 三个关键 viewport 的 document 均没有报告水平滚动（`overflowPx: 0`），说明问题来自固定列在隐藏 overflow 容器内挤压内容，而非可恢复的页面横向滚动。

启动前后 `~/.katrain/config.json` 的 SHA-256 均为 `f08265100377e481dc974ccf339bec706f8f230b17d04a7c179a02b70384436b`，因此无需恢复配置。
