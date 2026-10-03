# 五名中国棋手：主五语逐名来源候选（Luna）

研究日：2026-10-03；producer `/root/cao_source_luna`；运行模型 `gpt-6-luna`。本文件整理候选与可审来源，不是独立审核、姓名签批、人物身份 FK、raw 槽授权或数据库写入批准。候选数据与引用哈希保存在个人受保护目录 `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-primary-main5-candidates-luna/`。

## 依赖与已签审核链

按父代理指示复用已完成来源研究，不重抓同一批页面。最新修正版 [95 格独立来源审核](kifu-name-five-primary-frequency-41-60-95-aux-span-corrected-independent-review-sol-2026-10-03.md) 签署 **95 source-name PASS / 0 HOLD**，且四项辅助 `actual_name_span` 修正 **4/4 PASS**；本批 25 格在此包内均有精确 source row。本次选择的是该修正版记录的原文和值；新建候选 JSON 仍标记 pending，不继承为本次候选包审批。

| 依赖 | 固定对象 / SHA-256 |
|---|---|
| 修正版来源审核记录 | `five-primary-41-60-95-aux-span-corrected-independent-review-sol/review.manifest.json` · `db8e02d5a52e45cf58179e7b14f86dd671f238553880940d943d55f6b3937867` |
| 95 格候选文件 | `candidates.pending.json` · `f69ae74059cd547c0615c733c47fb92747a3d4d916481234e4d4ccaa3de6e325` |
| 修正版来源清单 | `sources.manifest.json` · `4ac657425e9057ea0458c7748479adf1d16ecd9e41e28a84b4c407f3ba471c7b` |
| 修正版总 manifest | `manifest.json` · `8794c45ae9d05cfe8332dfbcee716072640b41a75d139c2d4c5708d480768899` |
| 固定出版方 registry | `kifu-name-source-registry-2026-10-02.8.json` · `2cfd665b215d1e8651ec9313953504d7c9ac0536d02548bfb8b8f80210593911` |
| 五条已签官方原名 / GoRatings 同人锚点集合 | `raw-anchors-v3.approved.json` · `0a0c13fdb84a2f34706203bf758043d7f0054ef6dbd18629afa77c7d7fd37b78` |
| 已批准精确 raw-scope 文件 | `raw-display-scopes.approved.json` · `583c459d153c1a6ab6fc005f10b68784ca76138e6f3ac884e576cc046a31dc15`; binding · `7606b9b1f03d27d3822d28067bbcaff4635b5dab57a66bfc0463991bcec12bd1` |
| 本次 25 格候选 JSON | `candidates.pending.json` · `64e891f5f3f2cae426b652dc6287af783662c0e91731b0d7b81a43776bf77d7f` |

锚点已签者 `/root/five_cn_v3_independent_review_sol` 仅批准各自中文原名和英文 reading；原 review 明确排除人物 FK 与数据库写入。raw scope 是五组既有精确槽位总计 **4,358**，不据此宣称每条原始棋谱身份已绑定。五条完整 anchor record SHA、CWA ID、GoRatings profile ID、DOB、scope SHA 如下：

| 原名 | CWA 稳定 ID / GoRatings ID | DOB | 原始 scope 槽数 | 完整已签 anchor SHA-256 | 精确 scope SHA-256 |
|---|---|---|---:|---|---|
| 唐韦星 | `CWA000040` / GoRatings `897` | `1993-01-15` | 858 | `45f0bf09fba99d594f44165a7edab06ec660a51816936f79fb94c3a27dd7c87c` | `65505d8fe7de985f966a08d82fea1e4b2a2d9e1da5ea74aec4662588a650231a` |
| 杨鼎新 | `CWA000062` / GoRatings `1193` | `1998-10-19` | 864 | `8cb311fc1d691febb15e80d81c9f6c31548ec42bca5b2283df3089d822e79fd4` | `9b184c3d5e07141a3fd9a7d58ab119c20c28dc1d0ca0b61d695e8eeb2c0cdb4d` |
| 檀啸 | `CWA000018` / GoRatings `995` | `1993-03-10` | 911 | `b83f1e6ca41806687b8e7c0223afc357856fbb2da1be409ead6e79018b3bd241` | `f501e78501e5246f8435fd983e1bb7a3e05f3ef1de15fafdf30d357fb63d647a` |
| 胡耀宇 | `CWA000025` / GoRatings `184` | `1982-01-18` | 868 | `511c54aaa004a0262537ca9685caa457c39e3edd5f1a7045f553a3578977f74c` | `c23b71ed4f6910dfa92e6aeacf9c08d6875998ff7433fd68a8bbd52e3755c40d` |
| 连笑 | `CWA000052` / GoRatings `1082` | `1994-04-08` | 857 | `3dc02b1ff6a19bd265e2c6732db7e465c650f641b6fcef3f3ae936fc1c6fde31` | `7190be57ee3dba0a7c2fb61cb0546ca4502edfef7050abe8dd8891c0d9ce8dac` |

身份链是已签 CWA 职业名录原名 / 完整生日 → GoRatings `/zh/` 同 ID、同 DOB 中文身份桥 → 同 ID 的英语读音页，并有逐人正式锚点。`/zh/` 页面只作中文桥接身份，不算 `cn` 或 `tw` 候选。下面每个 GoRatings 目标页均来自其目标语 URI，保全的实际 `html lang` 与 H1 均为目标语言；逐页 DOB 与上述同一 ID 一致。所有行可在最新 95 格审核记录按 `candidate_id` 查到 prior source-name PASS。

## 25 个主五语候选与正文定位

来源类型：CWA 中国围棋协会职业名录为 `cn` 官方源；海峰棋院专业赛事/棋士资料为 `tw` 职业围棋来源；日本棋院官方历史对局页支持唐、杨的 `jp` 名字，其余日文候选由 GoRatings 日文职业排名档案直接显示；GoRatings 英/韩档案直接支持 `en`/`ko` 实际显示。GoRatings 多语页是同一出版者，不当作五个独立来源。正文定位、观测语种、确切姓名跨度、候选值和原始 body hash 均逐行列出。

| 原名 / GoRatings ID | 语标 | 候选 | 正面来源、目标语 / 正文定位 | 正文 SHA-256 | 当前候选状态 / 冲突 |
|---|---|---|---|---|---|
| 唐韦星 / `897` | `cn` | `唐韦星` | [weiqi-association](https://wqapi.cwql.org.cn/playerInfo/professional/list) · 实际语种 `zh-Hans` · data.Z09[43].playerName; 同对象 birthday=1993-01-15 | `18ba2a04efdca69d47528cbe703d9c54e1005b7f986af782434cbc3f1dd316f9` | 来源研究候选；此前独立来源审核 PASS。 无已知显示冲突。 |
| 唐韦星 / `897` | `tw` | `唐韋星` | [haifong](https://www.haifong.org/news/content/551BC5AC6433866A399BA046C8A9AF22) · 实际语种 `zh-Hant-TW` · 留存提取文本第80行，姓名原文 `唐韋星`；比赛/冠军项目上下文 | `ba1e7b2a6f159b37b676256faed2e7bde4c034f97f11e21fbba5820f2f2646ff` | 来源研究候选；此前独立来源审核 PASS。 无已知显示冲突。 |
| 唐韦星 / `897` | `jp` | `唐韋星` | [nihon-kiin-archive-jp](https://archive.nihonkiin.or.jp/match/2014/03/33_17.html) · 实际语种 `ja` · 2014-03-18 百霊杯一回战棋院结果表姓名格原文 `唐　韋星`；候选去除排版用空格 | `f4a7c29a68f42e653c2429eef2988744915f9e458ef3103f8a238b2b292035e2` | 来源研究候选；此前独立来源审核 PASS。 候选来自棋院直接日文；同 ID GoRatings /ja/ H1 是简体 `杨鼎新` / `唐韦星`，不采作日文候选。 |
| 唐韦星 / `897` | `ko` | `탕웨이싱` | [goratings-ko](https://www.goratings.org/ko/players/897.html) · 实际语种 `ko` · HTML `html lang=ko`；`<h1>`=`탕웨이싱`；同页DOB=1993-01-15 | `c67a6866506bc780ed38270224de8639f41fe1f1ef72f0a758a760a373687c3d` | 来源研究候选；此前独立来源审核 PASS。 无已知显示冲突。 |
| 唐韦星 / `897` | `en` | `Tang Weixing` | [goratings-en](https://www.goratings.org/en/players/897.html) · 实际语种 `en` · HTML `html lang=en`；`<h1>`=`Tang Weixing`；同页DOB=1993-01-15 | `7eb06f7f883c62fd286be39beb2c5b1a7fb9172871042d47df4a1aeae7db0924` | 来源研究候选；此前独立来源审核 PASS。 无已知显示冲突。 |
| 杨鼎新 / `1193` | `cn` | `杨鼎新` | [weiqi-association](https://wqapi.cwql.org.cn/playerInfo/professional/list) · 实际语种 `zh-Hans` · data.Z09[58].playerName; 同对象 birthday=1998-10-19 | `18ba2a04efdca69d47528cbe703d9c54e1005b7f986af782434cbc3f1dd316f9` | 来源研究候选；此前独立来源审核 PASS。 无已知显示冲突。 |
| 杨鼎新 / `1193` | `tw` | `楊鼎新` | [haifong](https://www.haifong.org/news/content/551BC5AC6433866A399BA046C8A9AF22) · 实际语种 `zh-Hant-TW` · 留存提取文本第83行，姓名原文 `楊鼎新`；比赛/冠军项目上下文 | `ba1e7b2a6f159b37b676256faed2e7bde4c034f97f11e21fbba5820f2f2646ff` | 来源研究候选；此前独立来源审核 PASS。 无已知显示冲突。 |
| 杨鼎新 / `1193` | `jp` | `楊鼎新` | [nihon-kiin-archive-jp](https://archive.nihonkiin.or.jp/match/2014/03/33_17.html) · 实际语种 `ja` · 2014-03-18 百霊杯一回战棋院结果表姓名格原文 `楊　鼎新`；候选去除排版用空格 | `f4a7c29a68f42e653c2429eef2988744915f9e458ef3103f8a238b2b292035e2` | 来源研究候选；此前独立来源审核 PASS。 候选来自棋院直接日文；同 ID GoRatings /ja/ H1 是简体 `杨鼎新` / `唐韦星`，不采作日文候选。 |
| 杨鼎新 / `1193` | `ko` | `양딩신` | [goratings-ko](https://www.goratings.org/ko/players/1193.html) · 实际语种 `ko` · HTML `html lang=ko`；`<h1>`=`양딩신`；同页DOB=1998-10-19 | `778c2c48b04fe02488ccbe2ff6ddb446f12bff691fb93bed022c59de09060055` | 来源研究候选；此前独立来源审核 PASS。 无已知显示冲突。 |
| 杨鼎新 / `1193` | `en` | `Yang Dingxin` | [goratings-en](https://www.goratings.org/en/players/1193.html) · 实际语种 `en` · HTML `html lang=en`；`<h1>`=`Yang Dingxin`；同页DOB=1998-10-19 | `67e1f929e8464ea756fc9d4677a9ce4c002fef944d85528cc93f2697b2fdc574` | 来源研究候选；此前独立来源审核 PASS。 无已知显示冲突。 |
| 檀啸 / `995` | `cn` | `檀啸` | [weiqi-association](https://wqapi.cwql.org.cn/playerInfo/professional/list) · 实际语种 `zh-Hans` · data.Z09[41].playerName; 同对象 birthday=1993-03-10 | `18ba2a04efdca69d47528cbe703d9c54e1005b7f986af782434cbc3f1dd316f9` | 来源研究候选；此前独立来源审核 PASS。 无已知显示冲突。 |
| 檀啸 / `995` | `tw` | `檀嘯` | [haifong](https://www.haifong.org/game/classes/889B583FD295AC653FB6B4B0AA0DA5CC) · 实际语种 `zh-Hant-TW` · 留存提取文本第79行，姓名原文 `檀嘯`；比赛/冠军项目上下文 | `0fde45b3c5deae8be98c436dbc034cbb766a4f910df6781165df34d9a8b3cb71` | 来源研究候选；此前独立来源审核 PASS。 无已知显示冲突。 |
| 檀啸 / `995` | `jp` | `檀嘯` | [goratings-ja](https://www.goratings.org/ja/players/995.html) · 实际语种 `ja` · HTML `html lang=ja`；`<h1>`=`檀嘯`；同页DOB=1993-03-10 | `0a24cf487408677813856e0551e8b1bc3048d0380753674825d1934bae1e2919` | 来源研究候选；此前独立来源审核 PASS。 无已知显示冲突。 |
| 檀啸 / `995` | `ko` | `탄샤오` | [goratings-ko](https://www.goratings.org/ko/players/995.html) · 实际语种 `ko` · HTML `html lang=ko`；`<h1>`=`탄샤오`；同页DOB=1993-03-10 | `44b1bdf1446fd4c49737bcd32ff9c8867ee387a6c945418a9df2c6fc954794e1` | 来源研究候选；此前独立来源审核 PASS。 无已知显示冲突。 |
| 檀啸 / `995` | `en` | `Tan Xiao` | [goratings-en](https://www.goratings.org/en/players/995.html) · 实际语种 `en` · HTML `html lang=en`；`<h1>`=`Tan Xiao`；同页DOB=1993-03-10 | `b06b60a3b038d64995b4f398740d703143386d9fcd4033131917b42b56e727df` | 来源研究候选；此前独立来源审核 PASS。 无已知显示冲突。 |
| 胡耀宇 / `184` | `cn` | `胡耀宇` | [weiqi-association](https://wqapi.cwql.org.cn/playerInfo/professional/list) · 实际语种 `zh-Hans` · data.Z08[10].playerName; 同对象 birthday=1982-01-18 | `18ba2a04efdca69d47528cbe703d9c54e1005b7f986af782434cbc3f1dd316f9` | 来源研究候选；此前独立来源审核 PASS。 需修 anchor locator：签署 anchor 误记 Z09；原始 API 实际在 Z08[10]。此候选行已按真实 JSON 位置列出，修复前阻止下游 anchor 证据重用。 |
| 胡耀宇 / `184` | `tw` | `胡耀宇` | [haifong](https://www.haifong.org/news/content/4496661D67E47D9010BF3A4BA19CF293) · 实际语种 `zh-Hant-TW` · 留存提取文本第137行，姓名原文 `胡耀宇`；比赛/冠军项目上下文 | `30427986314f1b887040091fb39186fffc2e1fd8877edf9f40f8c60b78dc82c4` | 来源研究候选；此前独立来源审核 PASS。 无已知显示冲突。 |
| 胡耀宇 / `184` | `jp` | `胡耀宇` | [goratings-ja](https://www.goratings.org/ja/players/184.html) · 实际语种 `ja` · HTML `html lang=ja`；`<h1>`=`胡耀宇`；同页DOB=1982-01-18 | `094312c4418831fb5613ab0321ba2732a215911df8cff9b5d918a7e03fb178d4` | 来源研究候选；此前独立来源审核 PASS。 无已知显示冲突。 |
| 胡耀宇 / `184` | `ko` | `후야오위` | [goratings-ko](https://www.goratings.org/ko/players/184.html) · 实际语种 `ko` · HTML `html lang=ko`；`<h1>`=`후야오위`；同页DOB=1982-01-18 | `70ff48c78cf808fd7235012802231cdf8f78a660e2272ca16f44fda174991783` | 来源研究候选；此前独立来源审核 PASS。 无已知显示冲突。 |
| 胡耀宇 / `184` | `en` | `Hu Yaoyu` | [goratings-en](https://www.goratings.org/en/players/184.html) · 实际语种 `en` · HTML `html lang=en`；`<h1>`=`Hu Yaoyu`；同页DOB=1982-01-18 | `0486f51580b1e6624293a42a17ed0d40bb1ade9c904c1010d3eb371a3e2455fe` | 来源研究候选；此前独立来源审核 PASS。 无已知显示冲突。 |
| 连笑 / `1082` | `cn` | `连笑` | [weiqi-association](https://wqapi.cwql.org.cn/playerInfo/professional/list) · 实际语种 `zh-Hans` · data.Z09[21].playerName; 同对象 birthday=1994-04-08 | `18ba2a04efdca69d47528cbe703d9c54e1005b7f986af782434cbc3f1dd316f9` | 来源研究候选；此前独立来源审核 PASS。 无已知显示冲突。 |
| 连笑 / `1082` | `tw` | `連笑` | [haifong](https://www.haifong.org/game/classes/889B583FD295AC653FB6B4B0AA0DA5CC) · 实际语种 `zh-Hant-TW` · 留存提取文本第89行，姓名原文 `連笑`；比赛/冠军项目上下文 | `0fde45b3c5deae8be98c436dbc034cbb766a4f910df6781165df34d9a8b3cb71` | 来源研究候选；此前独立来源审核 PASS。 无已知显示冲突。 |
| 连笑 / `1082` | `jp` | `連笑` | [goratings-ja](https://www.goratings.org/ja/players/1082.html) · 实际语种 `ja` · HTML `html lang=ja`；`<h1>`=`連笑`；同页DOB=1994-04-08 | `1c6dd092c81bea2b76d3cee982caba0a542c45200a7b2bd2c26143c50d1ef377` | 来源研究候选；此前独立来源审核 PASS。 无已知显示冲突。 |
| 连笑 / `1082` | `ko` | `롄샤오` | [goratings-ko](https://www.goratings.org/ko/players/1082.html) · 实际语种 `ko` · HTML `html lang=ko`；`<h1>`=`롄샤오`；同页DOB=1994-04-08 | `a45876c05fdfb534f92136e6ea8c8df9c5e83ac91e081f10e7c70a06957c6e32` | 来源研究候选；此前独立来源审核 PASS。 无已知显示冲突。 |
| 连笑 / `1082` | `en` | `Lian Xiao` | [goratings-en](https://www.goratings.org/en/players/1082.html) · 实际语种 `en` · HTML `html lang=en`；`<h1>`=`Lian Xiao`；同页DOB=1994-04-08 | `bb3f45860914bd8b141f86f2525c5184002b76ea72849db29f43904952feefef` | 来源研究候选；此前独立来源审核 PASS。 无已知显示冲突。 |

## 来源日期、冲突与 HOLD 边界

- CWA API 原始响应保全于已签 anchor，HTTP 200，`2026-10-02T23:27:19.019119Z`；SHA 与表中 CWA 五格相同。源 API 本身无 HTML `lang`；中文语种根据协会 `zh-cn` 职业名录页面和 API 实际中文数据核定。
- TW 来源 manifest 记录 HTTP 200、`zh-tw`：海峰应氏杯报道 `2026-10-02T22:45:36.235621Z`；倡棋杯历史页同日 `22:45:36.290327Z`；胡耀宇职业历史文章 `2026-10-02T22:47:30.524009Z`。这些页面直接显示各候选姓名称呼，并有参赛、胜负或冠军上下文；CWA/GoRatings 的同生日同 ID 资料辅助区分人名身份。
- 保留的 GoRatings `capture-manifest.json` 有 URL、H1、`html lang`、DOB、逐页 SHA；它没有逐页 `fetched_at` 字段，故此处不补造抓取时间。每个 EN/JA/KO 候选页都是实际目标语 H1，不以 `/zh/` 页面回退。
- 日本棋院 2014-03-18 结果页 body SHA 为表中值；旧捕获清单未留下精确 fetch time。行文候选 `楊鼎新` 与 `唐韋星` 是其姓名格剔除排版用全角空格后呈现；比赛日期、对手、手番、结果与相同 profile ID 的个人历史用于同人交叉。无另外做翻译或音译。
- **已清除的辅助 metadata HOLD：** 初版 95 格审核中的四个 GoRatings-ja `actual_name_span` 错误已由修正版逐字节读取原 H1并签署 4/4 PASS。本五人中相关辅助页为 `https://www.goratings.org/ja/players/897.html` 与 `/1193.html`，实际原 H1 分别是简体 `唐韦星`、`杨鼎新`。它们不替换上表日文候选来源。
- **新增需修差异：胡耀宇 CN anchor locator。** 已签 v3 anchor 的 source record locator 写 `data.[Z09] roster row playerNo=CWA000025`，但同一哈希为 `18ba...` 的 CWA JSON 原文在 `data.Z08[10]`，playerName `胡耀宇`、playerBirthday `1982-01-18`；Z08 也与独立名录复核表一致。候选本身有正面来源，但签署 anchor 位置陈述需要生产者修订并独立复核后，才可让下游复用该锚点。此报告不修改或覆盖已签 anchor。
- 此五人 CN 与 TW 共 10 格均有当地目标语实际来源，因此不使用简繁正字生成分支。若后续发现目标语格缺少实际用名，规则只能以 `generated` 作为待审输出；代码门禁及独立完整姓名审核未通过前不批准，也不把候选描述为当地惯用名。
- 除胡耀宇 anchor 定位需修订后方可下游复用外，本五名的 25 个 exact source rows 均在修正版来源审核中 PASS。当前本文仍不新签 candidate bundle；所有最终候选格是否可批仍由独立 reviewer 处理。未批准其它历史原始拼法、别名、批次外姓名或 FK。

## 下一步（独立处理）

1. 候选审核可按上述逐格来源值、正文定位及哈希复核，不需重抓 95 格包。
2. 对胡耀宇的锚点，生产者应将 source locator 修正为原始 CWA JSON `data.Z08[10]`，重算对应 anchor content hash / 完整签署绑定，由原签署链独立重审；不在此处改写。
3. 在任何本地显示或 FK 操作之前，另需精确 scope 与本地对象/SGF 层证据审查。此文件和上游五个已签 anchors 均未授权数据库写入。

个人审计 JSON：`~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-primary-main5-candidates-luna/candidates.pending.json`，SHA-256 `64e891f5f3f2cae426b652dc6287af783662c0e91731b0d7b81a43776bf77d7f`。该 JSON 是本生产者的 candidate source crosswalk，不是审批签名。
