# 173,025 局棋谱棋手预处理：第一批中文暂定 ID

本批只做棋手原值分类、暂定中文人物 ID、精确原值映射和棋谱 FK 回填；不创建任何译名。全部 173,025 局、346,050 个黑白槽、7,251 种原始写法均在冻结 inventory 与全量候选清单内。原始 SGF 姓名不改。

## 选择规则与未决边界

对解析出 2–5 个纯汉字的姓名，以 OpenCC t2s 作候选字形键。仅单一 base、目录唯一 ID 或无 ID、现有 FK 不冲突、无同名区分后缀、无同名双方对局、排除 `1900-01-01` 占位日后跨度不超过 80 年、无名誉等另立目录 ID 的组进入自动批次。段位后缀只在同一明确 base 内拆分。当前 ID 若唯一且相符则保留；否则创建一个中文暂定 ID。逐条原值在 `review_metadata` 标为 `provisional_person_link`，`review_status` 保持 pending。仅原 FK 为 NULL 的槽被回填。

繁简候选相撞、同名区分、称号旧 ID、目录重复 ID、非人物或破损值保留在 `holds` 队列；这些不是已确认人物去重。目录中 `KataGoAI` 823/825、`KataGo` 824/826 是两组规范化重复的机器人，不进入人物自动合并；PROD 另有 23 个 canonical 含拉丁字母，需单列审查。前 20 个高频繁简候选见 [独立审查](kifu-player-top20-variant-identity-review-2026-10-04.md)。

| 环境 | 冻结旧目录 | 自动组 / 原值 | 暂定新 ID | 自动范围槽 | 本次新增 FK | 提交后 FK | 剩余 NULL 槽 |
|---|---:|---:|---:|---:|---:|---:|---:|
| TEST 实际 | 1,092 | 3,098 / 3,697 | 2,660 | 205,778 | 205,137 | 208,148 | 137,902 |
| PROD 实际 | 880 | 3,107 / 3,706 | 2,694 | 207,175 | 206,511 | 209,753 | 136,297 |

TEST 与 PROD 旧目录及原有 FK 不同，ID 编号不能互用。两边均先 dry-run，再提交首批；之后发现 152 个精确原值（344 槽）属于段位、队名、双人连写、称号或程序标签等，按 [修复清单](kifu-player-exact-rollback-152-2026-10-04.json) 逐项捕获前像、dry-run 和提交回滚。TEST 删除 151 个本批孤立 ID，保留旧 ID 1074；PROD 删除 152 个本批孤立 ID。两边逐行复核全部 173,025 局：原始黑白姓名均未改，TEST 有 205,137 个新增正确 FK，PROD 有 206,511 个新增正确 FK，其余槽均与冻结前像相同。现有原值 staging 覆盖和本批关联覆盖是不同指标；PROD 仍有 136,297 个 NULL 棋手槽待处理。

## 冻结输入与执行

- TEST inventory：`/tmp/kifu-five-test-inventory-post7.json.gz`，文件 SHA-256 `08007a829412fc585888cbbcadd2e0d1e2fd0080af3017f4a85019170689e52b`；TEST 批次 [JSON](kifu-player-auto-batch-test-2026-10-04.json)，SHA-256 `d01ff42b457520b1e3e326a4e206d4e7db7d69b859387228cd245c033604549c`。
- PROD inventory：`/tmp/kifu-five-prod-inventory-post7.json.gz`，文件 SHA-256 `dcc4f547ec196bbe850b79b6ce11a97dfda64e92343fcb2640dbd1aebaaad743`；PROD 批次 [JSON](kifu-player-auto-batch-prod-2026-10-04.json)，SHA-256 `84a3ec089e5ef3eb44d2391c644ee10d754c434811bbf23487e72575eec3bb22`。
- 首批历史批次的生成器与事务导入器：[kifu_player_auto.py](../../scripts/kifu_player_auto.py)。两个 JSON 是已执行、再按精确前像修复过的历史证据，不可在现行数据库上重放。现行 `build` 必须读取并钉住上述 152 条精确排除清单；`build` 需 `opencc-python-reimplemented`，`run` 不需要 OpenCC。

若需再处理剩余未决姓名，须从当前 TEST/PROD 数据库分别重新捕获 inventory 与目录，重新生成批次；不能复用首批旧前像。新批次的构建命令须包含精确排除清单：

```bash
python scripts/kifu_player_auto.py build \
  --inventory CURRENT-INVENTORY.json.gz --inventory-sha256 CURRENT-INVENTORY-SHA \
  --catalog CURRENT-CATALOG.json --catalog-sha256 CURRENT-CATALOG-SHA \
  --exclusions docs/resource/kifu-player-exact-rollback-152-2026-10-04.json \
  --exclusions-sha256 3ba7ccc09b3c683b40e487cf86d854eda48e437d71549ccc852ce1fb93a7da6c \
  --output NEXT-BATCH.json
```

`run` 默认 dry-run 并回滚；实际写入需先核对该批次的独立前像和计数。导入在同一事务内锁定相关表，核验全量棋谱原值和旧 FK 与目录前像，建立新 ID、写 raw 暂定映射、回填 NULL FK，并比较更新计数。精确回滚工具为 [kifu_player_repair.py](../../scripts/kifu_player_repair.py)，两库已执行计划分别见 [TEST](kifu-player-repair-test-2026-10-04.json) 与 [PROD](kifu-player-repair-prod-2026-10-04.json)。

测试：`pytest -q tests/web_ui/test_kifu_catalog_player_auto.py tests/web_ui/test_kifu_catalog_player_repair.py tests/web_ui/test_kifu_catalog_preprocess_players.py`。未决组和翻译是后续独立工作；不能把本批暂定 ID 数称为已经核实的多语言译名数。
