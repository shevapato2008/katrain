# Kiosk 棋手卡片可见间距与真实等级实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to implement this plan after independent Astra Max review (最多两轮计划评审及修改). Steps use checkbox syntax. 用户已授权按 feature → develop → Smartbox main gitlink → RK3562 发布；无需再次征求执行许可。

**Goal:** 统一全部 Kiosk 同类交错梯形的实际可见斜缝，补齐真实等级，并明确无权威数据的未知状态。

**Architecture:** 复用原批准的圆角 SVG，抽取同一双卡几何/描边样式；以画出来的斜边间距验收，不用 box gap 代替。等级按真实来源呈现：大厅现有中央 active-games/spectator 元数据、账号新鲜 AI-ladder status、AI 冻结目录/计算难度、平台已验证棋局数据、SGF BR/WR；没有来源就显示未知。仅做本旅程所需局部契约补充，不改对局/计时/识别/纠错/权限/收费逻辑，不新增云端发布依赖。

**Tech Stack:** 现有 React/TypeScript/CSS/SVG、FastAPI/Python、Vitest/Pytest、真实 Chromium 1024×600；沿用 UI UX Pro Max 下的已有 Kiosk 字体及设计。

**Baseline:** `origin/develop=09ee7f59faf40e4908e70d6c201aebd25257d33c`；Smartbox main=`8c29181163542d6e53cecfc52e33850c16254807`。实际发布前重新 fetch，保留教程字体/十九路 policy 及所有后续更新。

## Chunk 1: 调查结论与合同

已读源码：
- `PvpSpectatorPage.tsx` 复制了梯形 SVG，却仍用两个 grid 列 + 8px gap。AI/Lobby 是左右绝对定位，box 重叠16px，因此画出的斜缝约相差24px。
- `LobbyGamePanel.tsx` 只渲染姓名，漏了等级；中央 `/api/v1/games/active/multiplayer` 已返回 `player_b_rank_label/player_w_rank_label`，strict box 已重写本人的 session_id，因而可复用现成权威 API，无需新增中央端点或部署中央。
- `PvpSpectatorPage` 已渲染中央段位；`GolaxySpectatorPage` 显示平台 rank，但缺失时静默隐藏，且名片仍是矩形。
- `GameControlPanel` 的 `rank_display` 仅用于冻结阶梯 AI；`calculated_rank` 只为 AI 计算，真人为 None。不能拿当前 AI 对手等级给真人，也不能用过时 profile/cache 填充。
- OGS `PlatformGameSession` 已验证两席身份，但等级未带到 Kiosk；旧 opponent.rank 的缺值默认15不能用来构造真实等级。星阵机器人 level_name 是机器人难度，不能给真人。
- `core/baipu.py` 已读 SGF 的 PB/PW，却未把 BR/WR 放入 meta。
- 本地逐手确认两侧整体操作席和棋谱列表/报告紧凑姓名条不套新梯形；本地未绑定账号的临时两名玩家没有可验证真人等级，明确未知。

等级显示合同：
- known：真实 label；无头像/默认数字补齐。AI 计算值是难度/估计等级，tooltip/aria 标明来源；不当真人等级。
- unrated：仅权威 AI-ladder 明确返回 `placement_state.phase === 'placement'` 时显示“尚未定级”。大厅/观战的 null、空白或缺失 label 均为未知；不能根据 rung 猜标签，因为 playable_rungs 会过滤目录不可用项。
- unknown/error/missing：显示“等级未知”；加载时可显示“等级加载中”。空白、无字段与明确未定级不能混同。
- 长姓名与等级分开：姓名省略并保留完整 title；等级为不收缩的小字，避免排在长姓名末尾一起被截掉。
- 大厅请求按账号身份 + route session + game_id 隔离，取消/超时/身份切换丢弃旧响应；只读取现有 API，不落本地缓存、不把上个房间段位带进新房间。

## Chunk 2: 可执行任务

### Task 1: 统一可见斜缝（前端工程子 agent）

**Files:** `katrain/web/ui/src/kiosk/shell/PlayerCardSurface.tsx`、新增同目录 `playerCards.css`；`kiosk-shell/game-redesign.css`、`engine-game-redesign.css`、`golaxy-spectator.css`；`LobbyGamePanel.tsx/.css`、`PvpSpectatorPage.tsx`、`GolaxySpectatorPage.tsx`、`BaipuSessionPage.tsx`、`baipuReviewed.css`。

- [ ] 在真实 React + API fixture 下，先取 AI 参照、邀请对局、观战的 1024×600 修改前图与几何。保存 SVG 斜边在25%/50%/75%高度的可见间隙（含描边）以及 card box，不只记录 gap。
- [ ] 同一原 SVG 左右直线在归一化 viewBox 中相距210，宽234。若组宽G、单卡宽C，则中段路径间隔 `G - (74/39)*C`。以原 AI 约8.4px路径缝为目标，统一 `C=(39/74)*(G-8.4px)`；描边后约6.9px。用当前Chromium支持的CSS calc（必要时等价小数表达），不引入 ResizeObserver/JS逐帧布局。
- [ ] 公共 pair/card/surface classes 控制几何；不同页面只保留各自高度、内容及padding。AI/Lobby104、摆谱76、现有大厅观战136保持；星阵观战改为104以复用同样对局卡，保留原棋盘与计时数据。
- [ ] 所有消费者复用 PlayerCardSurface，删除大厅/观战复制的 SVG；不改黑白顺序、轮到谁判据、时钟来源及业务事件。
- [ ] 修改后重拍代表页面；各同类斜缝在三条测量线上与AI参照差≤1px。核对无页面/操作区溢出、长中英文姓名不碰斜边。保存参考/前后/并排/叠加图。

### Task 2: 最小等级数据契约（后端工程子 agent，可与 Task 1 并行）

**Files:** `katrain/core/baipu.py`、`katrain/web/interface.py`、`katrain/web/session.py`、`katrain/web/platforms/models.py`、`platforms/manager.py`、`platforms/ogs/adapter.py`、`platforms/golaxy/adapter.py`；扩展现有对应测试（按实际现有名称定位，不另造大型套件）。

- [ ] SGF meta 增加可选 `player_black_rank/player_white_rank`，仅来自原 BR/WR；保留专业段位字符串，不凭姓名查库或猜段位。
- [ ] PlatformGameSession 增加默认空的 B/W `player_ranks`。OGS 从已验证game_data.players的实际 ranking/显式rank解析；缺失/非法/provisional按真实标志留空，不能沿用默认15。星阵引擎仅把已确认level_name放在AI色；真人没有平台rank时留空。
- [ ] Manager 在创建/恢复该平台棋局时将 player_ranks 写入独立 `platform_player_ranks`；包含 OGS新建、恢复、同局着数未变的重连，以及独立 start_engine_game 星阵路径。即使新结果为空也更新/清空，跨新局和SGF加载清空旧值。星阵只能取真实 level_row.level_name，不接受现有 AI-{level} fallback。Interface序列化，不改 calculated_rank/rank_display 语义。
- [ ] 为账号真人提供可核验席位：SessionManager 从真实账号参数显式注入独立 `account_user_id`，不能用引擎 UUID。用一个极小的内部准入参数/标志，在首次 start/get_state 前确定资格：research、multiplayer、平台/engine 调用传 False，普通私有 play 传 True；research不能等首个last_state之后才清除。Interface跟踪当前局来源：`_do_new_game` 的 move_tree/sgf_filename 非空（含 load_sgf）清当前局资格，只有新建的非SGF私有AI开局能重建；缓存owner同时移除/刷新。仅会话准入及当前局来源有效、账号正整数、唯一human与另一席真实AI、自由/阶梯AI局时生成 `rank_owner: {user_id,color}`。平台/研究/多人/匿名后续管理认领均不推断。前端必须与当前认证 user.id 相等才读该账号现有status。
- [ ] 聚焦测试：BR/WR有无；OGS缺ranking不变15级、两席颜色、同局无落子重连及切局清空；星阵等级只给AI且缺level_row不取fallback；有效私有AI黑/白owner、engine UUID非账号、play→load_sgf清资格、research首个last_state无owner、多人/平台首帧排除、匿名认领不赋。不得更改DB或调用真实平台。

### Task 3: 等级显示集成（Task 1/2后，主工程 agent）

**Files:** `src/kiosk/hooks/usePlayerRanks.ts`（或两个小职责hook）、`src/kiosk/utils/playerRank.ts`；`src/api.ts`、`api/baipuApi.ts`；`GamePage.tsx`、`GameControlPanel.tsx`、`LobbyGamePanel.tsx`、`LocalConfirmGame.tsx`、两观战页及摆谱页。

- [ ] common纯显示 helper规范化已知/未定级/未知，区分内部数值、k/d标签、SGF专业原串、AI等级；不再让parseInt把20k解释成20段。
- [ ] 大厅从现有 `/api/v1/games/active/multiplayer` 取当前route session精确匹配行（strict box已重写），读取两席 rank_label。scope含user/uuid/token/session/game；8秒超时，前台最多30秒刷新，不并发积压，错误清为未知。null、空白、缺失label和“非null rung+null label”均未知，不称未定级。组件props显式传sessionId。
- [ ] 自由/阶梯局仅在 `rank_owner` 与当前账号匹配时调用 `getAiLadderStatus`，从明确placement_state取本人等级；不用user.rank/本地存储/AI对手等级。不匹配/匿名为未知。小hook采用8秒截止、单请求、前台最多30秒；进入页面、身份/棋局/席位变更、恢复可见及权威结算后刷新，不随每次gameState更新请求。渲染时按scope校验；切换/卸载取消并丢弃迟到响应，隐藏页不持续轮询，失败清未知，不复用会保留旧值的阻塞页useAiLadderStatus。
- [ ] GameControlPanel、LocalConfirmGame、Lobby姓名旁显示独立等级；平台局用platform_player_ranks，AI用冻结rank_display或明确AI calculated难度。摆谱用BR/WR。两观战用各自当前快照等级，无字段明确未知。保留姓名title、计时、回合、提子和全部按钮条件。
- [ ] 相关单测覆盖邀请两席等级、长姓名等级、跨房间/账号迟到响应、空白及rung有值但label为null、未知不伪造、颜色/来源不混。后端至少运行 `pytest tests/test_baipu_load.py tests/web_ui/test_ogs_platform_game_bridge.py tests/platforms/test_engine_manager.py tests/web_ui/test_interface.py` 及新增owner来源测试；前端运行 GameControlPanel/clock、LobbyGamePanel、PvpSpectatorPage、GolaxySpectatorPage、`src/kiosk/__tests__/BaipuSessionPage.test.tsx` 以及新增hook/helper测试。最终记录精确文件/命令，不扩张到无关全仓失败。

### Task 4: 审核、合并与 RK 定向发布

- [ ] 独立 `gpt-6-astra` + `max` 代码与真实 1024×600 视觉/交互审核；修复must-fix后复审至Approved。提交模块盘点、间距实际测量、等级来源与客观缺失表。计划审查最多2轮；实现审核按用户要求直至通过。
- [ ] feature重新fetch/merge最新develop，解决冲突且不丢十九路policy/字体；必要聚焦测试、full及strict Kiosk构建、检查合并树；commit/push feature，再正常FF合入并push develop（不用force、不动他人develop checkout）。
- [ ] 独立Smartbox工作树基于最新main，只更新vendor/katrain到实际已发布commit（程序读取完整SHA并验证对象，不手写猜hash），commit/push main；与主agent协调并发写入。
- [ ] 按最新教程发布回执导出391+实际新增Python、`content/kiosk19_policy.json`及全量full/strict静态。先验真实进程/文件hash及设备当前活跃棋局，不能用旧marker回退。保护SQLite、配置/身份/key、模型、全部硬件状态、policy、其他棋类；备份至/mnt/data，根盘≥2GiB。只有安全闲置窗口才重启围棋服务。
- [ ] 验证manifest逐项hash、真实served入口/卡片chunk、health/视觉硬件与原页面；正常主页→围棋恢复现有SSO并回原URL，不读取/注入cookie、不新开局/摆盘。清本次上传/解包候选，留rollback/SQLite快照/清单/证据。
- [ ] 发布回执独立证据分支，汇报published develop/Smartbox/RK实际版本、Astra结论、盘点/测量/真实等级来源/未知例外。若发现必须中央新契约才能获得的数据，先回主session明确依赖，不部署模拟数据。

## 计划修订记录

- R1指出并已修正：大厅/观战null不能推断未定级；账号准入必须在首帧前确定，并随SGF、research和multiplayer清除。
- R2只复核上述修订及刷新/平台恢复/fallback验收。计划最终Approved前不修改产品代码。
