# Galaxy 英文品牌字体静态发布 · 2026-10-24

已更新 TEST https://go.sailorvoyage.top/galaxy/play 和 PROD https://modelstella.com/galaxy/play。`StellaBox` 使用与 RK/Kiosk 相同字节的自托管 Fondamento Regular，16px、400、normal、禁用合成；中文品牌字、logo、其余布局与业务保持原值。两站均在全新、无临时样式注入的 Chromium 会话中通过实际字体检查，可直接正常刷新查看，无需清缓存。

这是 **3 文件热静态覆盖**，不是整套新版网页构建。源码 `adbb60017cc2715d0df040d9994899d44b32daf2` 已有正确字体实现，本轮不重复修改产品源码，不移动 develop `4bf9a699a35ecdf025f5ec2f414425e3f2a13693` 或 Smartbox main `c4a31024095434b894beaad23995651cabf56b1d`，不操作 RK。现役旧云 UI/JS、同步与大厅后端均保留。

## 发布内容与持久性

Artifact：`galaxy-brand-font-20261024`；资源内容、完整 SHA256 见 [artifact.json](artifact.json)。

- `assets/fondamento-latin-regular-01e17adcd642.woff2`：与源码/Kiosk 字库 SHA256 相同。
- `assets/galaxy-brand-latin-10e120749af9.css`：仅 `header[data-testid="galaxy-top-bar"] .galaxy-brand-latin` 选择器；属性取已发布 GalaxyTopBar，足够覆盖 Emotion，无 `!important`。
- `index.html`：原字节中只增加上述 CSS 的一条 link；新 SHA256 `51794ab8c9ab1fb0987ca64ad608da4ecf62a6557fb3f32ad3add48faafc94b9`，原 SHA256 `c9b96a5386d784b85e7cdba18d6955a920cfa89d3d9feab1e48267d1341860e5`。

先上传 CSS/font 并验证公网 200 与 hash，再原子替换 index。没有编辑压缩 JS。现役旧静态中没有其他 Fondamento 引用，选择器也不匹配 Kiosk 元素。

同时分别以本次现役镜像为 FROM 创建同一 3 文件持久镜像，逐项验证全部原静态/后端继承一致；只把当前 compose 文件链最后一份 override 的 web image 字段改为新 tag，env 等配置完全相同。**没有 recreate/restart**：当前运行 image ID 仍是下表原镜像，字体通过容器可写层立即生效；普通 restart 保留该层，以现役完整 compose 文件链 recreate 时使用新镜像。`KATRAIN_BUILD_SHA=4bf9a699a…` 仍只描述之前后端覆盖来源，不代表整棵网页源码。

| 环境 | 原运行镜像 SHA256 | 后续 recreate 持久镜像 SHA256 |
| --- | --- | --- |
| TEST | `2eaccedb9fe74f51810b9e77e2367bf2cd40b0181b19719c9b33c568fde735d8` | `d67dd7b38d7e0de615156f966447cadeddc377ec0b990c231ce5d51ae32570be` |
| PROD | `6ced68bdd5db0fde24838f384c450bcd7e329b681eaa40788578bc0a0c4042d2` | `5c82b80d306b5b4f1c5577c29da013d390041ac4f976d5888b8b307a168162fb` |

两站新 tag 均为 `katrain-galaxy-brand:20261024-10e120749af9`。可复核 Dockerfile 在本目录；构建上下文为 `payload/`，例如 `docker build -f test.Dockerfile payload/`，须先确认本地 FROM tag 的 image ID 与表中该站原镜像一致，避免使用另一主机/后来变更的同名 tag。

## 实际验收

[verification.json](verification.json) 记录实际 HTTP/CDP 与容器回执，原始 inventory before/after 同目录保留。两站均通过：

- CDP `CSS.getPlatformFontsForNode`：`Fondamento-Regular`、`isCustomFont=true`、9 glyphs；computed `"SmartBox Fondamento", serif`、16px、400、normal。之前实际为 `.SFNS-Bold`、14px、600。没有仅靠 `document.fonts.check` 判定。
- CSS/font 公网 200，下载 SHA256 与 artifact 一致；新浏览器直接从线上加载，无样式注入或 mock。PROD 字体响应 MIME 为既有服务的 text/plain，但 Chromium 实际成功解码/渲染上述 WOFF2，无需为本任务扩改服务器 MIME。
- `/api/v1/health` 200/status ok；`/openapi.json` 含原 `POST /api/pvp/territory`，匿名只读鉴权探针 401；棋谱列表有限 GET 200；原入口 JS、Galaxy JS、CSS、logo 均 200 且字节 hash 保持原值。
- 所有服务容器 ID/image/start time 相同，web env/mount/user/cmd 摘要相同；11 个同步模块及 server.py/领地 helper 共 13 个后端文件 hash 不变。cron、DB、GPU、MinIO、鉴权、调度和 receiver 未操作，无写者中断。
- 同尺寸 1280×720 before/after 全图逐像素比较：**两站差异均仅位于英文品牌字矩形 [134,18,200,33]**；该区域之外像素完全一致。中文字体/字号/字重/矩形、logo src/矩形、顶栏矩形亦完全相同。

真实截图保存在 [screenshots](screenshots)，[TEST 顶栏对比](screenshots/test-actual-before-after-topbar.png) 与 [PROD 顶栏对比](screenshots/prod-actual-before-after-topbar.png) 的上行为 before、下行为已发布 after。未启动新对局、付费任务或修改用户浏览器/RK；不为纯静态改动重跑业务测试或全量前端构建。

## 回滚与运行记录

| 环境 | 持久发布目录 |
| --- | --- |
| TEST | `/mnt/disk1/fan/galaxy-brand-font-20261024` |
| PROD | `/home/ubuntu/galaxy-brand-font-20261024` |

每个目录有 payload、Dockerfile、artifact.json、prepared.json、activated.json、verification.json 和 `rollback/index.html`、`rollback/last-compose.override.json`。原最后 override 路径见对应 [test-deployment.json](test-deployment.json) / [prod-deployment.json](prod-deployment.json)；它位于各站 `golaxy-name-guard-overlay-4bf9a699a-20261024/golaxy-web.override.json`。仅 image 字段从旧 tag 改为上述新 tag，原文件完整备份保留，其他 compose 文件 hash 不变。

若需热回滚，先确认当前 container ID、index hash 和最后 override hash 仍与回执一致，避免覆盖后来发布；将备份 index 复制到同目录临时文件后原子 rename，并将备份最后 override 同样原子恢复。无需重启；新增 hash 资源可以留存。若已发生后续部署/recreate，应基于其最新状态重新判断，不能盲用旧回滚。字体授权 [OFL-Fondamento.txt](OFL-Fondamento.txt) 随 artifact 留存。

本任务无需必须后续操作；已经打开的旧网页正常刷新即可。整个新版网页发布仍是独立任务，不包含在本轮字体覆盖中。
