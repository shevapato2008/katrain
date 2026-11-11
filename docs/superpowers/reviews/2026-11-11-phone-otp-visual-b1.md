# Phone OTP B1 visual gate

**Decision: Approved — 2026-11-11.**

独立审查范围为 B1「手机号 OTP 登录 / 首次自动注册」的前端 Fixture 视觉阶段。用户已委托 Astra 代表视觉决策；本批准允许进入当前旅程对应的后端实现。基准为 `60817167c` 及本次前端工作区，包含审查中完成的 Galaxy 登录弹窗局部对比度修订。没有遗留视觉阻塞。

本次使用 `ui-ux-pro-max`，读取现有 Galaxy/Zen 与 Kiosk 主题，直接检查真实 React 页面截图、同尺寸参考、并排图及 overlay；没有以测试通过替代目视确认。

## 目视材料

材料目录：`output/playwright/phone-otp-2026-11-11/`。

| 页面与 viewport | 已查看材料 |
| --- | --- |
| Galaxy 1440×900 | `galaxy-reference.png`、`galaxy-implementation.png`、`galaxy-side-by-side.png`、`galaxy-overlay.png`，含局部提亮后的更新版 |
| Kiosk 1024×600 | `kiosk-reference.png`、`kiosk-implementation.png`、`kiosk-side-by-side.png`、`kiosk-overlay.png` |
| 代表性反馈 | `kiosk-delivery-unknown.png`、`galaxy-delivery-rejected.png`、`galaxy-canonical-confirmed.png` |

Kiosk unknown 最终图在 MUI 浮动标签/按钮过渡结束后重拍一次；最终截图中标签与验证码无重叠。这是截图时机调整，没有为此修改产品。

## 通过依据与接受差异

- **构图与几何：** Galaxy 弹窗宽度、居中位置及字段分组合理。相比静态参考增加约 22px 高度，来自实际 MUI 标题及底部动作留白；不影响层级、可达性或 viewport 内完整展示。Kiosk 采用既有品牌/表单双栏，卡片及反馈状态均完整落在 1024×600 内，无横向溢出、遮挡或挤压。
- **组件层级：** 默认短信验证码，账号密码作为并列次选 tab；手机号、单个验证码输入和发送动作分组清楚。首次创建账号、50 积分仅赠一次及旧账号先密码登录后绑定的提示完整、相互独立，不把已有账号误引向再次注册。空输入时主按钮禁用符合状态。
- **字体、材质与素材：** 保留现有文楷、品牌字与真实 logo；深色表面、玉绿强调、圆角及间距延续各自主题。参考图的外壳为简化示意；实现保留已发布 Galaxy 导航和 Kiosk 背景网格，不将其视为本切片偏差。MUI 空字段标签位于框内、聚焦/填值后浮起，属于接受的真实控件行为。
- **可读性修订已关闭：** Galaxy 原绿色小字 `#4a6b5c` 对纸面 `#252525` 仅 2.59:1；`primary.light` 用作小字也仅 3.57:1。修订只作用于 `LoginModal`：选中 tab 用 `text.primary`，非错误聚焦标签及可用的文字/描边按钮用 `text.secondary`（7.50:1），焦点边框和 tab 指示线用 `primary.light`。未改变全局主题、disabled/error 语义或 contained 主按钮。更新后的原图、并排及 overlay 已确认。Kiosk 原主色对纸面为 6.51:1，无需修改。
- **状态语义：** unknown 图使用琥珀色警告图标和明确文字说明「状态未确认、收到码仍可验证」，显示冷却且验证按钮可用；没有把未知送达画成成功。rejected 图使用红色错误、冷却、禁用验证按钮，并给出稍后重试或账号密码路径；没有成功提示。canonical 图显示确认后登录弹窗退出，使用 Fixture canonical 身份。
- **操作语义：** 源码核对显示手机号有真实 label、`type="tel"`、`autocomplete="tel-national"`；验证码为单输入框，支持 `inputMode="numeric"`、六位限制与 `autocomplete="one-time-code"`。Tabs 48px、发送按钮 56px、提交按钮 48px、取消按钮 44px，满足本旅程触控下限。

## 边界

结论仅覆盖上述中文目标尺寸及必要代表状态，不宣称逐一目视验收 11 种语言。实施者报告的聚焦测试、strict 模式检查和构建结果另行记录，本审核未复跑测试。手机号/OTP 不公开指身份、URL、日志等保密边界，不要求在本次表单追加隐私宣传句。

本 gate 不包含 B5 旧账号绑定页面，不包含最终前端/后端安全代码审查、真实短信、数据库、支付或生产部署验收；这些仍按已批准计划在相应阶段完成。
