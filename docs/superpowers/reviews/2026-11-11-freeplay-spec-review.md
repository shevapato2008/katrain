# 自由对弈付费分析 A 切片：独立规格审核

审核依据为 [实施计划 Chunk 1](../plans/2026-11-11-phone-signup-and-freeplay-analysis.md) 与 [R2 Approved](2026-11-11-phone-freeplay-plan-astra-r2.md)。对象为基线 `c6a48d2d7da4d350f4bc0bd82c2f695e58266ce2` 之上的当前未提交 A 切片改动，包含新增 `usePaidPlayPosition.ts`。本次仅做规格符合性审核，不扩展质量/风格要求。

**结论：✅ 规格通过。** 首轮唯一问题 A-SPEC-01 已定向复核关闭，无剩余规格阻塞。B 手机号/SMS 未开通，不计作本次 A 的缺失；本结论不替代 A4 的独立验收与发布门。

## 已关闭的发现

### A-SPEC-01：付费领地投影上下镜像（已修复）

- 位置：`katrain/web/ui/src/features/analysis/usePaidPlayPosition.ts:18–20`。
- 首轮发现：投影曾把 upstream ownership 第 0 行放到 `ownership[0]`，与现有 `var_to_grid` 和 `Board.gridToCanvas` 的底部原点约定相反。
- 修正核对：现按 `(height - 1 - y) * width` 倒序取行，与既有转换一致；未扩展到研究页重构。
- 独立复核：定向运行新增 `usePaidPlayPosition.test.ts`，**1 passed**。非对称 receipt 的 A19 `+1` 映射到 `ownership[18][0]`，T1 `-0.75` 映射到 `ownership[0][18]`，另外两角保持中性；原输入与共享 history 不被修改。
- 实际截图核对：[1024×600 Kiosk 角点领地](../../../output/playwright/freeplay-2026-11-11/kiosk-1024x600-ownership-corners-corrected.png) 中，左上 A19 为黑格，右下 T1 为白格，与 receipt 一致。该截图替代旧方向结果图，不要求全状态重拍。

## 已符合的规格边界

- ✅ 真实认证与 `analysis_delivered` 分开；authenticated free 且允许分析、存在 key 时可主动进入付费流程；服务端 participant/owner 校验继续拒绝无主或他人 session。
- ✅ 两端主动点击复用原报价确认框，发送 `session_id`、`expected_position_key`、`profile: normal`；支招/领地/score 共用 hook 的一个 receipt，同局面切视图不再创建执行。
- ✅ `get_state` 的盘面、节点和 key 在实际 `ai_ladder_commit_lock` 内生成；quote/execute 共用 `_position_input`，在 session → runtime 既有锁顺序中捕获不可变完整路径 SGF，之后才进入 DB/await。
- ✅ play 的 advanced 在报价与执行前拒绝；normal 沿用 catalog 的 500 visits、模型及响应最低 visits 校验；research session 与直接研究 SGF 的 advanced 能力保持。
- ✅ 缺失/过期局面 key 在 reservation/引擎前返回 `position_changed`；前端清报价和视图，不落入通用 409 自动重报价；返回 quote 的 fingerprint 也需匹配所见 key。
- ✅ 私有结果只生成局部 GameState 投影，不调用共享 `setGameState`，不写服务端节点、WS 或对手广播；换手/分支/身份/session/unmount 的 scope 与旧回执丢弃机制保留。
- ✅ 已移除 Kiosk 节点变化自动分析 effect；新 paid 路径不自动报价或扣费，正常 AI 落子路径未更改；Kiosk 普通浏览器支招不再依赖 physicalPlay。
- ✅ ranked、未结算 ranked、大厅 bot、非参与者与原反作弊 lease 保留；账务 reservation、幂等、结果复用及失败退原来源实现未被重写。
- ✅ `membership:error_position_changed` 在全部 11 语 PO 中存在且非空，batch 字典同步；`Dockerfile.web` 已沿用 `compile_gettext_catalogs.py` 编译完整目录。

## 审核证据与未宣称事项

首轮检查当前 diff、关键调用链及聚焦测试源码，执行了 11 语 key 完整性检查与 ownership 非对称纯转换探针。修正后只复核 ownership 改动、新增单项测试及替代截图，未重复全量回归，未运行 PostgreSQL 用例。PG 三例、普通/strict Kiosk 构建、代表性真实浏览器旅程及最终质量/视觉审核仍由 A4 单独记录，不能由本报告替代；PG 新用例对既有 owned 复用响应的断言调整不属于本次方向修复复核。

未 SSH，未连接真实数据库/GPU/支付或 RK3562，未修改产品代码。实体灯动态效果仍保留明日实机验收，本报告不将云浏览器行为描述为设备灯已通过。
