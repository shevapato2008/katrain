# 下一批赛事候选：中日交流／日本专业十杰（只读）

捕获：2026-10-04 PROD ucloud-v100 / katrain_prod_20260725，只执行 SELECT；原始数据未写入。详细 exact album 行在同目录 JSON，每行含 id,event,date_sort,sgf_md5,source_path，可作为 ID、日期和 SGF 前像门禁。

## 候选范围

|组|状态|盘数|exact raw|日期|建议|
|---|---|---:|---:|---|---|
|中日围棋对抗／Japan-China Go Exchange|candidate|692|86|1960-06-07–1991-06-01|可作为一个中日定期交流赛事类型；届次仍按明确期次/日期人工复核|
|日本专业十杰／Pro Best Ten|candidate, Astra identity review|105|89|1963-09-12–1975-05-01|日本专业十杰战 identity likely；English ProBestTenTournament/Final needs source confirmation|
|日本 Pro-Ama/Asahi Best Ten|hold|10|9|1968-07-15–1975-07-13|职业—业余赛与专业十杰分开|
|韩国 SK New Stars Best Ten|hold|2|2|2000-05-03–2001-08-17|韩国赛事，不并入日本类型|
|AsahiProBestTen,12th|hold|1|1|1975-02-13|名称不足以在 Pro-Ama 与专业十杰之间判定，保留待审|
|Nihon Ki-in #1 / Number One Position|hold, Astra identity review|386|16|1900-01-01–1972-09-27|既有审核已指出 event 45/46 歧义；本包不猜测归属|

## 中日范围排除

核心候选谓词排除 exact raw 中含特别、NEC、魅力湘西、新星/NewStars、三番棋、快棋、青年棋手的记录；这些是特别赛、冠名赛、青年组或不同赛制，应单独审查。没有把裸 generic 段位赛、个人赛、团体赛纳入（已有 generic 决策与全国个人／团体批次）。

## 门禁

执行前逐行断言：PROD 当前 event_id IS NULL；id,event,date_sort,source_path 等于 JSON；读取 SGF 后重新计算 md5(sgf_content) 等于 sgf_md5。不得按 event 前缀扩大集合。TEST 需用同一 exact raw 谓词重新捕获并比较 ID 集后再做计划。

## 待 Astra 决定

1. 是否把中文／英文中日交流名称统一为一个赛事类型；其中 Japan-China Go Exchange 跨 1960–1986，中文无届次值跨 1973–1991，日期吻合但需赛事史来源确认。
2. 是否把 ProBestTenTournament,Nth、Nth Pro Best Ten Final 与中文 专业十杰战 统一为日本专业十杰；Pro-Ama 与韩国 New Stars 明确保持 hold。
3. Nihon Ki-in #1 的 386 盘不能按简称猜 event 45/46，继续 hold。

JSON SHA-256 should be recorded after review; this artifact is candidate-only and contains no apply payload.
