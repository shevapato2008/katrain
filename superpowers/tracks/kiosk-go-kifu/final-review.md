# kiosk-go-kifu 最终代码审查

日期：2026-09-15。工作树：`/Users/fan/Repositories/katrain-kiosk-go-kifu`，分支 `feature/kiosk-go-kifu`。

审查原始范围：`git diff 6fab2c77...7a00bdae`，覆盖 8 个代码提交。需求以 `prd.md` 为准；遵守 `plan.md` Global Constraints 和 `codex-handoff.md` 的环境事实。

## 结论

未发现已核实的 Critical / Important **产品实现缺陷**。发现并修补了 2 组 Important 接线测试盲区、3 处 Minor 测试不足；另修正计划中的 pytest 失败集合过滤命令。最终生产源码与 `7a00bdae` 一致，改动仅为测试和文档。

审查与本机验证已完成，没有遗留 Important 审查项。RK3562 实测、文案确认及是否合入 develop 仍由 Fan 决定。本次没有 push、合并、切换旧提交、改 PO 或操作其他 worktree。

## 一、发现、证据与处理

以下旧测试行号按审查起点 `7a00bdae` 记录；修复位置是当前分支行号。测试缺口描述的是“引入所述回归时原测试仍会通过”，不是声称当前产品已经发生该回归。

### F1 · Important：真实摆谱入口未覆盖未标定状态，fixture 会放行误接的守卫

- 生产接线：`katrain/web/ui/src/kiosk/KioskApp.tsx:146`；`PhysicalBoardGuard.tsx:25-30` 会无条件放行 `disabled`。
- 同形 fixture 共 **3 处**：`tests/baipu.spec.ts:21` 依赖真开发后端 geometry 404；`tests/kiosk-screen-17-baipu.fourup.spec.ts:91-96`、`tests/kiosk-shell-scroll.spec.ts:1191-1196` 显式回 `disabled`。已有 `BaipuSessionRoute.test.tsx:44-45` 直接挂路由组件，未经过 KioskApp。
- 失败场景：误把应用入口重新套入 PhysicalBoardGuard 后，盒上 `required` 状态进不了上线态摆谱，而上述 fixture 仍放行。反向漏掉采集态守卫也缺少真实组合测试。
- 修复：`src/kiosk/__tests__/KioskApp.test.tsx:164-197` 增加真实 app → route → guard → provider 的两态测试，`isAuthenticated=true`、`token=null`、geometry=`required`；只替换叶子页面和 API。
- 红绿证据：临时误加外层守卫时，新上线态用例失败；临时删除采集态守卫时，新采集态用例失败。两次都是 **1 failed / 13 passed**，恢复后 **14/14 passed**。视觉 fixture 保留其布局测试职责，不批量重写。
- 提交：`a907c378`。

### F2 · Important：N9 的 HTTP → ApiError 接线由测试 fixture 自行代办

- 同形缺口共 **2 处**：`src/kiosk/__tests__/KifuPage.test.tsx:201-203`、`KifuDetailPage.test.tsx:105-106` mock 整个 KifuAPI，然后自行构造 `ApiError(503)`。
- 失败场景：`src/api/kifuApi.ts:14` 若退回普通 Error，两屏不再显示“要联网”，但上述测试不会发现。
- 修复：新增 `src/api/kifuApi.test.ts:7-21`，只桩 HTTP 响应，真实调用列表/详情客户端，检查 503/404 的 ApiError 类型、status 和原消息格式。
- 红绿证据：临时改回普通 Error，原两页测试 **37/37 仍绿**；新客户端测试 **2/2 失败**。恢复后客户端、两页及另外两个消费者合计 **55/55 passed**。
- 提交：`2c9f97a3`。

### F3 · Minor：采集开关的 CLI / lifespan 正向接线没有被执行

- `tests/test_baipu_api.py:93-104,229` 两处直接注入 `app.state.baipu_collect`；`tests/test_baipu_capture.py:394-402` 只测 resolver。T4 真服务 curl 无相机，仅验证默认关闭；e2e 的 mode 也来自 fixture。
- 失败场景：删掉 `server.py:3490-3491` 的 CLI 赋值，或把 `:672-674` 的 lifespan 赋值固定为 False，采集机开关失效仍能通过旧验证。
- 修复：`tests/web_ui/test_board_lifespan_camera_degraded.py:314-377` 复用隔离启动环境，运行真实 `run_web/argparse → settings → _lifespan_board → resolver → mode/capture`。覆盖默认关、CLI 开（env=0）、env 开；真实 CaptureService 搭正常启动的相机桩，不直接赋所测 state。
- 红绿证据：断 CLI 赋值为 **1 failed / 2 passed**；断 lifespan 赋值为 **2 failed / 1 passed**；默认关闭均保持绿。恢复后连同采集端点与 resolver 测试 **35/35 passed**。两次均以 finally 恢复 server.py，字节校验一致。
- 提交：`fbbb83d9`。

### F4 · Minor：N9 成功测试只检查默认空值，未核实请求参数

- `tests/web_ui/test_kifu_offline.py:26-28,79-84` 的列表 fixture 是空库，断言仅为 `total == 0`；列表与详情两条成功路径均没有核实远端收到的参数。
- 失败场景：在线请求成功后丢弃云端数据、返回空库，或传错搜索/分页/详情 ID，原成功测试无法可靠发现。
- 修复：当前 `test_kifu_offline.py:80-91` 使用非空结果与非默认查询参数，检查完整返回值和两条远端调用参数；`:94-108` 同时补上列表/详情各自的 403 保留、500 → 503 映射。
- 红绿证据：临时丢弃成功列表结果并返回空库，原测试 **5/5 仍绿**；增强后为 **1 failed / 8 passed**；恢复后 **9/9 passed**。
- 提交：`4000d4d6`。

### F5 · Minor：两条超时测试跟随实现常量，不能独立守住 3 秒契约

- 起点 `src/api/baipuApi.test.ts:124,138` 都使用实现导出的 `BAIPU_MODE_TIMEOUT_MS` 推进时钟。常量误改为 30 秒时，它们仍按 30 秒验证。
- 修复：当前 `baipuApi.test.ts:118-147` 独立检查 2999ms 尚未返回、3000ms 已返回 false，body 挂起同样按 3000ms；`:151-176` 补真实 AbortController signal 触发后、fetch 在 3001ms 才 reject 的用例，核实只有一次返回且无未处理拒绝。
- 红绿证据：临时把常量改成 30000，新契约断言在 3000ms 处明确失败；恢复后相关四份测试 **38/38 passed**。
- 提交：`b3c88037`。

## 二、8 条 deferred minors 的最终判定

| # | 判定 | 理由 / 结果 |
|---|---|---|
| 1 | 不修 | 两份 Playwright 配置均有 Number(env) 无 NaN 保护；非数字值进入 URL 后启动失败，不会误复用服务或假绿。有效独立端口 5273/8102 已真实跑通，保持本轮范围。 |
| 2 | 不修 | `endpoints/kifu.py:117-118` 的 `if not result` 在正常云端契约下通常不走，但远端 JSON 为 null/空对象仍可触发。保留轻量 404 兜底，无副作用。 |
| 3 | 修 | F4 新增列表、详情各自的非 404 4xx（403）测试，核实状态码和 `Remote kifu request failed (403)`。 |
| 4 | 修 | F5 新增 abort 后延迟 reject 的自动化测试；明确区分超时返回与后续拒绝的时点。 |
| 5 | 不修 | source 改变但组件不卸载时 phase/steps/k（以及新增 wrongSize）不会完整重置，确属既有形状。当前各入口均从棋谱/详情页进入，会先卸载旧会话；没有会话直接切换会话的产品导航。后续引入此导航时须一起处理。 |
| 6 | 不修 | 两处 offline 标志只在对应 error 分支中读取；成功清 error，下一次失败重新分类，旧布尔不会造成可见错误。 |
| 7 | 不修 | 四图标签 `kiosk-screen-17-baipu.fourup.spec.ts:142` 两处半角逗号不影响功能；保留已获 Fan 确认的图中文字。 |
| 8 | 修 | `plan.md:178,2201` **两处**均改为 `^(FAILED\|ERROR) tests/`。本次全量严格按此过滤，没有把日志 ERROR 算作失败。 |

## 三、已核实的产品边界

- **模式与时序**：BaipuSessionRoute 等 mode；上线态再等 `geometry.loaded`，随后按 `waiting_empty / dark_reference / flashing_corners / verifying / building_baseline` 五态决定是否显示标定屏；真实 Provider 的初始 required 不被当作已读结论。五态名单与服务端一致。
- **超时**：mode 的 race 同时涵盖 fetch 和读 body，错误/不认识的响应回 false；abort 后的拒绝被接住，迟到 true 不会改判。
- **旧后端、离线**：mode 404 回 false；geometry 404/旧返回格式回 disabled 并置 loaded；geometry 其它错误尚未读到时保留有返回键的等待屏。断外网不要求本机后端离线，缓存/导入谱通过本机 load 解析。
- **非 19 路**：摆谱加载后在设置 steps/进入 guiding 前拦截，forgetSgf 删除 SGF、进度并从 recent 摘除对应项；详情按钮同步禁用。非方形 SGF 仍按 PRD 明确排除。
- **N9**：两条 dispatcher 都调用原有 `_remote_only`，离线/TransportError/5xx → 503，404 保留；前端真实客户端提供 ApiError.status。board lifespan 确实注入 remote_client，未断开其在线条件。
- **采集门**：`__main__.py` 保留采集 CLI 参数，argparse 与 lifespan 使用同一个 settings；`/mode`、`/capture` 共用“采集服务存在且开关打开”的判断。关闭时在几何与采帧操作前 404。
- **部署与 import**：新增判断不读 token；没有 kiosk → galaxy 或共享代码 → kiosk/galaxy 的新增反向依赖。两套常规构建和严格 Box SSO 包均构建成功，严格包输出了 token 边界通过信息；这不代表已经在盒上跑过真实 SSO 身份链。

## 四、验证命令与结果

完整本机日志位于 `.superpowers/sdd/plan/final-review-evidence/`（不提交）。始终在本 worktree 运行。Node 使用 `/Users/fan/.hermes/node/bin` 的 **v22.22.3**；一次 Node 26 的 localStorage 环境错误未计为产品回归，最终相关测试与全量均用 Node 22。

### 聚焦与变异

- `UV_CACHE_DIR=/private/tmp/kifu-review-uv CI=true uv run --offline pytest tests/web_ui/test_board_lifespan_camera_degraded.py tests/test_baipu_api.py tests/test_baipu_capture.py tests/web_ui/test_kifu_offline.py -q` → **44 passed**。
- `npx vitest run src/api/kifuApi.test.ts src/kiosk/__tests__/KifuPage.test.tsx src/kiosk/__tests__/KifuDetailPage.test.tsx src/kiosk/components/report/ReportLibraryImportDialog.test.tsx src/galaxy/components/research/CloudSGFPanel.test.tsx` → **55 passed**。
- `npx vitest run src/api/baipuApi.test.ts src/kiosk/__tests__/BaipuSessionRoute.test.tsx src/kiosk/__tests__/BaipuSessionPage.test.tsx src/kiosk/__tests__/KioskApp.test.tsx` → **38 passed**。
- F1–F5 变异均只改当前工作树中的对应表达式，逐项执行、finally 还原；从未 checkout 旧提交。最终所有生产源码与交接 HEAD 一致。

### 构建与边界

- `npx tsc -b` → 0。
- `npm run build`、`npm run build:kiosk-2d` → 0；`kiosk boundary clean`。
- `npm run build:smartbox-kiosk-2d` → 0；`strict Box SSO boundary clean`、`kiosk boundary clean`。
- 按 Task 7 Step 1 对列出的 8 个生产源码文件运行 eslint → 0，无输出；`git diff --check` 通过。

### 最终全量失败名字集合

- `npx vitest run --reporter=default --reporter=json --outputFile.json=<本次新报告>`，跑前删旧报告、记开跑毫秒及退出码，再调用基线原有 `vitest_failset.py`。结果：**164 文件 / 1755 用例，exit=0，REPORT_OK，新增失败=∅**。相对 T7 新增 1 个文件、5 个用例符合本次变更。
- `UV_CACHE_DIR=/private/tmp/kifu-review-uv CI=true uv run --offline pytest tests -q -rfE --continue-on-collection-errors` → **59 failed, 3866 passed, 7 skipped, 1 xfailed, 20 errors；exit=1，PYTEST_RAN**。
- pytest 按 `^(FAILED|ERROR) tests/` 提取并删掉 ` - ...` 后排序去重，与 `$HOME/.cache/kiosk-go-kifu/baseline/pytest-fail.txt` 比较：**新增失败=∅**；不再失败仅 `tests/test_galaxy_polish.py::test_user_repo_get_by_id`，为交接注明的 PG 环境相关翻转，不宣称是本次修复。
- 首次受限环境的全量 pytest 在 Kivy 图形初始化处段错误，exit=139、没有汇总，明确判为 `PYTEST_DID_NOT_RUN`。随后允许本机图形访问重跑上述原命令，才得到有效全量结果。
- pytest 后 `git status --short katrain/config.json` 为空；测试生成的 `test_user_data.db` 已清理。

### Playwright

- `KATRAIN_PW_VISUAL_PORT=5273 npx playwright test --config=playwright.visual.config.ts tests/kiosk-shell-contract.spec.ts tests/kiosk-shell-geometry.spec.ts tests/kiosk-shell-scroll.spec.ts` → **76 passed**。
- `KATRAIN_PW_E2E_PORT=8102 npx playwright test tests/baipu.spec.ts` → **8 passed**。使用已重新生成的普通 build、一次性 SQLite 和测试密钥；运行前后备份/还原 `~/.katrain/config.json`，逐字节一致；临时数据库已删除。
- `.last-run.json` 已按运行前字节还原。端口不复用，未杀其他服务；未重取或改动已确认的四图。

## 五、新增提交

| 提交 | 内容 |
|---|---|
| `4000d4d6` | N9 非空结果与参数断言、两端错误映射 |
| `2c9f97a3` | 真实 KifuAPI 的 HTTP 错误类型接线 |
| `a907c378` | token=null、required 下真实摆谱入口守卫 |
| `fbbb83d9` | CLI/env → lifespan → mode/capture 正向接线 |
| `b3c88037` | 独立 3 秒契约及 abort 后迟到 reject |

本报告与 plan 的两处 pytest 过滤修正作为最后一份文档提交；不混入上述各项测试修复。

## 六、仍待 Fan 的事

沿用交接事项，本次没有新增产品决策项：

1. **RK3562 上板**：按 `task-7-report.md` Step 5，一次只跑一家、人工在场，部署本分支后端及 **`build:smartbox-kiosk-2d` 严格包**。服务重启不标定即可摆完；核对黑红/白绿/提子蓝；前后比较 **`/root/.katrain/baipu_captures/`** 无新目录；mode=false；标定中返回再进摆谱应先等标定，取消后第一颗灯正确；退出/完成均回棋谱且 Dock 可见；拔网后两屏说要联网。结果回填 `prd.md` §7。
2. 确认「正在检查棋盘状态」「棋盘标定还在进行」两句新文案。
3. 保留已接受的小窗口：服务端终态之后 finally 再清灯，可能冲掉摆谱第一颗灯；「重新点灯」可恢复，上板时一并观察。
4. `prd.md` §4 D1–D7 仍待拍板；本轮 16 个 i18n key 未进 PO（D7）。
5. 上板顺带记录全屏 Chromium 的 SGF 文件选择器（S5），以及一次触摸是否误跳两手；不提前加冷却。
6. **由 Fan 决定是否合入 develop**。本次未 push、未合并，也未用本机 fixture 结果替代硬件验收。
