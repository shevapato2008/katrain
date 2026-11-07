# Galaxy 根路径发布回执 — 2026-11-08

正式环境 `https://modelstella.com/` 和测试环境 `https://go.sailorvoyage.top/` 已在根地址显示 Galaxy，地址栏保持 `/`。站内页面使用 `/play`、`/kifu` 等根路径；旧 `/galaxy`、`/galaxy/`、`/galaxy/kifu` 实测返回 404，无兼容跳转。RK3562 的严格 Kiosk 构建也已更新，设备已恢复发布前的 Hermes 模式和原启动页。

## 已发布的软件版本

| 仓库/分支 | 已发布的软件提交 |
| --- | --- |
| KaTrain `fix/kiosk-ui-debug`、`develop` | `16f60a1912c457db67eff033982fee5b6191a3eb` |
| smartbox-software `main` | `aef718a4b59dbd9560f60082148632e3a19612d2` |
| 父仓 `vendor/katrain` gitlink | `16f60a1912c457db67eff033982fee5b6191a3eb` |

顺序为：追最新 develop 并推功能分支 → 合并并推 develop → 推父仓 main 的 gitlink → TEST → PROD → RK3562。集成无冲突，未 force push。父仓原工作区已有的 submodule 修改保持原状。当前回执及计划完成标记在部署后以纯文档提交发布；上述软件版本和部署产物不因此改变。

初始未提交的 `katrain/web/static/rime-client.js` 与 develop 的 public 源文件一致，属于应忽略的构建产物；未作为独立源码提交。

## 构建与审核

- writing-plans 的独立 Astra Max 计划审核共两轮，第二轮通过；按文件归属并行开发后，独立规格检查及新 Astra Max 完整代码审核均通过，无未解决的阻塞或重要问题。
- UI 集成 304 passed / 4 构建模式 skips；Kiosk 路由在 strict/non-strict 下各 6 passed / 10 full-mode skips；聚焦后端路由、退出地址及 WS/guest 检查 69 passed；实际 Chromium 路由旅程 3 passed。
- 已发布软件的干净 checkout 使用 `npm ci` 锁定依赖，full 与 strict Kiosk 构建均通过 TypeScript、打包、Galaxy/three/live 排除和 strict token 检查。
- 全量静态产物 492 文件；strict Kiosk 385 文件。模块边界报告 `galaxyModules: []`；未包含 ZenModeApp chunk。
- 已知无关基线问题：完整 termination 测试文件因旧 lifespan fixture 缺少数据库不可变触发器出现 28 个 setup errors，修改前已复现。本次四个退出地址用例使用隔离 fixture 通过；不宣称全量 pytest 通过。

最终产物摘要：

| 内容 | SHA256 |
| --- | --- |
| `server.py` | `c759e49f44d5ed2e41db495d91ecb098469f2e2ac53635040eed84fe41dd06c1` |
| full `index.html` | `def882d2dc6bd86fe88e155525908b780124ecbca1e5fb3aca77fe1e66d0a215` |
| strict `index.html` | `f3677b7842bca169eb554a15979c4a3df51ce268a63ceb36eeef45a109ee5461` |
| cloud payload | `90b4cef09b682b520c0a183bca7d2076847c2db03e44c2da96dbab85bea7bf43` |
| RK release manifest | `34ce88afda0a5337445b1af6beb3f461abfdd6709ca8ba825f0d70e853be2aeb` |

## TEST 与 PROD

两端均从各自现役不可变镜像构建有界候选，仅替换已审核的 `server.py` 与完整 full static。镜像记录本次软件 SHA；不将旧镜像的全部运行时声明为该提交的完整 checkout。保留角色配置、挂载、网络和资源限制；无需修改 Nginx。

| 项目 | TEST / home-ubuntu | PROD / ucloud-v100 |
| --- | --- | --- |
| 新镜像 | `sha256:00848b56e9157f82aa97ff8a1be28274423f018039b4d5eed450256af9c8a601` | `sha256:983ddc4b0a4e957d48933e058dc8bd5444287aca49763312dd8bde33f5621bde` |
| 容器状态 | running，restart 0，HTTP health ok | running/healthy，restart 0，HTTP health ok |
| 非 Web 容器 | 223 个身份、镜像、状态、启动时间及 restart count 保持 | 69 个身份、镜像、状态、启动时间及 restart count 保持 |
| 私有发布目录 | `/tmp/galaxy-root-16f60a1912c4/private` | `/var/tmp/galaxy-root-16f60a1912c4/private` |
| 原容器备份 | `katrain-web-membership-backup-5126e4e33b1e-507dd422` | `katrain-ucloud-katrain-web-1-membership-backup-cb8ac696fdf5-16817ccd` |

每端均完成 20 项公开 HTTP 检查：根地址、新深链接、query、GET/HEAD、尾斜杠、Kiosk 返回预期结果；根与 Galaxy HTML 为 no-cache、无 Location，旧前缀及缺失 API/JS 为真实 404，入口 JS/CSS 字节与 manifest 相符。两端 health 均显示引擎 reachable。真实浏览器确认根地址 Galaxy、导航/刷新、带 query 棋谱及 Kiosk 页面实际渲染，截图已人工查看。

切换前未观察到在线真人/观战连接；PROD 的三局记录为机器人对局。仅 Web 容器执行平滑替换，未重启数据库、引擎、Cron、MinIO 等其他服务。非 Web 配置摘要中 Docker Mounts 数组顺序变化已单独验证为顺序等价，没有配置差量。

使用已固定 hash 的 native helper prepare/apply，保留 stopped 旧容器及失败自动恢复机制；本次云端验收通过，未触发恢复。恢复需先核对实际新旧 full ID 和在用对局，再按审核计划操作，helper 无独立 rollback 子命令。

## RK3562

设备 `rk3562-local` / `gzpeite` 的原目录是源码归档，没有 `.git`。通过现有 Runtime 的锁、target、ready 和 page 恢复机制，仅替换 `server.py`、full static、strict static-kiosk-2d 共 878 个文件。没有运行父仓全量部署。

最终结果 `verified-and-original-mode-restored`。验收窗口通过 Go target 启动：KataGo ready、KaTrain health 正常，原 Chromium page 打开 strict 根地址后进入 `/kiosk/play` 并显示可操作页面；棋谱页诚实显示“登录后进入棋谱库”。未登录的棋谱数据未验收，也未绕过鉴权。画面显示摄像头未连接、需要标定；本次不宣称实体棋盘/摄像头识别通过。

随后停止验收 Go target，恢复原 Hermes target 和同一 page 的精确原 URL `http://127.0.0.1:8080/launcher`。独立收尾检查确认 mode ready、仅一个 page、维护锁已释放、Go/KaTrain inactive、Hermes active，新源码 hash 正确。原四棋全量版本标记保持，另写 `.katrain-routing-release.json` 记录本次差量和源提交，不宣称整机目录等于新提交。

操作器前两次验收分别遇到 systemd 动态 ExecStart 字段误判、未登录棋谱页需要识别权限界面；两次均自动回退并验证原文件、Hermes 和原 URL。修正操作器、补充离线用例并由 Astra Max 复核后，第三次成功。第三次复用同文件系统中已验证的候选目录，未删除旧备份、日志或设备数据。

- 最终成功现场：`/var/lib/smartbox/deployments/galaxy-root-16f60a1912c457db67eff033982fee5b6191a3eb-attempt3/`。
- 原文件回退位置：该目录的 `backup/`；`result.json`、journal、manifest 与前两次现场均保留。
- 最终 RK 操作器 SHA256：`3d38377dbeeb649eb479b916bfb3bf8e8cd06826025f7e9fa2cee8462c7817b7`，13 个离线用例通过。
- 同文件系统候选转移脚本 SHA256：`1c660547182aa454cd2e76b9ed4d88c0a65676fab80995bf8689dad26c7e8eb6`，Astra Max 审核通过。

## 本地证据

本次一次性工具、产物 manifest、HTTP/runtime 回执及设备结果保存在忽略目录 `output/releases/galaxy-root-20261108/`。云端准备脚本 SHA256 为 `c3a4fdff1cafadfdb94bee71ce911cb3f618513b1c293c05201036265534dfda`，20 个离线用例通过；固定 native helper SHA256 为 `98e816acbe780baf95e8f8168073ba2894efe852bb0bd3c0b454264e89027108`。所有最终操作器修改均经独立 Astra Max 批准。

实际浏览器截图位于 `output/playwright/galaxy-root-20261108/`：`test-root.png`、`test-kiosk.png`、`prod-root.png`、`prod-kiosk.png`、`rk-root.png`、`rk-kifu.png`。私有配置仅留在受限目录，回执未包含环境变量、密钥或 DSN。
