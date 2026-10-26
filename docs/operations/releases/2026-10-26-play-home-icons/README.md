# 对弈首页五图标接入发布

旧修复 f37f7ea7f1b259b4ae2e54a166defd4228fbd9fe 留在独立分支，未合入 develop。主调试分支曾仅加入对比 PNG；图片并非产品代码。2026-10-26 的最新 develop93f2038a0 及 RK 同源实际页仍只有五个右箭头，没有前导图标。不能将此归因为缓存或已上线代码遭后续回退。

沿用已批准的 2026-10-23 Play Home Icons 计划和既定 Kiosk 设计，按最新源码最小接入七个产品/测试文件：五入口分别使用机器人、奖杯、双人、地球、带钟针的历史图标。按钮尺寸、标题字号、文案、无障碍名称、导航、禁用和平台品牌标记保持。新增 Phosphor v2 clock-counter-clockwise regular/fill 与 manifest；Smartbox canonical 资产包同步相同字节，避免下次共享资产同步丢失。

## 验证

- 产品候选 277b09e17808b956468a9227c8f0d7e115fe6b34；基线及修改后现有三组测试均 34/34，diff check 通过。
- 完整构建与 strict Smartbox 2D 构建通过；strict SSO/2D资源边界通过。
- 代表真实 Chromium 使用 strict 打包静态产物，1024×600、楷体最大，与设备一致。五前导 SVG 均可见24×24，五右箭头20×20，五按钮219×63，标题22px，无标题截断或页面溢出。[实机修改前 / 本机实际产物预览](screenshots/before-preview.png)、[预览几何](preview-dom.json)。右图使用仅浏览器中的只读固定输入，时钟及问候为当时时间；不是设备已部署凭证。
- 设备修改前截图为真实 `/kiosk/play`，只读捕获，没有导航、修改偏好或操作盘面。设备当时 source93f、PID825578，vision unbound。

审核与最终发布回执在操作完成后追加，未完成部署前不得以预览替代实机验收。
