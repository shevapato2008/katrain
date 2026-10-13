# 本因坊 1,617 盘生产前像核对（2026-10-02）

在 `ucloud-v100` 的正式数据库 `katrain_prod_20260725` 中，以 `REPEATABLE READ READ ONLY` 事务读取 `event ~ '^[0-9]+(st|nd|rd|th) Honinbo$'` 的棋局，未执行写入。查询返回 **1,617** 个不同棋局 ID；其集合与受控 `kifu-name-inventory-prod-v2-20261002.json.gz` 的同一精确组完全一致。逐盘比较 `id`、重复标记、原始黑白棋手、原始赛事、轮次、段位、日期及现有黑白棋手和赛事关联 ID，全部相同；这 1,617 盘的 `event_id` 仍均为空。

在同一只读查询中，PostgreSQL 15 的 `sha256(convert_to(sgf_content, 'UTF8'))` 为每盘计算正式库 SGF 正文摘要。逐盘前像和摘要存于仓库外受控文件 `/Users/fan/.local/share/kifu-name-audit/2026-10-02/honinbo-1617-current-prod-preimages/album-preimages.jsonl`；目录权限 `0700`、文件权限 `0600`。该 JSONL 文件字节 SHA-256 为 `4a58e70039eaf623aa6ac5d6b33c68b4462954868fb985917ff0a89bb27038e7`，捕获结束于 `2026-10-02T13:40:47Z`。棋局 ID 范围 `24525–172954`。

此检查只证明这些字段在查询时仍与冻结清单一致，并提供每盘正式库 SGF 摘要。它没有核对所有来源链接或翻译前像，没有分配赛事 ID，也没有批准姓名候选或数据库写入。后续可写批次仍需纳入已审十一语名称、正式库完整目录快照、逐原文身份范围签名，并在写入前重新核对当前前像。
