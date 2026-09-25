# 教程管理：Galaxy 风格 Fixture 视觉对比

状态：Fan 已确认新版四图，可进入本地数据契约及后台实现；此确认不授权远程、真实写库、push 或部署。两态均为 1440 × 900：左列是已确认的 Galaxy 风格 HTML 设计稿；右列是本机 Chromium 打开的独立 React admin Fixture。设计截图和运行时截图不是同一来源。

| 状态 | 设计参考 | 运行时 Fixture | 并排 | 叠加 | 差异 |
| --- | --- | --- | --- | --- | --- |
| 图详情 | [参考图](./tutorial-admin-design-galaxy-detail-1440x900.png) | [实现图](./tutorial-fixture-galaxy-detail-1440x900.png) | [并排](./tutorial-fourup-galaxy-detail-side-by-side.png) | [叠加](./tutorial-fourup-galaxy-detail-overlay.png) | [差异](./tutorial-fourup-galaxy-detail-diff.png) |
| 编辑中 | [参考图](./tutorial-admin-design-galaxy-editing-1440x900.png) | [实现图](./tutorial-fixture-galaxy-editing-1440x900.png) | [并排](./tutorial-fourup-galaxy-editing-side-by-side.png) | [叠加](./tutorial-fourup-galaxy-editing-overlay.png) | [差异](./tutorial-fourup-galaxy-editing-diff.png) |

## 差异与核对

- 构图和几何：页眉 52px、1440px 档左栏 216px、标题区 64px；参考图与实现图的三栏边界一致。浏览器整页宽高为 1440×900，无整页溢出。编辑态右侧滚动区 `scrollHeight=760`、`clientHeight=615`；滚至底部时末项底部 715px，固定操作区顶部 731px，未遮挡。
- 字体和材质：两边复用本地 `LXGW WenKai`、`Galaxy Long Cang` 品牌字及仓库 `logo-white.png`；Chromium 确认文楷字样已加载。表面色取 Galaxy 的 `#0f0f0f`、`#252525`，灰绿主色 `#4a6b5c`。不新增远程字体。图标库与设计稿字符图标细节仍略有差别。
- 棋盘：外框/木色一致；实际共享 `SGFBoard` 的网格内边距和棋子比 HTML 静态原型更大，这是可编辑运行时组件的真实差异。未用棋盘图片冒充交互。
- 文案和状态：设计稿为 10 图示意，Fixture 只有 2 图样本；Fixture 明写“本地演示”“本地示意页，非原书扫描”“音视频未接入”，登录与保存均不访问服务。这些差异是为了不伪装真实内容或成功状态。右侧演示反馈、加载错误及重试由 React Fixture 提供。
- 行为：聚焦测试 13/13，lint 与独立 admin 构建通过；真实 Chromium 演示登录和右栏滚动核验完成。此阶段不声称真实身份、教程 API 或生产验收通过。

**Fan 已确认新版四图。** 进入契约与本地后台实现时仍须遵守切片 0 先发布及所有外部操作逐项审批的边界。
