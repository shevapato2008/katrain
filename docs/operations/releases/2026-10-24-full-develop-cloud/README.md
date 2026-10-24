# 完整 develop 网页发布 · 2026-10-24

已按用户更正后的标准发布要求，把 **完整应用 develop `495d0284c05cb7c9e8b388ded49a82f2959bfdf7`** 部署到 TEST 和 PROD，顺序为 TEST 完整验收通过后切 PROD。两站实际网页均使用正式共享 Fondamento 字体。此前 `a546e31d0` 只是独立字体静态覆盖回执，不代表本轮完整发布；该临时 CSS 已从新运行应用目录删除，正式 Vite 字库/CSS 接管。

## 发布来源

重新 fetch、发布后再次 ls-remote 确认 develop 仍为上述 `495d0284c…`；字体源码 `adbb60017cc2715d0df040d9994899d44b32daf2` 已是其祖先。父仓库远端 main 已为 `bfb939b1d7e9be923a77fd4060c83f06b9c8928c`，gitlink 已指向同一 develop。没有新的字体源码差异、合并冲突或必要指针更新，因此没有虚构修复/合并提交，也没有为记录移动已发布源码或父仓库指针。本目录仅在独立 evidence 分支提交。

发布工作树隔离在 `~/.config/superpowers/worktrees/katrain-kiosk-debug/full-develop-cloud-20261024`。主工作树、两个未跟踪调查报告、未合入的图标修复和 sibling 脏设计稿未纳入。没有操作 RK。

## 完整构建与版本

全部应用输入来自固定提交；打包前逐文件校验 Git blob。排除项遵循生产 Docker context 的历史数据/训练/研究文档排除规则，保留运行所需 registry/seed。前端在隔离工作树 `npm ci` 后执行 `npm run build`、`npm run build:admin`；锁定 Vite 8.0.16、React 19.2.3、TypeScript 5.9.3。直接从原提交 PO 编译 MO，不更改已跟踪源码。

两站各自仅复用现役镜像的**依赖层**：镜像构建中先删除整个 `/app`，再 COPY 完整应用源码和全新 full/admin 静态，彻底替换旧应用树。不是选择性 Python/静态文件覆盖；也没有重装无关 NVIDIA 依赖。具体 Dockerfile 随本目录保留。

| 环境 | 实际运行镜像 SHA256 | 启动 UTC |
| --- | --- | --- |
| TEST | `0fb0f640b44bc054d2cc064f3b7df644bf366c36bc4aebc68bc1777268b9d07f` | 2026-10-24 07:07:48 |
| PROD | `a6e5d74cd88dd43e581a12eb129d20563f77e269714885620b58a17b8716c41a` | 2026-10-24 07:10:21 |

两站 tag 为 `katrain-full-develop:495d0284c-20261024`，进程环境 `KATRAIN_BUILD_SHA`、`KATRAIN_FRONTEND_BUILD_SHA` 均为完整 495d SHA；镜像 label revision 相同。**4171 个源码及构建文件在候选和实际运行容器中逐项验证一致**，清单 [source-manifest.json](source-manifest.json) 的 SHA256 为 `69bcb7648d5faeaeb286a29b9b434224d1a4b34ffc79d6c135aa12c4a2e36f51`，容器路径 `/app/.full-develop-source-manifest.json`。新 full index SHA256 为 `ca2035e375f8377efe4b24e73771d1a31f865a597adcfab0d607accddca75fa1`；主入口 `index-DyeB9emj.js`、Galaxy chunk `GalaxyApp-CvcJJrsF.js`，公共 API chunk `api-F4MBphUX.js`。

配置沿用现役完整七文件 compose 链，最后追加本轮 `full-develop.override.json`，实际镜像 ID 已核对为上表，旧字体/同步 override 不会覆盖回旧镜像。差异仅 web image 及两个版本环境变量；挂载、其他 env、user/cmd/entrypoint/workdir 保留。仅重建网页服务；所有其他既存持久服务容器 ID/image/start time 未变，包括 cron、GPU、DB、MinIO 和独立 admin。admin 静态已随新 web 镜像完整构建，独立 admin 服务未重启。

## 验证与数据边界

- 后端聚焦 **71 passed**；前端品牌/大厅/领地聚焦 **23 passed**。full/admin 均完成 TypeScript 与 Vite 生产构建。
- 两站全部 **69 张服务 ORM 模型表**无缺表/缺列，教程 `tutorial_figures` 与当前模型相符；名称 schema、选择、不可变触发器及关键索引的只读 guard 均通过。只读候选成功读取现有教程与用户报告（TEST 1 份、PROD 15 份对应既有账户列表），没有创建报告。
- TEST/PROD `/api/v1/health` 均 200/status ok/local reachable。`1.17.1` 是语义版本，源代码版本以上述 env/镜像/清单为准。Galaxy/Kiosk 代表页面、全新入口实际 JS/CSS、棋谱列表/SGF、OpenAPI 均通过，下载资源与完整构建清单一致。
- 两站公开既存报告 `GET /api/v1/kifu/albums/23038/analysis` 均 **200/completed/185 positions**，只读取库存分析。最新新谱没有库存分析时仍诚实返回 unavailable。匿名 territory POST 与私有报告 GET 均 401，保留权限边界；未为验收创建对局、账户、报告或模型任务。
- 两个全新无样式注入的 Chromium 会话均实际渲染 **Fondamento-Regular，custom font、9 glyphs、16px/400/normal**，CSS/WOFF2 真实加载 200。不是仅依靠 `document.fonts.check`。正常 Galaxy 页面与 Kiosk 匿名登录门截图均已亲自查看；未把匿名门当作已登录对局页通过。
- TEST cron 的 **112 个实际 Python 文件**与 495d 对应 Dockerfile 输入全部 hash 相同，故保留原进程，避免重启立即执行任务。3600 秒调度、单向 receiver、持久 stage 和预算配置保留。
- 切换前按既有控制仅暂停未来 kifu 轮次，确认源/receiver PG advisory locks 和 stage writer lock 为空；没有杀在途写者。完毕后原先不存在的控制行已恢复为空。stage manifest SHA256 `a42c1e5a53f9274d88d7c74ee4dd9249faf5302ba0207e012587f2bfa07d8d11`、全部名称模型预算账本字节、所有已有 batch phase/manifest hash 前后不变，包含已完成的 20 新盘和原 78 盘；未重写原包或回执。

TEST 第一次切换曾因启动过程按 PO mtime 重编译 8 个 MO 缓存而触发完整校验自动回滚，健康当时正常。构建步骤改为直接由原始 pinned PO 生成更新的 MO 后，两站重新整树构建并验证全部 4171 文件稳定。此为构建派生产物修正，无产品源码/合并行为修复，因此未增加无关 Astra 代码复审。

完整原始回执见 [release.json](release.json)、各站 built/activated/prepared/browser/http/readonly JSON 与 [screenshots](screenshots)。release-scripts 为本轮已执行的可审计操作，不是新增产品基础设施。私有 env/原始 inspect/完整 compose 快照仅保留在服务器 0700 发布目录的受限文件，未提交凭据。

## 回滚与剩余范围

TEST 发布目录：`/mnt/disk1/fan/full-develop-495d0284c-20261024`；PROD：`/home/ubuntu/full-develop-495d0284c-20261024`。其中 `rollback/compose.private.json` 保留先前实际配置与持久字体镜像，`prepared.json` 给出精确 rollback 命令（仅 web、`--no-deps --no-build --pull never`）。回滚前核对当前镜像/版本仍为本轮，避免覆盖后续发布；备份及旧镜像未删除。八文件完整发布链与版本信息在 activated.json，verification.json 为最终汇总。

当前两站已完成完整发布，无必须后续动作，已打开的网页正常刷新即可。没有操作 RK、重启 GPU/DB/MinIO/cron、触发额外模型调用或修改棋谱数据。登录账户中的对局/真实 GPU/双设备旅程未新建实测；本轮验收覆盖实际页面、现有数据读取、权限拒绝和服务健康。
