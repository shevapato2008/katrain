# 本地对局标定后续开 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 本地实体对局点击开始后，标定成功自动继续同一次开局；标定失败留在标定页，只有手动返回才回设置。

**Architecture:** 在现有 PvpLocalSetupPage 内保留开局参数快照和待开局意图，标定 ready 后重新 preflight 并恢复一次；沿用现有 attempt/request 和未发布会话清理。失败不关闭 calibrationOpen，手动返回清掉待开局和异步结果，防止晚到成功自动开局。保持其他模式与共享标定组件行为。

**Tech Stack:** React/TypeScript、现有 GeometryContext/API、Vitest/Testing Library；不增加依赖或后端接口。

**计划审核：** Astra Max 独立第1轮 Approved，无需第2轮。preflight写回status不代表用户重新尝试，续开意图不得因其状态更新被再次激活。报告：`docs/superpowers/reviews/2026-10-23-local-pvp-start-plan-review.md`。

---

## Chunk 1: 最小修复与验证

### 已确认的原因

- RK3562在2026-10-23约18:32:57完成五点标定；只读状态 ready、5/5、session_calibrated 和 geometry/recognition/model ready。
- 设备代码与本地相同：PvpLocalSetupPage 的 preflight 未就绪分支打开标定屏后 return；ready effect 只 setCalibrationOpen(false)，没有继续 createSession/gameSetup。
- 当前测试明确要求 successful calibration returns to retained setup without automatically starting；相关24项测试通过，说明旧交互被固定下来。
- 自由对弈先创建对局、进入游戏路由，再由 PhysicalBoardGuard 暂挡；本地模式在设置页做 preflight，因此必须单独恢复原开局动作。

### 用户确认的行为

| 情况 | 结果 |
| --- | --- |
| 点击开始且设备已就绪 | 原流程创建一次对局并进入 |
| 需要标定，随后标定成功且识别/模型就绪 | 用点击时的参数，重新preflight后自动创建一次对局并进入；无需第二次点击 |
| 标定 failed/cancelled/仍未就绪 | 留在标定页，可使用原重试操作；零对局创建，不因失败退设置 |
| 用户手动“返回设置” | 保留输入参数，清掉待开局；迟到ready/网络结果不得创建/跳转 |
| 等待开局期间离开页面 | 原attempt失效；如会话后来创建，只清理该未发布会话 |
| 重新核验或创建对局请求失败 | 不循环重试/不重复创建。错误必须在当前页面可见；仍由用户手动返回设置或重新标定重试，不因错误自动退页 |
| 屏幕对局或非19路 | 保持原有无需标定开局 |

### 实现约束

- 只保存当前开局的必要数据：规则/路数/让子贴目/姓名/用时/onBoard/返回上下文快照；不重建全局新会话协调层。身份与权限沿用当前Auth/路由，不缓存额外凭据。
- ready 必须同时有 phase=ready、session_calibrated、geometry_ready、recognition_ready、model_ready!==false；不能只看几何成功或旧valid。
- 待开局在异步恢复前同步标记已消费/进行中；多次status轮询、StrictMode或重复点击最多创建一次。失败后不因仍ready而无限重开；用户下一次实际重试可以恢复该意图。
- 继续开局时仍preflight；未就绪/异常保持标定屏。用户点返回后，同步清意图、递增request并复位busy/loading/checking，晚到ready不得续开。
- 标定成功后开局请求在途仍保持标定/进入中内容，避免先闪回设置。可用现有标定页sub传入进入中/失败说明；不为本修复扩共享组件或加新页面。错误说明可要求手动返回设置再重试。
- 正常创建共用原有API链及createdSession/published清理，不删除别的会话，不在成功后额外RESET_SYNC或改标定/对局恢复流程。

### Task 1: 用聚焦RED用例钉住新交互

**Files:** Modify `katrain/web/ui/src/kiosk/pages/PvpLocalSetupPage.test.tsx`。

- [x] Step 1: 把“标定成功不自动开局”替换为“保持原参数、标定成功后自动开局一次”；先required→打开标定→ready→再次preflight ready，断言原姓名/规则/用时及onBoard、gameSetup和navigate各一次；重复ready不重复创建。
- [x] Step 2: 补failed/cancelled保持标定屏、零创建；重试后ready继续。补手动返回后迟到ready零创建、参数仍在；再点开始才开局。
- [x] Step 3: 补重新preflight未就绪/抛错、createSession/gameSetup失败在当前页可见且不循环；手动返回/卸载时在途结果被隔离并只清理自己未发布的会话。沿用现有覆盖屏幕/非19路和防重复测试，不新建测试平台。
- [x] Step 4: 在UI目录运行 `./node_modules/.bin/vitest run src/kiosk/pages/PvpLocalSetupPage.test.tsx`；新自动续开用例应因旧实现没有创建而FAIL，记录实际失败，不因修改mock制造绿。

### Task 2: 最小实现待开局续接

**Files:** Modify `katrain/web/ui/src/kiosk/pages/PvpLocalSetupPage.tsx`。

- [x] Step 1: 提取当前create/setup/publish/navigate链为可复用的同一次开局动作，携带点击时参数快照；保留attempt与清理语义，不改变后端载荷。
- [x] Step 2: 初次preflight需要标定时保留意图并打开原页面。ready effect在完整就绪且当前意图有效时只恢复一次，重核通过才进入API创建；请求中保留进入中内容。
- [x] Step 3: 手动返回清意图并使旧请求失效，保留设置。失败/取消状态不关屏；重试策略明确区分下一次标定与同一ready轮询，失败说明通过现有sub显示，不能隐藏在早退页面之外的Alert。
- [x] Step 4: 将“标定完成后返回设置，再开始对局”改为符合新行为的说明；不改其他标定入口。
- [x] Step 5: 同Task1命令转GREEN，检查24项旧测试中必须变化的旧语义已替换，其余仍通过。提交 `resume local game start after successful calibration`。

### Task 3: 独立审查与最低充分验证

- [x] Step 1: 独立子代理先核对上表要求及真实代码；Astra Max再独立检查异步幂等、取消、参数快照、错误可见性及会话清理，修具体问题直到通过。实施者不能自审替代独立审核。
- [x] Step 2: UI目录运行 `./node_modules/.bin/vitest run src/kiosk/pages/PvpLocalSetupPage.test.tsx src/kiosk/context/GeometryContext.test.tsx src/kiosk/__tests__/PhysicalBoardGuard.test.tsx src/kiosk/__tests__/PlayInputGuard.test.tsx`，再 `npm run build:smartbox-kiosk-2d`，预期通过。
- [x] Step 3: 本地1024×600真实页面做一组代表性运行时预览：标定中→failed仍留屏→用户重试ready→自动进入（不触发真实RK标定）；如现有测试/环境足够，可用临时mock transport，不将Fixture写入生产。文案不溢出，退出明确保留参数。
- [x] Step 4: 完成前查看git diff/status和审核结果，报告代码提交与实际检查；未经本轮发布授权，不推远端、不重启/部署RK。设备实机验证留待部署时进行，不冒称已上线。

### 执行范围

先Astra Max独立审本精简计划，最多两轮；之后独立工作树、TDD、subagent-driven-development实现并审查。此任务不执行另一个摆谱交互/语音大计划。

## 完成记录（2026-10-23）

实现提交 `fb19e95c24724d66dbc86010732868e199ca008d`；独立规范审核和 Astra Max 质量审核均通过。页面 40 项、相关三文件 46 项通过，生产构建通过，1024×600 临时 transport 预览确认失败留页和重试后续开一次。Task 3 Step 2 的 PhysicalBoardGuard 旧文案断言在未改动基线同样失败，记录为既有问题，不扩改共享组件。预览未覆盖完整对局或真实硬件；本轮不推送、不部署。

详细证据与两份独立实现审核见 [验证记录](../reviews/2026-10-23-local-pvp-calibration-verification.md)。
