# 视觉实验室 · Mac 采集设计基准

## v2 实际操作设计（2026-09-26）

- 当前操作基准：[admin-vision-capture-v2.html](./admin-vision-capture-v2.html)，参数 `state=unconnected|ready|stale`、`theme=dark|light`、`dialog=review`、`capture=true`（隐藏 Tweaks）。沿用已有后台 B/C＋楷体，不引入新主题或字体。
- 主表面 Operate、次表面 Inspect：同帧预览占主区域，右侧按连接→空盘标定→导谱/恢复→逐手采集；样本叠框用原生 modal dialog，冻结后仍明确待上传。HTML 是设计示例，不运行硬件或实际写文件。
- `ui-ux-pro-max` 查询表单标签、确认/错误、焦点与 React effect 清理；采用可见标签、独立确认 checkbox、禁用态、就地错误/重试和有界预览。俗套特征自检 0/10。
- 独立 GPT-6 Astra max 指出四项并已修正：未连接图像必须隐藏；标定/保存网格确认/采集/重拍先勾选才可操作；stale 状态提供视角变化后的新标定/新会话出口；下一手不重复已采样本。随后把 Camera 摘要与断开放同一行，使 1440×900 主采集按钮完整露出；最终裁定 **APPROVE**。
- 同视口当前参考：[未连接夜间](./vision-v2-design-unconnected-dark-1440x900.png)、[采集中夜间](./vision-v2-design-ready-dark-1440x900.png)、[恢复待复核夜间](./vision-v2-design-stale-dark-1440x900.png)、[样本复核白天](./vision-v2-design-review-light-1440x900.png)。真实 React 接入与新版四图正在进行；下面 v1 Fixture 四图只作历史，不能替代 v2 运行比较。

## v1 静态展示与 Fixture（历史）

- 可打开的 HTML：[admin-vision-capture.html](./admin-vision-capture.html)。参数 `?state=unconnected|ready&theme=dark|light`；`ready` 仅是设计示意，不接摄像头或网络。
- 目标桌面视口 1440×900：[未连接夜间](./vision-capture-design-unconnected-dark-1440x900.png)、[采集中示意夜间](./vision-capture-design-ready-dark-1440x900.png)、[采集中示意白天](./vision-capture-design-ready-light-1440x900.png)。沿用 B 石墨铜、C 雾白蓝、楷体和现有后台字号。
- `claude-design` 用 Operate／Inspect 构图落成单文件 HTML；`ui-ux-pro-max` 检查步骤层级、空态诚实性、可读性和主次操作。无营销 Hero、假指标、装饰性渐变或玻璃层；俗套特征自检 0/10。
- 设计状态把原图/warped 绑定为同一帧。未连接时设备列表“尚未读取”，标定“等待连接摄像头”；示意态的设备、棋图、SGF 步数和标定均明确标记。按钮禁用，不暗示实际相机、采集或上传已完成。
- 独立 GPT-6 Astra max 首轮要求修正重复数据集标签、设备状态措辞与标定前置状态；修后复核三态裁定 **APPROVE**。此裁定只替代 Fan 睡前的视觉决策，不授权 SSH、写库、push 或部署。
- React 隔离 Fixture 已在 Vite 真实运行时 1440×900 捕图：[可交互对比页](./vision-capture-fourup.html) 支持 `pair=unconnected-dark|ready-dark|ready-light` 与 `mode=side|overlay|diff`。

| 状态 | 实际运行 | 并排 | 叠加 | 差异 |
| --- | --- | --- | --- | --- |
| 夜间未连接 | [运行图](./vision-capture-fixture-unconnected-dark-1440x900.png) | [并排](./vision-capture-side-unconnected-dark.png) | [叠加](./vision-capture-overlay-unconnected-dark.png) | [差异](./vision-capture-diff-unconnected-dark.png) |
| 夜间示意 | [运行图](./vision-capture-fixture-ready-dark-1440x900.png) | [并排](./vision-capture-side-ready-dark.png) | [叠加](./vision-capture-overlay-ready-dark.png) | [差异](./vision-capture-diff-ready-dark.png) |
| 白天示意 | [运行图](./vision-capture-fixture-ready-light-1440x900.png) | [并排](./vision-capture-side-ready-light.png) | [叠加](./vision-capture-overlay-ready-light.png) | [差异](./vision-capture-diff-ready-light.png) |

独立 GPT-6 Astra max 查看三态参考/运行图及九张并排/叠加/差异图，裁定 **APPROVE**：状态字段全宽、采集按钮约低 22px、数据集卡约低 8px，但平衡、易读且无裁切；差异不阻断。这是视觉关卡，不是真相机/上传验收。聚焦 Vitest 12 passed，`build:admin`、聚焦 ESLint 与 `git diff --check` 通过；Fixture 入口未进入正式构建。真实集成后删除 Fixture。
