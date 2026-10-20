# 全局字体与字号 · 设计稿验证

入口：`docs/design/kiosk-current-based-redesign-2026-10-14.html#settings-typography`。

- 独立文字预览卡已移除。选择立即作用于当前设置页和之后导航到的所有围棋提案页面。
- `typography.js` / `typography.css` 提供共享状态、渲染后应用与字号规则；保留现有字号层级，三档依次减 0 / 2 / 4 px（最低 12 px）。控件保持原宽高。
- `localStorage` 键 `kiosk-design-typography-v1` 保存字体与字号，首次渲染前恢复。刷新和同一浏览器中新开页面已验证；正式应用仍需按用户／设备持久保存并在 RK3562 重启后恢复，本次不修改生产应用。
- 字体选项只改变汉字与中文标点；拉丁字母固定使用默认字体，数字保留原有等宽字体，不提供英文字体设置。`cjk-only/` 含报告与设置页核对截图；实际字形字体记录在 `output/playwright/typography-global/cjk-only.json`。
- 中文字体选择在非中文语言下保留，界面使用默认字体；切回中文恢复所选字体。字号跨语言保留。
- 品牌、图标、棋盘素材与有意设置的等宽字体保留。盒端启动门户不受围棋设置影响。
- 楷体、隶变体、黑体使用 macOS 本机字体；本机未安装时选项明确提示，不复制系统字体。

`default/{page-id}.png` 和 `small/{page-id}.png` 覆盖全部 54 个可打开的围棋页面：每张均为真实浏览器截图、1024×600。代表页为 `settings-typography`、`play`、`training`、`report`。`settings-lishu-small.png` 展示整页改用隶书。

自动检查记录在 `output/playwright/typography-global/`：`computed.json` 覆盖每页字体、字号、品牌和数字字体；`geometry.json` 记录默认与小两档按钮尺寸对比；`persistence.json` 记录即时切换、语言切换、刷新和新页面首次渲染恢复。
