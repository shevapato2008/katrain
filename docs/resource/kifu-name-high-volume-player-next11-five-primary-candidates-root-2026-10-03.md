# 高频历史棋手下一批 11 名：五语来源候选

2026-10-03。此表仅为**逐人来源名称候选**，全部待独立审核。它不批准原始棋谱姓名的同一人物归属、棋谱 FK、raw 显示范围、十一语补齐或数据库写入。11 个名字是已有前 20 高频名单的后 10 名，另加用户点名的 `Go Seigen`；这些原文合计 13,507 个候选黑白槽位。冻结清单中前 10 个名字共 12,558 槽的棋手 FK 均为 NULL，须审有限 raw 适用范围；`Go Seigen` 的 949 槽均已关联既有人物 ID `1`，应审实体名及既有 FK 的准确性，不按未关联 raw 值处理。

| 原始姓名 | GoRatings ID | cn | tw | jp | ko | en | 待核问题 |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| 大竹英雄 | 158 | 大竹英雄 | 大竹英雄 | 大竹英雄 | 오타케 히데오 | Otake Hideo | 日文协会档案姓名中有全角空格，需规范化比较。 |
| 刘昌赫 | 30 | 刘昌赫 | 劉昌赫 | 劉昌赫 | 유창혁 | Yoo Changhyuk | GoRatings 日/中页为兼容汉字 `劉`；英语拼法需独立核对。 |
| 武宫正树 | 82 | 武宫正树 | 武宮正樹 | 武宮正樹 | 다케미야 마사키 | Takemiya Masaki | 简繁/日字形必须分别保留。 |
| 井山裕太 | 601 | 井山裕太 | 井山裕太 | 井山裕太 | 이야마 유타 | Iyama Yuta | 棋谱中的同名适用性待审。 |
| 张栩 | 108 | 张栩 | 張栩 | 張栩 | 장쉬 | Chang Hsu | 台湾籍、日本棋院；英语用日本棋院档案拼法。 |
| 藤泽秀行 | 293 | 藤泽秀行 | 藤澤秀行 | 藤沢秀行 | 후지사와 히데유키 | Fujisawa Hideyuki | 繁中 `澤` 与日文 `沢` 不可混用。 |
| 徐奉洙 | 49 | 徐奉洙 | 徐奉洙 | 徐奉洙 | 서봉수 | Seo Bongsoo | 英语分词/连字符需独立核对。 |
| 王立诚 | 71 | 王立诚 | 王立誠 | 王立誠 | 왕리청 | Wang Li Chen | 日本围棋英文亦有 `O Rissei`；搜索别名需单列。 |
| 崔哲瀚 | 161 | 崔哲瀚 | 崔哲瀚 | 崔哲瀚 | 최철한 | Choi Cheolhan | 棋谱中同音/同字归属待审。 |
| 加藤正夫 | 193 | 加藤正夫 | 加藤正夫 | 加藤正夫 | 가토 마사오 | Kato Masao | 日文协会有本名与头衔，展示姓名不带头衔。 |
| Go Seigen | 856 | 吴清源 | 吳清源 | 呉清源 | 오청원 | Go Seigen | 日本棋院英文用 `Go Seigen`，GoRatings 英文页用 `Wu Qing Yuan`；两者是同人候选别名，须核对每盘原始写法。韩国棋院同时列 `우칭위안(오청원)`。 |

GoRatings 的 11 个稳定 profile ID 来自同页对局对手链接，四语 `zh/ja/ko/en` 相同 ID 的标题已逐页留存。它给出跨语线索，不单独证明棋谱身份。11×4 原文留存清单：`~/.local/share/kifu-name-audit/2026-10-03/high-volume-player-next11-root/manifest.pending.json`，SHA-256 `effee7544ce0c8dc6a3d5fa75dd53eba47dc4e3f7e517a5b403d7d8187f1035f`。例如 [吴清源四语 profile](https://www.goratings.org/zh/players/856.html) 可跨页切换同 ID。

权威对照的原文也已留存：日本棋院 [大竹](https://archive.nihonkiin.or.jp/player/htm/ki000008.htm)、[武宮](https://archive.nihonkiin.or.jp/player/htm/ki000003.htm)、[井山](https://www.nihonkiin.or.jp/player/htm/ki000385_34.html)、[張栩](https://archive.nihonkiin.or.jp/player/htm/ki000331.htm)、[藤沢](https://archive.nihonkiin.or.jp/player/htm/ki000005.htm)、[王立誠](https://archive.nihonkiin.or.jp/player/htm/ki000065.htm)、[加藤](https://archive.nihonkiin.or.jp/player/htm/ki000002.htm)、[呉清源](https://www.nihonkiin.or.jp/player/htm/ki001001.html) 的个人资料；韩国棋院 [劉昌赫](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000003)、[徐奉洙](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000008)、[崔哲瀚](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000123)、[呉清源](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=20001138) 资料。日本棋院的[英文悼念文章](https://www.nihonkiin.or.jp/english/topics/14/topics2014_12.htm)实际使用 `Go Seigen`。

简体字形由[中国围棋协会历史文章](https://wqwh.weiqi.org.cn/%E7%9F%B3%E4%BD%9B%E6%9D%8E%E6%98%8C%E9%95%90%E7%9A%84%E6%88%90%E9%95%BF%E4%B9%8B%E8%B7%AF%EF%BC%88%E4%B8%80%EF%BC%89/)、[吴清源文章](https://wqwh.weiqi.org.cn/%E7%AC%AC%E4%B8%80%E4%BD%8D%E5%A5%B3%E4%B9%9D%E6%AE%B5%EF%BC%8C%E8%8A%AE%E8%BF%BA%E4%BC%9F%E7%9A%84%E4%BC%A0%E5%A5%87/)、[张栩/崔哲瀚文章](https://wqwh.weiqi.org.cn/%E5%8F%A4%E5%8A%9B%EF%BC%8C%E6%A3%8B%E5%9D%9B%E5%85%AB%E5%86%A0%E7%8E%8B%E4%BC%A0%E5%A5%87/)、[野狐井山报道](https://foxwq.com/news/mlist/id/13081.html)及[王立诚专业报道](https://sports.sina.com.cn/go/2012-01-04/15385893876.shtml)核对。繁中字形由海峰棋院的[历史群像](https://www.haifong.org/news/content/DA2080B81489A3DA035BE72E6528AEB3)、[日本棋战报道](https://www.haifong.org/news/content/D5B0DCF41C47C92C4C3FBBC53CC6DD8B)、[应氏杯历届冠军](https://www.haifong.org/game/classes/8AD0F09CC001B8A2EEBBC376AEEAB539)、[藤澤报道](https://www.haifong.org/news/content/A37ECCFD369A6389C48235D6128E3838)、[井山报道](https://www.haifong.org/news/content/8A4A649B26B5007EC2A65A26D77B05D4)和[中央社吴清源/大竹报道](https://www.cna.com.tw/news/aspt/202411080075.aspx)核对。

这些资料只核实显示用名与可辨识人物线索。留存的权威页清单为 `authority-manifest.pending.json`，SHA-256 `bc5c033731ab588de90c270b9724857d9556f96d9f52e913da2e01dd4e027d01`；中国围棋协会三页的本机 TLS 验证失败，采用禁用本地 TLS 校验的抓取并标记 `tls_verified=false`，同时由检索引擎读到了同 URL 正文，补充清单 `supplement-manifest.pending.json` SHA-256 `ab4d623a8d8bf992625fb10445b98c276087d307f3766a4e6a25a4981996c8b8`；井山简体补充清单 `supplement-iyama.pending.json` SHA-256 `7318092b60abbd32a325a22521454725139e4cfc02506c57a4040add7ca8b50a`。所有资料均在仓库外受控目录，不进入 Git。

下一步是独立审核五语资料、解决英语变体和 `Go Seigen` 的身份/别名，再对未关联的 10 名判断有限 raw 适用范围；对既有关联的 `Go Seigen` 核对人物 ID `1` 与原始棋谱来源。六种次要语言按已核读音及统一规则离线批量生成、独立抽核后入候选；不能把资料候选数算作已部署覆盖。
