# 中国阿含桐山杯：精确赛事类型执行准备

独立决定 `kifu-event-china-ahan-independent-decision-astra-2026-10-04.json` 固定 SHA-256 `53c88b3efb87e0d331aaa27a9a35512129bc5d6896c378d1f0da4f6769f1f891`。仅批准 793 条 `event_id=NULL` → 新建的 `中国阿含桐山杯` 类型 ID；8 条本批 HOLD 和 4,265 条既有 HOLD 的 `event_id/event_edition_id` 维持 NULL。全部 801 条 `event_edition_id` 维持 NULL。

冻结快照分别为 TEST `faad5227926d3b94adb82c0d45f300b8fba44be0e14adb7ed5c695dd3767bc6d`、PROD `c0c7741efd5fd3ecd43d701165cce578ad69bd40a5b78b9b9bbbd8010a398ffa`。之后 new33 第二批玩家关联在本范围内精确改变 24 条 FK；执行器用双环境已提交计划、独立逐槽决定和提交记录固定这 24 个后像，其余专辑字段、SGF、来源关联、完整赛事目录/别名/届次、来源目录和已引用玩家条目仍逐行核对。TEST/PROD 的新玩家 ID 分别从 12588/6819 开始，依决定中的 16 名顺序分配；运行时核对精确 ID 与 canonical。其他漂移拒绝捕获。

本文件仅提供操作步骤；代码不自动连接数据库。每个环境单独设置 `KATRAIN_DATABASE_URL` 后执行：

```sh
python scripts/kifu_event_china_ahan_exact.py capture --environment test --plan /tmp/kifu-ahan-TEST-plan.json.gz
python scripts/kifu_event_china_ahan_exact.py capture --environment prod --plan /tmp/kifu-ahan-PROD-plan.json.gz
```

捕获输出各自计划字节 SHA。分别审阅两份计划（包括 793/8/4265 计数、新33 后像和完整目录）后，按各自 SHA 做回滚演练：

```sh
python scripts/kifu_event_china_ahan_exact.py dry --environment test --plan /tmp/kifu-ahan-TEST-plan.json.gz --plan-sha256 <TEST_SHA>
python scripts/kifu_event_china_ahan_exact.py dry --environment prod --plan /tmp/kifu-ahan-PROD-plan.json.gz --plan-sha256 <PROD_SHA>
```

经单独批准后才运行提交，分别将已批准的相同计划 SHA 同时传给两个参数：

```sh
python scripts/kifu_event_china_ahan_exact.py apply --environment test --plan /tmp/kifu-ahan-TEST-plan.json.gz --plan-sha256 <TEST_SHA> --approved-plan-sha256 <TEST_SHA>
python scripts/kifu_event_china_ahan_exact.py apply --environment prod --plan /tmp/kifu-ahan-PROD-plan.json.gz --plan-sha256 <PROD_SHA> --approved-plan-sha256 <PROD_SHA>
```

演练在事务内验证完整后像、回滚，再独立读取前像；提交在事务内核对后像、提交，再独立读取提交后像。两次均要求全范围一致。
