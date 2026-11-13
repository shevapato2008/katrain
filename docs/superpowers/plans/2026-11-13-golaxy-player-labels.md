# 星阵对局棋手名称中文展示 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** RK3562星阵机器人对局的两张棋手卡显示公开用户名／“我”和“星阵·机器人名称”，补齐真人平台等级；所有对弈模式真正终局留盘后停止本局识别与漂移计算，并清除过期“确认中”。

**Architecture:** 名称只修kiosk展示边界。GamePage已有登录用户；复用`displayAccountName(user, '')`获取公开显示名并传给GameControlPanel，在`engineMode`且`platform_engine_color`为B/W时，按该权威执色生成显示名。剥离机器人名称开头的`[golaxy]`技术前缀，复用`aiOpponentName`现有机器人名称翻译；等级继续使用`seatRank`，不复制等级表、不改后端姓名、棋谱或历史数据。

**Tech Stack:** React/TypeScript、Vitest、Python视觉服务及pytest、现有Playwright浏览器预览、Git跨仓库发布。追加等级和终局生命周期分别在Chunk 4、5实现；不修改反光识别或参考帧裁决规则。

## Chunk 1: 根因和已批准范围

- 用户已指定显示规则并授权开发到代码审核通过，发布按四步走；RK部署前必须通知，当前有对局时禁止部署、重启或操作对局。
- 原始取证：`output/diagnostics/golaxy-player-card-names-20261113/device-before.png`及`device-state-evidence.json`，主工作树内ignored输出。
- 现场1024×600：W卡`Me`，B卡`[golaxy] 星皮猴`，等级`2段`，顶部登录用户`shuangmei`。API明确`platform_engine_color=B`，两边player_type均为human，不能用player_type猜机器人执色。
- 根因：`platforms/manager.py:start_engine_game`使用`Me`和`[golaxy]`创建镜像名字，卡片直接显示`info.name`。
- 现有名称表：`platforms/golaxy/engine_client.py:GOLAXY_AI_LEVELS`，3星=星猛虎、2星=星雄狮、1星=星巨象、2段=星皮猴。卡片只使用已提供名称和等级，不自行按Elo估算。
- 工作树基线`ec6ca09d18069403235247866b6744843c9c4c12`，分支`fix/golaxy-player-labels-20261113`；保留原工作树和其他任务。

## Chunk 2: 一个闭环实施任务

**Files:**
- Create: `katrain/web/ui/src/kiosk/utils/playerName.ts`、对应`playerName.test.ts`。
- Modify: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx`（显示名透传，不改时钟和布局）。
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx`（用已有`displayAccountName(user, '')`传公开显示名，避免展示内部账号句柄）。
- Extend: `katrain/web/ui/src/kiosk/__tests__/GamePageEngine.test.tsx`、`components/game/GameControlPanel.playAi.test.tsx`，按需要选择最小测试位置。

- [ ] 先补失败用例：真人执黑／执白、用户名有值／为空、当前现场`[golaxy] 星皮猴 + 2段`、3星`星猛虎`、非engine原样显示。
- [ ] 纯函数按权威engine色处理，非engine或缺少合法engine色时不改名。真人优先trim后的登录用户名，无则“我”；机器人移除开头`[golaxy]`，复用现有名称翻译并加中文品牌，无名称回落“星阵”。
- [ ] 核心规则示意（函数入参可按现有类型组织）：
  ```ts
  if (!engineMode || (engineColor !== 'B' && engineColor !== 'W')) return rawName;
  if (color !== engineColor) return username?.trim() || t('game:me', '我');
  const bot = rawName.replace(/^\[golaxy\]\s*/i, '').trim();
  return bot ? `${t('Golaxy', '星阵')}·${aiOpponentName(bot, t)}` : t('Golaxy', '星阵');
  ```
- [ ] 不改GameState、不覆盖players_info，不新增请求、状态或机器人名称／等级副本。显示名贯通PlayerRow的可见文本和title；保留rank、时钟、提子等现有逻辑。
- [ ] 页面级用例证明登录公开用户名真正传到卡片，内部账号句柄复用既有规则回落“我”；组件级用例证明真人无用户名时“我”、机器人正确名称与原平台等级都可见，普通自由对弈、OGS和本地对局名字不变。
- [ ] 运行聚焦检查：
  ```sh
  npm run test -- src/kiosk/utils/playerName.test.ts src/kiosk/utils/playerRank.test.ts src/kiosk/components/game/GameControlPanel.playAi.test.tsx src/kiosk/__tests__/GamePageEngine.test.tsx
  npm run build:smartbox-kiosk-2d
  ```
- [ ] 主代理用现有浏览器工具做一次1024×600本地真实组件预览，检查两张卡名称和等级完整可读、无新增布局变化。临时fixture只放ignored输出，完成后退出测试进程；不占用／导航RK的当前对局。
- [ ] 按subagent-driven-development：独立实施者完成TDD与提交，之后独立规格检查，再独立最终代码质量审核；按本任务风险收敛范围，不重复全站回归。

## Chunk 3: 发布与设备部署门

本轮用户要求在部署之前先通知，因此只执行前三步并在第四步前交接，不立即触发任何设备或云端部署。用户已在本会话明确第四步目标为RK3562；项目通用的云端部署目标不作为本次擅自扩大生产发布的依据。

- [ ] 先fetch最新develop合入feature，核对冲突、验证后推feature。
- [ ] 将feature合入并推远端develop。
- [ ] 在隔离的smartbox-software工作树追main，更新vendor/katrain到发布的develop，推main，保留原父仓WIP。
- [ ] 向用户报告开发／审核和发布commits，**在部署RK之前停止并通知**。用户当前对局不得中断；单有vision unbound不足以证明没有在标定或创建对局。
- [ ] 之后获准且设备空闲时才部署；使用发布版本构建和现有有界部署流程，保留USB兼容修复、识别逻辑和用户数据，验收当前1024×600页面实际名称。此次到通知阶段前不进行设备写入。

## Chunk 4: 用户追加——真人的星阵等级

现场已通过现有owner-bound用户列表及资料接口只读确认：星阵本人`shuang`，`is_self=true`，等级`2段`。证据在`output/golaxy-player-labels/self-rank-live-evidence.json`。根因是`GolaxyAdapter.start_engine_game`把真人`player_ranks`写成None；前端已有正确的平台等级展示管线。

**Files:** `katrain/web/platforms/golaxy/adapter.py`、`tests/platforms/test_golaxy_engine_adapter.py`（必要时仅补相关fixture）。

- [ ] 使用TDD：真人B/W从已连接本人资料取得2段，机器人等级不变；无资料、未知level、超时、auth错误时仍可按原流程开局且真人等级未知。
- [ ] 在新开局时用现有`_rest._get_user_code()`和`get_player_profile()`读取一次本人资料，复用现有`_LOBBY_RANKS`；整次读取设置约3秒总上限，不在每帧／每手／每次渲染请求。
- [ ] 只有确认本人资料才填真人执色，另一色仍来自原AI level表；凭据在请求期间变更时不使用旧结果。不把盒内段位或AI强度当本人平台等级，不输出凭据、电话或完整响应到日志。
- [ ] `GolaxyLobbyError`、超时等资料不可用情况只降级展示，不修改既有登录/refresh/引擎走子行为；测试全部mock网络，不引入后台轮询或新公共API。
- [ ] 独立规格核对与最终代码审核覆盖此追加；运行adapter和engine integration相关聚焦测试。

## Chunk 5: 用户追加——终局留盘停止本局识别

**Evidence:** 原始截图`ended-before.png`两张卡均为“本局结束”，第183手仍出现“确认中”；同期vision bound、capture_pending且日志继续推理。静态缺陷及无硬件复现记录在`output/golaxy-player-labels/ended-vision-investigation.md`。现场终局是否由历史游标触发尚缺同时间state，不能把该路径当成已证实的现场唯一原因。

**Files:**
- Modify: `katrain/web/core/physical_play_orchestrator.py`，统一最终终局判定及本局需帧状态。
- Modify: `katrain/vision/ipc.py`、`service.py`、`worker_inprocess.py`、`worker.py`，窄终局状态及命令消费。
- Modify: `katrain/vision/camera.py`，沿既有需求超时去掉无需求周期解码，保留共享reader与USB缓冲排空。
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx`、`components/physical/PhysicalPlayStatusChip.tsx`，终局提示生命周期及timer。
- Extend: `tests/test_physical_play_orchestrator.py`、`tests/test_vision/test_vision_idle.py`、相关既有service/worker测试；`PhysicalPlayStatusChip.test.tsx`及`GamePage.playAi.test.tsx`/`GamePage.test.tsx`的现有共享路径。相机共享和drift已有测试按实际改动聚焦运行，不另建测试框架。

### Task 3: 权威终局与本局需帧的闭环

- [ ] 先写失败用例：`end_result`最终结束、只有`terminal_result`的历史节点仍结束、`awaiting_count`不结束、新绑定/新game恢复、旧无terminal_result记录真正清除结果可恢复。
- [ ] orchestrator以`bool(terminal_result or end_result) and not awaiting_count`认定最终终局；local-confirmation开关也使用该条件，关闭本局确认窗口。不要用UI文字或普通暂停推断终局。
- [ ] 通过VisionService发一个窄的本局terminal/frame-demand状态，终局时关闭“绑定对局”这个需帧来源；保持generic pause语义不变，lag/removal/hint仍可读取用于恢复。新bind/unbind重置终局状态。命令处理只在worker线程修改推理状态，两种worker均明确消费命令；subprocess实现须使用相同终局停推理边界，不借机重构整个架构。
- [ ] 在本局终局且无monitor/viewer/setup/USB恢复等独立需求时，worker不得继续read、warp、enhance、detect或提交旧候选；清理本局过期pending/window，保留既有source epoch和identity隔离。drift经现有`vision.needs_frames()`返回false同步停止。合法独立消费者仍保有自己的需求；绝不close/stop共享CameraHub。
- [ ] 无其他需求3秒后CameraManager闲时只grab/drain，不每秒cap.read解码；其它消费者读取即唤醒。长闲时恢复首帧须来自恢复后的新读取，不把闲前缓存当新帧；`grab_fresh`超时不返回旧图，保留既有timeout契约。沿现有`_last_demand`和帧时间戳窄改，不新增consumer注册框架。不承诺USB断电或整个进程零CPU。
- [ ] 前端沿既有sessionIsGameOver/isGameOver条件排除本局“确认中”、恢复弹窗等进行中视觉提示；必要时终止本页绑定，但不得修改全局`useVisionSync(null)`仍连接WS的语义（做题/摆谱依赖）。Chip的6秒隐藏deadline不被无关后续事件取消，换节点/卸载仍正常清理；旧pending不跨新game。
- [ ] 用明确camera fake避免MagicMock伪造`read_frame_with_metadata`导致的既有fixture线程异常。测试实际read/enhance/detect调用数、普通pause仍观察、新bind恢复、monitor/viewer/setup独立需求、共享consumer fresh wake；不能只断言paused/needs_frames布尔值。
- [ ] 聚焦验证命令（按最终实际测试文件补充必要service/worker用例）：
  ```sh
  python -m pytest -q tests/test_physical_play_orchestrator.py tests/test_vision/test_vision_idle.py
  python -m pytest -q tests/test_geometry_calibration_service.py tests/test_camera_hub.py tests/test_vision/test_shared_camera.py
  npm run test -- src/kiosk/__tests__/PhysicalPlayStatusChip.test.tsx src/kiosk/pages/GamePage.playAi.test.tsx src/kiosk/__tests__/GamePage.test.tsx
  ```
  根据真实路径对free/ranked/pvp/platform engine共享终局条件做最小参数化，不重复每模式全量截图。最终UI构建与Chunk 2一起跑一次。
- [ ] 独立实施者TDD并提交，独立规格核对，最后以新的Astra Max代理审核合并后的名称、等级、终局三项；修正阻塞发现直至通过。
- [ ] 主代理用一个1024×600本地真实组件预览验证终局提示隐藏、名字/平台等级可读；设备有活动局，不在RK操作或重启。开发及前三步发布完成后先通知，设备验收留到用户批准部署且空闲时。

## 独立只读调查（不混入本次产品变更）

升降级反光、假阳性和“盘面与对局不一致”由独立代理产出`output/golaxy-player-labels/ranked-glare-report.md`。主代理补充只读现场状态与运行版本。没有逐格证据前不把反光、参考帧分支、性能负载写成确定唯一原因；本轮不改相关识别裁决规则。
