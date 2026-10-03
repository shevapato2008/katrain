# 五棋手 TEST v2：完整55候选机械收口，最终独立复核待办

2026-10-03。Assembler：`/root/five_player_test_stage_preflight_sol`。本轮纯离线机械操作；DB/Docker访问、apply、候选自审、commit/push均为0。

受保护包：`~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-main11-test-v2-final55-mechanical-binding-pending-sol/`，目录0700、29文件0400（含manifest）。

| 对象 | SHA-256 |
| --- | --- |
| 新manifest字节 | `2931e0a87c99e3cfccf49200389b6d053562b7746c3da73ee5799f7b03571a18` |
| 完整55 bundle canonical | `ad890a5b111d39751652ee9ec8b7da207e5ab70d8f06bbca5d24d1fc031cb710` |
| 完整55 bundle字节 | `2d2e67029b470b46722d68434c0dc5d5419c46b70f66d3e05994eefb5e78507a` |
| 55 candidates字节 | `90a67e459af11e68dfb46608a110e3777ada9de21ce35a433019a9cffc710f3e` |

核对三个冻结输入manifest及全部文件：fresh55 producer `adf3dc68e2beeaad1abe35de64cb02f7ff9834ad7f4cfed244caf8da58dca03e`，postbinding batch6 reviewer `59dbaa2cf0b53197c7cd947817fbc1e923ef9a5fa6c080697fe57eef85bde982`，conventional25/preimage55 reviewer `3eb7b3e5c4842e1212a3bd21b6f82348bc5b5f72484cd767184fd1783b393d25`。

25 conventional批准记录原字节复用；30音译候选改指向postbinding六个完整signed batch SHA，并精确继承该独立reviewer的producer/reviewer/model/time/conclusion及approved状态。没有创建任何assembler审批字段。新batch审批时间 `09:10:30.625435 UTC` 晚于原 `bound_at=09:03:25.858394 UTC`。

55前像binding、独立55前像review、capture SHA及null值原样保留；25research、五scope/anchor、六rule、显示值及FK范围不变。前像review指向原fresh pending候选；收口后的signature／batch SHA变化及最终candidate SHA逐条记录在 `candidate55.binding-crosswalk.actual.json`，原55 pending记录也保留供最终reviewer核对。没有新capture。

现有 `validate_bundle` **离线PASS**：`approved=55 / pending=0 / missing=0 / rejected=0 / errors=[] / write_errors=[] / ready=true / write_ready=true`。这只验证已继承的组件批准与机械关系，**不等于最终独立bundle审批完成或活动库写入授权**。外层manifest及 `final-bundle-review.pending.json` 明确保持 `PENDING_FINAL_INDEPENDENT_BUNDLE_REVIEW`。

主要文件：`bundle55.mechanically-bound.json`、`candidates55.mechanically-bound.json`、`secondary30.exact-batch-inherited.json`、`conventional25.approved.unchanged.json`、`preimage55.reviews.approved.unchanged.json`、`validation.offline.PASS.json`、`final-bundle-review.pending.json`。

```sh
.venv/bin/python "$HOME/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-main11-test-v2-final55-mechanical-binding-pending-sol/build.py" --output /tmp/kifu-five-final55-replay-new
```

实际离线复放29项逐字节一致。外置0400回执 `.../china-professional-roster/five-cn-origin-main11-test-v2-final55-mechanical-binding-pending-sol-replay.actual.json`，SHA `0814edd301e64c30d366e237020457654984401f6d7deeb16873b70989e23d1c`；不是独立审批。

**下一闸门仅为另一reviewer对本完整55 bundle及before/after前像链的最终独立复核。** 本轮停在此，不继续dry-run/apply。目标仍为原停止的隔离clone `127.0.0.1:55445/katrain_db`；不重标为active TEST/PROD批准，不建立人物ID/FK。
