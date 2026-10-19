# 活跃 TEST：五人拆分及吴清源实体只读预检（HOLD）

2026-10-03。执行者 `/root/five_player_test_stage_preflight_sol`。本轮只做运行时元数据读取及本地冻结工件核对；没有修改共享代码、数据库写入、迁移、重启、apply、签署、commit 或 push。

## 活跃 TEST 的实际读取边界

此前成功只读查看了 `home-ubuntu / katrain-web` 的环境和代码：应用连接标识（密码隐藏）为 `postgresql://katrain_user:***@host.docker.internal:5432/katrain_db`，`KATRAIN_BUILD_SHA=ce8f81ce`、`KIFU_STRICT_NAMES=0`。Docker 元数据也已保存：Web image ID 为 `sha256:d43960ac5259c57dc36a21a3b596c5368a2f53777795107def089e11056d3949`，启动于 `2026-10-03T09:50:57.829811808Z`；镜像名称为 `katrain-web:kifu-name-ce8f81ce`。本地该提交完整 SHA 为 `ce8f81ce7f8fd94264202024a883ae76e017bfa1`；这不是一次远端完整 commit attestation。

只读 capture 的实际 SSH 在 `2026-10-03T10:05:32.793651Z–10:05:40.661305Z` 退出 **255**：`8.130.171.106:22 Operation timed out`。输出 **0 bytes**；远端 capture/DB 查询没有启动。已停止远程尝试。因此 **未取得 active TEST 的数据库 server identity、事务 snapshot、inventory、catalog、approved-name snapshot、五个 owner/55 前像、4358 context 或吴清源实际 ID/11 前像**。`173025 albums` 是上游部署报告；本轮没有从数据库重新核实。禁止将本地旧克隆前像称为 active TEST 当前前像。

此前实际核对的七个运行时模块与本地字节一致：`identity.py=45210851b5ba36caea539fcff9af673daa1b94c30ad9a4c4ae6965530bd118dc`，`name_batch.py=b83728910306ac685e583435d4a2b8cd5912aaada0be24f53c771f4796aee979`；其余 `name_candidates/name_evidence/name_inventory/name_raw_player_scope/name_transliteration` 的 SHA 记于保护目录 `capture-config.expected.json`。其中额外的 `core/models_db.py` SHA 只是 capture 预期值，本轮失败的 capture 未验证它。

## 五人可以机械拆名，尚不能判为实体可安全入库

冻结历史包 canonical SHA `ad890a5b111d39751652ee9ec8b7da207e5ab70d8f06bbca5d24d1fc031cb710` 的全部 28 个 manifest 成员、本体、独立终审字节均已本地核对。每人已有独立批准的 11 个历史克隆名称决策：

| raw owner | 黑槽 | 白槽 | 总槽 | 可机械拆出的名称 |
|---|---:|---:|---:|---:|
| 唐韦星 | 413 | 445 | 858 | 11 |
| 杨鼎新 | 403 | 461 | 864 | 11 |
| 檀啸 | 417 | 494 | 911 | 11 |
| 胡耀宇 | 434 | 434 | 868 | 11 |
| 连笑 | 431 | 426 | 857 | 11 |

这些是 `readable_unlinked / raw_player` 决策，**不批准人物唯一 ID 或 album FK**。五人都有可复用来源/显示研究；五人都缺本轮实际目标库核对，当前可确认安全导入人数为 **0**。历史六个次要语言 batch 均各含五人；一人子集不是原完整签名内容，不能截取成员后继续使用原 batch SHA。要逐人入实体，应先确认真实实体 ID 与目标前像，再按实际 owner 重绑依赖；发生新 `bound_at` 时，相关终审及 batch chronology 必须满足新绑定之后的签审顺序。

槽键 `(album_id, side)` 全部互不重叠；4358 槽覆盖 4238 盘，其中 **120 盘同时有本组两人**，精确 ID 列于本地核对结果。若逐人只写名字，原始槽 context 不受影响；若逐人写 album FK，同盘对手 scope 内也记录两个 FK，旧对手 context 会变化，应刷新后再处理下一实体，不能复用旧 scope 签名。

运行时 `identity.py:766–767,827–828` 在非 NULL `black/white_player_id` 时只选实体名；raw 名仅在 FK NULL 时使用。未来批准人物 FK 时应同时确保该实体十一语名字已导入，避免失去已审 raw 展示。

## 吴清源优先试点：旧资料 11/11 可复用，active TEST 未核实

吴清源旧两份批准包仅含 **existing `player:1` name-only**，无 `album_links`。本轮机械核对了以下五个旧文件 SHA，并确认候选与 bundle 一致、11 语言完整、批准状态和旧前像/签署 chronology 一致：

- 九语 bundle `wu-v4-prod-bound-v2-bundle.json`：`2172c77a48aec4e82da3b25cadff079855960382873ebfca13ef3733c319c890`；候选 `d4b40556a2fb7ea934163c5c4de62c0a9153af069ade484eb112c73584a8bdbd`。
- 两语 bundle `wu-v4-prod-bound-v3-bundle.json`：`78608644d0044d02dabde91ba13e38441a09a5bf6dc949d1452986ccf947bf1a`；候选 `5aab0e1dc3c0e0e8428d08ae8674461ec271a9eb803ef6f41acde83e73c094ae`。
- 旧 capture `wu-name-preimages-prod-20261002.json`：`b1008149c2163938e31822119e38f5e5425b973517073a6aeb4a4f1ba605ea7b`，实际 `captured_at=2026-10-01T20:22:44.345508Z`，数据库 `katrain_prod_20260725`。六语 `cn/de/en/fr/jp/tw` 有旧行前像；`es/ko/ru/tr/ua` 明确 NULL。完整哈希在核对结果中。

原目录为 `~/.local/share/kifu-name-audit/2026-10-02/`，旧来源/名称批准可作为不变研究输入；未重搜、重签或组合新包。旧 `player:1` 是 PROD 历史事实，不能据此声称 active TEST 同一 ID/前像。下一步先读 active TEST 的实际实体行及十一语全行前像；对照实际 catalog/inventory 与导入器门禁决定有限目标绑定。当前只因连接失败停在此处，没有新增身份或候选审查。

## 保护产物及可复放检查

目录：`~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-main11-active-test-rebind-pending-sol-v1/`。`check-local-frozen.py` 是离线核对入口；`local-frozen-preflight.actual.json` 保存精确槽位/共享盘、吴清源 11 语和旧审批/前像；`capture-command.actual.json` 保存失败收据。空 gzip 是失败输出证据，不是快照。目录 0700，文件 0400，manifest 标记 `HOLD_ACTIVE_TEST_PREIMAGES_NOT_CAPTURED`，没有可 apply 新包或新批准。

重放：`.venv/bin/python <保护目录>/check-local-frozen.py`（脚本重写本地结果前需复制到可写隔离目录）。本轮结果为 `local_integrity=PASS / shared_albums=120 / wu_approved=11`，远程重试为 false。当前阻塞仅为缺失 fresh active TEST 数据；连接恢复后的有限只读 capture 应由后续执行者另行安排，本轮没有重试。
