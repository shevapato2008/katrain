# Kiosk 弹窗字体独立审核

结论：**Approved — 允许进入既有发布流程。无 must-fix。**

- 审核日期：2026-10-25；分支：`fix/kiosk-dialog-typography-20261025`；基线：`597f3a9b96cdafe92df5115d4d82b228b755d2c2`。审核对象是当前未提交的 `tokens.css`、`KioskApp.tsx` 及新增 `dialog-typography.css`。
- 代码：18 / 22 / 28px 基准接入原有 `installKioskTextSizing`，没有新增字号状态；字体变量仅在 Kiosk 激活时扩展至 body，解决 MUI portal 继承。选择器受 `.kiosk` 或 `body[data-kiosk-typography]` 限制；Galaxy/admin、教程 19 路/policy、玩家卡片间距及真实等级逻辑没有改动。危险色、动作和业务数据流程保留。
- 视觉：亲眼检查 1024×600 删除弹窗修改前后、大/小字号、并排、叠加/差异图，以及 MUI 棋谱库导入大/小字号截图。字号层级明显改善，正文和操作完整，无遮挡或裁切；small 档继续按已有规则从基准减 4px。实现方提供的 CDP 记录确认 portal 标题实际使用 TW-Kai。
- 独立补充预览：在本机 Chrome 的真实 Kiosk 运行环境中，以现有 `kioskTheme` 挂载实际 `PhysicalSyncEscalationDialog` 组件，使用本地 fixture 和空回调。380px 侧栏弹窗实测为 380×311px，标题 28px、按钮 22px；长说明和三颗按钮完整可见、自然换行，没有横向溢出。证据：`output/playwright/kiosk-dialog-typography/side-dialog-astra-large.png`。未操作真实棋局或设备。
- 验证：本次独立执行 `git diff --check` 通过。实现方已报告相关 57 项测试和 `npx tsc -b` 通过；按本次低风险样式改动的比例原则，审核未重复运行这些检查或增加测试层。

审核只覆盖本次字号修复；发布、合并和部署验证仍由既有流程完成。

## 共享组件补漏复核（同日）

结论：**Approved — 允许发布最终补漏版本。无 must-fix。**

- 范围：基于已批准的 `209476bd8ce500936cf2eb1e0276c30cec889edc`，仅复核 `dialog-typography.css` 新增的 8 行。`AccessPrompt` 和 `ChartTabHelp` 的共享组件、鉴权逻辑及图表数据均未改动；新增规则受 `body[data-kiosk-typography]` 限制，不影响 Galaxy/admin。
- 在本机 Chrome 的 1024×600 Kiosk 运行环境中挂载实际 `AccessPrompt`（个人复盘、盒子主页登录）与现有 `kioskTheme`：标题 28px、正文/按钮 22px、辅助提示 18px，弹窗约 460×462px，文案和两颗按钮完整可见，没有裁切或横向溢出。截图：`access-prompt-astra-large.png`。
- 挂载实际 `ChartTabHelp` 与 `AnalysisHelpContent`（失误说明）：标题 22px、正文 18px，正常内容完整可见，关闭按钮可见。仅为检查溢出追加一段临时长文 fixture 后，弹窗保持 380×568px、`overflow-y: auto`，实测内容高 724px / 可视高 566px，通过鼠标滚轮滚动到底部（`scrollTop=158`），无横向溢出。截图：`chart-help-astra-top.png`、`chart-help-astra-bottom.png`；均位于 `output/playwright/kiosk-dialog-typography/`，已亲眼检查。
- 独立执行 `git diff --check` 通过。未扩展全页面或全状态测试，未操作设备、真实棋局或真实账号，未修改产品代码。
