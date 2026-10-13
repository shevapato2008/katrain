# TEST 韩文名人战：只读诊断

2026-10-05；`/root/hide250_review_astra`。未改应用代码或数据库。

**结论：搜索正确，差异在渐进展示的结构化原文回退。** TEST `q=한국 명인전&lang=ko&page_size=100` 返回 **926** 局；首 100 项的 `display_event` 全部仍是带届数／轮次的原始中文，因而运行时检查失败在 `all(display)`，不是 `total > 0`。先前误指的吴清源／Go Seigen 查询已确认 TEST 两者各 1023，首 100 IDs 一致，不继续扩查。

## 运行时证据

当前 TEST image `katrain-web:kifu-event-translation-test-20261005`；`KIFU_STRICT_NAMES` 实际为 false。数据库诊断执行 `REPEATABLE READ` 和 PostgreSQL `read_only=on`。脚本及输出：`/tmp/kifu-myeongin-readonly-diagnose.py`、`/tmp/kifu-test-myeongin-readonly-diagnose.json`。

- `strict_matching_names('한국 명인전')` = 唯一赛事 ID **49**；legacy exact/partial 别名均为空。列表进入 `event_id == 49` 的精确分支，可见棋谱数 **926**，没有模糊搜索或身份歧义。
- 名称 ID **188**、证据 ID **425**：`ko`、`한국 명인전`、`translated`、revision 1、`event-title-translation-v1`；owner、候选与独立 approved 证据相符。
- `strict_display_maps` 已正确返回 `{49: '한국 명인전'}`，证明名称读取与新决策过滤正确。
- 棋谱 **21446** 的 event_id=49，原文为 `48届韩国名人战决赛3番棋2局0-1`。`structure_event` 识别 `48届` 的 edition component；raw owner **67031** 仍 pending，未有 raw 名称。
- `resolve_strict_display` 第859行因此将缺少 exact raw 的默认显示设为 `None`。非严格模式下 `display_maps` 又只读取无 evidence 的旧名称（984–987行），排除了刚批准的主名称，最终 `fallback_names[2]` 回到原文。
- PROD legacy `_summary` 第306行直接使用已关联赛事主名称，因此同一查询的显示不同。主线程已验证 PROD total=926。

## 最小修正建议

在 `resolve_strict_display` 的普通 event 分支，仅当传入非严格模式的 `fallback_names` 时，允许已批准的 `event_name` 作为结构化原文缺少 exact raw 名称时的默认显示。已有 exact raw 显示继续优先；上游 obscured GN、formal/Oteai 专用分支保持现有处理。原始 event 字段仍保留完整届数与轮次。

严格模式及 `strict_slot_approvals` 的完整原文证据要求不变；不改搜索、别名、FK、候选身份或数据。聚焦验证一个 translated 主名称＋带 edition 的真实形态、strict 模式仍不授予 raw 槽位即可。尚未实施建议。
