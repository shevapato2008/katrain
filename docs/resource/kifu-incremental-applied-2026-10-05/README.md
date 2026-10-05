# 已实际写入的增量名称与来源页面

每个压缩 JSON 保存具体环境的已签 bundle、source registry、研究证据、真实 dry-run/apply/verify 回执；只收录两库已经提交并核对名称的批次，不把 pending 研究计为交付。新棋手批还包含 authoritative_pages 同步回执。

首批来源页面迁移另存 `player-pages-{TEST,PROD}.json.gz`：包括预览、提交后的前后值及重复预览的零变更结果。页面字段只追加已批准证据的正面来源、官方身份锚点和明确同人档案桥；URL 精确去重，已有手工元数据保留。

`kifu_players.authoritative_pages` 是 JSON 数组，每项含 `url`、`source_id`、`language`、`role`、`evidence_ids`。`role` 表示登记的来源类别，维基或专业资料不会被标成官方。后续棋手主页可按棋手 ID 使用这些页面及现有棋谱 FK，不需要再次找源；生平和名局介绍尚未开发。

统计网页是带时间的正式库快照；五语齐全指实体名称已独立批准并写库，完整覆盖指棋局双方棋手及赛事类型均具备五语名称。未关联实体的原文展示、中文首遍和未完成语言不计入这一覆盖率。
