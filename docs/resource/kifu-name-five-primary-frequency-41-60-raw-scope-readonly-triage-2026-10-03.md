# 五主语言 95 个来源姓名对应的原始棋谱槽位：只读分流

2026-10-03。按[已独立核实的 19 人 × 五主语言来源姓名](kifu-name-five-primary-frequency-41-60-95-aux-span-corrected-independent-review-sol-2026-10-03.md)，在冻结的正式库副本清单中精确匹配 19 种原始姓名，得到 **17,241 个黑白棋手槽位**。这些槽位的 `black_player_id` / `white_player_id` 全为 NULL；来源 key 均为 `19x19`，其中一盘有三个同 key 来源链接。18 个槽位的日期是 `1900-01-01` 占位值；其余有年份的槽位未出现早于来源人物出生年的值。此结果只是批次分流，不能证明每个同名原值都属于该人物。

受控只读材料：`~/.local/share/kifu-name-audit/2026-10-03/five-primary-41-60-raw-scope-readonly-root/`。`scope-readonly.json.gz` 保存精确 album ID、黑白方、原值、日期、段位、现有 FK 与来源链接，文件 SHA-256 `7c0603ae67d5b4acd5ca333eee44d523af2dd8994b75ad951fd56f357c79f849`；`summary.json` SHA-256 `1ea87c148be31ecf0336fac0ff231906e54e5f1abd89dfb93dfc111b19efd84b`。输入库存内容 SHA-256 `f4907ffbe70d62b4b77f6d3bf5ba7ed789f2685f46eff7ffdfe080f2abc4bab1`。

下一步独立审核每个原值的有限适用范围与异常槽位，确定可显示的精确 `(album_id, side)` 集合；五主语言的来源姓名签署不能自动变成人物关联、十一语覆盖或写入批准。副本源自先前正式库快照，部署前还需重取实际目标前像。此次无数据库写入。
