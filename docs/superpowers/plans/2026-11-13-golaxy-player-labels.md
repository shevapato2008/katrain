# 星阵对局棋手名称中文展示 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** RK3562星阵机器人对局的两张棋手卡显示实际用户名／“我”和“星阵·机器人名称”，保留平台真实等级。

**Architecture:** 只修kiosk展示边界。GamePage已有登录用户；把可选用户名传给GameControlPanel，在`engineMode`且`platform_engine_color`为B/W时，按该权威执色生成显示名。剥离机器人名称开头的`[golaxy]`技术前缀，复用`aiOpponentName`现有机器人名称翻译；等级继续使用`seatRank`，不复制等级表、不改后端姓名、棋谱或历史数据。

**Tech Stack:** React/TypeScript、Vitest、现有Playwright浏览器预览、Git跨仓库发布。

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
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx`（传已有`user?.username`）。
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
- [ ] 页面级用例证明登录用户名真正传到卡片；组件级用例证明真人无用户名时“我”、机器人正确名称与原平台等级都可见，普通自由对弈、OGS和本地对局名字不变。
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
