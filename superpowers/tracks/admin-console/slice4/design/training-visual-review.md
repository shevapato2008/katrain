# 训练与模型 Fixture 视觉核对

目标 viewport：1440×900，字体加载后截图；四态 unknown/dark、running/dark、failed/dark、completed/light。[四图入口](./training-fourup.html)。参考与运行均未连接真实训练服务，示例集中于隔离 Fixture 控制器。

- 构图/几何：左 320px 创建表单，右当前运行与模型版本；导航、流程条、面板、进度、日志、表格位置对齐。高级参数默认收起，主 CTA 与完成态模型行均在首屏可见。
- 层级/字号/字色：复用楷体与后台 B/C 主题；关键文字16–17px、技术日志12px。表单标签、禁用说明和焦点样式清晰。
- 图标/素材：React 使用现有 lucide 图标；页眉状态图标随状态切换，参考 HTML 页眉为通用活动图标。完成态 CircleCheck 更明确，非阻塞差异。
- 文案/语义：运行图明确标注 Fixture，参考标注 HTML 设计示意，因此免责声明像素不重合；unknown 没有 GPU/数据集/run/指标，其他状态均声明示意。指标 null 不填零；取消仅演示确认后改变本地状态，下载禁用。
- 功能核对：16项页面/正式构建入口测试通过，局部 ESLint、build:admin 通过；浏览器控制台0 error/0 warning。正式 admin import 图未引入 Fixture。

独立 GPT-6 Astra max 实际查看四态全部参考/Fixture/并排/叠加后裁定 **APPROVE**，无视觉阻塞。可冻结本地契约并进入后端；不得据这些示例声称真实训练验收，外部授权仍独立。
# 正式接口接入后的代表性核对

`training-runtime-disabled-dark-1440x900.png` 为1440×900本机8015真实API/React画面：训练开关关闭、临时空业务库，没有mock接口或样例运行。Chromium0error/0warning。独立GPT-6 Astra max对该空态裁定APPROVE；正式接入只增加真实运行历史与操作状态，不重复拍此前已批准的四态。真实GPU、测试机上传、模型下载和用户设备验收仍未完成。
