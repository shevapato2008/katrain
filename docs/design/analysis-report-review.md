# 分析报告页面评审

本分支统一了桌面端的职业棋谱报告与个人复盘报告，以及 RK3562 盒端对应页面。按当前 React / Canvas 实现逐项复原的 HTML 原型：[analysis-report-preview.html](analysis-report-preview.html)。它从源码加载现有的 logo、字体、木纹与棋子素材。

HTML 根据浏览器 viewport 展示 Galaxy 桌面版或 1024×600 盒端版。职业棋谱为默认模式；个人报告在网址后加 `?mode=personal`；如需在预览页内切换模式，加 `?controls=1`。示例棋局数据来自本地测试 fixture 或设计样本，仅供视觉与交互评审。

本次校正了桌面预览在浏览器默认缩放下的布局：右栏按现有 Galaxy 棋盘页的宽度规则计算，棋盘保持正方形；推荐区固定露出四行，第五行可在该区滚动查看；走势图按可用高度收缩。预览以浏览器 100% 缩放查看即可，无需手动调到 80%。

## HTML 预览截图

- Galaxy 2048×1080：[职业棋谱报告](analysis-report-preview-desktop-2048.png)
- RK3562 1024×600：[职业棋谱报告](analysis-report-preview-kiosk-professional-1024.png)、[个人复盘报告](analysis-report-preview-kiosk-personal-1024.png)、[分析弹层](analysis-report-preview-kiosk-analysis-1024.png)

棋盘格距、棋子图、终手圈、AI 胜率与 visits 标记来自现有 `LiveBoard` 绘制规则；盒端按当前页面的 516×516 木纹框、28px 坐标带、460×516 右栏和 44px 操作行还原。右栏、五选点、状态行、逐手控制、评分 tab 与弹层按现有组件排列。预览中的跨模块导航、重算入口只说明目标位置，不发起真实请求。

## 实际页面截图

- 桌面 2048×1080：[个人报告](analysis-report-runtime-desktop-2048.png)
- 盒端 1024×600：[职业棋谱报告](analysis-report-runtime-kiosk-professional-1024.png)、[个人复盘报告](analysis-report-runtime-kiosk-personal-1024.png)、[分析弹层](analysis-report-runtime-kiosk-analysis-1024.png)

截图由真实 React 页面和路由请求模拟数据生成，展示布局与交互状态；不是正式环境的棋局数据。2026-10-03 的桌面个人报告及盒端职业、个人报告截图已按确认后的 HTML 排版重新拍摄。HTML 原型可以切换桌面/盒端和职业/个人模式。

## 已实现的交互

五个 AI 候选点与棋盘标记、逐手播放和进度条、胜率/目差与七档分析、对局详情、坐标和支招开关。桌面右栏在目标尺寸不滚动，盒端已完成报告在 1024×600 不滚动。详细分析使用原位展开（桌面）或弹层（盒端）。白方待落子与让子局按 SGF 棋色显示推荐数据和变化图。

盒端任务失败或重试提示在固定右栏内覆盖显示，不会把底部导航挤出屏幕。设计已获用户确认并在本分支实现；本分支尚未部署。
