# 教程管理 Fixture：1440 × 900 同尺寸视觉对比

状态：**旧版对比，已被 Galaxy 风格/字体新要求取代**。Fan 曾确认此版四图，但此记录不再作为进入后端的当前视觉关卡。下表参考图来自旧版 HTML 设计稿；实现图来自本机 Chromium 打开的独立 React admin 入口，非同一张设计截图。两种状态均为 1440 × 900。

| 状态 | 参考图 | 运行时实现 | 并排 | 叠加 | 差异 |
| --- | --- | --- | --- | --- | --- |
| 图详情 | [设计](./tutorial-admin-design-detail-1440x900.png) | [Fixture](./tutorial-fixture-detail-1440x900.png) | [并排](./tutorial-fourup-detail-side-by-side.png) | [叠加](./tutorial-fourup-detail-overlay.png) | [差异](./tutorial-fourup-detail-diff.png) |
| 编辑中 | [设计](./tutorial-admin-design-editing-1440x900.png) | [Fixture](./tutorial-fixture-editing-1440x900.png) | [并排](./tutorial-fourup-editing-side-by-side.png) | [叠加](./tutorial-fourup-editing-overlay.png) | [差异](./tutorial-fourup-editing-diff.png) |

## 核对记录

- 构图与间距：页眉 54 px、左导航 180 px；内容三栏边界、标题区、右侧操作区在并排图中基本对齐。浏览器页面无整页滚动，右侧讲解区可独立滚至审核状态，固定操作区不遮挡最后一项。
- 棋盘：外框位置和木色接近；实现使用真实共享 `SGFBoard`，棋线比 HTML 原型更接近边缘，棋子也更大。这是组件本身的实际渲染差异，不用静态图片假装棋盘；图编辑中的落子、撤销可操作。
- 层级、字体、颜色与材质：深灰背景、暖木棋盘、灰绿按钮、三栏密度及主要标题层级一致。实现沿用本地中文系统字体与图标库；个别图标细节、正文换行与设计稿不同。
- 文案与状态语义：Fixture 仅有 2 张示例图，而原型写 10 张；实现明确标注“本地演示会话”“本地示意页，非原书扫描”“音频/视频未接入”。登录不验证真实身份，保存、生成语音、逻辑检查及审核只改变页面内存或显示演示反馈。原型中的可播放媒体或真实后台语义不能在此阶段伪装成已接入。
- 加载/错误/重试：本地 Fixture 有加载态与加载失败重试；真实网络 401、保存冲突、TTS/媒体失败留待后端集成时接入，不在视觉图中假造成功状态。

此记录保留第一版差异证据。新版 Galaxy 风格设计、Fixture 和四图需重新确认；新四图确认前，不冻结契约、不启动教程后台实现。
