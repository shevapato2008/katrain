# Hoensha 来源说明分类复核

2026-10-03，审核者 `/root`。对 Luna 冻结的 `Hoensha game` 候选包，独立核对 595 个精确原始赛事槽位：578 个 CWI `Hoensha` 目录路径，加上[已由独立 Astra 逐谱核对的 17 个 `Honinbo_Shuho` 路径](kifu-name-hoensha-17-scope-independent-decision-astra-2026-10-03.md)。原始 `EV` 均为 `Hoensha game`，`event_id` 均为空，候选没有赛事实体、别名或棋局关联提案。

**分类 PASS：**批准这 595 个固定槽位使用 `archive_source_description` 类别，表述方圆社历史棋谱的来源语境；不把它认定为同一正式赛事或某届比赛。把受保护候选的完整来源行与冻结 inventory 逐行比对，并重新读取 CWI 和日本棋院留存正文，核验字节 SHA-256、原文摘录及登记来源。`validate_archive_description_scope(..., check_files=True)` 对已签分类和原库存通过。

受保护分类记录：`~/.local/share/kifu-name-audit/2026-10-03/hoensha-archive-description-v1-category-review-root/category-review.approved.json`，SHA-256 `0d3ebc32f292630b9964a5d3998099894a90f4bef3935ea48d9553f3e2b64872`；完整 manifest SHA-256 `0585403708f5fb87259f27b7b625d171f82e14b470ec5b1573b039dfdd255c95`；已审 scope 规范哈希 `d10c54be5c4e0bfe13f1f6fa9480549c0f29c2fa55ed36e222f45b114d820b44`。原生产者包字节哈希仍为 `c64379e014a2c7d3958812d29e7133ad6642fc3c810101101df46d2f32b45076`。

此次只批准分类与精确 595 行范围。十一语模板、名称候选、目标库当前前像和最终导入包仍需后续绑定、独立复核及隔离演练；正式和测试数据库均未写入。
