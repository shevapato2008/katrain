# Ranks101–150：20 PASS anchors → 103 direct-source候选重绑

2026-10-03。Producer：`/root/five_player_test_stage_preflight_sol`。仅处理Astra独立通过的20个reading anchors对应103语言格；没有新候选审批、数据库连接或线上写入。

## 冻结包与可审核范围

受保护目录：`~/.local/share/kifu-name-audit/2026-10-03/player-ranks101-150-pass20-anchor-direct103-rebind-pending-sol-v1/`，目录0700、121文件0400（含manifest）。

| 对象 | SHA-256 |
| --- | --- |
| 新 producer manifest 字节 | `ec3b5ec5a001719c60db7ab966516cee182e2a98e5000e784de6a733f7344104` |
| Astra identity/reading签审输入 manifest | `dc034fd59cc13fea4d146854e114eab22e59e18574444c4fffba908a48f9670c` |
| 前层 raw30/direct155 pending输入 manifest | `5b5748cb13b33c3249299bb763add88b0a5697d381fc121ebc86b9c24703aa25` |
| 新 bundle canonical | `9d7f4567d6797e955bf3584173cd6d63107af3402044999faf7eacadcfcbc647` |
| 103 research JSONL 字节 | `343d2c70f458b9b7bd1fc4384ffb14c0a16bde80a0558a0e76df28f55a7b907b` |
| 103 frozen-preimage-bound candidate JSONL 字节 | `eaacdc7ba963eac51449c21b9c8d41c623ae3a4632120ad79d62ebedd319a3fe` |

可进入下一独立候选审核的是**20 owners、103 direct-source语言格**：cn20、jp20、ko20、en20、tw17、fr4、es2。逐人／逐语计数见 `summary.actual.json`，精确映射见 `rebind103.crosswalk.actual.json`。

## 实际机械核对

- 原输入279文件、Astra签包9文件及其manifest核对通过。20 signed anchors原字节复用；其20 source-profile identity记录保留完整已签对象，20 owner/scope/category内容不变。现有anchor与source-profile签名实际校验通过，profile identity的full-record SHA与anchor审批中的指针一致。
- 103 research/candidates都记录真实 `signed_source_anchor_sha256`、`signed_source_identity_sha256`及原signed scope SHA。research原语tag仅按已签anchor补精确script标签；103显示字符串及 `source_checks`不变，research hash与candidate指针重新计算。没有音译候选、规则或batch生产。
- 103 research结构校验PASS；实际bundle `approved=0 / pending=103 / missing=0 / rejected=0 / write_errors=[] / write_ready=false`。仅20条“new raw category lacks corresponding approved display decision”预期阻塞；没有未签scope／断指针错误。候选是否可批准仍由下一reviewer判断。
- 103个null前像仅机械重绑冻结PROD事务：原capture时间 `2026-10-03T07:36:56.499701+00:00`，capture SHA `457959f10c94a38e87c1a90b19ffb8fbcbe9de9f507bfcba9f7fe229e9ab0bed`。本轮未重新查询数据库；前像的新binding不等于当前线上前像已核对，下一reviewer须审此边界。
- 原10 HOLD anchors、5 mapping记录及余52 direct-source语言格留在原受保护包，未编辑、重绑或提升；secondary172也未处理。

导入证据文件是 `evidence.direct103.pending.jsonl`，只含103 conventional research。20 signed anchors作为包内单独已验证的provenance依赖；它们不在这次conventional bundle的导入evidence列表中。现有校验器若收到standalone anchor导入证据，会要求signed finite transliteration section；本轮不建立该section。新增signed-source指针由producer机械核对和下一reviewer检查，不能声称现有conventional importer自动强制此额外provenance关系。

## 复放与下一闸门

```sh
.venv/bin/python "$HOME/.local/share/kifu-name-audit/2026-10-03/player-ranks101-150-pass20-anchor-direct103-rebind-pending-sol-v1/build.py" --output /tmp/kifu-ranks101-150-direct103-replay-new
```

实际新目录复放121项逐字节相同。外置0400回执 `~/.local/share/kifu-name-audit/2026-10-03/player-ranks101-150-pass20-anchor-direct103-rebind-pending-sol-v1-replay.actual.json`，SHA `2188f90d1c82d1003764847d91d95931b1ea7978008f56b49ebfade5189899a0`。这里只是producer机械复放，不是独立候选审核。

**下一闸门：另一个reviewer审核103格新research／candidate／冻结前像binding，逐格批准或保留HOLD。** 20 anchors及30 source-profile签审仅批准外部来源身份／读音，不批准目标语言显示名、canonical person ID、album FK或生产写入。后续dry-run/apply仍需真实目标库新鲜inventory/catalog/preimage对比及runtime/schema闸门。将来获批player FK时还须同步实体11语approved names，避免FK优先级覆盖raw显示后出现回退。本轮到候选独立签审闸门停止。
