# 棋手预处理：非汉字名次 321–360 双库执行记录

2026-10-04 独立复核两批身份来源、TEST/PROD 实时目录及棋局 FK 后，
将第 321 名 `Miyamoto Yoshihisa` 加入安全名单：第 292 名
`MiyamotoYoshihisa` 已建立同人的“宫本义久”ID，TEST `12501`、
PROD `6732`。[关西棋院本人资料](https://kansaikiin.jp/kisi_prof/miyamotoyoshihisa.html)
与 [CWI 罗马字对照](https://homepages.cwi.nl/~aeb/go/misc/progression.html)
支持该身份。原 321–340 名单废弃，采用修订后的 safe17。

两批先在 TEST/PROD 各自捕获冻结计划并作事务预演、回滚，再按
321–340 TEST → PROD、341–360 TEST → PROD 顺序提交。每步均核对
白名单及计划 SHA、实时原值、来源、旧 FK、目录主名和审核行前像。

| 批次 | 白名单 SHA-256 | TEST 计划 SHA-256 | PROD 计划 SHA-256 | 各库新增 FK（黑／白） | 各库新建 ID |
| --- | --- | --- | --- | ---: | ---: |
| 321–340 safe17 | `23225206995f87d0d133c51c56a82d2c8d5fe03f057e07b7d216ae8f81854c5f` | `1cc46e99d24ca1681c7ceffcb1d863b4be1dca4c037998a941492cffe3781cb9` | `aca2fba051efafeb3a63eb91db3868e1b03731f36d8f7831803295639411c7bd` | 430（246／184） | 4 |
| 341–360 | `95f5d08052756923cea6c8b51310aba34c1677c737bb79b78094a60940975b45` | `bb178c29ab86c7042bf0e37e639f09a3312c2af5e53a416792e5b78a062f5500` | `b66b4b7733e6559aae0795091fa1185d8aace90e10bf604b9d12de6525659a37` | 376（204／172） | 3 |

| 步骤 | TEST 已连席位／棋手 ID | PROD 已连席位／棋手 ID |
| --- | ---: | ---: |
| 写入前 | 267,933／3,829 | 269,538／3,651 |
| 321–340 完成 | 268,363／3,833 | 269,968／3,655 |
| 341–360 完成 | **268,739／3,836** | **270,344／3,658** |

最终合并核对 33 个 exact raw、806 个目标 FK、33 行审核元数据
及目标目录 ID。两库各 173,025 盘的 346,050 个原始黑白姓名字段
与冻结 inventory 逐项相同。七项身份或目录待决的原值共 171 席
继续 FK 为空，审核行仍 `pending`、元数据为空：
`Takahashi Shutoku`、`Takeuchi Sumio`、`HoJangHee`、
`Kajikawa Shurei`、`Akedo Kazumi`、`HeoChang-heui`、
`Ishigure Makiko`。

本批完成后棋手关联覆盖率为 TEST `268739/346050`（77.659%）、
PROD `270344/346050`（78.123%）。原始姓名没有翻译或改写。
