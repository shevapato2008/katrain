# 管理后台可点击原型

发布为 Artifact：https://claude.ai/artifact/AhKNmhErvEHoFovBmKMkyn （私有）。

- `src/`：原型脚本与样式；`python3 build.py` 把 `AdminApp.css`、`CronPage.css`、logo 与品牌字体内联，生成单文件 `index.html`（不入库，随时重建）。
- 全部数据为标注过的示意，不连接任何服务；「原型控制」切换点不到的状态（错误、陈旧、主题）。
- 2026-09-26 v2 按 Fan 意见改：视觉实验室三个子模块移入侧栏折叠菜单；采集页原图 / warped / 标注改为标签页，加入棋谱库搜索与指示灯逐手摆谱（复用 `baipu_capture.run_capture` 语义：红=黑、绿=白、蓝=提子，确认后等灯稳定再抓帧）；诊断页七阶段改为标签页大图。
