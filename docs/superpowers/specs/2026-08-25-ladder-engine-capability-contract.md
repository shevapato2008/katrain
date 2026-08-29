# 升降级对弈的引擎能力契约（**两侧都已实现，缺的是部署**）

> **2026-08-25 当天更正。** 本文最初写作「KataGo 侧待实现」，**那是错的**，而且错在
> 一个值得记的地方：我拿**线上 `/health` 的载荷**推断「服务端没实现」，却没有去看
> KataGo 仓库。判据应当是「我查的这个位置，是这类事实该待的地方吗」——
> 实现在不在，只有源码说了算；一个旧镜像的响应只能证明**那个镜像**没有。
>
> 实际情况：KataGo `develop` 上三个提交早就把这套做完了 ——
> `e1b68dd0`（2026-07-21，attest realtime API model routing，引入 `capability_schema`）、
> `d11d80ea`（2026-07-21，harden realtime API identity checks）、
> `74d7e7fe`（2026-08-05，warm every model before advertising it ready）。
> 仓里的 `config.yaml` 也已经是多模型格式（`models:` 列表 + `default_model: b28`）。
>
> **真正的缺口是部署**：两台服务器上跑的 katago 镜像构建于 **2026-03-31**，
> 比这套东西早四个月；容器里那份 `/app/config.yaml` 还是旧的单 `model:` 格式，
> `/health` 自然只能吐出扁平的 `{status, has_human_model, model, pid}`。
>
> 所以下文「KataGo 侧要做三件事」应读作**验收清单**（新镜像必须满足它们），
> 而不是待办事项。

**代码是唯一权威**，本文只是导航。三个判据函数：

| 判据 | 位置 | 什么时候跑 |
|---|---|---|
| 启动时验能力载荷 | `katrain/core/engine.py::_validate_certified_capabilities` | 建引擎时读 `/health` |
| 每步棋前验档位可用 | `katrain/core/engine.py::require_ladder_capability` | `ai.py::LadderStrategy` 每一手 |
| 每步棋后验回执 | `katrain/core/ladder.py::validate_analysis_attestation` | 拿到分析结果之后 |

## 现状：第一句就拦下了（因为镜像是旧的）

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

## 新镜像必须满足的三条（验收清单，非待办）

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

## 部署要点（2026-08-25 实地摸过）

- **只需重建镜像**，不需要改代码、不需要开分支。测试机 `home-ubuntu` 的
  `/home/fan/Repositories/KataGo` 已在 `develop 74d7e7fe`，但**有 7 个文件的未提交本地改动**
  （给 7 个模块加 `from __future__ import annotations`，以及 `main.py` 里一个
  `_warmup_timeout_override()`）—— 那是那台机器的本地适配，**别清掉**。
- **要多下两份权重**：`b18`（`kata1-b18c384nbt-s9996604416`）与 `humanv0`
  （`b18c384nbt-humanv0`），配置里 `auto_download: true`。ucloud 上外网时通时断，
  这是那台机器上最可能卡住的一步。
- **新代码会先把每个模型都 warm 完再宣布 ready**（`74d7e7fe` 的语义）。模型从 1 个变 4 个
  （2 主 + 2 人类），首次 TensorRT plan 构建会明显拉长「引擎不可用」的窗口，切换要挑时间。
- **先打回滚标签再 build**：`katago-trt:latest` 是 `katago-gpu0/gpu1/katago-calib` 共用的标签，
  覆盖了就没有退路。测试机上现役那版已打成 `katago-trt:rollback-20260325`。

## 2026-08-30 收口：生产的缺口已补，两处代码缺陷已修

**部署（modelstella.com / ucloud-v100）。** 2026-08-25 那次实测的两台里，**测试机当天就换了镜像**
（`katago-trt:new`，Compile Time Aug 25 2026，`/health` 已是 schema-1，b28 + b18 双模型），
**生产没换** —— 镜像仍是 2026-03-31 那版，`/health` 只有
`{"status":"ok","pid":…,"has_human_model":true,"model":"…"}`。用户 2026-08-29 在生产上
用一个未定级账号开局，日志逐字：

```
ERROR:katrain_web:[ladder] engine unavailable at certified strength; no move:
rung 15: HTTP engine does not advertise certified ladder capabilities
```

补法**不是重建镜像**：ucloud 外网时通时断，真正的重建很可能中途停死，而现役镜像一旦被覆盖
就没有退路。改成在现役镜像上**叠一层**（`/tmp/katago-capability/Dockerfile`）：

- `python/realtime_api/`  ← 取自测试机 `home-ubuntu:/home/fan/Repositories/KataGo` 的**工作树**
  （`develop 74d7e7fe` + 7 个未提交的本地适配）。那些适配不是可有可无的：生产镜像里是
  **Python 3.8.10**，`X | None` 必须靠 `from __future__ import annotations` 才能解析。
- `config.yaml` ← 多模型格式，`default_model: b28`，b28/b18 各挂 humanv0。
- `kata1-b18c384nbt-s9996604416-d4316597426.bin.gz` ← 生产机上早就有（旧 release 目录里），
  sha256 与配置一致，**不需要联网下载**。b28 与 humanv0 镜像里本来就有，sha256 也对得上。
- `ENV REALTIME_API_WARMUP_TIMEOUT=1800` ← 写进镜像而不是 compose：compose 归 release 管，
  下一次部署会把手改覆盖掉。

镜像 `katago-realtime:capability-schema-20260830`；旧镜像仍在，另打了
`katago-realtime:base-20260331`。切换只改一个变量（`/etc/katrain/ucloud.env` 的
`KATAGO_IMAGE`，备份在 `ucloud.env.bak-20260830-ladder`），回滚就是把那一行改回去再
`docker compose ... up -d --no-deps katago-web`。

**代码（本仓）。** 引擎补好之后仍有两条会独立地伤到用户，它们**与部署无关，galaxy 与 kiosk 同源**：

1. **「本局不计入升降级」曾经是句空话。** `/ai-ladder/games/{id}/end`（前端「离开对局」）调
   `finalize_reserved_game(terminal_source="remote_resign")` 时不传 `engine_stalled`，
   于是 `_ignored_reason` 里那条 `if engine_stalled: return "engine_unavailable"` 永远看不到
   停摆。生产账本第一行就是这么来的：`counted=t`、`reason` 为空，未定级用户的定级窗口
   当场从 1..32 被砍成 1..16。现在从 `origin_session_id` 回读会话的 `last_ladder_error`。
   **残留的洞**：那个会话若已经没了（重启/超时），这里问不出来，照旧计分 —— 要真补上，
   得让停摆写进 lifecycle 行。
2. **开局前没有人问过引擎。** 预约、pending 账本、坐玩家、开钟全部走完，第一手棋才发现
   引擎服务不了这一档。现在 `/start` 在**第一次落账之前**问一次 `require_ladder_capability`，
   过不去就 503 + 撤预约 + 回收会话，前端说「本次没有开局，也不影响你的段位」。
3. 附带：`last_ladder_error` 从单向闩改成**有界重试**（5/15/30/60 秒），
   瞬时故障（引擎重启）不再永久打死一局棋。

`docs` 与代码不一致时以代码为准；上面每一条都有对应的用例（`tests/web_ui/test_ai_ladder_api.py`
的四条、`tests/web_ui/test_ladder_injection.py` 的四条），且都做过变异检查（把修复摘掉会变红）。
