# 两名棋手五语候选独立复核：周鹤洋 PASS，钱宇平繁中 HOLD

2026-10-03。复核对象是不可变原包 `five-primary-next40-pending-luna` 的两个候选。本复核核对精确 `cn/tw/jp/ko/en` 显示及专业赛事／人物来源之间的交叉对应；不批准棋手数据库实体或 FK 绑定、任何 SGF／专辑归属、数据库写入、导入或生产使用。原包候选 SHA-256 `cbd0c57f69fcb114531ad02a3adb5bfca0080040723e29f10bdcfda1505889dd` 未改写。

## 周鹤洋 / CWA000014 — 五语显示 PASS

原包把 `official_roster.url` 错填为 GoRatings 页面。替换候选已改成冻结协会来源的真实 URL：`https://wqapi.cwql.org.cn/playerInfo/professional/list`。留存响应 SHA-256 `18ba2a04efdca69d47528cbe703d9c54e1005b7f986af782434cbc3f1dd316f9` 中，`CWA000014` 对应 `周鹤洋`、生日 `1976-06-18`。GoRatings 135 号中文人物页也写出同一姓名和生日；它的中、英、日、韩历史榜单行分别链接到 135 号人物页，并逐字显示候选 `周鹤洋 / Zhou Heyang / 周鶴洋 / 저우허양`。

[海峰棋院赛事历史页](https://www.haifong.org/game/classes/889B583FD295AC653FB6B4B0AA0DA5CC) 带 `lang="zh-tw"`，列出第二届倡棋杯、2005-10-23 至 10-25、冠军周鶴洋。[2006-01-08 新浪转载的赛事报道](https://sports.sina.com.cn/s/2006-01-08/0706751732s.shtml) 具体写出周鹤洋以 2:0 战胜孔杰夺冠；[2006-02-07 新浪转载的人物报道](https://sports.sina.com.cn/go/2006-02-07/14092029179.shtml) 给出周鹤洋生日 1976-06-18 并记载 2006 年 1 月获得倡棋杯冠军。赛事名、胜者、同日人物生日与协会行／GoRatings 135 号资料互相吻合，支持把海峰的 `周鶴洋` 显示对应到这位协会棋手。裁决仅限姓名和来源对应，不延伸至任何棋谱。

## 钱宇平 / CWA000044 — cn/en/jp/ko PASS；tw HOLD

协会冻结响应把 `CWA000044` 列为 `钱宇平`、生日 `1966-10-06`；GoRatings 521 号中文人物页也具同名和同生日。中、英、日、韩历史榜单行均链接到 521 号人物页，并逐字显示 `钱宇平 / Qian Yuping / 銭宇平 / 첸위핑`，四项显示 PASS。

[日本棋院富士通杯历届记录](https://www.nihonkiin.or.jp/match/fujitsu/archive.html) 列出 1991 年第四届决赛：赵治勋九段（日本）对钱宇平九段（中国）；[CWI 的赵治勋富士通赛事索引](https://homepages.cwi.nl/~aeb/go/games/games/Cho_Chikun/tournaments/Fujitsu.html) 记录 1991-08-03 决赛对手 Qian Yuping，结果 `+F`。该决赛是不战胜／弃权，不是已进行的对局，未声称存在决赛 SGF。HK2 人物页确实在相应富士通杯叙述中写出繁中 `錢宇平九段`，与专业赛事身份吻合；首页也表明 HK2 属妙手围棋院这一香港围棋培训机构。

`tw` 仍为 **HOLD**：HK2 的出版方／该人物页目前不在固定来源登记 `.2`（SHA-256 `e2ed3cafa9b6f32d8ba30c78aecdf9667801df3cf34745227e5da588e98dd58e`）或 `.5`（SHA-256 `d64180400bfdd95fa558e04dada00a7b4e0a31a6b361b2a8845ebd49e43bb88f`）中；页面没有 HTML `lang` 标签，繁中写法位于赵治勋人物传记，而非钱宇平专页。按[台湾／繁中来源裁决](kifu-name-tw-traditional-source-policy-astra-2026-10-03.md)，香港来源本身可以支持 `tw` 候选，地区不是拒绝理由；但用于正式研究的出版方仍须在该批固定登记中按实际身份和来源类型纳入，并保留实际 `zh-Hant-HK` 地区，不得把它改写成台湾来源。该先决项未完成，所以不把已有精确繁中字符串提前签成 PASS。修复需要获准的新来源登记版本和独立复核；其余四语 PASS 不消除此 HOLD。

## 受控替换包

新包位于 `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-primary-next40-replacement-review-luna/`（目录 `0700`、文件 `0600`），包含替换候选、审核报告、来源索引、原始页面留存和签署 attestation。替换候选修正协会 URL，并逐语记录 PASS/HOLD、证据文件及限制；原候选目录保持只读且未改动。

- 替换候选 `candidates.replacement.jsonl` SHA-256：`9bb82ecd9ccb92661da7f108745bc6ecad7248eb921bd4cd3225002f8e1e6e27`
- 审核报告 `reviewed.json` SHA-256：`cc44d08b5ba93de23e1ab0fb302dc8e18dd95175b8702e5adeaeea5e653cd132`
- 来源索引 `source-index.json` SHA-256：`2750842289f10391d1a71aec4ef0bb1da9b260a09fecc1533d551d040b3452c4`
- 签署 attestation `review-signature.json` SHA-256：`7478cbdd5e3ddb294ee96f1e4304432e6655c33da5781bb01551074fb1efd7cf`

未检查当前目录碰撞，未作数据库或代码修改，未提交 Git。赛事结果与同名协会资料的核验不等于棋谱人物归属；候选 `production_authorized` 均为 false。
