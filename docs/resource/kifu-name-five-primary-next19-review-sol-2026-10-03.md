# 下一批 19 人五种主语言名称证据独立复核

2026-10-03，北京时间。**91 个精确显示值 PASS，4 个 HOLD；15 人五语全部通过。** 结论仅为名称证据：正式导入候选、人物／QID 绑定、SGF 归属、FK、前像和数据库写入批准均为 **0**。原候选包保持 pending；未改代码、写数据库、部署或提交 Git。

审核者 `/root/honinbo_composition_runtime_sol`，没有生产这批候选。运行时标明 GPT-6，具体型号／配置未独立认证；签署文件记录审核者声明和 SHA 绑定，不冒充模型身份的密码学认证。完成时间 `2026-10-02T19:25:55.844545+00:00`。

## 核查方法与边界

输入为 [next19 候选说明](kifu-name-five-primary-next19-candidates-2026-10-03.md)的固定 JSONL，bytes SHA `438012112ce330e6faf097d26073d4472360c76dbe8cf212d7830aa1a595e8ec`。逐项读取原始协会名册、Wikidata 分组响应、四语 GoRatings 榜单 HTML、原留存中文人物页及海峰棋院正文；重新核对文件哈希、完整姓名边界、站内 ID、完整生日和上下文。另独立留存同 ID 的英／日／韩人物页 **57 份**，全部 HTTP 200，标题与候选、完整 DOB 与名册逐项一致，页面实际含相应语种的数据标签及棋局表。[中国围棋协会名册](https://www.weiqi.org.cn/player/professional)、[GoRatings](https://www.goratings.org/en/)

19 人的协会姓名／编号／DOB、GoRatings 同 ID 姓名／DOB，以及 Wikidata 明确 `zh/en/ja/ko` 标签、日精度生日和 `P2805` 站内 ID 全相合。GoRatings 榜单和人物页仍是同一出版方；Wikidata 只作结构化交叉线索。此对应关系支持人物资料语境，不能替代正式实体或棋谱身份审核。

繁中逐项读回 [2019 海峰报道](https://haifong.org/news/content/C95D148BBA79CCD1F15DA6B77FE4BF9D)及三篇后续原始 HTML，核对固定正文行和相邻行，不接受 substring 命中。19 个繁中值全部确实印在正文中，但人物对应不足的两项仍 HOLD。阶段词、读音体系、英文姓／名分词均不在本次批准范围；例如英文只通过来源实际写出的 `Yangu Yunqi`，没有据此签署转写读音。

## 逐人／逐语结果

表中未标 HOLD 的值为 PASS；只覆盖所列精确值，不批准同音、异体或自动转换后的其他值。每一格的来源 URL／字节 SHA、人物 ID／DOB、原候选行 SHA 和决定均在 protected packet。

|原名／协会编号|CN|TW|JP|KO|EN|
|---|---|---|---|---|---|
|丁世雄 / CWA000530|`丁世雄`|`丁世雄`|`丁世雄`|`딩스슝`|`Ding Shixiong`|
|严古韵琪 / CWA000867|`严古韵琪`|`嚴古韻琪`|`严古韵琪` **HOLD**|`옌구윈치`|`Yangu Yunqi`|
|何天予 / CWA000826|`何天予`|`何天予`|`何天予`|`허톈위`|`He Tianyu`|
|孔祥明 / CWA000742|`孔祥明`|`孔祥明`|`孔祥明`|`쿵샹밍`|`Kong Xiangming`|
|尹航 / CWA000085|`尹航`|`尹航`|`尹航`|`인항`|`Yin Hang`|
|常昊 / CWA000008|`常昊`|`常昊`|`常昊`|`창하오`|`Chang Hao`|
|曹大元 / CWA000012|`曹大元`|`曹大元`|`曹大元`|`차오다위안`|`Cao Dayuan`|
|李康 / CWA000041|`李康`|`李康`|`李康`|`리캉`|`Li Kang`|
|李星彤 / CWA000844|`李星彤`|`李星彤`|`李星彤`|`리싱퉁`|`Li Xingtong`|
|毛彦新 / CWA000744|`毛彦新`|`毛彥新` **HOLD**|`毛彦新`|`마오옌신`|`Mao Yanxin`|
|王昊天 / CWA000715|`王昊天`|`王昊天`|`王昊天`|`왕하오톈`|`Wang Haotian`|
|王禹程 / CWA000748|`王禹程`|`王禹程`|`王禹程`|`왕위청`|`Wang Yucheng`|
|田瑞祺 / CWA000408|`田瑞祺`|`田瑞祺`|`田瑞祺`|`톈루이치`|`Tian Ruiqi`|
|石豫来 / CWA000644|`石豫来`|`石豫來`|`石豫来`|`스위라이`|`Shi Yulai`|
|范蔚菁 / CWA000264|`范蔚菁`|`范蔚菁`|`范蔚菁`|`판웨이징`|`Fan Weijing`|
|蒋辰中 / CWA000283|`蒋辰中`|`蔣辰中` **HOLD**|`蒋辰中`|`장천중`|`Jiang Chenzhong`|
|蔡文鑫 / CWA000656|`蔡文鑫`|`蔡文鑫`|`蔡文鑫`|`차이원신`|`Cai Wenxin`|
|薛宏哲 / CWA000737|`薛宏哲`|`薛宏哲`|`薛宏哲`|`쉐훙저`|`Xue Hongzhe`|
|韩卓然 / CWA000710|`韩卓然`|`韓卓然`|`韩卓然` **HOLD**|`한줘란`|`Han Zhuoran`|

## HOLD 与角色判断

- **JP 严古韵琪：** [同 ID 日文页](https://www.goratings.org/ja/players/2465.html)及明确日文标签仍用 `严／韵`。本轮未留存能排除源语回退的另一个实际日语用名依据；未断言该形式错误，也未批准替代值。
- **JP 韩卓然：** [日本棋院 2019 梦百合杯正文](https://www.nihonkiin.or.jp/match_news/match_result/42_39.html)使用 `韓卓然初段（中国）`，与固定候选 `韩卓然` 不同。保留冲突，新值另建候选。
- **TW 毛彦新：** 2019 海峰名单确为 `毛彥新 6 段`（业余），而同 ID 专业人物页最早列出的对局在 2019 年 8 月。原报道没有生日／稳定 ID，本轮没有把六月业余人物与后来的职业人物连起来的可靠锚点；合理年龄和同字不足以通过。其 JP 值 `毛彦新` 另见[日语棋局资料页](https://kifudepot.net/kifucontents.php?id=Z2mfp8vQrQtd1NVZlg%2BxXg%3D%3D)，不因 `彦` 与繁中字不同就自动拒绝。
- **TW 蒋辰中：** 两处 `蔣辰中` 均在 2022 海峰报道的领队／教练栏，字面清楚，但没有生日／段位／稳定 ID 或独立锚点对应到本候选职业人物。因此 HOLD；其余四语的人物页证据通过。

**常昊、曹大元、李康、蒋辰中在候选引用的繁中材料中均为 staff-only。** 前三人的名字证据通过，补充依据是[パンダネット 2020 围甲资料](https://www.pandanet.co.jp/event/chinaevent/backnumber2020.htm)的同职业姓名、段位、相容年龄及对应队伍教练身份；这是跨资料人物语境判断，没有批准他们是这些文章中的参赛者，更未批准任何 SGF 槽位。蒋辰中缺少这类独立对应锚点。

严古韵琪的 TW 值在 2019 原文确为业余五段；另留存[广西日报／国际在线 2019 报道](https://gx.cri.cn/20190830/bcbff3b9-3741-3e34-eb51-28c06295ae07.html)，同完整姓名、2005 年出生及五段竞赛经历相合，补强人物对应。该报道只核出生年，没有从年龄反推完整 DOB。另一补充网页因证书域名不匹配未采用，失败也写入 capture manifest。

`石豫来` 的 JP 值另有上引パンダネット日语正文、三段和相容年龄支持，`来` 不等于未经核查的源语回退。没有将简繁转换当作日文自动判据。

## 同名与碰撞

按运行时 `NFKC → casefold → 合并空白` 核对本批同语候选、六期 GoRatings 索引和冻结目录：组内碰撞 **0**；四语精确值在该索引中均只对应候选站内 ID；与冻结目录 canonical name／alias／同语 display name 的碰撞 **0**。目录 SHA `420ed4a10445a8d50c49d1132cd47ee8eee893b871dce2a968e8593775fa6105`，含 876 人、22 个显示名和 23 条别名；**没有重查当前数据库**。零碰撞不证明归属，也不表示全网不存在同名。

留存 Wikidata 搜索线索中，丁世雄、尹航、常昊、曹大元、李康、蔡文鑫均有多个同字人物／消歧项；特别是尹航、常昊、李康还有运动员或其他职业同名。使用完整 DOB、围棋人物描述和 GoRatings ID 排除字面自动合并，原搜索线索逐人保留，未批准任何其他 QID。

2019 海峰同一篇另见 `李 康 七段`（正文第 287、385 行），与当前协会六段资料有差异。该条不在本候选引用的教练 occurrence 中，本轮不把它自动并入李康候选，也不拿它批准参赛或 SGF 身份。

## 哈希绑定产物

目录：`~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-primary-next19-review-sol/`（0700；文件 0600）。原候选每行的 bytes／规范 JSON SHA、全部原始来源 URL／body SHA、逐语决定和角色限制均在 packet；Wikidata 原分组请求 URL 未留存，只有真实实体定位 URL 和分组响应 SHA。

|产物|SHA-256|
|---|---|
|`reviewed-19.jsonl`|`65b7dacde279288cb4e13535d53c24dc128c42be0a6eb2b5e76e88985ae121be`|
|`complete-five-pass-15.scope.json`|`660addd0ecb14ae9bd44ff7ff9e8e82be4bf915f4a4f75370d7c816435e3b5f7`|
|`name-evidence-pass-91.scope.json`|`958ce0cc9f6e553ca6aec152791c983e0059b1443e72aac6ffe19fe353fe5246`|
|`name-evidence-hold-4.scope.json`|`feeac085cc590ea689362cfea5e04c94e1fb87509b32b14b76480e1f04c1fc7f`|
|`source-bindings.json`|`90c807266773071d7fa86331decaaf146d59ceb3aebc7c597d1982730f2a3389`|
|`review-manifest.json`|`f2589cf5c62b7341cdddf3b474ca38563c884a058673f543eff80fb8d2310594`|
|`review-signature.json`|`d83042be2f762a6f45b1d0f629517df99db279e1281aaa920fa352c710eecccb`|

本批 3,135 个库内原始槽位仅为候选背景计数，关联批准为 0。全部产物均为有限名称证据审核，不能直接导入。
