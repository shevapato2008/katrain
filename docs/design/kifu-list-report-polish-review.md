# 棋谱与报告局部调整 · 2026-10-09

状态：用户已审核通过并授权发布。设计基于 develop `12b3d54c`；实施分支 `feature/kifu-list-report-polish` 已同步 develop `c0483a6a`。发布按仓库集成与部署流程执行。

- Kiosk 保持 1024×600：棋盘仍为 x16/y70，516×516；报告右栏仍为 460×516。
- 棋谱库删除“导入 SGF”；报告/棋谱以 18px 图标表示，整张卡片保留原跳转语义。右侧棋手、日期、手数对齐到同一右边缘。图标提供可访问名称与悬停提示。
- Kiosk 与 Galaxy 统一为 `[<] [可输入页码]/总页数 [跳转] [>]`，删除“第”“页”“共”与 Galaxy 编号分页。箭头居中。直接输入整数页码，点击“跳转”或回车；合法范围 1 到总页数，非法输入留在当前页并提示。搜索改变后回到第 1 页。数字输入用于触摸键盘，箭头/跳转保持 44px。
- Galaxy 同样使用一行紧凑分页；保留上一页、下一页的边界禁用状态。
- 报告播放条不继承文字输入框的内边距。0 手与末手的滑块圆心分别对齐可见轨道两端。
- 职业/个人报告把“清空”替换为“实体棋盘”，复用 BaipuSession 的 SGF 缓存、19 路限制、硬件识别/LED/恢复进度。返回回到对应报告。切换手数、退出试下和关闭候选变化仍会清理预览。

## 数据与验收边界

设计数据复用原有隔离快照（职业棋谱 24171）。只收录前两页；其他页诚实展示预览缺少快照，绝不伪造线上结果。设计预览中的实体棋盘按钮仅展示流程说明，不控制设备。Fixture 位于 docs/design，产品无依赖。

实际实现已接入现有棋谱 API 和实体棋盘摆谱流程。本轮浏览器验收运行构建后的前端，使用隔离的 API 快照校验布局、导航、跳页和返回；未运行后端或连接实体棋盘。设备上的摄像头识别和 LED 引导需在后续部署后验收。

最低充分验证：列表卡片布局/跳页合法与非法输入；两类报告实体棋盘入口及返回/19 路限制；播放条 0、中段、末手；Galaxy 窄右栏分页；全量与 kiosk 2D 构建。已有测试只补本次行为。

## 已完成的聚焦核对

- Kiosk 预览无 JavaScript 错误。跳转第 2 页通过；输入 0 不改变当前页。
- 实体棋盘流程说明可打开；没有连接硬件。
- 0 手、46 手、211 手预览截图已检查；圆心对齐可见轨道端点。
- 基线测试：KifuPage、KifuReportDetailPage、ReportDetailPage 共 93 项通过。
- 同 viewport 的参考、预览、并排与 50% 叠加已生成。
- 构图、字体、色彩、棋盘位置不变；差异限于卡片入口/右对齐、分页与报告实体棋盘按钮/播放条。右侧白棋身份中的棋子圆标放在姓名前，便于姓名和日期末端对齐。
- Galaxy 预览使用当前发布前端（modelstella.com）的只读数据快照，1440×900，309px 分页可用宽；统一紧凑分页一行摆放，44px 控件在窄栏内完整显示。

## 实现自测与审核截图

- 同步 develop 后，5 个相关测试文件共 112 项通过（新增包含大厅回归检查）：列表/搜索、合法与非法跳页、职业/个人报告、完整 SGF 导航与报告返回、非 19 路入口禁用。
- 常规前端构建及 strict kiosk 2D 构建通过；kiosk 构建边界检查通过。`git diff --check` 通过。
- 构建产物浏览器验收通过：Kiosk 1024×600、Galaxy 1440×900；白方姓名与日期/手数右边缘均为 x989，分页控件圆心均为 y482。
- 触屏页码输入自动打开数字键盘；输入区保持在键盘上方；键盘“跳转”、按钮和回车均使用同一提交逻辑。提交后关闭键盘。Galaxy 跳页保留搜索条件。
- 职业与个人报告的第 0 手、末手，以及实体棋盘入口和返回标签通过；摄像头与 LED 尚未进行实机验收。
- 后端和设备配置未修改；旧报告中的“清除变化”、退出试下与切换手数仍能清理预览。

截图来自修改后的构建产物：

- [Kiosk 棋谱列表](kifu-list-report-polish-assets/runtime-kiosk-library.png)
- [触屏页码输入](kifu-list-report-polish-assets/runtime-kiosk-page-input.png)
- [Galaxy 分页](kifu-list-report-polish-assets/runtime-galaxy-library.png)
- [职业报告第 0 手](kifu-list-report-polish-assets/runtime-professional-start.png) · [末手](kifu-list-report-polish-assets/runtime-professional-end.png)
- [个人报告第 0 手](kifu-list-report-polish-assets/runtime-personal-start.png) · [末手](kifu-list-report-polish-assets/runtime-personal-end.png)
