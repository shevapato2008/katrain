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

**结论（2026-07-12 三轮调研）：下一个做【野狐围棋 / 腾讯围棋】。** 详见 [`research-platform-selection.md`](./research-platform-selection.md)。

## 文档

- [`research-platform-selection.md`](./research-platform-selection.md) — 平台选型调研报告（三轮对抗验证 + 一手核实），含总排序、双轴可行性、野狐官方接入通道、待验证项、验证清单、方法与局限。

## 下一步（待用户在本分支推进）

1. 需求沟通与规划（PRD / plan）。
2. 拿到野狐 FoxGTP 手册后，据实际协议评估工程量并设计 GTP 适配器（复用 Golaxy 隧道架构）。
