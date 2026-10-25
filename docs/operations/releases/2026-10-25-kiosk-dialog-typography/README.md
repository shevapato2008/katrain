# Kiosk 弹窗字体

复盘删除确认框仍使用旧 `.empty` 与 `.kiosk-btn--pill` 规则：标题 15px、正文 11.5px、操作 12px。全局字号器会正确扫描它，但只会从旧基准减去当前字号档位，无法自动补成页面已经采用的 18 / 22 / 28px。部分 MUI portal 还引用了只在 `.kiosk` 内定义的字体栈变量。

修复将原有三个字体栈变量共享给 `body[data-kiosk-typography]`，沿用既有 Provider 的进入/离开清理、中文字体选择和 `--kiosk-size-step`。一个 Kiosk 共用样式文件补齐弹窗标题、正文、辅助信息和操作层级；不修改业务逻辑或新增主题。长文保留滚动，操作区允许换行，危险操作颜色及 disabled 条件保留。

## 范围盘点

| 弹窗类别 | 处理 |
| --- | --- |
| 复盘历史删除 | 28px 标题、22px 正文及按钮，48px 操作高度 |
| 研究分析/清空、OGS 挑战/接受、平台退出账号 | 共用 `.cdlg` 模板同步修复 |
| MUI Dialog：对局确认/错误、实体盘引导/恢复、AI/本地开局说明、升降级占用、摆谱确认、复盘导入 | 共用 Kiosk 作用域规则：标题28、正文22、辅助18、操作22，保留各弹窗位置、颜色、滚动与关闭条件 |
| 共享组件中的 Kiosk 登录提示、报告图表说明 Popover | 自定义 HTML 标题/正文/提示/按钮补齐28/22/18层级；仅 Kiosk body 作用域生效，不改登录、图表或 Galaxy 行为 |
| 标定说明/光线警告 | 旧模板标题/正文/提示/操作同步修复；不执行标定 |
| 设备棋盘说明、课程来源说明、成长说明关闭键、观战说明标题、教程视频返回键 | 补齐现存20/24或旧药丸字号 |
| 平台棋力选择浮层 | 可滚动列表采用22px选项及18px辅助，辅助信息另起一行，保留滚动及选择逻辑 |
| 大厅邀请说明、星阵 Kiosk 资料、棋局详情 | 已有18/22/28层级，检查后保留 |
| 图表放大/报告数据工作区、棋盘坐标/数字标尺、视频本身 | 保留已有专用几何与固定字体规则，不作整层强制字号覆盖 |
| Galaxy、admin | 未修改 |

## 聚焦验证

真实 Chrome、1024×600、本机 Vite + 隔离 API fixture 打开实际 `ReportsPage`。没有在真实设备执行删除、清空、开局、付费分析或标定。

- 删除框 large：28 / 22 / 22px；small：24 / 18 / 18px，操作始终48px高，确认与取消均可见。取消保持原行为。
- 棋谱库导入 MUI portal large：标题28、棋谱名称22、辅助18、操作22；small 按原规则减4px。CDP 确认中文标题实际使用 `TW-Kai`。
- `npm test -- src/kiosk/pages/ReportsPage.test.tsx src/kiosk/typography/KioskTypographyContext.test.tsx`：57项通过，包含已有确认删除及失败流程验证。
- `npx tsc -b`、`git diff --check` 通过。没有为纯样式改动另建测试层。
- 共享图表说明的已有 `AnalysisChartHelp.test.tsx`：1项通过；补充验证由实际组件预览覆盖。

截图：[旧版](screenshots/delete-before.png)、[新版大字号](screenshots/delete-after-large.png)、[新版小字号](screenshots/delete-after-small.png)、[同尺寸并排](screenshots/delete-side-by-side.png)、[叠加](screenshots/delete-overlay.png)、[差异](screenshots/delete-diff.png)、[棋谱库导入](screenshots/library-after-large.png)。旧版图由同一实际页面关闭新增样式表得到，原 `.rvconfirm` 字体变量及业务结构相同。

独立 fresh `gpt-6-astra` / `max` 已完成代码与真实截图审核，结论 **Approved，无 must-fix**，并独立补充380px侧栏长文及三操作预览，未裁切。见[审核报告](../../../superpowers/reviews/2026-10-25-kiosk-dialog-typography-astra-review.md)和[侧栏预览](screenshots/side-dialog-astra-large.png)。发布版本及设备回执在部署后另行记录。

补漏复核同样为 **Approved，无 must-fix**：[登录提示](screenshots/access-prompt-astra-large.png)实测460×462px、28/22/18px；[图表说明](screenshots/chart-help-astra-top.png)标题22/正文18，临时长文在380×568px浮层内可[滚动到底](screenshots/chart-help-astra-bottom.png)，无横向溢出。临时长文只用于本机预览，不进入产品。

## 最终发布与 RK 回执

- 功能分支与 published `develop`：`105661aba56bc6b27c80e0acf8066425338d258c`。Smartbox published `main`：`3a9e9926fa22dc68a02681c8b9bec4b43d77b7e5`，`vendor/katrain` 精确指向上述 develop。
- RK3562 实际 `smartbox-katrain.service` PID **565010**，进程 `KATRAIN_BUILD_SHA` 与 release marker 均为上述 develop。只重启围棋服务；kiosk服务及围棋mode target的PID/启动时间保留。
- 以干净、已发布 develop 构建完整 full 和 strict；strict SSO/无three.js检查通过。受控391个Python、十九路policy及完整双static合计1189个文件逐项SHA校验一致，实际入口为 `/assets/index-CTOP7LY8.js`。462个设备配置、字体与标定等保护文件哈希保持，SQLite在线备份保存。
- 实际原账号 `fan` / id2 / HTTP200，恢复原 `http://127.0.0.1:8081/kiosk/report`，历史仍共34局。重启后的SSO通过真实主页登录入口、围棋tile恢复，未读取或注入cookie。恢复后只读教程19路适配/保留例外API验证通过。
- 实机删除框由15/11.5/12px及26px高按钮变为28/22/22px及48px高按钮，CDP确认中文为TW-Kai。打开后取消，记录到的DELETE请求为零。登录提示同样实测28/22/18px、操作22px，完整可见。
- 未执行真实删除、清空、开局、付费分析、标定或实体盘动作；不宣称物理完整端到端验收。云服务无本次依赖，未更新。

设备截图：[真实旧版](screenshots/rk-delete-before.png)、[真实新版](screenshots/rk-delete-after.png)、[同尺寸并排](screenshots/rk-delete-side-by-side.png)、[真实登录提示](screenshots/rk-access-after.png)、[原复盘页恢复](screenshots/rk-restored-report.png)。设备前后图来自不同真实时间，时钟变化不属于字号差异。

详细证据：[设备文件/进程/健康验证](verification.json)、[浏览器字号、字体、身份与零删除请求](browser-verification.json)、[登录提示字号](access-browser.json)。设备部署、回滚脚本和备份保留在 `/mnt/data/smartbox-deployments/20261025-kiosk-dialog-typography-105661aba/`；本机脚本在 `/tmp/kiosk-dialog-typography-final-20261025/`。候选和备份都在data分区；根盘约2GiB可用，完整双static合计约97MB且略小于旧版，本次采用1GiB剩余安全储备门槛，未清理用户或系统缓存。

本段回执提交位于独立证据分支；上列功能 develop / Smartbox提交及实际部署版本保持不变。
