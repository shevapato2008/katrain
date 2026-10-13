# 棋手预处理：非汉字名次 181–220 独立身份复核

**后续状态：修正后的 181–200 与未改的 201–220 均已获得独立批准并双库写入，
见 [执行记录](kifu-player-nonhan-ranks-181-220-application-2026-10-04.md)。**

**后续修正：181–200 白名单中仅 `Iwasaki Kenzo` 的证据 URL 已更正，
新白名单 SHA `85661785cd281fc5f94ba62dd4bb06c10238dfa3408eb5795042eac1dbb36222`，
新 TEST／PROD 计划 SHA 分别为
`f870a2ef54433820e69e6eabad718672b29e23df353c10a4a323bbe9c73c3234`／
`76e11c25352145491cbf670924e80b2f1d00b33bc802eed7a79d89cb2141f31c`。
两库新计划事务预演已通过并回滚；18 个原文／1,124 席保留，旧计划作废。
下文记录修正前发现与判断。**

2026-10-04 只读审查，未改白名单、冻结计划或数据库。逐项对照 35 个候选
exact raw 的姓名、年代、现有目标 ID 与审核来源，并检查历史旧名、代际同名、
中文异体及新建目录名称。原双库事务预演已通过；本报告只评身份和来源安全。

| 批次 | 白名单 SHA-256 | 冻结计划 SHA-256：TEST／PROD | 独立结论 |
| --- | --- | --- | --- |
| 181–200 | `9c05e2520b6dbb820b14d259c46f27a23cc71ce2185c348e74cd2e641913eb11` | `5726744f7abf6f712cb153bc633736d1fc7ea9db5e8a875393ec09e8fbb9102b`／`42ba3c8eb9bd406b10bfdfdfc6358a19f8b7a0d27a3e799090948110021ce52b` | 17 个原文／1,068 席可保留；`Iwasaki Kenzo` 的 56 席需更正来源并重新冻结计划。原计划整体暂缓。 |
| 201–220 | `98fcd9cbe688229a1fef7146725a6a20ab7257de64978cd91db8ae4143b2c9af` | `c97c1fe2e53ca97e278ce874e548ee8011de777307609a1ecd353f377d3b073c`／`5dbe8610e83788dc4d95381fb4a4fad4369a154301b8c6de60376cfd6b13d537` | 17 个原文／897 席未发现新增身份冲突，可进入执行前独立批准。 |

## 精确原文结论

| 批次 | 结论 | exact raw |
| --- | --- | --- |
| 181–200 | 保留 17／1,068 席 | `Hattori Rittetsu`, `Hirano Masaaki`, `Honinbo Retsugen`, `Takenaka Kotaro`, `Yasui Chitetsu`, `ChoSeonJin`, `Hisajima Kunio`, `Miyazaki Hiroshi`, `Morikawa Masao`, `Watanabe Reiji`, `Baba Shigeru`, `Hirose Heijiro`, `Suzuki Tsuna`, `Nakayama Noriyuki`, `Ezura Yuichi`, `KatoMasao`, `Kawai Tetsuyuki` |
| 181–200 | 来源修正后再定 1／56 席 | `Iwasaki Kenzo` |
| 201–220 | 保留 17／897 席 | `CheongSu-hyeon`, `HongTaeSeon`, `Sato Sunao`, `Ito Showa`, `Kanashima Tadashi`, `Sekiyama Sendayu`, `Izumitani Masanori`, `Mizuno Ichiro`, `YoonKihyun`, `ChoiGyuByeong`, `KimSuJang`, `Okatani Mitsuo`, `Yasui Sanei`, `Noguchi Hitoshi`, `Oka Mitsuo`, `Otani Motohiro`, `ImSeonKeun` |

`Iwasaki Kenzo` 的原白名单 `identity_evidence_url` 指向
[CWI 方圆社首卷目录](https://homepages.cwi.nl/~aeb/go/games/games/Hoensha/)，
该页没有 Iwasaki 条目，不能作为要写入审核元数据的直接证据。
身份本身有交叉材料：[CWI 秀哉棋谱](https://homepages.cwi.nl/~aeb/go/games/games/Shusai/index.html)
列 1890、1896、1898 年的 Iwasaki Kenzo 对局，
[庆应大学藏书目录](https://www.lib.keio.ac.jp/collection/files/mita/igo_collection.pdf)
列《巌崎健造打碁集》，与原文 1882–1900 年范围相符。
建议仅更正该行来源，重新生成 181–200 白名单与 TEST／PROD 计划；
不从旧计划直接 apply，也不因来源链接错误推断两个人。

历史旧名和代际检查：[CWI 丈和姓名对照](https://homepages.cwi.nl/~aeb/go/games/games/ancient/Honinbo_Jowa/)
明确把 `Hattori Rittetsu` 与井上幻庵因硕归为一人、把 `Ito Showa` 与
伊藤松次郎归为一人，并列 `Sekiyama Sendayu` 的汉字；
[日本棋院历代家谱](https://www.nihonkiin.or.jp/teach/history/rekidai.html)
区分第三代安井知哲和第十代安井算英。
[幸手市烈元资料](https://www.city.satte.lg.jp/soshiki/kyoudomuseum/siteibunnkazai/14309.html)
确认十世本因坊烈元及其 1750–1808 年代。
现代日本棋手以[平野正明](https://www.nihonkiin.or.jp/player/htm/ki000121.htm)、
[久岛国夫](https://www.nihonkiin.or.jp/player/htm/ki000056.htm)、
[金岛忠](https://www.nihonkiin.or.jp/player/htm/ki000060.html)、
[泉谷政宪](https://archive.nihonkiin.or.jp/player/htm/ki000118.htm)等日本棋院
姓名／读音对照为主；韩国棋手以[郑寿铉](https://www.baduk.or.kr/record/player_view.asp?pkey=10000012)、
[洪太善](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000040)、
[金秀壮](https://www.baduk.or.kr/record/player_view.asp?pkey=10000014)等韩国棋院
汉字姓名为主。复用目标 ID 的两环境现主名与白名单目标相同；拟建名及
已知历史旧名在两环境目录与别名表无同人碰撞。`Oka Mitsuo` 与
`Okatani Mitsuo` 是不同的日文姓名，继续指向不同的现存 ID；
`KimSuJang` 与已关联的 `KimSu-chang` 指向同一现存 ID。

原研究已经暂缓的 5 个原文仍应暂缓：`Imai Kinemon`（64 席，历史身份
未直接证实）、`Kitani Reiko`（57，目录双 ID）、`Miyazawa Goro`
（55，目录双 ID）、`Ito Kotaro`（54，汉字对应未直接证实）、
`Miyamoto Naoki`（51，旧名／异写未定），合计 281 席。此次新发现的是
`Iwasaki Kenzo` 的证据 URL 错指，不是身份相反证据。
