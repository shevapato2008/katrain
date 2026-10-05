# GoRatings 批量名称采集：有限抽样决策

**可行：把“本人身份核对一次、同 ID 各语实字分别取证”作为现有流程的快速路径。** 已有本人 Wiki 条目继续优先；对应语言 Wiki 已查不到时，可用 GoRatings 的实际刊载名字作为 conventional 正证。官方桥已明确本人且无矛盾时，无须对五种语言重复调查生日；仍逐格保留正文、HTTP200、SHA、姓名摘录、语言/script、owner 绑定和独立审核。四语页面是同一出版者，不算四份独立身份证据。

## 13 人小样本

从高频未完成名单选丁浩、许嘉阳、石井邦生、淡路修三、金彩瑛、王晨星、谢科、洪性志、金明训、安祚永、伊田笃史、孟泰龄、廖元赫。取得 **51 个实时 GoRatings 原始页面、13 个官方人物页，官方页均 HTTP200 并核对本人姓名**；同 numeric ID 已取得的语言页具有一致的本人链接表。淡路修三的 GoRatings 韩文请求失败，已有实时韩文 Wiki 正文可直接优先使用，无需为凑齐抓取再查。

例如 [GoRatings 丁浩韩文页](https://www.goratings.org/ko/players/1511.html) 直接连接 [韩国棋院本人档案](https://www.baduk.or.kr/record/player_view.asp?pkey=20000987)；王晨星的 [官方档案](https://www.baduk.or.kr/record/player_view.asp?pkey=20000384) 同页给出 `왕천싱(王晨星)`，可以一次桥接本人身份与实际韩文名字。13 人完整来源与实际标题见 `/tmp/kifu-goratings-sample-20261005/sample-captures.json`、`official-bridges.json`，原 HTML 同目录；石井韩文复用生产者已留存正文。

**边界：** GoRatings 只有 zh/ja/ko/en，不能单凭 `/zh/` 声称 TW 或 CN 两格均完成；繁简异体须沿用 Wiki variant、已有当地正证或当前已批准字形转换流程。`/ja/`、`/ko/` 路径本身也不证明名字脚本合格：逐格看 H1，不能把 Latin fallback 当日/韩名。许嘉阳、谢科的 ja H1 实际保留中文简体；已有 Wiki/官方日文名优先，不根据 URL 擅自改字后称“原文刊载”。

本轮还遇到旧网页缓存与实时正文不一致：石井邦生旧缓存 KO 标题为 Latin，但生产者实时 11:44:55 UTC 原文是 `이시이 구니오`（SHA `7e29535339ab822f466ddb78258e7e037234b9b45c88fae2e370bb14c3b3e44c`）。已撤回基于旧缓存的当前判断；正式候选只采用实时/已留存原正文。

## 现在可推进的具体对象

这些本人桥及多语正证已就绪，均属于现有 W/X 生产范围，不新增重叠任务；下表是可用正证，最终名字仍服从 Wiki 优先。

| 棋手 / 现有 ID | 姓名槽频次 | GoRatings ID | 实际 EN / KO 标题 | 已核对官方桥 |
| --- | ---: | ---: | --- | --- |
| 王晨星 / 575 | 560 | [1073](https://www.goratings.org/en/players/1073.html) | Wang Chenxing / 왕천싱 | KBA 20000384 |
| 洪性志 / 175 | 556 | [340](https://www.goratings.org/en/players/340.html) | Hong Seongji / 홍성지 | KBA 10000280 |
| 金明训 / 128 | 554 | [1364](https://www.goratings.org/en/players/1364.html) | Kim Myounghoon / 김명훈 | KBA 10000791 |
| 伊田笃史 / 75 | 550 | [1188](https://www.goratings.org/en/players/1188.html) | Ida Atsushi / 이다 아쓰시 | 日本棋院 ki000427 |
| 廖元赫 / 91 | 536 | [1427](https://www.goratings.org/en/players/1427.html) | Liao Yuanhe / 랴오위안허 | KBA 20000951 |

两位 producer 的最小操作：每人复用一次官方身份桥，先取已知 Wiki 本人页及语言链接；只对缺格抓同 numeric ID 的 GoRatings 对应页。已有正证到手便停止重复生日/拼写搜索；原文 script 不合格或身份冲突时仅保留该格待查，不拖住同批其他人。继续每五人出包、复用 association/catalog 快照，仅刷新目标名称前像。无需新平台、表或降低导入门槛。

## 90–95% 目标的实际口径

冻结 inventory 中公开 172,766 局，双方 player FK 均非空 143,984 局（**83.34%**）。因此纯实体 names-only 路线的双方棋局覆盖上限就是 83.34%；已批准 raw-name 显示可另增，但不能靠翻译零 FK 孤立实体补足。按姓名槽频率，覆盖现有已关联槽的 90%/95% 约需 **907/1,255 名**。应优先高频有 FK 棋手，批内兼顾“另一方已完成”的新增完整棋局收益，同时保留未关联 raw 姓名的独立工作线。统计仅本地复用冻结资料，未重抓或写数据库。
