# 教程后台 B/C＋楷体视觉核对（Fan 已确认外观）

目标视口均为 1440×900。B「石墨铜」对应系统深色模式，C「雾白蓝」对应系统浅色模式；后台中文界面优先 `Kaiti SC`，Windows 使用 `KaiTi`，其他环境回退到仓内 `LXGW WenKai`。仅 `AdminApp.css` 的后台视觉发生变化，公开 Galaxy 和数据/权限逻辑未改。

- [交互式并排、叠加、差异对比](../../../output/playwright/admin-theme-visual-compare.html)：可切 B/C 与登录、详情、编辑三态。源图和运行图均为 1440×900；叠加透明度可调。
- B 详情：[设计参考](../../../output/playwright/admin-design-graphite-detail-kaiti-1440x900.png) · [React 运行](../../../output/playwright/admin-runtime-dark-detail-kaiti-1440x900.png) · [并排预览](../../../output/playwright/admin-visual-compare-graphite-detail-1440x900.png)
- C 详情：[设计参考](../../../output/playwright/admin-design-mist-detail-kaiti-1440x900.png) · [React 运行](../../../output/playwright/admin-runtime-light-detail-kaiti-1440x900.png) · [并排预览](../../../output/playwright/admin-visual-compare-mist-detail-1440x900.png)
- 登录和编辑态的 B/C 参考与运行截图也可在对比页切换；真实登录页没有使用模拟 API，详情与编辑态由 `output/playwright/admin-theme-preview.mjs` 临时拦截本地请求，仅用于视觉核对，不进入生产构建或真实数据库。

核对结果：

- 字体、色彩、材质：楷体及 B/C 主背景、面板、选择、焦点、操作强调均已进入 React；绿色主题未再显示。木色棋盘和原书白纸仍是内容素材，不作为后台主题色。
- 构图与间距：保留已有 React 工作台的 216px 左栏、235px 原书栏、388px 右栏，而设计参考为 194/246/390px；真实页多一个小节选择器。此差异来自既有功能布局，本次不重排。
- 内容与状态：参考图是展示样本（示意书页、9 路棋盘及示意文案）；运行图使用截图脚本的 19 路棋盘与缺失原书页/音视频状态，不能拿素材差异判定主题失败。运行页按钮为真实「预检查」语义，未冒充「逻辑检查」完成。
- 图标与文案：继续复用现有后台图标及功能文案，没有为视觉对齐改动功能含义。

Fan 已确认 B 夜间／C 白天＋楷体的本地 React 外观。此确认仅解除本次视觉停点；详情／编辑预览仍用了截图脚本模拟响应，不代表教程模块的真实后端集成或验收，也不授权远程连接、写库、push 或部署。
