# Ranks101–150：signed raw30 scope 重绑层与 identity/reading 草案

日期：2026-10-03。Producer：`/root/five_player_test_stage_preflight_sol`。本轮仅完成离线可复放的 producer 层，新的身份、原语、读音、映射及155候选均未独立审批；没有连接、读取或写入本轮的活动 TEST/PROD，也没有执行迁移、重启或 apply。

## 冻结产物

目录：`~/.local/share/kifu-name-audit/2026-10-03/player-ranks101-150-signed-scope-direct155-anchor30-pending-sol-v1/`。目录0700、文件0400，279个 manifest 受控文件；不改旧 producer 或 scope reviewer 原包。

| 输入／产物 | SHA-256 |
| --- | --- |
| 本包 manifest 字节 | `5b5748cb13b33c3249299bb763add88b0a5697d381fc121ebc86b9c24703aa25` |
| 输入 signed raw30 scope/category manifest | `bcdf46e05579da96ecfe4241d64ba44baab94d7e8589557d8302484779acc1b1` |
| 输入 direct155 v2 producer manifest | `36de195a01a1d9863f13c14adff8ac2d4e6c7bd09917c62338edc8ee8351f894` |
| 新 bundle canonical | `1825544ea037c7b90a446a39ac9b1d78cfc11e3b18238d0251ce734f2b1f2737` |
| 新 bundle 字节 | `8f18a346a69334e09938ce13031ed5de2164539d05f924186caa157f5489642c` |
| reading30 JSONL 字节 | `74dcc53cda97c4024e6345643e3cffc687fdac990ba594a4b1e94527c190e528` |
| identity30 JSONL 字节 | `2c01aa1daa6aa112f356deb8205cdd8df62bb5b4b54e20c0938f5994c5df677c` |

主要文件：`owners.raw30.reviewed.unchanged.json`、`scopes.raw30.approved.unchanged.json`、`identity30.signed-scope.pending.jsonl`、`reading-anchors30.signed-scope.pending.jsonl`、`raw-original-mappings5.prerequisite.pending.jsonl`、`research.direct155.signed-scope.pending.jsonl`、`candidates.direct155.signed-scope.preimage-bound.pending.jsonl`、`bundle.direct155.signed-scope.pending.json`、`validator.actual.pending.json`、`summary.actual.json`、`build.py`。

## 本轮实际核对

- 30 signed owner/category/scope 原字节复用。30 identity/reading、155 research/candidate 的 scope 指针均绑定完整已签记录的 canonical SHA；identity 原始记录 SHA 与 signed owner 外部来源指针一致。
- 155 候选名称字符串没有改变。155 research 均通过现有 `validate_research_record`；新 producer/timestamp、scope/hash/preimage 链已重绑，原 proposal 与研究 hash 保留在变更表。
- 修正86条研究记录的原语来源选择：旧脚本按 official URL 主机选择原语，韩国棋院页面包含中国／日本棋手时会选错来源。本包按冻结的逐人 original-language 线索提出新原语来源，仍为 pending；这不是新 source-name 或译名批准。
- 冻结 localized 网页字节、profile ID、完整 DOB、heading/DOB 字符跨度与罗马姓名分词拼接均核对。25 anchors 通过 localized content 的机械结构检查，5个在 unsigned mapping 处 HOLD。全部30实际 `validate_transliteration_anchor` 都因缺精确独立审批拒绝；没有伪造 approval 绕过检查。
- 实际 bundle：`approved=0 / pending=155 / rejected=0 / missing=0 / ready=false / write_ready=false / write_errors=[]`。仅30条“new raw category lacks corresponding approved display decision”预期阻塞；没有 unsigned scope/category 或错指针错误。
- 原26 context HOLD 排除、16525 display slots、26同名 canonical 线索及 unsigned identity-ID 队列原样保留。172 secondary rule proposals 未提升、未生成规则或批次签名、未建立 FK/alias。

本轮 preimage 只复用冻结 PROD read-only repeatable-read 事务：2026-10-03 07:36:56–07:38:29 UTC，snapshot `1647002:1647002:`。capture SHA `457959f10c94a38e87c1a90b19ffb8fbcbe9de9f507bfcba9f7fe229e9ab0bed`；format2 inventory `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`；catalog `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09`。155 null preimages来自该事务整表为空的事实，不能称为本轮的新鲜线上核对；receipt明确保留原 capture 时间。

## 复放

在新输出目录执行，不覆盖受保护原包：

```sh
.venv/bin/python "$HOME/.local/share/kifu-name-audit/2026-10-03/player-ranks101-150-signed-scope-direct155-anchor30-pending-sol-v1/build.py" --output /tmp/kifu-ranks101-150-producer-replay-new
```

实际一次独立目录复放已完成，manifest及全部文件共280项逐字节一致。这里只是 producer 自己的机械复放，不是独立 reviewer 签审。外置0400 receipt：`~/.local/share/kifu-name-audit/2026-10-03/player-ranks101-150-signed-scope-direct155-anchor30-pending-sol-v1-replay.actual.json`，字节 SHA `0ef1425de33948400851d6b4b5def06d7711a8decf5ece22534d88c63b3e5c15`。

## 下一闸门

1. 另一个 reviewer 审30 identity/original-language/reading 草案。8个韩国 published Roman aliases仅机械拼接相符；`Kim/Myounghoon/Sungjoon/Nungwuk`等不可据此直接视为标准 RR，需审核真实读音、别名规范化及 syllables。
2. `金明训、伊田笃史、罗玄、Hane Yasumasa、杨子萱`没有精确 raw localized 页面，5 mapping 先独立审。草案当前引用历史 pending identity proposal SHA；reviewer须核实 prior-reviewed 身份来源，如需实际已签 identity/research记录，应先产生并重新绑定该 SHA。映射批准后必须重新产对应 anchor：现行校验要求 `mapping.reviewed_at <= anchor.produced_at`，不能在当前草案上倒填时间直接签。
3. 另一个 reviewer 审155新 research/candidate/preimage-binding，包括本次原语来源更正。现有 source-name review和raw scope签名不能代替本轮候选审批；本 producer不自审这些新产物。
4. 后续 dry-run/apply另需真实目标库新鲜 inventory/catalog/preimage 对比，以及缺失 event-selection schema、运行时部署边界；本包只绑定冻结 format2 PROD。30 raw阶段候选不等于人物唯一ID完成；26个 canonical 同名只是线索，不批准 FK。

`identity.py`严格解析优先级仍是：slot有 player FK时仅取实体名，FK NULL时才取 raw scope 名称。因此未来审批唯一人物ID／album FK，必须同时保证实体11语 approved names已集成，避免失去已审核 raw显示。本轮到上述独立签审闸门即停止。
