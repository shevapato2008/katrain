# 棋谱库首次加载与报告入口修复（2026-10-06）

## 原因与修复

- 列表原本只返回 20 条，约 10 KB；延迟并非下载全库。全库 COUNT 约 393ms，实际 20 条查询约 3.5ms。已在线建立可见谱计数索引，保留准确分页总数。
- 首次加载同时下载其他业务页面、随后再请求首局详情；现在按路由加载，HTML 提前请求当前页 20 条，列表只附带首条完整 SGF，详情复用这一份预览。
- 棋盘的两个绘制入口都在等待全部材质图片。现在立即用现有绘制函数和真实 SGF 画盘，图片加载完成后补齐材质；字体、素材与布局保留。
- 界面翻译曾等待直播译名接口，导致晚通知和额外英文列表请求。界面翻译现在独立通知，直播译名在后台加载。
- 网关未压缩 JS/CSS，并使用 HTTP/1.1。两站已开启前端文本 gzip 和 TLS HTTP/2；职业棋谱 JSON 仅在 `/api/v1/kifu/` 路径压缩。鉴权 API 与流式接口未加入 JSON 压缩。
- 最近 60 局原本只有正式主库有数据，测试主库已补入 12,664 个分析局面，详见同目录 `kifu-report-sync-20261006.md`。

## 数据与入口契约

`has_analysis` 由当前页的一次集合聚合查询计算，不读取分析 JSON；只有当前 SGF、模型 SHA256、2000 visits、已完成任务与全部连续局面满足校验时才为 true。字节完全一致的重复谱共享主谱结果。

- 有完整报告：Galaxy 显示「查看分析报告」，进入 `/galaxy/kifu/:id/report`；kiosk 卡片进入 `/kiosk/kifu/:id`。
- 没有报告：显示「查看棋谱」，进入对应 `replay` 路由。不请求分析、显示默认 50% 或声明深度报告；对局详情只显示棋谱信息。
- 已完成报告只下载一次；正在生成的报告按响应状态轮询，离开时停止。

最新一局 24171：两站公共接口均为 completed，211/211 手、212 个连续局面，最低 root visits 2003。模型 SHA256 为 `93bdb63a3bfae4a70db0cb5265287495ecfc10b1ba1cc6814feeba1cdf055871`。

## 实测与视觉验收

macOS Chrome，Galaxy 2048×1080，kiosk 1024×600；直接访问已部署网站，正常登录自建无特权 QA 账户。计时终点为真实棋盘像素已绘制或 20 条卡片已呈现，不是接口返回时间。

| 入口 | home 测试站 | ucloud 正式站 |
| --- | --- | --- |
| Galaxy，清浏览器缓存，复用站点连接 | 946ms | 691ms |
| kiosk，清浏览器缓存，20 条卡片 | 613ms | 633ms |
| 测试站 kiosk 点击最新对局至完整 211 手报告 | 869ms | — |

补测全新 Chrome 进程、首次站点连接：启用 HTTP/2 前 home 为 4485ms，启用后 **908ms**，导航协议 h2，首条列表请求在 83ms 开始、345ms 完成。

这些是本次网络和浏览器的实测，包含不同缓存/连接条件；不是任意网络的延迟保证。1024×600 为浏览器尺寸验收，未声称已在 RK3562 实机测 CPU/网络延迟。材质和字族可继续后台下载，棋局显示不等待它们。

已实际查看两站 Galaxy 最新报告和 kiosk 最新报告截图，并点击测试站无报告棋局 24107，确认「查看棋谱」进入回放；对局详情没有报告类型、分析状态或 visits，胜率显示暂无数据。报告右栏与 kiosk 页面没有整页滚动。

证据保存在工作树忽略目录 `output/playwright/`、`output/kifu-fix/public-verification.json`：

- `home-library-h2-final.png`
- `home-galaxy-report-24171-final.png`
- `home-kiosk-report-24171-1024.png`
- `prod-galaxy-report-24171-final.png`
- `prod-kiosk-report-24171-1024.png`

## 发布与后续部署

只更新 Web 与其静态目录；数据库、GPU 引擎和 cron 未重启，未启动新分析任务。部署保留了当天赛事译名、搜索和隐藏谱修复。

本次基础镜像为 `katrain-web:kifu-library-fast-{test,prod}-20261006`；随后其他开发工作在其上叠加 `katrain-web:tokyo11-title-{test,prod}-20261006`，已确认仍包含本次报告可用性与 preview 契约。**不能用较旧的完整 endpoint 文件覆盖这些后续变更**。本地分支不混入其他开发工作的源代码；后续合并/发布需保留这些变更。

发布目录：home `/mnt/disk1/fan/kifu-library-fast-20261006`，prod `/home/ubuntu/kifu-library-fast-20261006`。静态文件更新保留旧 hash 资源，最后原子替换 index.html，两站入口 hash 一致。Web compose override 加在当时完整配置链后，不移除其他配置。

网关配置已先备份、`nginx -t` 通过后平滑 reload：

- test：`alicloud-ecs-gateway` 的 `go.sailorvoyage.top` 站点。
- prod：ucloud 的 `modelstella.com` 站点。
- 前端压缩 include 对应仓库 `deploy/nginx/frontend-gzip.conf`；职业棋谱 location 沿用该站点的原 proxy 设置并增加 `gzip_types application/json`。
- 当前 Nginx 1.24 使用 `listen 443 ssl http2`（IPv6 同样开启）。

聚焦验证：前端 **65 passed**；后端 **21 passed / 1 skipped**（已有真实 PG 基准测试的条件跳过，本次已另行测量真实 PG）；标准生产构建通过；kiosk 2D 构建及 no-three/no-Galaxy/no-live-API 边界检查通过。独立 Astra 一轮审核发现的预加载重试与回放虚假元信息问题已修正。
