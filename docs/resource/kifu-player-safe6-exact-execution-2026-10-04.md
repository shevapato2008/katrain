# 六名高频棋手精确关联：执行准备

独立逐槽决定 `kifu-player-safe6-independent-exact-slot-decision-astra-2026-10-04.json` SHA-256 `38bf557857dd70995d094347c3573230ca5b0adf6ffd0ffaa2691c2fd68c382e`，批准 601 个 NULL 玩家 FK，保留 180 个 HOLD。复用四名既有玩家的环境专属 ID，仅新建 `赵哲伦`、`陈嘉锐` 两个 canonical。不得改动别名、姓名、原始值暂存、SGF、来源、赛事或其他字段。

执行器逐行检查 777 张完整专辑、781 个待审槽位、777 条来源关联、全部玩家/别名/姓名目录、完整来源/赛事/届次目录和六条原始值暂存。最初 11:22 UTC 前像之后的 new33 第二批 10 条玩家 FK 变化已在独立决定中逐行冻结。已提交的中国阿含桐山杯批次只在本范围内改变专辑 103194、125109、134804 的 `event_id` 为 89，并增加赛事目录 ID 89。执行器固定双库 Ahan 计划、提交记录及完整后像，拒绝任何额外漂移。TEST/PROD 均分别捕获计划和校验 ID。

设置目标环境的 `KATRAIN_DATABASE_URL` 后，分别执行只读捕获：

```sh
python scripts/kifu_player_safe6_exact.py capture --environment test --plan /tmp/kifu-safe6-TEST-plan.json.gz
python scripts/kifu_player_safe6_exact.py capture --environment prod --plan /tmp/kifu-safe6-PROD-plan.json.gz
```

检查输出的计划 SHA 和完整快照。用各自 SHA 运行事务回滚演练：

```sh
python scripts/kifu_player_safe6_exact.py dry --environment test --plan /tmp/kifu-safe6-TEST-plan.json.gz --plan-sha256 <TEST_SHA>
python scripts/kifu_player_safe6_exact.py dry --environment prod --plan /tmp/kifu-safe6-PROD-plan.json.gz --plan-sha256 <PROD_SHA>
```

只有计划经过单独审批后，才以同一已批准 SHA 提交；每次提交后执行器独立读取并核对完整后像：

```sh
python scripts/kifu_player_safe6_exact.py apply --environment test --plan /tmp/kifu-safe6-TEST-plan.json.gz --plan-sha256 <TEST_SHA> --approved-plan-sha256 <TEST_SHA>
python scripts/kifu_player_safe6_exact.py apply --environment prod --plan /tmp/kifu-safe6-PROD-plan.json.gz --plan-sha256 <PROD_SHA> --approved-plan-sha256 <PROD_SHA>
```
