# 日本10人两库实时capture及事务回滚预演

TEST / PROD均完成实时capture和真实SQL事务回滚dry-run，`applied=false`；每库3,035候选槽、20hold、10原文。没有apply，冻结review没有修改。

复用 `/tmp/highfreq-next6-import` 的 models_db、catalog_player_second/family/exact，复制到独立 `/tmp/jpnext10-import` 后加载。runner仅允许capture/dry，调用 `run_exact_plan(apply=False)`，核对review SHA、inventory SHA和current_database。TEST数据库 `katrain_db`；PROD数据库 `katrain_prod_20260725`。

事务内获取相关表锁、复核整份前像、按exact album ID/side/raw/date/NULL做比较并更新3,035槽，再核验20hold槽和目录前像，包括传统目录别名/显示名/证据，最后ROLLBACK。两个环境回滚后再次capture，计划SHA与预演前完全相同，证明持久状态未改。

19占位日期hold及杉内雅男1934年1hold精确匹配冻结review；7个传统目录ID均进入plan.catalog。既有FK保护0槽，因为目标10个exact raw全部当前未关联。

|库|计划文件|plan SHA-256|
|---|---|---|
|TEST|[计划](./kifu-player-japanese-next10-TEST-plan-2026-10-04.json.gz)|`9c79b893e3e22abf2a9449a7fbdb9725003240840ba556d8726f3ea701b2c39b`|
|PROD|[计划](./kifu-player-japanese-next10-PROD-plan-2026-10-04.json.gz)|`a62d627332a839e3149994fb730ec448e4473aef68cd33581cd9889a62118f97`|

对应capture、dry及postrollback-capture日志均保存为同前缀JSON；汇总 [verification](./kifu-player-japanese-next10-dry-verification-2026-10-04.json)。执行条件仍需独立审核和明确批准；预演成功本身不是apply授权。
