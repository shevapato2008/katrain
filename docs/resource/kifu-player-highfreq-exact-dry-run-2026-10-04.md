# 高频中文三人精确槽：实时预检与回滚预演

状态：TEST / PROD 均已实际 SQL 预演并回滚，后按独立审核和协调授权提交；结果见 [application](kifu-player-highfreq-exact-application-2026-10-04.md)。身份依据独立 gpt-6-astra max 最终审查，批准核心 3,805 个 NULL 槽；28 个其他称号／混写原值继续 hold。

| 环境 | review SHA-256 | plan SHA-256 |
| --- | --- | --- |
| TEST | `fa5ab38a6aef38be30ce60a0e122ded24112ee7963903a1a6f06f795d63bd89d` | `33ae23a772f50da57f841d311db611f221fd4c05f7943bc6fe5edf349a60b0f9` |
| PROD | `545390ccb4374b2133fbf1ef434a2404630dd215051675486ec377511045450f` | `1a46ffefdbe0245bbd586fa51f7142247d898efe7ebcfa3c6e5ab40c51843c02` |

每库实际预演：新增 FK 3,805（小林光一 1,639、井山裕太 1,279、萧／蕭正浩 887），保护既有正确 FK 5，同名双方 hold 2，覆盖 exact raw 10。两库目录当前 canonical、别名无冲突；10 个 raw staging 均为 pending / NULL metadata。捕获目标及称号 ID 的 aliases、译名、evidence 原像：TEST 56/82/151/339，PROD 56/82/150/338。

工具：[catalog_player_exact.py](../../katrain/web/kifu/catalog_player_exact.py)、[CLI](../../scripts/kifu_player_exact_slots.py)。分别捕获完整 exact raw 的 album ID、side、PB/PW、日期、重复指针、来源及 FK。候选、保护、hold 三种槽必须精确覆盖其原值范围，不能漏槽或重复槽。运行在表锁内重新捕获前像；仅逐槽预先批准的 NULL FK 可更新，并校验日期与原文。PostgreSQL 使用事务临时槽表批量 compare-and-swap，SQLite 使用逐槽更新。

对 raw staging，已有 metadata 中 player_id 与目标不一致即拒绝；其他字段保留。井山裕太基本姓名含坏棋谱 93943，因此保留 pending，metadata 明确 `held_album_ids: [93943]`；不会把同名双方两个 hold 槽解释为已确认。其余九种 exact raw 标 approved。称号旧 ID 及所有目录、译名、别名、evidence 无写入，PB/PW 和段位无写入。

预演在提交／回滚前逐槽核对完整 raw/date/source/FK 范围及目录，之后回滚再重新捕获，两库所得计划完全相同。TEST 使用已有 web 容器单独 Python 进程；PROD 使用专用 importer image `katrain-kifu-importer:five-gate-978491a2`、`katrain-ucloud_backend` 网络与既有 env-file。最新源文件只放临时目录，未改在线 `/app` 文件。

验证：`pytest -q tests/web_ui/test_kifu_catalog_player_exact.py` → 5 passed。覆盖 rollback/apply、保护槽和 hold 槽、partial raw 状态、缺审批 SHA 拒绝、hold FK 前像变化拒绝，以及 canonical alias 和 raw metadata 异人冲突拒绝。实际两库 dry-run 返回 `applied: false` 且 3,805 槽更新计数相符。

提交必须使用上述各环境对应 review/plan 文件，CLI `pinned()` 核验输入 SHA，另传 matching `--approved-plan-sha256`；本批已获协调批准并完成 `--apply`，不得重放。

独立代码审核指出 exact raw 目录冲突门禁不足后，已添加每个 exact raw 的 canonical 与 normalized alias 检查，并把完整查询结果（包含空结果）冻结到 `exact_raw_catalog`。新增段位原值的异人 canonical／alias 冲突测试先失败后通过。上述计划 SHA 是修复后重新捕获、重新实际 SQL 预演及回滚复查的版本，旧计划 SHA 作废。
