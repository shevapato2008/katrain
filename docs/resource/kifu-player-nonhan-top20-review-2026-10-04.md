# 非汉字棋手原值前 20 名身份审查（2026-10-04）

TEST 与 PROD 各用 `REPEATABLE READ READ ONLY` 事务查询当前未关联槽位；两库前 100 个非汉字原值排名及槽位数一致。目标 ID 来自同日只读目录快照，执行时须以新快照重新绑定。只审 exact raw，不按音译模糊关联。

占位值 `Unknown` 1,198、`Black` 1,158、`White` 1,158 槽排除。前 20 个真人原值合计 7,117 槽；17 个原值、6,012 槽通过姓名身份审查，3 个原值、1,105 槽因目录重复或错字暂缓。

| exact raw | 未关联槽 | 中文规范名 | PROD ID / TEST ID | 决定 |
|---|---:|---|---|---|
| `Hane Yasumasa` | 524 | 羽根泰正 | 5737 / 11506 | 可列入精确 raw 白名单 |
| `Shinohara Masami` | 388 | 筱原正美 | 5706 / 11477 | 可列入精确 raw 白名单 |
| `Iwamoto Kaoru` | 384 | 岩本薰 | 暂缓 | 暂缓 |
| `Maeda Nobuaki` | 367 | 前田陈尔 | 暂缓 | 暂缓 |
| `Kudo Norio` | 366 | 工藤纪夫 | 347 / 348 | 可列入精确 raw 白名单 |
| `Nakamura Yutaro` | 360 | 中村勇太郎 | 3793 / 9591 | 可列入精确 raw 白名单 |
| `Tamura Hoju (later Shusai)` | 357 | 本因坊秀哉 | 4833 / 10619 | 可列入精确 raw 白名单 |
| `Hashimoto Utaro` | 356 | 桥本宇太郎 | 新建 / 新建 | 可列入精确 raw 白名单 |
| `Fujisawa Hosai` | 354 | 藤泽朋斋 | 暂缓 | 暂缓 |
| `Chino Tadahiko` | 349 | 茅野直彦 | 5798 / 11567 | 可列入精确 raw 白名单 |
| `Hisai Keishi` | 349 | 久井敬史 | 3813 / 9611 | 可列入精确 raw 白名单 |
| `Shimamura Toshihiro` | 345 | 岛村俊广 | 4511 / 10302 | 可列入精确 raw 白名单 |
| `Hayashi Yutaro` | 341 | 林有太郎 | 5188 / 10968 | 可列入精确 raw 白名单 |
| `Sometani Kazuo` | 330 | 染谷一雄 | 5211 / 10991 | 可列入精确 raw 白名单 |
| `Ohira Shuzo` | 328 | 大平修三 | 4249 / 10044 | 可列入精确 raw 白名单 |
| `Takagawa Kaku` | 327 | 高川格 | 6472 / 12236 | 可列入精确 raw 白名单 |
| `Ishii Kunio` | 325 | 石井邦生 | 5639 / 11412 | 可列入精确 raw 白名单 |
| `Nakagawa Shinji` | 325 | 中川新之 | 3792 / 9590 | 可列入精确 raw 白名单 |
| `Kajiwara Takeo` | 322 | 梶原武雄 | 新建 / 新建 | 可列入精确 raw 白名单 |
| `Kageyama Toshiro` | 320 | 影山利郎 | 4698 / 10488 | 可列入精确 raw 白名单 |

## 暂缓原因

- `Iwamoto Kaoru`：棋院直接证实岩本薫，但 PROD 有 `岩本熏`、`岩本薫`、`岩本薰` 三个目录 ID；先合并目录身份。
- `Maeda Nobuaki`：可靠日文写法为前田陳爾，当前目录为 `前田陈二`，先修正错误汉字并核对既有关联。
- `Fujisawa Hosai`：藤沢朋斎与藤沢秀行是不同人，PROD 同一朋斎有 斋/斎 两个目录 ID；先合并。

## 特殊审核

- `Tamura Hoju (later Shusai)` 原值中的后名不是另一位棋手；[日本棋院围棋殿堂](https://www.nihonkiin.or.jp/profile/sisetsu/dendou/list05.html)直接把田村保寿列为第 21 世本因坊秀哉。
- `Shimamura Toshihiro` 的目录 `岛村俊宏` 与后名 `岛村俊广` 为同人；[立命馆大学的围棋史研究](https://ritsumei.repo.nii.ac.jp/record/13960/files/ir_33_2_kago_kahyo.pdf)明确列出从岛村利博到俊宏、俊广、俊廣的更名，需保留现有 ID。
- `Shinohara Masami` 对应 1904 年出生的围棋棋手筱原正美；同名的 1892 年出生夏威夷居民与本批 1925–1978 年日本职业棋谱语境不同。[棋手升段目录](https://homepages.cwi.nl/~aeb/go/misc/progression.html)、[日本棋院对局表](https://www.nihonkiin.or.jp/match/meijin/001.htm)支持职业棋手身份。

各条精确证据 URL、目标 ID 及具体区分说明见同名 JSON。未改数据库或导入代码。
