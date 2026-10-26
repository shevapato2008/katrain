# 新 ucloud 隔离恢复：代表真实功能只读验收

日期：2026-10-27。对象：新机 `10-60-162-188`，未触碰旧生产机、DNS、服务配置或业务数据。

结论：本轮已验范围未发现新的服务阻塞。共 60 个有界 GET（含一次 HTTP/1.1 WebSocket Upgrade）；47 个 HTTPS 请求均正常验证证书，`ssl_verify_result=0`。每次 curl 上限 30 秒，未重试服务失败。所有请求通过新机 loopback staging nginx（HTTPS 使用原域名 SNI，443 映射至 `127.0.0.1:18443`）或新机 loopback 服务端口完成。

## 验收结果

| 项目 | 状态 | 实际证据与边界 |
| --- | --- | --- |
| 主 Web / Galaxy / kiosk | PASS | `modelstella.com/`、`/galaxy/`、`/kiosk/`、`www.modelstella.com/` 均 HTML 200，内容哈希一致；入口 JS、runtime、ui-core、API JS、入口 CSS 以及 GalaxyApp / KioskApp 的 JS 与 CSS 均 200，响应类型正确。 |
| 主 Web 健康 | PASS | `/api/v1/health` 200：status ok，version 1.17.1，local engine reachable。未重复提交 GPU 推理。 |
| 公开棋谱入口与列表 | PASS | `/galaxy/kifu` HTML 200；`/api/v1/kifu/albums?page=1&page_size=4&lang=cn` 200，total 176625，首四行见下表。仅有界读取公开列表，未扫描 SGF。 |
| 红框相关 rank snapshot 字段 | PASS（契约） / PENDING（真实屏幕） | 四条代表记录携带 display rank、origin 与来源 snapshot；unknown 保持空串，未捏造段位。此轮只验 HTTP 与数据契约，未执行浏览器截图、实际屏幕渲染或设备视觉验收。 |
| 五语同一代表棋谱 | PASS | cn/tw/en/jp/ko 共 5 GET（cn 复用上述列表），均 200，同一 ID 178765、total 176625，翻译字段实际变化且段位保持 `空 / 8p`。这里只验证恢复与展示契约，未审校历史译名。 |
| 教程分类与公开媒体 | PASS | `/api/v1/tutorials/categories` 200，共四类；真实 page_011.png 的 `/api/v1/tutorials/assets/{key}` 302 到 `https://modelstella.com/media/{key}`；只请求同一对象一次 Range，取得 206、1024 字节，完整证据见下。 |
| 报告入口 | PASS（公开入口） / PENDING（登录后） | `/galaxy/report` HTML 200，实际 ReportsPage 延迟加载 JS 200；未访问私人报告正文、创建任务或触发分析。 |
| 练习入口与题库 | PASS | `/galaxy/tsumego` HTML 200，TsumegoLevelsPage JS 200；`/api/v1/tsumego/levels` 200，22 levels / 21072 problems。未读取或写入个人进度。 |
| 平台健康与大厅静态资源 | PASS | 8090 `/health` 与 lobby / ranked 两个域名 `/health` 均 200，source_rev `419d2c7cb42145951ff62710faaf4ed31b369b03`；`/lobby/chess/` HTML、其 JS/CSS、共享 fonts.css 与一个字体文件均 200。 |
| 平台 SSO / 登录边界 | PASS（未认证边界） / PENDING（真实会话） | `/api/v1/auth/me` 无凭据 401；`/auth/callback` 无 code 返回 HTML 400；`/kiosk/login` HTML 200。没有兑换 code、登录用户、创建账号或执行 POST。 |
| 平台 WebSocket | PASS（代理与拒绝边界） / PENDING（真实会话） | 同源、无凭据的 HTTP/1.1 `/ws/lobby?variant=chess` 实际返回 101，随即收到 close code 1008 / `No credentials`。未进入已认证大厅或对局。 |
| 统一 Admin 健康与登录壳 | PASS | 8010 `/api/admin/health` 200，katrain / platform 两个 providers 均 available；`/admin` 与其 JS/CSS 200。Go provider 18010 的同名健康端点无 admin session 返回 401，符合 provider_only 边界；统一 Admin 的 provider 汇总已验证其实际可达性。 |
| Legacy Kifu A/B | PASS | 8013 / 8014 的 `/api/v1/kifu/health`、`/readiness`、`/search?limit=1&offset=0` 全部 200；两个实例 games / public_total 241719，active_generation = catalog_generation = 2，plan_cache_forced true；readiness 与搜索响应哈希分别一致。 |
| Pitch | PASS（已验公开路径） / PENDING（写入旅程） | `pitch-api-staging.modelstella.com/api/v1/health` 200 / status ok；`/platform-admin` 与其 styles.css / main.js 200；根路径 404，符合 Caddy 仅允许 `/api/*` 与 `/platform-admin*`。未登录、预约、支付、创建任务或迁移 schema。 |
| 外部入口切换与后台 writer | PENDING | 目前仍为 loopback staging。生产 DNS / public nginx / VPN 切换未由本轮执行；业务 cron、Pitch worker 和 NativeReceiver 实际写入旅程不在此轮只读验收内。 |

## 四条公开 snapshot

| ID | 黑方 | 黑段位 / origin | 白方 | 白段位 / origin |
| --- | --- | --- | --- | --- |
| 178765 | 池本辽太 | 空 / unknown | 六浦雄太 | 8p / library_current |
| 178764 | 金恩持 | 9p / library_current | 仲邑菫 | 空 / unknown |
| 178763 | 赵治勋 | 9p / library_current | 许家元 | 9p / library_current |
| 178762 | 羽根直树 | 9p / library_current | 田中伸幸 | 5p / library_current |

五语代表的黑方 display name：cn `池本辽太`，tw/jp `池本遼太`，en `Ryota Ikeguchi`，ko `이케구치 료타`。均读取恢复库中的实际公开展示值。

## 媒体精确证据

- key：`tutorial_assets/曹薰铉布局技巧-上册-曹薰铉-1997/pages/page_011.png`
- API：302，Location 为新批准的 `https://modelstella.com/media/...`，没有访问旧预览域名。
- 对象：206，`Content-Range: bytes 0-1023/64338`，`Content-Type: image/png`，1024 字节。
- SHA-256：`68f53c831803a81cd42b6a09be11c09030c4ee07f7a2774028c6882081650ad4`，与 controller 先前单对象证据完全一致。
- 旧基线异常：旧媒体域名 NXDOMAIN 是 controller 提供的既有基线；本轮未访问旧机复测。新 staging 的 API→302→真实字节链路已通过。

## 路由误判排除与原始证据

已先读实际 nginx / Caddy 配置及部署镜像中的路由源码。统一 Admin 明确禁用 OpenAPI，因此该处 `/openapi.json` 404 不构成服务故障；真实 `/api/admin/health` 已 200。lobby / ranked 根路径有意由 nginx 拒绝为 404。最初一次 WebSocket 请求协商为 HTTP/2，仅得到普通 GET 404；随后用标准 HTTP/1.1 Upgrade 一次取得 101 + 1008，前一请求不解释成 WS 服务失败。

新机原始请求元数据、响应头和响应正文：`/var/lib/ucloud-migration-20261027/services-preflight/`。目录权限 700，所有文件 600，`requests.jsonl` 共 60 条。原始响应仅保存在新机私有目录；本报告不包含认证数据。未修改账号、锁、队列、模型、MinIO policy、外网 network、服务或数据库。
