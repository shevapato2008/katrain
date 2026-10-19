# 全库SGF补充赛事字段提取（只读）

当前生产快照未关联赛事、raw category=unclassified_pending 共 **62675局**，全部读取解析成功、0错误。PROD事务 `REPEATABLE READ READ ONLY`，结束 `ROLLBACK`。只生成候选，未自动批准、写库、翻译或去重。

| 指标 | 数量 |
| --- | ---: |
| 根EV存在 | 3933 |
| GN含多个值 | 47606 |
| GN后续值/GC含不同于album.event的候选 | 15016（23.96%） |
| 候选值次数 | 15077 |
| distinct精确候选文本 | 8108 |
| 补充候选结构core不同的棋局 | 14498 |
| EV原文字段与album.event不同 | 0 |

core不同只是现有结构提取规则的字符串差异，不是已证明赛事身份矛盾。15016局是有补充文本，不能报告成15016局已确认真实赛事。候选包括`Black wins the ko`等评论，全部保持UNREVIEWED。

GN来源候选14342次，GC来源15016次，同一个文本同时来自GN/GC有14281次；这些都来自同一份SGF，不能当独立证据。13个候选含换行，3个长度超过256字符（最长562），保留为待审文本。

## 实现与负载

程序只读当前未关联且raw类别待分类的棋局，以album_id排序、单个服务端流式游标、250行一批，每批暂停50ms。120秒statement_timeout与2秒lock_timeout限制单次数据库等待。原SGF在程序内只截取并解析根节点，不构建全部棋谱落子树。生产容器尚无当前name_structure模块，因此远端仅提取根属性与精确原文差异，Mac本地用仓库event-components-v5补结构core比较；没有部署或修改生产应用。

100行小批0.169秒，随后全量62675行72.553秒。此数为采集程序墙钟时间（包含节流），不是数据库CPU测量。一次有序SELECT、无逐局SQL；没有采集CPU峰值，因此不额外声称零负载。

聚焦验证4项通过；30份长尾真实SGF的裁剪根属性与完整SGF parser结果逐项完全相同，其中17份产生补充文本。

## 可运行命令

在仓库根目录：

```sh
ssh ucloud-v100 'docker exec -i katrain-ucloud-katrain-web-1 /opt/venv/bin/python - --limit 100 --batch-size 100 --pause-ms 50' < scripts/extract_kifu_sgf_event_candidates.py > small.jsonl
```

确认manifest的read_only=on及summary的parse_error、complete、ROLLBACK后，全量流式捕获：

```sh
set -o pipefail
ssh ucloud-v100 'docker exec -i katrain-ucloud-katrain-web-1 /opt/venv/bin/python - --limit 1000000 --batch-size 250 --pause-ms 50' < scripts/extract_kifu_sgf_event_candidates.py | gzip -n > full.jsonl.gz
PYTHONPATH=. python scripts/summarize_kifu_sgf_event_candidates.py full.jsonl.gz enriched.jsonl.gz report.json
```

数据库URL仅由容器内KATRAIN_DATABASE_URL读取，不传参数、不输出。全量上限1000000高于本次范围，不改变SQL授权边界。本次输入/输出文件和代码SHA在JSON与.sha256清单，可离线重复本地补结构和聚合。

## 恢复方式

每段JSONL先写manifest、随后有序album或parse_error、最后完整summary。缺末尾summary即未完成，本地汇总器拒绝发出完整报告。已接收完整记录可使用`--after-id 最后完整album_id`另建新段继续；必须保留新的事务快照和独立SHA。生产内容可能变化，跨段不能冒称同一快照，也不得覆盖旧输出或直接拼成一个已验收批次。可离线按album_id核对分段唯一性与覆盖后另发汇总。

## 后续归并建议

优先调查大量补充具名赛事：历史全国团体赛、2007全国段位赛各轮、2004/2005韩国联赛、中国围甲、日本天元/十段/本因坊等。对2007段位赛“第五轮半决赛”等可疑语义保留原文冲突，专业来源未核对前不统一轮次。

先依据补充文本生成 exact album_id→候选赛事与届次/年份/轮次的只读提案，用专业/官方来源核对，再提交类型审查。原始EV/GN/GC全部保留，任何归并都不能仅凭core相同、简称、相同年份或同棋手来批准，也不能由这些字段批准棋谱去重。日期、黑白、结果冲突分别HOLD。

完整精确候选分组与core差异分组见JSON；逐局映射与所有根字段见 enriched JSONL.gz。两份压缩逐局artifact约6.4MB和6.9MB，JSON报告约2MB，不需要重复查询生产即可继续研究。
