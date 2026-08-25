# 升降级对弈的引擎能力契约（KataGo 侧待实现）

**状态**：katrain 侧**已经全部实现并在生产/测试上跑着**；缺的是 KataGo HTTP 服务
（`realtime_api`）那一半。写这份是为了让实现方不用反推。

**代码是唯一权威**，本文只是导航。三个判据函数：

| 判据 | 位置 | 什么时候跑 |
|---|---|---|
| 启动时验能力载荷 | `katrain/core/engine.py::_validate_certified_capabilities` | 建引擎时读 `/health` |
| 每步棋前验档位可用 | `katrain/core/engine.py::require_ladder_capability` | `ai.py::LadderStrategy` 每一手 |
| 每步棋后验回执 | `katrain/core/ladder.py::validate_analysis_attestation` | 拿到分析结果之后 |

## 现状：第一句就拦下了

2026-08-25 实测，两台服务器的 KataGo `/health` 都只返回旧载荷：

```json
{"status": "ok", "has_human_model": true, "model": "...", "pid": 12345}
```

于是 `require_ladder_capability` 第一句 `if self.capability_schema != 1` 抛
`HTTP engine does not advertise certified ladder capabilities`，
`interface.py` 记一行 `[ladder] engine unavailable at certified strength; no move`，
状态里 `last_ladder_error=true`，前端 `GamePage.tsx` 弹「阶梯引擎不可用，AI 无法落子」。

**所以升降级对弈在两个环境都开不了局。** 界面是诚实的（不是「点了没反应」），
但功能等于没有。

## 为什么不能把这道闸放松掉

因为**账本不可变**。生产库实测：`ai_ladder_game_ledger` 上有触发器
`reject_ai_ladder_ledger_mutation()`，删一行直接报 `ai ladder ledger is immutable`。
一局升降级会往里写一行、并改用户段位。

而每一档是**冻结的配方**（`rung=15` 那档：`net=humanv0, mechanism=humansl,
human_sl_profile=rank_6k, max_visits=1, selection=human_weighted`），
档位的胜率闸是一批批对局标定出来的。**如果引擎能悄悄换权重，那些标定过的胜率
就都在量另一个东西，而账本上的字删不掉。** 放松这道闸 = 把一个硬保证换成一个假设。

## KataGo 侧要做三件事

### 1. `/health` 返回 schema-1 能力载荷

```jsonc
{
  "capability_schema": 1,
  "katago_version": "<非空字符串>",
  "default_model": "<别名，必须出现在 models 里>",
  "models": {
    "<别名>": {
      "running": true,                    // 必须是 bool，不是 "true"
      "has_human_model": true,            // 必须是 bool
      "model_path": "<非空>",
      "model_sha256": "<非空>",
      "model_sha256_verified": true,      // 必须**恰好** true，不是 truthy
      "human_model_path": "<有人类模型时非空>",
      "human_model_sha256": "<同上>"
    }
  }
}
```

类型判据是 `type(x) is not bool` 和 `_nonempty_string`，**字符串 `"true"` 会被判失败**。
`model_sha256_verified` 的语义是「服务端真的算过这份权重的 sha256 并比对过」，
不是「配置文件里写了一个值」。

### 2. 支持按别名的 per-query 模型路由

`engine.py::ladder_extra_settings` 会往查询里塞 `settings["model"] = <别名>`
（走 `overrideSettings.model`）。服务端要认这个字段并**真的**用那份权重跑。

### 3. 每个分析响应带 `_wrapper` 回执

```jsonc
{
  "...": "正常的分析结果",
  "_wrapper": {
    "selected_model": "<本次实际用的别名>",
    "model_path": "...", "model_sha256": "...",
    "katago_version": "...",
    "human_model_path": "...", "human_model_sha256": "..."   // 用到人类模型时
  }
}
```

`validate_analysis_attestation` 会拿它**逐字段**比对启动时留存的那份 identity，
任何一处不等就 `LadderMoveError`。注意它的豁免只有一条：
`spec.main_model is None`（原生 HumanSL 单 visit，没有显式路由）时跳过回执校验——
但**启动时那道 schema-1 闸对所有档位都成立**，所以这条豁免救不了现在的局面。

## 验收判据（做完怎么知道成了）

不要只看 `/health` 的形状。端到端一条：

1. `POST /api/v1/ai-ladder/start` 开一局；
2. `POST /api/move` 落一手；
3. 状态里 `player_to_move` 应当**从 W 回到 B**，且 `last_ladder_error` 保持 `false`；
4. 服务端日志里**不应**出现 `[ladder] engine unavailable at certified strength`。

对照组（证明判据有效）：把 `/health` 里任一个 `model_sha256_verified` 改成 `"true"`
（字符串），第 3 步必须回到 W 不动。

## 相关

- 本仓 2026-08-25 的排查过程与实测数据见 `docs/operations/ucloud-migration-runbook.md`
- 多模型服务那条线：`katrain/core/ladder.py` 的 `rung_engine_params` / `rung_strength_spec`
