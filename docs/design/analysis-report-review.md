# 分析报告页面评审

本分支统一了桌面端的职业棋谱报告与个人复盘报告，以及 RK3562 盒端对应页面。HTML 原型：[analysis-report-preview.html](analysis-report-preview.html)。

## 实际页面截图

- 桌面 2048×1080：[个人报告](analysis-report-runtime-desktop-2048.png)
- 盒端 1024×600：[职业棋谱报告](analysis-report-runtime-kiosk-professional-1024.png)、[个人复盘报告](analysis-report-runtime-kiosk-personal-1024.png)、[分析弹层](analysis-report-runtime-kiosk-analysis-1024.png)

截图由真实 React 页面和路由请求模拟数据生成，展示布局与交互状态；不是正式环境的棋局数据。HTML 原型可以切换桌面/盒端和职业/个人模式。

## 已实现的交互

五个 AI 候选点与棋盘标记、逐手播放和进度条、胜率/目差与七档分析、对局详情、坐标和支招开关。桌面右栏在目标尺寸不滚动，盒端已完成报告在 1024×600 不滚动。详细分析使用原位展开（桌面）或弹层（盒端）。白方待落子与让子局按 SGF 棋色显示推荐数据和变化图。

盒端任务失败或重试提示会占用额外空间，此时可滚动以保留完整错误信息与操作入口。设计仍待用户最终视觉确认；本分支尚未部署。
