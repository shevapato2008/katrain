# 逐手确认 · 真实前端切片

2026-10-12。用户已确认实际前端；现已完成真实后端集成和浏览器验收，正在合并发布。

以下 runtime 截图来自前端确认阶段的隔离 HTTP/WebSocket Fixture。该临时 Fixture 已在真实集成验收后删除，生产应用未新增预览路由或模拟业务数据。

## 同尺寸视觉核对

画布均为 1024×600。[并排图](./runtime-side-by-side.png) 左侧为已确认 HTML，右侧为运行时；[四图](./runtime-comparison.png) 下方分别为 50% 叠加和像素差异。

| 项目 | 核对与差异 |
|---|---|
| 构图/几何 | 三栏 224 / 512 / 224，16px 间距；主体在 (16,70)，992×516。两侧确认键均 190×108，y=461；主面板、时钟与提示无内部溢出。 |
| 组件层级 | 时钟与大确认键保持首要层级；等待方降低亮度且姓名/时间可读；辅助操作在两侧固定位置。 |
| 字体/色彩 | 复用真实 kiosk 字体资源、青玉/深灰/琥珀。真实字库的部分中文字重较 HTML 内嵌字库细，已实际查看，文案可读。 |
| 棋盘材质 | 用现有 Canvas、真实木纹和棋子资源替代原型 SVG，木色更亮、棋子细节不同；外框保持 512px，交叉点与坐标按现有准确刻度对齐规则，网格较原型展开。未更改共享棋盤材质。 |
| 图标 | 顶栏沿用共享 speaker-high / arrow-left 图标；确认键使用可读勾号。 |
| 文案/语义 | 实体盘提示移开双手再确认；屏幕版显示最后预选坐标，允许再次改选。多子用虚线圈，未拿净提子用叉号；失败不表示已换方。 |
| 终局/显示偏好 | 终局仍走原 GamePage 布局和结果组件。坐标/手数显示偏好保留在“落子说明”的显示设置中。 |

代表画面：[实体盘](./runtime-black.png)、[屏幕预选](./runtime-screen-selected.png)、[提交中](./runtime-screen-confirming.png)、[已接受](./runtime-screen-accepted.png)、[多子](./runtime-multi.png)、[提子待拿净](./runtime-capture.png)。

## 行为验证

- 6 个相关 Vitest 文件共 **161 项通过**，覆盖既有 GamePage/人机/音效行为及新增预选、连点、失败保留、换局清理与认输归属。
- 实际浏览器先选 E5 再改 F6，确认前没有提交；请求仅含 `[5,5]`（F6），确认后预选清除并切白方。连续状态巡检无页面 JavaScript 异常。
- 实际 `HTMLMediaElement.play()` 观察：预选期间 0 次；成功显示第 34 手后 `stone1.wav` **1 次**。复用现有画面完成后的 WebSocket 音效链路，没有给确认按钮另加重复音效。
- 逐手确认两段引导语已生成 MP3，尊重独立语音偏好；“播放说明”可重播。失败、预选或改选不播放落子音效。
- TypeScript 检查、聚焦 ESLint、`build:kiosk-2d` 和 kiosk 构建边界检查通过。测试环境已有 Node localStorage 提示与 React Router 升级提示，不影响上述行为。

## 真实后端集成

真实 `/api/local/ready`、`/api/local/confirm` 已接入。后端拥有回合、计时、棋谱与幂等约束，实体识别窗口完整复用自由对弈识别及 reference 后处理。生产只在服务端下发 `local_confirmation.enabled` 后启用新流程。

实际 API、数据库认证、WebSocket 与 React 页面联调证据见 [INTEGRATION-REVIEW.md](./INTEGRATION-REVIEW.md)。本地软件验证不代表 RK3562 实体盘已经验收；设备发布单独记录。
