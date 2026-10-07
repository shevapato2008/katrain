# ret78 五人：韩文姓名有限决策

日期：2026-10-08（Asia/Shanghai）。审阅者：`/root/ret77_ko_astra_decision`；该既有子任务本次调度配置为 `gpt-6-astra`，reasoning effort `max`。此次仅审阅 ret78 的五项 KO；原始资料目录为 `/tmp/kifu-player-next5retired78-20261008/`。

本决定锚定冻结输入 `source-producer-frozen25-v1/source-matrix25.json`，SHA-256：`cd61c02678adbb30a574927db3fff655898d8df8258af39f8070a3b3dd99d5c6`；`freeze-manifest.json` SHA-256：`8d69ae8c347888d69d8f681c061f9e4d4c873eddf9138f42fe87986704c9f4a0`。已核对该包确为 25 个语言单元格、34 份原始正文，manifest 文件散列全部匹配；五项 KO 的候选值及方法与下表完全一致。此核对不扩大为其余 20 个语言单元格的完整审阅。

**决定：5/5 PASS。** 三项采用已核实的韩文刊载姓名，两项采用官方完整假名的规范转写。以下 ID 仅用于对应执行任务；本审阅不进行数据库身份绑定、SQL、签名、Git、合并或棋谱重新链接。

| 任务 owner | 来源人物 | 接受的 KO | 方法与结论 |
| --- | --- | --- | --- |
| 5110 | 村松竜一 | **무라마츠 류이치** | **PASS，`published_name`**；保留 Hangame 实际刊载形式。 |
| 5121 | 楊嘉榮；日本棋院写作楊嘉栄 | **양자룽** | **PASS，`published_name`**；以原中文姓名对应韩文刊载名，不按日语音读生成。 |
| 4256 | 大淵盛人 | **오부치 모리토** | **PASS，`published_name`**；Cyberoro 明确将这个韩文名与父亲大淵盛人对应。 |
| 5271 | 森島薫 | **모리시마 가오루** | **PASS，`normative_ja_to_ko`**；由モリシマ　カオル转写。 |
| 6669 | 久島国夫 | **히사지마 구니오** | **PASS，`normative_ja_to_ko`**；由ヒサジマ　クニオ转写。 |

## 三项实际刊载名

三份原站响应记录均为 HTTP 200。我直接读取原始 bytes，严格按 CP949 解码，并重算 SHA-256，与各自 `.capture.json` 一致。以下不是仅依据 Naver 片段的判断。

### 5110：무라마츠 류이치

[Hangame 棋手个人资料](https://baduk.hangame.com/people.nhn?m=detail&seq=1337) 的同一人物资料区实际列出 `무라마츠 류이치`、`村松竜一`、`Muramatsu Ryuichi` 和 1963-01-20。该原字、英文名、出生日期均与日本棋院对应人物资料吻合；原网页使用 HTML 数字实体表示的 `竜` 已正常解码。

- 正文：`5110-ko-hangame.body`；抓取记录：`5110-ko-hangame.capture.json`。
- 抓取时间：`2026-10-07T18:40:04.706194+00:00`。
- SHA-256：`4f509aceb566b2cbf81445756f62a5f7e1d23c7222118d4b439832f1123e779d`。

官方完整读音为 `ムラマツ　リュウイチ`。按 NIKL 转写，ツ应为쓰，规范形式会是 `무라마쓰 류이치`；保存的 Naver 结果中也存在此形式的 Namu 片段。此次接受的是已核实专业网站实际刊载的 `무라마츠 류이치`，因此标记 `published_name`，不声称 `츠` 由 NIKL 推导，也不声称只存在一种韩文写法。

### 5121：양자룽

[Netmarble 围棋专栏《대만세가 장악한 일본 바둑계》](https://baduk.netmarble.net/News/Column/ReadColumn/BbsContentView.asp?seq=6953566) 正文明确写出 `양자웬(楊嘉源)-양자룽(楊嘉榮) 형제`，上下文为赴日的台湾围棋棋手。日本棋院官方资料同时记载台湾出身、楊嘉源为亲兄，足以将此处 `양자룽` 对应到目标人物。

- 正文：`5121-ko-netmarble.body`；抓取记录：`5121-ko-netmarble.capture.json`。
- 抓取时间：`2026-10-07T18:40:03.949236+00:00`；网页标示刊载时间为 2011-12-20。
- SHA-256：`682e0d5e1d7c647acb63f057b11170781808d4afc52f6739664a0321e7d4bcbe`。

此人的原姓名按中文 `楊嘉榮` 处理。官方日语资料的 `ヨウ　カエイ` 是日语音读，另列 `ヤン　チァーロン`；本项没有将中文原名错误标为日语原名，也没有用 `ヨウ カエイ` 制造 KO 候选。Naver 的“양자롱”搜索建议只属于搜索界面，不能替代正文刊载的 `양자룽`。

### 4256：오부치 모리토

[Cyberoro 的大淵浩太郎资料页](https://www.cyberoro.com/info/player_view.oro?prpl_code=20000504) 在特记事项中明确写出 `오부치 모리토(大淵盛人)가 부친`，即该姓名对应父亲大淵盛人。日本棋院大淵盛人本人档案又明确记载大淵浩太郎为其亲子，父子关系双向吻合。

- 正文：`4256-ko-cyberoro-family.body`；抓取记录：`4256-ko-cyberoro-family.capture.json`。
- 抓取时间：`2026-10-07T18:40:04.600089+00:00`。
- SHA-256：`f34a73efcda999bd23175b466160d22d0ea1f275b567684fe9fa55c326c5f736`。

这里仅以父亲那一句证明韩文姓名；页面主体是儿子 `오부치 고타로 [大淵浩太郞]`。页面头部的段位、空生日、出身地及入段／升段履历均不转入父亲资料。父亲官方完整读音 `オオブチ　モリト` 与接受的韩文名亦吻合，但本项已有实际刊载依据，采用 `published_name`。

## 两项规范转写

| owner | 实际官方完整读音 | 逐音转写 |
| --- | --- | --- |
| 5271 | モリシマ　カオル | モ・リ・シ・マ → 모・리・시・마；独立给定名的词首カ→가，再接オ→오、ル→루，得到 **모리시마 가오루**。カオル中的オ保留。 |
| 6669 | ヒサジマ　クニオ | ヒ・サ・ジ・マ → 히・사・지・마；独立给定名的词首ク→구，再接ニ→니、オ→오，得到 **히사지마 구니오**。 |

沿用本审阅者在前批已实际阅读的三份 NIKL 原始规则，不重新展开规则研究：

- [日本人名表记原则](https://korean.go.kr/front/page/pageView.do?mn_id=97&page_id=P000146)，正文 SHA-256 `91ca51068bdf397629c183aa6b537d3ace51ba1a852c72e9ba8cb358a0422f38`。
- [日语假名对照表](https://www.korean.go.kr/front/page/pageView.do?mn_id=97&page_id=P000108)，正文 SHA-256 `94edbf8feed1569ed74c4700b4188511a7cccb226d879dd5d7fd1a49f3deb220`。表中词首カ／ク分别为가／구，シ为시、ジ为지。
- [日语细则](https://www.korean.go.kr/front/page/pageView.do?mn_id=97&page_id=P000129)，正文 SHA-256 `66b46fad43c49262a56cdc572f63244229f006f221e5ff7bfe94f1311d346f55`。本批两项规范生成姓名均无需要省略的长音或需要处理的促音。

两项均保留姓在前、名在后，以一个空格分隔。它们是规范生成结果；搜索片段的词形呼应不升级为原站刊载名认证。

## 官方人物对应资料

以下姓名、英文和假名字段均从对应原始正文读取；生日与亲属关系仅用于来源之间的对应，不代表本审阅已查验数据库 owner。

| owner | 官方资料与核对字段 | 原始正文／SHA-256 |
| --- | --- | --- |
| 5110 | [ki000211](https://archive.nihonkiin.or.jp/player/htm/ki000211.htm)：村松竜一；Muramatsu Ryuichi；ムラマツ　リュウイチ；1963/1/20 | `5110-official-retry.body`；`0a043f8f18db11c2f7092366172243f07de1212916f19e4fde45e5f8e1145863` |
| 5121 | [ki000243](https://archive.nihonkiin.or.jp/player/htm/ki000243.htm)：楊嘉栄；Yang Chia Jung；ヨウ　カエイ／ヤン　チァーロン；台湾出身；楊嘉源为亲兄 | `5121-official-cwi.body`；`6fa6e3132a6a829b3c6e638c8c45e1bbda8faf1405660a22ab09a29f4a8b390e` |
| 4256 | [ki000183](https://archive.nihonkiin.or.jp/player/htm/ki000183.htm)：大淵盛人；Obuchi Morito；オオブチ　モリト；大淵浩太郎为亲子 | `4256-official-cwi.body`；`1e02b97cf27c19e7114805abbe55fe65904866af5ade8cfc53ab6d9d00699a9e` |
| 5271 | [ki000082](https://archive.nihonkiin.or.jp/player/htm/ki000082.htm)：森島薫；Morishima Kaoru；モリシマ　カオル；1939/1/29 | `5271-official.body`；`ca645a2a7bcf839a1706a058f551d8538cdd1b9a18660473e6ff293f853f3eb2` |
| 6669 | [ki000056](https://archive.nihonkiin.or.jp/player/htm/ki000056.htm)：久島国夫；Hisajima Kunio；ヒサジマ　クニオ；1946/6/5 | `6669-official.body`；`0743165c9a3b87e4735326ac66cac8d9db444e01027a66daa06abee1878ae3db` |

文件名中的 `official-cwi` 是捕获文件命名，不改变出版者：这两份正文实际 URL 均为日本棋院官方档案。

## 十个查询的有限核对

已读取 `ko-finite-v1/` 内十份 Naver 原始 HTML。捕获记录均为 HTTP 200；页面标题与记录中的查询一致，并有实际结果区或明确的无结果区。它们只用于有限发现／冲突检查，不证明全网不存在其他韩文写法。

| owner | 原字查询与实际观察 | 候选查询与实际观察 |
| --- | --- | --- |
| 5110 | `村松竜一 바둑`：发现 Hangame 的 `무라마츠 류이치` 资料链接，原站正文已核实。 | `무라마쓰 류이치 바둑`：Namu 棋战片段出现规范形式，保留与刊载形式的差异。 |
| 5121 | `楊嘉榮 바둑`：有韩国棋院赛事表等结果；不以泛结果代替名字证据。 | `양자룽 바둑`：出现 Netmarble 专栏链接及“양자롱”搜索建议；接受原站正文实际词形。 |
| 4256 | `大淵盛人 바둑`：Cyberoro 父亲说明及围棋栏目结果。 | `오부치 모리토 바둑`：人物卡及围棋结果；最终刊载证据采用已读取的 Cyberoro 父亲语句。 |
| 5271 | `森島薫 바둑`：结果主要是围棋商品，未构成韩文人物名证明。 | `모리시마 가오루 바둑`：Namu 第37／39届本因坊战片段出现候选词形；只作线索。 |
| 6669 | `久島国夫 바둑`：正常显示本次查询无结果；这不证明该人没有韩文名称。 | `히사지마 구니오 바둑`：Namu 第16／14届新名人战等片段出现候选词形；只作线索。 |

每项原始正文、URL、抓取时间及散列保存在该目录的 `<owner>-original_go.body/.capture.json` 与 `<owner>-candidate_go.body/.capture.json`。本次未追加搜索，也未把搜索片段或空结果冒充已读取的第三方原站姓名证据。

采用结果为开头表内的五个值：**3 个 `published_name`，2 个 `normative_ja_to_ko`**。刊载来源之间的对应与两项规范推导已充分核对，本批 KO 决策完成。
