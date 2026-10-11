# 下一批高频棋手精确关联执行记录

2026-10-04。按 [独立身份裁决](kifu-player-next15-independent-decision-astra-2026-10-04.md)，TEST 与 PROD 各为 13 名棋手关联 **5,423 个 exact 原文 NULL 槽**；31 个逐局异常、两位整项待查棋手的 811 个槽位仍为空。六位尚无目录身份的棋手只建立中文 canonical ID；复用其余七位的现有 ID，保留旧 canonical、别名与名称行。原始 SGF、日期、来源、raw staging 和既有棋手关联均未修改。

独立代码审核发现两处跨 ID 名称碰撞检查遗漏，修正后增加了针对旧 canonical 和 normalized alias 的回归测试，4 项聚焦测试通过。执行程序见 [player_next15.py](../../katrain/web/kifu/player_next15.py) 与 [CLI](../../scripts/kifu_player_next15.py)。两环境 capture 得到相同的 5,423／31／811 分区；真实事务 dry-run 后重新 capture，计划完整一致，再依次 TEST、PROD 提交。两库提交后逐个读取 5,423 个候选及全部 HOLD／保护槽，结果符合计划。

| 环境 | 冻结计划 SHA-256 | 新增关联槽 | 新建棋手 ID | 提交后棋手关联槽／346,050 | 完整关联棋局／173,025 |
| --- | --- | ---: | --- | ---: | ---: |
| TEST | `c4d65f3a1a0fab1462bb2314b7e8462bc32ec564c64d33219996bdfc55ed0ef5` | 5,423 | 12552–12557 | 298,425 | 69,048 |
| PROD | `eccf4a8a38595ceea6d33d8a33f719818560d3cb62e189e0bca9ac06ea2b0076` | 5,423 | 6783–6788 | 300,030 | 70,077 |

新建的中文目录依次为林士勋、周俊勋、黄世元、张凯馨、韩尚勋、张哲豪。名单与 source/身份依据见独立裁决。原中文 canonical 与已有五语译名并不等同于“翻译完成”；本批未升级任何名称验证状态。
