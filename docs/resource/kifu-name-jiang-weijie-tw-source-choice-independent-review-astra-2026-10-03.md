# 江维杰 `tw` 主显示选字独立裁决

2026-10-03；独立审核者 `/root/jiang_tw_choice_astra`。审核[本轮候选](kifu-name-jiang-weijie-tw-source-choice-candidate-root-2026-10-03.md)及[此前补证审核](kifu-name-five-primary-frequency-41-60-cn-tw-ko-followup-independent-review-sol-2026-10-03.md)，并直接读取留存原始响应。

**PASS：外部职业棋手江维杰（CWA000019、GoRatings 964、1991-10-17）的产品 `tw` 主显示采用精确值 `江維傑`，性质为 `conventional`。** `江維杰` 是同人的真实台湾来源异体，可作为后续搜索别名；本次没有写入别名。此裁决解决本轮主显示选择，不声称台湾来源只有一种写法，也不把 `杰` 判为错字。

独立重算 `~/.local/share/kifu-name-audit/2026-10-03/jiang-weijie-tw-source-followup-root/` 的 manifest 与三份 HTML：全部与候选记录相符。manifest SHA-256 为 `73243a4a6474088d29ed918b4198781e150dc434ce295404287562926d4ff787`。从原始 UTF-8 HTML 重新提取可见文本，三个页面均为 `html lang="zh-tw"`；以下序号为去除脚本、样式后的非空文本节点，0 基。

| 实际来源与定位 | 独立核对结果 | 原 HTML SHA-256 |
| --- | --- | --- |
| [2020 应氏杯参赛名单](https://haifong.org/news/content/18E64F5ECB046179BCAC5B3C2531710B)，85 | 同一条目直接出现 `江維傑九段`、上海及 `1991.10.17`，提供姓名与完整生日的连接。 | `b555797b10ba5f157a2f14718c66709ebabb8bc4aac1cf4b8c02211ef05be2d0` |
| [2019 三星杯预选报道](https://www.haifong.org/news/content/597ACC72216421AB3FBA315B0767CDEB)，111、113、114、116、124 | 五处完整姓名均为 `江維傑`。7月1日林士勛执黑获胜，与 GoRatings 964 原文同日执白负 Lin Shixun 的记录对应。 | `fb188cfda19535ee081ab836f09f15fba51ad9a6361f0d841e348d7063fba3ad` |
| [2023 倡棋杯报道](https://haifong.org/news/content/8DED310014B476F8D98C294EDA8EE570)，51 | 三十强名单直接用 `江維傑`。此项支持后续仍有该写法，名单本身不单独承担身份消歧。 | `5c4342c13242254dcc9f3e712810bc92946433447f14fd88d4acb1f1fd04e864` |

身份依据也从历史原字节重新读取：`five-primary-41-60-second9-luna/cwa-professional-roster.json` 唯一对应记录为 `playerNo=CWA000019`、`playerName=江维杰`、`playerBirthday=1991-10-17`；同目录 `964-en.html` 实际标题为 `Jiang Weijie`，生日相同。两份 SHA-256 分别为 `18ba2a04efdca69d47528cbe703d9c54e1005b7f986af782434cbc3f1dd316f9`、`7bec33472036126e8d54b203b88ed49a1dc88824d08af768899c90f34ce22727`，与此前记录相符。它们的共同父目录为 `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/`。

旧[2020 应氏杯战报](https://www.haifong.org/news/content/551BC5AC6433866A399BA046C8A9AF22)原 HTML 也已读回，SHA-256 为 `ba1e7b2a6f159b37b676256faed2e7bde4c034f97f11e21fbba5820f2f2646ff`，与旧包相符。结果正文使用 `江維傑`，对柯洁的对阵行使用 `江維杰`；GoRatings 同时对应 2020-09-08 白胜村川大介、09-09 白负柯洁。这足以确认两种字形指向同一人。该异体应保留在证据和后续搜索别名候选中；本次没有实际检索本地别名碰撞，不能据此直接写入或合并本地身份。

主显示取舍依据是有完整生日的台湾专业参赛档案，加上可独立匹配对手、日期和手番的台湾赛事正文，后续报道再支持实际使用。此前要求的“补一份有同人连接的台湾专业直接用名”已经满足。三篇均属海峰，2019 年五处出现也只是一篇文章；本裁决没有把命中数当作出版方多数，也没有依赖机械繁化或日文用字。现有证据没有要求以 `江維杰` 为专属主显示的订正或个人声明，因此其真实存在可以通过保留异体处理，无须继续阻止采用已获直接证据的 `江維傑`。

本次只新增这一项来源及精确显示裁决。旧候选、旧审核和原 pending 状态保留；正式研究记录仍须绑定适用的固定来源登记并记录本次裁决。本地人物主键、raw 槽位、FK、棋谱归属、十一语完成度及数据库写入均未获本次批准。未改代码、数据库、来源登记或别名，未提交 Git。
