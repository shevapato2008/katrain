# Kiosk 跨平台对弈（人人对弈 · x-platform）

智能围棋实体棋盘（KaTrain kiosk）"对弈"模块下的**跨平台真人对弈**子轨：让用户在实体棋盘上落子，与各在线围棋平台上的真人棋友对弈（human-relay：人落子 → 视觉识别 → 转发上平台；对手落子 → LED 指引）。

> ⚠️ 本轨与 `feature/kiosk-local-play`（人人对弈·本地面对面对局）是**两码事**，不要混。本轨聚焦"接入外部在线平台"。

## 现状

已接入的平台（本轨之前已完成，位于 golaxy/ogs 相关分支）：

| 平台 | 形态 | 协议 | 状态 |
|---|---|---|---|
| OGS (online-go) | 西方真人池 | 官方 gtp2ogs + OAuth2 | ✅ 已接入 |
| 星阵 Golaxy | 中国 AI（人机） | 官方 REST genmove 隧道 | ✅ 已接入 |

## 本轨目标

为"第一阶段主打**中国大陆**用户"选定并接入**下一个真人对弈平台**。

**结论（2026-07-12：三轮选型 + 野狐协议精读 + 手机 App 路子核实 + 第二梯队核实）**

一句话：**2026 年不存在"大陆 + 自助 + Linux-native + 真人"的干净选项**——大陆真人池被结构性地锁在"商务合作(野狐)或高封号逆向(弈城)"后面。于是**拆成两条线**：

| 线 | 平台 | 定位 | 依据 |
|---|---|---|---|
| **工程下一步** | **KGS** | 立刻做 | 唯一同时满足 自助 / 协议清晰 / 桥接 **Linux-native**（官方 `kgsGtp` 是 Java jar，回路**零 Windows**）/ 允许 relay 的平台。最便宜地把 human-relay 全链路（棋盘→平台，对手→LED）在**真人对手**上跑通，零商务依赖。**代价**：池子在欧美日韩、非大陆，是能力验证不是大陆市场落地。 |
| **商务里程碑** | 野狐 | 产品上市后再谈 | 大陆最大真人池 + 半官方 FoxGTP 通道，但卡在 Windows 客户端 / 商务合作，产品未上市谈不动。**重归类为 BD 里程碑，不是工程冲刺项。** |
| **搁置** | 弈城/Tygem | 不投入 | 唯一开源客户端 qGo **已废弃**、逆向协议对 2026 服务器大概率失效、反 AI 封号激进。外部封锁，"不惜代价"也解不开。 |

**诚实的一期姿态**：大陆客户先给 **星阵(AI) + KGS(欧美真人 human-relay)**；大陆真人对弈作为**野狐 BD 解锁**写进路线图，不承诺工程上做不出来的"干净大陆真人对接"。

选型全过程见 [`research-platform-selection.md`](./research-platform-selection.md)；野狐协议要点与工程量见 [`protocol-and-integration-assessment.md`](./protocol-and-integration-assessment.md)（作为 BD 解锁后的实现蓝图）。

## 文档

- [`research-platform-selection.md`](./research-platform-selection.md) — 平台选型调研报告（三轮对抗验证 + 一手核实），含总排序、双轴可行性、野狐官方接入通道、待验证项、验证清单、方法与局限。
- [`protocol-and-integration-assessment.md`](./protocol-and-integration-assessment.md) — **野狐协议要点 + 工程量评估**（一手通读接入协议 v1.05 + 接入手册 v2.01）：三段式架构、`$FA/$AF` 私有协议速查、GTP 层要点、human-relay 映射、三条集成路径(A 官方 FoxGTP / B 自研 Controller / C 手机 App 中继)对比、关键约束(Windows 客户端在环/时间控制/合规)、决策岔路。**野狐已重归类为 BD 里程碑；此文作为解锁后的实现蓝图。**
- [`kgs-plan.md`](./kgs-plan.md) — **KGS 接入实施计划**（brainstorming→writing-plans 产出，2026-07-13）：10 个 TDD 任务，从既有 KGS 脚手架补完 live 真人 human-relay。范围=MVP+路线图；决策=浏览棋友+邀请 / 时限每局自选对齐 KGS 设置页 / LED 方案 B(`platform_engine_color`→`platform_guided_color`)。**KGS 工程开发从这里开始。**

## ✅ 大陆可达性闸门：已实测通过

OGS、KGS 都是境外托管，曾担心大陆需 VPN。**2026-07-12 在 kiosk（`gzpeite`，大陆网络，无 VPN）实测：闸门过。**

```
== online-go.com   http=200  connect=0.62s  total=1.66s
== gokgs.com       http=200  connect=0.39s  total=1.10s   (KGS 反而更快)
```

- **证明**：两站均非域名封锁，直连成功、延迟可接受。"必须 VPN"的假设**被否**。也顺带说明已上线的 OGS 在大陆并非完全不可用。
- **未证明**（残留低风险）：① HTTP 一次性请求 ≠ 长连接 WebSocket 实时稳（GFW 可能掐长连接）；② 单点单时刻单 ISP，GFW 会变。
- **对我们用法风险很小**：human-relay 是**慢棋**（一手几十秒~几分钟），1~2s 延迟/偶尔重连都无所谓——"读秒超时判负"只对快棋成立。
- **剩余唯一顺手确认**：在设备浏览器真开一盘棋看长连接稳不稳（低优先）。复测命令：
  ```bash
  for u in https://online-go.com/api/v1/ui/config https://www.gokgs.com/ ; do echo "== $u"; curl -sS -o /dev/null -w "  http=%{http_code} connect=%{time_connect}s total=%{time_total}s\n" --max-time 15 "$u" || echo "  FAILED/timeout"; done
  ```

> **可达性不再是拦 KGS 的理由。** KGS 剩下的唯一保留意见只是"欧美池 = 能力验证、非大陆市场落地"，与网络无关。

## 下一步（待用户在本分支推进）

1. ~~可达性实测~~ ✅ 已过（见上，2026-07-12 `gzpeite`）。网络不再是拦路项。
2. **决策：现在做 KGS 还是押后**——可达性已排除，剩下的是产品优先级：KGS 是"human-relay 打真人"能力验证（零商务门槛、协议干净、Linux-native），但服务欧美池、非一期大陆客户。做，则复用 Golaxy/OGS relay 栈把 `kgsGtp`(Java jar) 当"引擎"口（board→`genmove`，对手 `play`→LED）；动手前再证实 KGS 2026 注册是否真自助、免费局 human-relay 是否合 ToS（排位需 `Ranked Robot` 授权）。
3. **野狐**留作 BD 里程碑；协议蓝图与工程量见 [`protocol-and-integration-assessment.md`](./protocol-and-integration-assessment.md)。
