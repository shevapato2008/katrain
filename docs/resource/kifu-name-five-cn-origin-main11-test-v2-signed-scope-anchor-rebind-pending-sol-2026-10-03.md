# 五位中国棋手 TEST v2：signed-scope anchor 重绑草案

2026-10-03，Producer：`/root/five_player_test_stage_preflight_sol`。仅完成离线机械依赖层，没有独立审批任何新 anchor、batch 或候选，没有连接活动 TEST/PROD 或本地克隆，也没有迁移、重启、apply、undo。

受保护包：`~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-main11-test-v2-signed-scope-anchor-rebind-pending-sol/`，目录0700、20文件0400（包含manifest）。原 producer／reviewer 包未改。

| 对象 | SHA-256 |
| --- | --- |
| 新 producer manifest 字节 | `917ca1e848218ba506165047aba4a8e58c29e1a948f639dc49e13d5a8d9348e6` |
| 输入五 scope 独立签审 manifest | `9c266a0ba00410c6bd4599e6eda773dad0b3f3692673603061fd312d9a7344be` |
| 输入 TEST v2 pending manifest | `bc0e99c9bc31df9efaac195efe82a40c01648544b012ceb365554cc22cfa9fa6` |
| `anchors.signed-scope.pending.json` 字节 | `0a7958db8d613a5fb535bf49c4b76517887265bbe4566cd9e76a9ad44561e760` |
| downstream draft bundle canonical | `9b9c75ff691bfe913e89aad08fc1f7ceaddca026d32d9270821092f533ef055f` |

## 实际机械结果

- 核对原 pending包35文件及 scope签审包5文件的 manifest 哈希与字节长度；五已签 scope 原字节复用，scope内容／4358槽位／4238albums、category、occurrence IDs均不变。
- 新生产五 pending anchors，scope指针引用真实完整已签记录SHA；三个说明字段中残留的更早scope SHA也同步替换。原名、原语、reading system、syllables、罗马读音、三来源记录及官方roster SHA均保持不变。去除旧 approval conclusion／reviewer信息；没有新签名。
- 仅生成25 research、6 batch、55 candidate依赖草案；25 `source_checks`、55显示字符串及六已签 language rules不变。hash指针机械连通至当前 pending anchors。25 research结构校验PASS；五 anchor 的实际校验均在“transliteration content lacks exact approval”拒绝。
- 新候选没有 `preimage_binding`：旧capture只作为历史输入保留，未将变化后的候选冒充已重新捕获／绑定。实际bundle `approved=0 / pending=25 / candidate_count=55 / write_ready=false`：其余30次音译在未签anchor／batch处阻塞，55次write checks均报告缺独立前像绑定；这是预期HOLD，不能误报完整55候选校验PASS。
- inventory仍绑定停止的独占克隆 `postgresql+psycopg2://postgres@127.0.0.1:55445/katrain_db`，format4 SHA仍为 `d5f376a980d12ec82ca18940b199295d6ce0f14b052261e9ce95afe58eb8af54`。未改端点、未宣称active TEST绑定或新鲜前像。

## 可复放与下一闸门

```sh
.venv/bin/python "$HOME/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-main11-test-v2-signed-scope-anchor-rebind-pending-sol/build.py" --output /tmp/kifu-five-test-v2-anchor-replay-new
```

实际新目录复放：manifest及全部文件共20项逐字节相同。外置0400回执 `.../china-professional-roster/five-cn-origin-main11-test-v2-signed-scope-anchor-rebind-pending-sol-replay.actual.json`，SHA `16961cc84b5751c0cdc6bd7ce866c37a9f3cf048abafb8e39b846ac927ab1fbd`。这是producer机械复放，不是独立签审。

**下一步仅为另一 reviewer 独立签审 `anchors.signed-scope.pending.json` 的五个新内容。** 签名会改变完整anchor SHA；后续producer必须据真实signed hashes重新生产25research、6batches及55candidates，batch生产时间晚于anchor审批，并真正重新捕获／绑定55目标前像，再走相应独立候选／完整batch审批。当前downstream drafts不能直接终签，也不代替后续validate/dry-run。

将来active TEST migration或写入仍需root另外决定，并使用真实active URL、新capture及该目标的新审批链；本包clone签名不能重标为active TEST。到上述五anchor签审闸门停止。
