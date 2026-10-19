# 棋手预处理：非汉字名次 161–180 修正版双库预演

**后续状态：修正版已按独立审查批准的冻结计划写入两库并全量核验，
见 [执行记录](kifu-player-nonhan-ranks-161-180-corrected17-application-2026-10-04.md)。**

2026-10-04 修正了旧白名单中 `Miyasaka Shinji` 的目标中文主名：日本棋院
[90 周年官方照片说明](https://www.nihonkiin.or.jp/special/90anniversary/message/index.html)
列“宮坂寀二”，因此使用“宫坂寀二”，保留该 exact raw 的 72 席。
旧白名单及旧双库计划保留为审查记录，**不再用于执行**。新的
`kifu-player-nonhan-ranks-161-180-corrected17-exact-allowlist-2026-10-04.json`
SHA-256 为 `5a19bb0c510cb35793e7691011bc3b792e0ea32f1ddb4a520580d96645f6adfe`。

| 原文 | 中文目标 | 席位 | TEST 目标 ID | PROD 目标 ID |
| --- | --- | ---: | ---: | ---: |
| `Tamura Hoju` | 本因坊秀哉 | 80 | 10619 | 4833 |
| `Koyama Shizuo` | 小山镇男 | 79 | 10201 | 4410 |
| `Fukui Susumu` | 福井进 | 77 | 新建 | 新建 |
| `JangSuYeong` | 张秀英 | 77 | 10457 | 4667 |
| `Kawamura Masamichi` | 川村匡迪 | 75 | 10358 | 4568 |
| `Ito Hiroshi` | 伊藤弘 | 74 | 9679 | 3882 |
| `Tainaka Shin` | 鲷中新 | 74 | 新建 | 新建 |
| `Miyasaka Shinji` | 宫坂寀二 | 72 | 新建 | 新建 |
| `HaChanSeok` | 河灿锡 | 70 | 新建 | 新建 |
| `HashimotoUtaro` | 桥本宇太郎 | 70 | 12341 | 6577 |
| `Oka Nobumitsu` | 冈信光 | 70 | 9779 | 3982 |
| `Sakai Yasujiro` | 酒井安次郎 | 70 | 新建 | 新建 |
| `Awaji Shuzo` | 淡路修三 | 69 | 592 | 591 |
| `Karigane Junichi` | 雁金准一 | 69 | 12157 | 6391 |
| `KimSu-chang` | 金秀壮 | 69 | 11979 | 6213 |
| `SeoNeung-uk` | 徐能旭 | 68 | 10504 | 4714 |
| `Asano Hideaki` | 浅野英昭 | 67 | 11169 | 5394 |

TEST 冻结计划为 `kifu-player-nonhan-ranks-161-180-corrected17-plan-test-2026-10-04.json.gz`，
SHA-256 `7b4e9380e13469f4fec93ab37e4bdfcdfc846c3095beef7000319bf270576e87`；
PROD 为 `kifu-player-nonhan-ranks-161-180-corrected17-plan-prod-2026-10-04.json.gz`，
SHA-256 `2d9940463f7e5794f7f4f2c3afb86a82781f3a8efae4124821db459c9065182c`。
两库各 17 个 exact raw、1,230 席（黑 689／白 541）、拟建 5 ID。两端
fresh capture 与事务 dry-run 均通过并回滚，输入、目录、FK、原文审核行与完整
来源范围的实时前像和冻结清单一致。聚焦测试 11/11 通过。

回滚后只读复查：TEST 仍为 261,536 席已连、3,781 棋手 ID；PROD 仍为
263,141 席已连、3,603 ID。修正版 1,230 席及另外暂缓的 `SeoBongSoo`、
`Fujisawa Kuranosuke`、`YangChae-ho` 全部 FK 为空；20 个原文审核行
仍为 `pending` 且元数据为空，5 个拟建中文主名尚不在目录。

**尚未正式写入；等待修正版白名单和计划的独立审查。**
