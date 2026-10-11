# 三人 exact canonical 棋手 FK：执行前捕获与 dry

本执行器只按独立审查的精确 `(album_id, side)` 清单处理周鹤洋、赵善津、工藤纪夫：每库 1,529 个 NULL 槽；580 个 HOLD 槽保持不变。审查文件 SHA、候选／HOLD 清单 SHA 和目标 ID 按环境固定。执行器不改 raw staging、目录、别名、显示名、原谱或赛事字段。

先由审核人分别设置 TEST／PROD 的 `KATRAIN_DATABASE_URL`，**不要混用计划**。以下命令中的计划文件路径可自定，建议置于受控非公开目录。`capture` 只读；`dry` 在同一事务中更新后完整核对并回滚。两个命令均须逐库审阅输出和压缩计划 SHA。最终 `apply` 需单独输入已经审核的相同计划 SHA；本文件不授权执行 `apply`。

```sh
python scripts/kifu_player_canonical_three.py capture --environment test --plan /tmp/kifu-player-three-test-plan.json.gz
python scripts/kifu_player_canonical_three.py dry --environment test --plan /tmp/kifu-player-three-test-plan.json.gz --plan-sha256 <capture 输出的 SHA>

python scripts/kifu_player_canonical_three.py capture --environment prod --plan /tmp/kifu-player-three-prod-plan.json.gz
python scripts/kifu_player_canonical_three.py dry --environment prod --plan /tmp/kifu-player-three-prod-plan.json.gz --plan-sha256 <capture 输出的 SHA>
```

捕获时对 2,105 盘当前整行（原谱以 SHA 锁定）、三人目录／名称／别名、raw staging、来源关联逐项核对。三人姓名的 NFKC／繁简／casefold 碰撞检查覆盖全目录、所有 alias 及旧 cn／tw／jp 名称。冻结原像之后只接受已应用且 SHA 固定的计划列出的变化：mixed11 在 `7189、8956、61465、66226、66241、132947、134184、134220` 的 8 个对手 FK，日本大赛批次的 47 个 `event_id`，以及[独立赛事决定](kifu-event-next-scope-independent-decision-astra-2026-10-04.json)和[跨库计划](kifu-event-next-scope-compared-plan-2026-10-04.json)与本范围相交的 9 个 `event_id` NULL→75。后 9 个必须仍指向目录 ID 75 `中日围棋对抗赛`。每个值必须等于对应计划的批准后像；任意其他 ID、FK 或赛事类型均拒绝。这些差异均记录为新的当前计划前像，不会写入本批。其他字段或成员变化使捕获失败。`dry` 在表锁内重验计划前像、只做批准槽的 NULL→目标 ID CAS、核对完整结果并回滚。回滚或提交后，执行器另开只读事务再核对全部范围、目录、来源及 HOLD。

新增赛事 9 盘中，`36687/黑、36688/白、36755/白、65378/白、65387/黑、66039/白、66058/白` 这 7 个棋手槽仍属原审 HOLD，必须保持 NULL；另 2 个棋手槽仅按原三人批准清单处理。

另按[next15 独立后续变化决定](kifu-player-canonical-three-next15-rebase-independent-decision-2026-10-04.json)，执行器只接受与本范围相交的 19 个**对手**棋手 FK 精确 NULL→目标 ID 后像。TEST／PROD 目标 ID 分别固定，并验证五个目录 ID 与现存 canonical（包括 `溝上知親`、`岛村俊宏`）。这些变化与前述 64 个单元格无重叠；总计允许 83 个单元格（56 个赛事 FK、27 个对手棋手 FK），涉及 81 盘。此 19 盘中三人原审的 4 个 HOLD 槽依旧 NULL；三人批次仍只写原批准的 1,529 槽。

审核人若决定应用，在相同数据库、相同计划仍有效时执行：

```sh
python scripts/kifu_player_canonical_three.py apply --environment test --plan /tmp/kifu-player-three-test-plan.json.gz --plan-sha256 <已审核 SHA> --approved-plan-sha256 <同一 SHA>
python scripts/kifu_player_canonical_three.py apply --environment prod --plan /tmp/kifu-player-three-prod-plan.json.gz --plan-sha256 <已审核 SHA> --approved-plan-sha256 <同一 SHA>
```

计划前像一旦变化，`dry`／`apply` 会失败；应重新捕获并重新审核 SHA，不应跳过检查。
