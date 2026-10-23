# 大厅统一对局与本地标定续开发布

用户已在本地实现审核通过后明确授权集成、推送、Smartbox 子模块更新及 RK3562 部署；本记录取代先前验证文档中“仅本地、未授权部署”的当时交付边界。棋谱同步调查和修复不属于本次范围。

## 发布输入与合并验证

- 功能实现基线 `5016186ed`，大厅本地交付 `d345a45e8`；包含已审核本地对局标定成功续开 `fb19e95c2`。
- 当前 `origin/develop` 为 `ab29b9927ddf7640de68cd1028369462c99422b0`。功能分支合入其 25 个提交；唯一冲突为 `PvpLocalSetupPage.tsx` 两行 imports，合并 `useCallback` 与新版 MUI Dialog 依赖，未改双方业务逻辑。
- 合并后：本地设置页、GeometryContext、PlayInputGuard **46 passed**；大厅/会话/面板等前端范围 **219 passed、1 既有 develop 测试断言失败**；相关后端 **96 passed、3 先前已证实的旧 fixture 失败**；大厅 Playwright **3 passed**；`build:smartbox-kiosk-2d` 通过，严格 SSO/kiosk 边界通过。
- 新发现的 develop 既有失败是 `GameControlPanel.clock.test.tsx` 的“未配置时限的自由对弈忽略继承用时、不调 onTimeExpired”：新版 paired 卡两侧都显示“不限时”，旧 `getByText` 只允许一个。合并树的该组件和该测试与 `origin/develop` 完全一致；没有为本次发布扩改它。
- 保留已证明的 PhysicalBoardGuard 旧文案失败、三个 box MagicMock fixture 失败；没有把它们伪报为通过。
- 合并后真实 1024×600 大厅截图已重新检查，board/rail、四键/显示键尺寸、图标和无溢出断言通过。截图在忽略目录 `output/playwright/lobby-game-unified/`。

## 部署策略

严格按用户顺序先发布功能分支，再将其合入并推送 develop，再更新 Smartbox main 的 `vendor/katrain`，最后部署所需后端及 RK。

两云当前 web server 与功能基线字节一致，缺少领地 helper/route。使用现有运行镜像为基础，只加入已发布 commit 的新 helper 和对应 server；保持既有 compose 环境、挂载与服务身份，只重建 web，不重启 GPU、cron、数据库或对象存储，不运行数据导入。

RK 使用既有 git archive + 精确 gitlink 导出 + 校验和 rsync 的发布机制，限定围棋运行包/静态产物；不执行会更新其他棋类及数据库的四棋全量脚本。先按存储文档恢复根分区至少 2 GiB 余量，备份、上传、解包和回滚文件放 `/mnt/data/smartbox-deployments/`。保留数据、模型、配置、鉴权和硬件标定。实际部署及版本回执在后续记录补齐。

## 最终发布回执

代码发布与子模块：

| 项目 | 已发布 revision |
| --- | --- |
| `origin/feature/lobby-game-unified-20261023` | `0ac3190d8a114403f35d37ffd76c34caaa31825b` |
| `origin/develop` | 同上；包含大厅实现及本地标定续开 `fb19e95c2` |
| Smartbox `origin/main` 子模块更新提交 | `a87024e2af512685998cdb65b771ece6db565a40` |
| `vendor/katrain` gitlink | `0ac3190d8a114403f35d37ffd76c34caaa31825b` |
| RK 进程 `KATRAIN_BUILD_SHA` / source marker | 同上；实际 PID `35814` |

本仓库主工作树 `fix/kiosk-ui-debug` 已安全快进到发布代码，唯一未跟踪棋谱同步调查文件保持原样；Smartbox 本地 main/子模块亦已快进并保持干净。最终验收文档独立保存于 `release/lobby-local-evidence-20261023`，避免为纯记录改动移动已经部署并复核的代码 revision。

### 云端范围与证据

仅发布 `server.py` 的新入口和 `core/pvp_territory.py`，以各自主机原运行镜像为基底，未发布整棵新代码树；**云端 static UI 明确保留原版**。原镜像、完整新 image ID、两文件实际 hash、环境/挂载指纹、其他服务身份和浏览器结果见 [cloud JSON](releases/2026-10-23-lobby-local/cloud-receipts.json) 和 [cloud 说明](releases/2026-10-23-lobby-local/cloud-receipts.md)。

- home-ubuntu：`katrain-web`，新 image `sha256:cf26206cf6d51560ccd276ae0af9f42d99c8b8d76f0f7ca01559c3cbed0f31c2`。
- ucloud-v100：`katrain-ucloud-katrain-web-1`，新 image `sha256:b4f36e32127420656266e1cd53417375075bd3d1bacd3a7ada8a7ddaf3c5d4ae`。
- 两台实际 `server.py` SHA256：`d7525ae106b1fc1347565231902fe4340b28572065135a5fbfd8a06575c2315a`。
- 两台实际 helper SHA256：`8bdc390ac039b23b4b09f325e4ade41e1595f2d1dfd65ebc598d69a257b5ba52`。
- `https://go.sailorvoyage.top`、`https://modelstella.com`：`/api/v1/health` 均 200/ok；OpenAPI 有 `POST /api/pvp/territory`；未认证 POST 均 401，已排除中央 404 问题。
- 两站真实 `/galaxy/play`、`/kiosk/play/pvp/lobby` 浏览器只读渲染通过；未登录时 auth/me 401 为预期。限制为 GET/HEAD/OPTIONS，无账号/对局创建。
- 只重建 web；GPU、cron、DB、MinIO、admin 等其他容器 ID/启动时间均不变；未跑棋谱导入或同步任务。

### RK 运行和存储

- 仅发布 384 个受控运行 Python 文件及同源 full/strict static，共 **1165** 文件逐项校验；不覆盖 docs symlink、设备数据、配置、鉴权、模型或硬件目录，不运行四棋全量部署/provisioning。
- source 与两套静态实际 hash 对齐发布源；strict index：`366702d3598a7f50c43e7bfb869c1538823ffe0c10ae151dbeb387df53ab0fd0`，入口 `index-gNws6MT_.js`。发布文件与状态详见 [RK JSON](releases/2026-10-23-lobby-local/rk-receipt.json)。
- 实际 `GamePage-BTwYxS4q.js` 包含四操作，`PvpLocalSetupPage-C4kAMT7u.js` 包含标定续开代码标记，`api-DyCYjWfx.js` 包含真实领地端点。
- 仅停起 `smartbox-katrain.service`，旧进程 2574 退出后新进程 35814 启动；保留模式、kiosk 和其他棋类服务。
- `/health`、`/api/v1/health`、`/kiosk`、`/kiosk/play/pvp/lobby` 为 200；新入口 OpenAPI 存在且未认证 401；local engine reachable，camera/geometry/model/recognition/LED 就绪，vision 未绑定实体对局。
- durable config、设备身份、SSO key、视觉模型、旧几何 JSON/NPZ 六份文件哈希完全未变。SQLite 通过在线 backup 保存，未重置数据或棋盘。
- 已将经引用核对的旧发布目录/上传包迁到数据盘，checksum 校验后以 symlink 保留旧入口；根盘从 1.909 GiB 恢复，发布与叶级 static 清理后为 **2.091 GiB**。上传压缩包、解包候选已删，回滚、SQLite 快照、manifest 和验收截图保留在数据盘。

设备可复核路径：

```text
/root/smartbox-software/.smartbox-deploy-revisions
/root/smartbox-software/vendor/katrain/.smartbox-deployed-commit
/root/smartbox-software/vendor/katrain/.smartbox-release.json
/mnt/data/smartbox-deployments/20261023-lobby-local-0ac3190d8/manifest.json
/mnt/data/smartbox-deployments/20261023-lobby-local-0ac3190d8/verification.json
/mnt/data/smartbox-deployments/20261023-lobby-local-0ac3190d8/browser-verification.json
/mnt/data/smartbox-deployments/20261023-lobby-local-0ac3190d8/rollback/
```

### 真实页面与既有 SSO 恢复

部署前用户从棋谱页进入一个已保存棋谱的研究页，vision 仍 unbound，保护检查确认非实时对局后继续。先保持原 URL 刷新检查新 bundle，遇到登录墙。根因是既有 `BoxSSOState` 只在内存保存 active_generation，服务重启有意使旧应用 cookie 失效，并非身份/key 文件丢失。

随后通过登录墙正常“去盒子主页”按钮返回 launcher，同源 GET `/api/auth/me` 确认既有有效 real 会话为 `fan`，点击真实 `#tile-go`，由既有 `/api/launcher/switch` → `bootstrap_go` → Set-Cookie 恢复应用 SSO。没有读取/注入 cookie，没有伪造 generation，没有写凭据或放宽 strict。KaTrain auth/me 200、同用户 fan 后恢复原保存研究页，实际 1024×600 显示真实第 132 手棋盘、新入口，已完成视觉核对。未创建账号或对局。

本地截图保存在忽略目录 `output/playwright/lobby-game-release-20261023/`：

- `rk-after-reload-1024x600.png`：恢复前登录墙，保留根因证据。
- `rk-after-sso-restored-1024x600.png`：正常入口恢复后的真实研究页、fan 和新 bundle。

### 验收边界

已完成代码发布、中央 API 就绪、RK 程序/资源/版本匹配、硬件状态、正常登录恢复及实际当前用户页面验收。没有创建真实对局来跑双设备/GPU完整业务旅程，不把本地 fake-engine 测试或研究页自动分析当作该验收。

用户可进一步人工验收：

1. 本地实体盘开局触发标定，标定完整 ready 后使用原参数自动进入一次对局；取消/失败留页可重试。
2. 两端真实大厅对局中请求领地，确认仅本人参考并在落子后失效；继续走原数子协商，正式结果仍来自终局数子。验证断线重连、停一手和认输按实际权限执行。
