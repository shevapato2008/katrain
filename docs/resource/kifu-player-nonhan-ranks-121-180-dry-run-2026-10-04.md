# 棋手预处理：非汉字名次 121–180 三批双库预演

**后续状态：121–140、141–160 已分别按独立审查后的冻结计划写入并全量核验，
见 [121–140 执行记录](kifu-player-nonhan-ranks-121-140-application-2026-10-04.md)
和 [141–160 执行记录](kifu-player-nonhan-ranks-141-160-application-2026-10-04.md)。
本页 161–180 的旧白名单和计划已因 `Miyasaka Shinji` 字形错误作废；
请用 [修正版 17 项预演](kifu-player-nonhan-ranks-161-180-corrected17-dry-run-2026-10-04.md)。**

2026-10-04 对已审精确白名单分别从 TEST、PROD 实时目录捕获前像，逐批执行
建目录 ID、关联棋局 FK、更新原文审核行的事务预演，核对影响行数后回滚。
**本记录未执行正式写入；每批仍待独立审查后才能 apply。**

| 名次 | 白名单 SHA-256 | exact raw／席位 | 黑／白 | 复用／拟建 ID | TEST 计划 SHA-256 | PROD 计划 SHA-256 |
| --- | --- | ---: | ---: | ---: | --- | --- |
| 121–140 | `81093337d3ae4ccc2657bdccc795538283fa8e9f2d6795619dad80398abfe9f5` | 16／1,896 | 1,001／895 | 10／6 | `47919246e265e43e6b0d5ac8024ed97724a3bf8284619847302e52c06f65b0f9` | `172095c37aef0c54f4e89a56d3409ebabc1ab7dd05be2814b415fbe88ae4c824` |
| 141–160 | `9c9df1b7e1672f1e63a626b74ec1da3a7d3a38a5aa92ba2ce41a8a58e92e95bb` | 17／1,601 | 811／790 | 12／5 | `996cbc891a5c4496362613418b15b31ee98d57d7861d90c3b883cd044a1493f6` | `3e6eaf4b69affb36e57b5d4cd485b317022b857ee317408c3840e012dfc874bb` |
| 161–180 | `77e62a92f9eeac0a8c98880a1fca073b3c27b16a68bc095f5d29e4945cedafd3` | 17／1,230 | 689／541 | 12／5 | `2162f7001d7fd3444ce9bbf28589ab1dfdfc3be455e60ba256faf4c2ede111a8` | `8880140ea323d061e59c641ae2ed5d29b29d05daf728bc63433e6f2641de104a` |

白名单为 `kifu-player-nonhan-ranks-{121-140,141-160,161-180}-exact-allowlist-2026-10-04.json`；
环境专属计划为同前缀的 `-plan-{test,prod}-2026-10-04.json.gz`。
导入器 `scripts/kifu_player_nonhan_batch.py` 使用冻结 inventory SHA-256
`dcc4f547ec196bbe850b79b6ce11a97dfda64e92343fcb2640dbd1aebaaad743`。
捕获与预演均检查 exact raw、盘号、黑白位置、日期、对手原文、重复标记、
完整来源链接、现有 FK、原文审核前像、两环境目标 ID 及中文主名；所有复用 ID
的实时中文主名均与审定目标一致。聚焦测试 `tests/web_ui/test_kifu_catalog_player_nonhan.py`
为 10/10 通过。

以下原文不在白名单，保持暂缓：

| 名次 | 暂缓原文（席位） | 合计 |
| --- | --- | ---: |
| 121–140 | `Fujisawa Shuko`（141）、`Inagaki Koichi`（135）、`Yasui Sanchi`（123）、`Shuwa`（122） | 521 |
| 141–160 | `Sekiyama Riichi`（86）、`Takahashi Shigeyuki`（85）、`Kubouchi Shuchi`（83） | 254 |
| 161–180 | `SeoBongSoo`（83）、`Fujisawa Kuranosuke`（81）、`YangChae-ho`（74） | 238 |

`Yasui Sanchi` 等代际同名、`Fujisawa Shuko` 等目录冲突继续排除；
`Kubouchi Shuchi` 与本批获准的 `KubouchiShuchi` 同人，尚未建立第二个 ID。
`Ishii Senji` 是有独立身份证据的二世中川龟三郎原名，与此前暂缓的
`Nakagawa Kamesaburo` 混代原文分开处理。三个批次合计候选 50 个 exact raw、
4,727 个席位和 16 个拟建中文 ID，另有 10 个原文／1,013 席位继续暂缓。

预演后的只读复查：TEST 仍为 3,770 棋手 ID、258,039／346,050 席位已连；
PROD 仍为 3,592 棋手 ID、259,644／346,050 席位已连。两库各 173,025 盘；
50 个候选原文的 4,727 席位和 10 个暂缓原文的 FK 全为空，60 个原文审核行
均为 `pending` 且元数据为空，16 个拟建中文主名均未出现于目录。
