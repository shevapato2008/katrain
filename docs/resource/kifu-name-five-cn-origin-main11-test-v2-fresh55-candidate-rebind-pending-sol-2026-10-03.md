# 五棋手 TEST v2：signed research/batch + fresh clone前像的55候选草案

2026-10-03。机械binder：`/root/five_player_test_stage_preflight_sol`。本轮仅启动原隔离克隆进行只读capture，生成55 pending候选；无候选自审、apply、undo、活动TEST/PROD连接或写入。

包：`~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-main11-test-v2-signed-research-batch-candidate-rebind-pending-sol/`，目录0700、27文件0400（含manifest）。

| 对象 | SHA-256 |
| --- | --- |
| 新 producer/binder manifest 字节 | `adf3dc68e2beeaad1abe35de64cb02f7ff9834ad7f4cfed244caf8da58dca03e` |
| 输入Astra research25/batch6签审 manifest | `874cd34418ef65b4aaf7d487898c6905efd28c14703e540e220990a5a470f49b` |
| fresh clone前像capture字节 | `c55c7355e30bd4d7d060ca52494f41e40b1f7ad1dc84f665425e80a500bb5478` |
| 55 pending candidates字节 | `8414e510e4e2b42fa65214fa8310984d3de3867dbb278df6cd14e396f6ca9d96` |
| pending bundle canonical | `9475984a72bf96ef991f6279b1104f4e170c1a16d4a7325409fb62b320a7b9cb` |

## 实际clone核对与capture

启动前确认本地Docker Unix socket、原容器ID `facc819d4d75635debced92f024ec3ff9591c2ab280f2a4aaaa4b9cad8e916f5`、原同名volume `kifu-five-test-rebind-sol-v2-20261003`（创建于07:43:31 UTC）、旧启动/停止时间及exited状态、127.0.0.1:55445映射均符合原演练记录。实际URL始终为 `postgresql+psycopg2://postgres@127.0.0.1:55445/katrain_db`。

实际capture：`09:00:50.483697–09:00:51.822442 UTC`，repeatable-read/read-only；55名字前像均NULL，五raw owner均不存在，4358精确槽位context、4238 albums及occurrence集与签审目标一致。新inventory SHA仍为 `d5f376a980d12ec82ca18940b199295d6ce0f14b052261e9ce95afe58eb8af54`，catalog仍为 `3d4625b37b57c49f8fbf594a15f2bdb51525067df1cf2e7a5612dc5622f8fa79`，approved-name snapshot未变。SQL计数387 SELECT、4 SHOW、writes0。

capture后立即停止原clone，检查同一container/volume/端口，`Running=false`。完整preflight、真实capture及停止回执在包内；这不是active TEST新鲜核对。

## 机械重绑结果

复用25 detached research签审及其原始research、五signed anchors/scopes、六已签language rules和batch依赖。25 conventional候选指向真实research SHA及detached-review SHA；30音译候选指向真实完整batch SHA。55显示值与25 source checks未变。

55候选均保持pending、移除reviewer字段；每条实际前像binding记binder、capture哈希、精确source-candidate SHA。新的真实 `bound_at=2026-10-03T09:03:25.858394+00:00`。原research/candidate/batch来源producer元数据保留，binder单独记录此次操作；现有conventional校验要求candidate producer与被复用research producer一致，不能任意改写已审research作者。

实际validator：`approved=0 / pending=25 / candidate_count=55 / write_errors=[] / ready=false / write_ready=false`，共35预期错误（30 pending音译尚无可继承的最终approved batch signature，五raw owner尚无approved display决策）。不把它误报55候选全PASS；本轮没有最终签名或dry-run/apply。

## 下一独立闸门与chronology

当前六batch的 `reviewed_at=08:52:33.554004 UTC` 早于新 `bound_at=09:03:25.858394 UTC`，**这些签名仅是当前依赖，不能作为最终可写批准**。`batches6.chronology-HOLD.actual.json`逐批列明：独立reviewer须在新的bound_at之后检查55前像bindings并重新审批六个完整五成员batch，随后producer重绑30候选的完整batch SHA及其精确继承签名。

另一个reviewer须审核25 conventional候选和55真实前像bindings；这一步不由本binder自审。完成上述闸门后再做最终validate/dry-run，当前包即停于此。active TEST migration/写入另需真实URL、新capture及对应审批链，不能把clone签名重标到活动库。

## 离线复放

```sh
.venv/bin/python "$HOME/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-main11-test-v2-signed-research-batch-candidate-rebind-pending-sol/build.py" --output /tmp/kifu-five-fresh55-replay-new
```

实际离线复放27项逐字节一致，复放不连接数据库。外置0400回执 `.../china-professional-roster/five-cn-origin-main11-test-v2-signed-research-batch-candidate-rebind-pending-sol-replay.actual.json`，SHA `ed0f244168b4c2dc6f3720dace5801fa6f25fc5a4ac52ec93e8005bd2a8e20ba`。这里是producer机械验证，不是独立候选签审。
