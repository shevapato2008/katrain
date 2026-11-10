# 本地对局标定后续开：验证记录

实现提交：`fb19e95c24724d66dbc86010732868e199ca008d`。仅修改本地对局设置页及测试；标定完整就绪后使用点击时参数重新预检并续开一次，失败留页，手动返回取消待开局和旧请求。

## 独立审核

- [规范审核](2026-10-23-local-pvp-calibration-spec-review.md)：Spec compliant，无实现缺口。
- [Astra Max 代码质量审核](2026-10-23-local-pvp-calibration-code-review.md)：Approved，无必须修复项。
- [计划审核](2026-10-23-local-pvp-start-plan-review.md)：第 1 轮 Approved。

两份实现审核均针对上述实际提交，完整报告已随本记录归档。审核为独立静态核对，运行验证由实施者和主代理分别执行。

## 自动检查

| 检查 | 实际结果 |
| --- | --- |
| TDD RED，页面文件 | `16 failed / 24 passed`；旧实现没有自动续开，或 ready 后提前关闭标定页。日志 `/tmp/local-start-red.log`。 |
| TDD GREEN，页面文件 | `40 passed`，覆盖完整 ready、参数快照、StrictMode/重复点击/轮询、失败/取消、手动返回及未发布会话清理。 |
| 页面 + GeometryContext + PlayInputGuard | `46 passed`；主代理独立重跑亦通过。 |
| 加上 PhysicalBoardGuard 的指定四文件 | `50 passed / 1 failed`；唯一失败为已存在的旧文案断言，主代理在主工作树基线同样复现。 |
| `npm run build:smartbox-kiosk-2d` | 主代理独立执行通过。 |
| 页面 ESLint；`git diff --check` | 通过。 |

PhysicalBoardGuard 第 62 行预期“准备空盘标定”，共享 GeometryCalibrationScreen 实际文案已是“等待棋盘稳定”。本次未修改这两处，也未为消除基线失败扩大修复范围。Vitest 的 Node localStorage ExperimentalWarning 为现有环境提示。

## 1024×600 本地运行时预览

主代理使用临时 mock transport，在真实本地页面确认：标定失败仍留在标定页，`creates=0`；原页面重试后 ready，自动导航至 `/kiosk/play/pvp/local/game/preview-local-session`，`creates=1`、`setups=1`、`preflights=2`。

失败状态截图：`output/playwright/local-start-failed-20261023.png`（本地忽略产物，已检查 1024×600 画面，并复制到主工作树同一路径）。Fixture 未写入产品代码。完整对局 mock 状态不全，本预览只证明标定失败留页与重试后的单次续开，不代表完整对局页面或真实硬件验收。

## 交付边界

代码及验证文档保存在本地提交；主工作树仅在干净、分支为 `fix/kiosk-ui-debug` 且 HEAD 仍为基线 `16aaf31d3cd0048768718695b4c7d04200427e92` 时使用 `git merge --ff-only` 接入。本轮未推送、SSH、重启服务或部署；实机验收留待后续发布。未修改同级 `katrain-kiosk-ui-redesign` 仓库。
