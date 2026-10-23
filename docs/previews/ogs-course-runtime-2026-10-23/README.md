# OGS 课程运行预览（1024 × 600）

截图来自真实 Kiosk React 运行时，课程数据由现有 TEST 导出导入到临时本地 SQLite，通过实际只读课程 API 提供。未使用设计稿的示例数据，也未向生产库导入内容。

| 页面 | 实现 | 同尺寸对照 | 叠加 | 差异 |
| --- | --- | --- | --- | --- |
| 课程首页 | [截图](home-runtime.png) | [并排](home-side-by-side.png) | [叠加](home-overlay.png) | [差异](home-difference.png) |
| 章节课目 | [截图](chapter-runtime.png) | [并排](chapter-side-by-side.png) | [叠加](chapter-overlay.png) | [差异](chapter-difference.png) |
| 棋盘练习 | [截图](exercise-runtime.png) | [并排](exercise-side-by-side.png) | [叠加](exercise-overlay.png) | [差异](exercise-difference.png) |

[19 路局部棋盘与实体盘不可用状态](physical-19-crop-runtime.png)：真实导入的布置题采用 19×10 裁切，A/B/C 标记已保持可读。当前预览环境没有摄像头和视觉服务，因此入口如实禁用并说明原因。实机识别、摆局、应手及提子需在 RK3562 部署后验收。

对照结论：内容区的左右栏宽度、卡片位置、棋盘坐标、按钮层级与参考稿相符。运行截图顶部缺少完整品牌图，并显示 AI 引擎状态横幅；这是本次隔离预览只启动课程 API、未启动完整静态资源和 KataGo 服务所致。练习稿原先没有实体盘按钮，新版按已确认需求加入该按钮与状态提示。

实际走通的来源数据：第一课棋盘落子后进入下一步；`ending-the-game` 三步依次为停一手、棋盘拿除死子和确认终局；选项题、旧教材入口及不可用提示也已核对。
