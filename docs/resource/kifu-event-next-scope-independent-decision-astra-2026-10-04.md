# 下一批赛事身份独立裁定（Astra，2026-10-04）

**结论：743 盘仅批准赛事类型；453 盘 hold。没有数据库写入，没有届次批准。**

| 目标类型 | 批准 | ID 决策 |
|---|---:|---|
| 中日围棋对抗赛（正式代表团定期交流） | 637 | 当前73个类型中无对应项，可新建；执行时重新查重 |
| 日本职业十杰战 | 106 | 复用 **44** |

## 身份与范围

日本棋院沿革区分职业十杰、职业业余十杰、日本棋院第一位及全日本第一位；朝日职业十杰共12届，首届本战跨1963—1964。原候选105盘可用，原hold **63395** 的1975-02-13赵治勋—高川格与第12届表一致，增加1盘。[日本棋院沿革](https://www.nihonkiin.or.jp/profile/enkaku/)、[第12届档案](https://homepages.cwi.nl/~aeb/go/games/games/ProBest10/12/index.html)、[日本棋院赵治勋记录](https://archive.nihonkiin.or.jp/joho/pressroom/newsrelease/20070319.htm)

中日类型限于正式代表团定期交流，不能把收录各种访问棋谱的年度资料夹当作一个赛事。1960年代往来和1973重启后的系列可归同一类型；擂台赛另立。1984、1986、1988等常规交流采用番棋，因此 **119437、119439** 的“3番棋”不构成排除理由。[日本棋院陈毅档案](https://archive.nihonkiin.or.jp/igodendou/list09.html)、[中国奥委会历史](https://www.olympic.cn/sports/other/2003/0918/24504.html)、[中日交流档案](https://homepages.cwi.nl/~aeb/go/games/games/CJGoExchange/index.html)、[1986](https://homepages.cwi.nl/~aeb/go/games/games/CJGoExchange/1986/index.html)、[1988](https://homepages.cwi.nl/~aeb/go/games/games/CJGoExchange/1988/index.html)

## Hold

| 范围 | 盘数 | 原因 |
|---|---:|---|
| 藤泽秀行私人青年团（含1盘疑似） | 9 | 与常规定期代表团不同；82961日期存在异文 |
| 1981—1982中日新秀系列 | 10 | 6盘只有泛称，也由系列对阵识别出来 |
| 电视快棋/快棋表演 | 3 | 另一GN根属性明确更具体身份 |
| 1978神户新闻、安永一、杉内另行访问团 | 26 | 含英文副本；不足以并入6月常规交流 |
| 其他日期与代表团名单不合的中日对局 | 7 | 暂无充分证据排除私人访问/表演 |
| 职业业余十杰 | 10 | 独立赛事 |
| 韩国新锐十杰 | 2 | 根属性已明确韩国身份 |
| Nihon Ki-in Number One | 386 | 主要为日本棋院第一位决定战，夹有全日本第一位；不能整批套45或46 |

前两项依据：[藤泽访问团档案](https://homepages.cwi.nl/~aeb/go/games/games/CJShuko/index.html)、[新秀系列回顾](https://www.foxwq.com/news/mlist/id/14616.html)。全部hold是本次不批准写入，不表示已经为每盘确定另一目标类型。386盘保持原hold，不扩展第三类型写入工作。

## 类型可定，元数据不动

- **124124、126054**：原始届次与年份/另一GN冲突，批准类型，禁止推导届次。
- **113606**：库/DT为1991-06-01，档案同对阵为6月4日；类型明确，保留日期疑点。[1991档案](https://homepages.cwi.nl/~aeb/go/games/games/CJGoExchange/1991/index.html)
- **157456、157457**：1975单局表日期11月28日与年度轮次表不合，但窪内对华以刚/沈果孙的类型可确认；本次不修日期。

## 实际核验与执行边界

PROD `katrain_prod_20260725` 于 **2026-10-04 07:24:51 UTC** 在只读重复读事务中抓取全部1196候选和73个赛事类型，最终ROLLBACK。1196行的原始event、date_sort、source_path、SGF MD5与候选包一致，全部event_id及event_edition_id为空；全部根节点解析成功。743批准行的event逐字存在EV/GN，date_played逐字存在DT，双棋手有值，无duplicate_of_id。

证据强度是赛事类型裁定，未逐盘外查全部棋谱内容。来源、日期、多个GN产生身份冲突时才深入查单局。新旧届次编号、跨年和名次战不能由文本直接生成edition。

[机器清单](kifu-event-next-scope-independent-decision-astra-2026-10-04.json)完整分割1196个exact ID，附原值、SGF SHA256/MD5、根属性、hold理由、证据链接与目标类型。后续仅允许对其中743行写event_id；按清单重验preimage并重新确认44及新类型查重。不得按raw文本扩大范围或生成无条件泛称别名。源数据及event_edition_id保持不动。
