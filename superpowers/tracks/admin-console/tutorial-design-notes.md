# 教程管理切片：设计方向（Galaxy 视觉修订已获 Fan 确认；新版 Fixture 四图待确认）

> 后续视觉变更：Fan 已选后台专属 B「石墨铜」夜间版、C「雾白蓝」白天版与楷体，不再沿用公开 Galaxy 的绿色主题/文楷界面。新[本地设计稿](./tutorial-admin-design-v2.html)及[React 同视口核对](./tutorial-theme-visual-review.md)优先于下方旧配色说明；Fan 已确认新 React 外观，但这不等于教程模块验收。

- 目标视口：1440 × 900，桌面浏览器；参考 Fan 提供的现有 Galaxy 教程编辑截图。该截图是**后台工作台**参考，不是公开用户成品页。
- 独立站点：页眉写明「KaTrain 管理后台」和本机/测试/生产环境；教程是第一个完整模块，cron 导航暂不提供假页面。
- 用户旅程：登录后台 → 选书/章节/图 → 对照原书页与 2D 棋图 → 编辑棋图或讲解 → 保存/生成语音/审核 → 切换下一图。公开 Galaxy 的成品阅读由另一 session 负责。
- 构图：左侧后台专用导航；内容区三栏（原书页、棋图、讲解/媒体/操作）。不照搬公开站的业务路由，但视觉与普通用户的 Galaxy 页面一致。
- `ui-ux-pro-max`：以“内部深色密集工具”和“深色教学工作台”为检索方向，采用其高信息密度、可见焦点、键盘可达、错误贴近输入和明确当前导航建议。检索返回的营销页结构及蓝黑/荧光绿、靛紫/橙色配色均不适合现有产品，视觉以 Galaxy 现行主题为权威。
- Galaxy 视觉修订：取自 `src/theme.ts` 与 `src/galaxy/theme.ts` 的 `#0f0f0f` 背景、`#252525` 面板、`#4a6b5c` 灰绿强调、`#f5f3f0` 主文字，中文复用本地 `LXGW WenKai` 字体；品牌用 `Galaxy Long Cang`「智星盒」及系统字体 `StellaBox`。页眉 52px；1440px 视口侧栏 216px；按钮圆角 8px。原书纸页与木色棋盘继续保留。这些都是本地资产，没有新增远程字体请求。
- 修订原型：[tutorial-admin-design.html](./tutorial-admin-design.html?state=detail)；[登录](./tutorial-admin-design-galaxy-signin-1440x900.png)、[详情](./tutorial-admin-design-galaxy-detail-1440x900.png)、[编辑中](./tutorial-admin-design-galaxy-editing-1440x900.png)均为本机 Chromium 1440×900 截图。旧版预览仍保留供对照。设计稿中的数据是隔离的展示样本，不进入生产构建。
- 独立 admin 构建应复用 Galaxy 视觉资产，但不导入 Galaxy 业务路由、认证或完整应用；现有字体文件在 `src/galaxy/assets/fonts`，实现时需移到中性共享资产路径或用 admin 独立资源，保持 SBC 构建隔离。`katrain/img/logo-white.png` 是本地品牌图。
- 契约待四图对比后冻结：后台同源 `/api/admin/tutorials/*`，独立后台令牌，原书图/音视频 URL 可在隧道内读取；保存需要 `expected_updated_at`，错误/重试要贴近对应操作；开发 Fixture 在后端集成后删除。
- 视觉关卡：旧设计稿及其 Fixture 四图曾获 Fan 确认，但 Fan 随后要求与普通 Galaxy 页面风格、字体一致，因此旧四图不再代表最新视觉基准。本修订设计稿已获确认；临时 Fixture React 页面已换肤，见[新版四图记录](./tutorial-visual-review-galaxy.md)。新四图确认前暂停该模块后端。
