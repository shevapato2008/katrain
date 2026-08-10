# StellaBox 品牌边界

## Inventory

本次 inventory 使用以下范围：`katrain/`、`scripts/`，排除生成产物 `katrain/web/static/`、文档 `docs/` 和工作轨迹 `superpowers/`，搜索旧品牌 `弈航|BoardNavi`。

| 初始匹配 | 分类 | 处理 |
| --- | --- | --- |
| `katrain/web/ui/src/legal/terms.ts` | product-facing | 用户协议标题、产品名、账号和团队称谓改为“智星盒 / StellaBox” |
| `katrain/web/ui/src/legal/privacy.ts` | product-facing | 隐私策略标题、产品名和团队称谓改为“智星盒 / StellaBox” |
| `katrain/web/ui/src/galaxy/pages/Dashboard.tsx` | product-facing | 默认欢迎语改为“智星盒” |
| `katrain/web/ui/src/galaxy/components/auth/LoginModal.tsx` | product-facing | 默认登录标题改为“智星盒” |
| `katrain/web/ui/src/galaxy/components/layout/GalaxySidebar.tsx` 及测试 | product-facing | 移除旧的大尺寸品牌块；全局品牌由 `GalaxyTopBar` 承载 |

PO 文件没有 `弈航|BoardNavi` 初始匹配，但品牌专用键 `dashboard:welcome`、`auth:login_title` 中的 `Galaxy Go` 属于 product-facing 品牌文案：`cn` / `tw` 使用“智星盒”，其他 locale 使用 `StellaBox`。

## 保留边界

旧品牌 `弈航|BoardNavi` 没有保留匹配。

下列类别不属于产品品牌替换范围，保持原样：稳定内部名（例如 KaTrain、Galaxy 路由/组件名）、法定实体名、作者署名、第三方与许可证归属、数据库/API 枚举。Inventory 未在这些类别中发现 `弈航|BoardNavi`。

## Post-check

使用与 inventory 相同的搜索范围和排除规则复查，`弈航|BoardNavi` 无匹配。
