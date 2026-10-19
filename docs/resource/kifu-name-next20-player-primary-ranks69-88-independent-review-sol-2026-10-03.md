# 频次69–88：18人五主语言来源独立复核

2026-10-03；独立审核者 `/root/freq41_60_95_review_sol`，真实审核 `2026-10-03T00:28:51.147820+00:00`。审核Luna `next20-player-primary-luna` 的原始pending矩阵，逐格裁决 **63 PASS / 27 HOLD**；整批未完成。

PASS只批准精确来源显示姓名与所列外部profile/生日对应，不批准本地raw槽、人物主键/QID、FK、棋谱归属或数据库写入。19个原HOLD保持；原71个证据格中另有8格HOLD。

独立重算81份留存响应hash全部相符；从原字节重读76个GoRatings页面（含ID69与72消歧各四页）、4个海峰个人页及Wikidata JSON。实际H1、html lang、完整DOB均已独立解析；4个海峰职业个人页的姓名/出生日期/入段语境及GoRatings直接链接一致。18个外部profile姓名/生日对应成立，限定于来源记录；多数多语页仅为GoRatings同一出版方，未声称18个身份均获得第二机构审核。

冻结inventory的排名69–88按双席位计数重新计算，18人恰好为排除已审邱峻（81）和王檄（85）后的集合。此频次核对不签署其raw出现槽适用性。

| 原名 / profileID | cn | tw | jp | ko | en |
| --- | --- | --- | --- | --- | --- |
| 申旻埈 / 1314 | `申旻埈` P | H | `申旻ジュン` P | `신민준` P | `Shin Minjun` P |
| 林君谚 / 1327 | H | `林君諺` P | `林君諺` P | `린쥔옌` P | `Lin Junyan` P |
| 罗洗河 / 43 | `罗洗河` P | H | `罗洗河` H | `뤄시허` P | `Luo Xihe` P |
| 於之莹 / 1225 | H | H | `於之瑩` P | `위즈잉` P | `Yu Zhiying` P |
| 片冈聪 / 235 | `片冈聪` P | H | `片岡聡` P | `가타오카 사토시` P | `Kataoka Satoshi` P |
| 林立祥 / 1533 | `林立祥` P | `林立祥` P | `林立祥` P | `린리샹` P | `Lin Lixiang` P |
| Kitani Minoru / 591 | H | H | `木谷實` P | `기타니 미노루` P | `Kitani Minoru` P |
| 桥本宇太郎 / 588 | `桥本宇太郎` P | H | `橋本宇太郎` P | `Hashimoto Utaro` H | `Hashimoto Utaro` P |
| 山城宏 / 223 | `山城宏` P | H | `山城宏` P | `야마시로 히로시` P | `Yamashiro Hiroshi` P |
| 谢赫 / 53 | `谢赫` P | H | `谢赫` H | `셰허` P | `Xie He` P |
| 党毅飞 / 1135 | `党毅飞` P | H | `党毅飛` P | `당이페이` P | `Dang Yifei` P |
| 许皓鋐 / 1692 | H | `許皓鋐` P | `許皓鋐` P | `쉬하오훙` P | `Xu Haohong` P |
| 藤泽里菜 / 1224 | `藤泽里菜` P | H | `藤沢里菜` P | `후지사와 리나` P | `Fujisawa Rina` P |
| 李轩豪 / 1175 | `李轩豪` P | H | `李轩豪` H | `리쉬안하오` P | `Li Xuanhao` P |
| 芝野虎丸 / 1540 | `芝野虎丸` P | H | `芝野虎丸` P | `시바노 도라마루` P | `Shibano Toramaru` P |
| 村川大介 / 913 | `村川大介` P | H | `村川大介` P | `무라카와 다이스케` P | `Murakawa Daisuke` P |
| 王磊 / 69 | `王雷` H | H | `王雷` H | `왕레이(雷)` H | `Wang Lei (s)` H |
| 赖均辅 / 1706 | H | `賴均輔` P | `賴均輔` P | `라이쥔푸` P | `Lai Junfu` P |

P=PASS，H=HOLD。分语言：cn 12P/6H、tw 4P/14H、jp 14P/4H、ko 16P/2H、en 17P/1H。仅林立祥具备5/5来源PASS。

## 王磊与王雷：四格HOLD

王磊身份元数据声明ID69 / 1977-12-26，留存ID69四页实际为cn/jp `王磊`、ko `왕레이`、en `Wang Lei (b)`，生日均1977-12-26；Wikidata Q6134696的王磊标签、围棋职业描述和完整生日独立相符。此身份来源对应PASS。

但原bundle及CSV的王磊cn/jp/ko/en四格仍引用ID72 / 1986-10-11，实际为 `王雷`、`王雷`、`왕레이(雷)`、`Wang Lei (s)`。这四个姓名确属另一人，全部HOLD。其source说明还误写“profile ID69”；不能由正确identity元数据补救错误证据绑定。最小修复为生产者另开更正包，明确用ID69的实际原文/URL/hash/生日重提四格后再审；本次没有替换或新增这四个正式候选。

## 其余必要HOLD

罗洗河jp `罗洗河`、谢赫jp `谢赫`、李轩豪jp `李轩豪`是真实ja页面H1，但简体fallback没有独立日文职业用名印证；仅ja界面不足以签署这三个精确字形。桥本宇太郎ko `Hashimoto Utaro`为真实韩文界面的拉丁H1，尚无韩文姓名证据。这四格HOLD，不自动转字或音译。

原14个tw缺证及5个cn未提交合格格继续HOLD。HOLD不是否认相应棋手或字形：尤其於之莹的姓於不因字符外观判为错字，本次未将producer已held线索提升为正式格。cn PASS逐页实读了简中页面正文与姓名，没有仅由URL或姓名字形决定语种；GoRatings通用zh未转算为tw。

## 冻结签署记录

受保护审核包：`/Users/fan/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/next20-player-primary-independent-review-sol`。`review-record.json`含90格精确裁决与18个来源profile对应，SHA-256 `1f7ef9cfde5b3402c67d87ab11316d227a83d63727bb3136e161efbecc21adf4`；原包文件另冻结于`input.frozen/`。目录0700，冻结文件0400。

| 输入 | SHA-256 |
| --- | --- |
| bundle.pending.json | `747cf886cf0c6a66a42d0719c87e6d9ff110f74051698411a93b2181d2fb2a0c` |
| matrix.pending.csv | `af590948f2af26878f806290d2c40ca719a8e3c1f050159c45b09456dcc2b952` |

只新增此报告及独立审核包；原producer候选/CSV/pending状态保持，未访问数据库、改代码、绑定FK或提交Git。
