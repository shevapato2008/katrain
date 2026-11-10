# Local PvP calibration resume — specification review

**Verdict: Spec compliant.** 未发现本次已确认行为的实现缺口。

审核提交：`fb19e95c24724d66dbc86010732868e199ca008d`，父提交 `16aaf31d3cd0048768718695b4c7d04200427e92`。
工作树：`/Users/fan/.config/superpowers/worktrees/katrain-kiosk-debug/local-start-resume-20261023`；审核时 HEAD 与目标提交一致，工作树干净。

依据：已确认的行为、`docs/superpowers/plans/2026-10-23-local-pvp-calibration-resume.md`、实际实现及测试。仅审核两份变更文件；未修改生产或测试代码，未执行 SSH、部署或测试套件。

## 规范逐项核对

以下 `Page` 指 `katrain/web/ui/src/kiosk/pages/PvpLocalSetupPage.tsx`，`Test` 指同目录 `PvpLocalSetupPage.test.tsx`。

| 要求 | 实际代码证据 | 对应测试 |
| --- | --- | --- |
| 需要标定时保留本次开始意图，完整成功后自动续开一次 | Page 207–210 保存 intent 并打开原标定页；255–264 同时检查 ready、session_calibrated、geometry_ready、recognition_ready、model_ready，并在恢复前同步清空 pendingStart；192–205 通过 busy 和 request 隔离重复调用并重新 preflight。 | Test 282–340：StrictMode、重复点击/ready、第二次 preflight、单次 create/setup/navigate、逐项不完整 ready。 |
| 使用点击时参数、onBoard 和返回上下文 | Page 173–189 在点击时快照规则、路数、让子、贴目、双姓名、全部用时字段、label、onBoard、backToState；220–231 使用 intent 完成 setup、发布和导航，不重新取页面设置。 | Test 282–310 明确断言完整载荷、onBoard、label、返回路径。 |
| 标定失败/取消留页，原重试成功可继续，不自动退设置 | Page 255–264 对 failed/cancelled 不消费 pending；276–284 持续渲染原 GeometryCalibrationScreen。关闭 calibrationOpen 只发生在手动 returnToSetup。 | Test 313–325 覆盖 failed/cancelled → waiting_empty → ready；247–266 覆盖初次 preflight 的四类需标定状态。 |
| 手动返回保留参数并取消意图，迟到 ready 不续开 | Page 266–273 同步清 pending、递增 request、复位 busy/loading/checking 并关闭标定页；没有重置表单值。 | Test 343–355 验证保留输入、迟到 ready 零创建、下一次手动开始可用。 |
| 返回/离页后在途结果不得发布，晚创建会话只清理自身 | Page 104–108 在卸载使 request 失效；196、206、219、221 校验当前请求；197–198、237 只删除本次已创建但未发布的 session。 | Test 384–420 覆盖续开 preflight/create/setup 中手动返回及续开 setup 中卸载；451–475 覆盖离页后的 preflight/create 迟到结果。 |
| 续开失败留识别页、错误可见、不得循环；允许提示手动返回设置再试 | Page 207–212 在 resuming 时不重新保存意图；233–242 设置错误并复位忙状态；276–282 在当前标定页 sub 显示错误和“请返回设置后重试”。恢复前已消费意图，因此状态轮询甚至新的 ready 不会自行重开。此行为符合本轮明确允许的手动退出重试方案。 | Test 358–381 覆盖重核未就绪、重核异常、create 和 setup 异常，以及随后状态变化不重试；setup 失败清理本次 session。 |
| API 在途保持标定/进入中内容；不先闪回设置 | Page 276–284 在 calibrationOpen 期间持续返回原标定页，loading 时 sub 为“正在进入对局…”，成功直接导航。 | Test 384–400 在三个恢复阶段均断言标定页仍存在。 |
| 屏幕、非 19 路、其他模式保持原行为；无新共享组件或后端框架 | Page 187、199–204 仍以点击时 onBoard 决定 preflight；保留原 create → setup → publish → navigate 链。差异仅这两份页面文件，无共享组件、其他模式或后端改动。 | Test 485–496 覆盖屏幕和非 19 路跳过 preflight；原有普通开局及设置载荷用例保留。 |

## 验证边界

这是独立的静态规范审核，不替代下一阶段代码质量审核或运行时视觉验收。本轮未重跑测试；实施者报告的页面 40/40、相关 46/46 及 RED 16 项失败记录未在本审核中重新执行。已知 PhysicalBoardGuard 旧文案用例失败不属于此提交改动范围，也未据此认定新回归。

无需为规范符合性修改本次实现。
