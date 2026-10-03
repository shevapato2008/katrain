# next20 ranks69–88：修正版五主语言独立来源复审

日期：2026-10-03；复审者 `/root/raw7_high_yield_binder_sol`（GPT-6；具体子型号未独立暴露）。制包者 Luna，二者分离。本复审只签原文用名和外部来源对应关系，无 raw slot、数据库身份、FK、SGF 归属或写入批准。

## 结论

18 人 × 5 语言共90格：**79 PASS / 11 HOLD**，尚未五语言全部完成。旧 **63 PASS** 的候选对象、URL/文件/hash引用和原始正文 bytes 全部逐项相同，才予以延续；原27 HOLD中，新增来源的17格为 **16 PASS / 1 HOLD**，另外10格继续 HOLD。

| 语言 | PASS | HOLD |
|---|---:|---:|
| cn | 13 | 5 |
| tw | 13 | 5 |
| jp | 18 | 0 |
| ko | 17 | 1 |
| en | 18 | 0 |

已核94份原始响应体 SHA-256、76份 GoRatings 本地化 profile，并确认修正版CSV与bundle的全部90格一致。排名范围与原包相同；排除既审邱峻(rank81)、王檄(rank85)。频次排序不构成导入槽位适用性批准。

## 全90格

✓ 表示该精确发布用名的来源 PASS；HOLD 不接受对应候选值。

| Rank / 原名 | cn | tw | jp | ko | en |
|---|---|---|---|---|---|
| 69 申旻埈 | 申旻埈 ✓ | 申旻埈 ✓ | 申旻ジュン ✓ | 신민준 ✓ | Shin Minjun ✓ |
| 70 林君谚 | HOLD | 林君諺 ✓ | 林君諺 ✓ | 린쥔옌 ✓ | Lin Junyan ✓ |
| 71 罗洗河 | 罗洗河 ✓ | 羅洗河 ✓ | 羅洗河 ✓ | 뤄시허 ✓ | Luo Xihe ✓ |
| 72 於之莹 | HOLD | 於之瑩 ✓ | 於之瑩 ✓ | 위즈잉 ✓ | Yu Zhiying ✓ |
| 73 片冈聪 | 片冈聪 ✓ | HOLD | 片岡聡 ✓ | 가타오카 사토시 ✓ | Kataoka Satoshi ✓ |
| 74 林立祥 | 林立祥 ✓ | 林立祥 ✓ | 林立祥 ✓ | 린리샹 ✓ | Lin Lixiang ✓ |
| 75 Kitani Minoru | HOLD | 木谷實 ✓ | 木谷實 ✓ | 기타니 미노루 ✓ | Kitani Minoru ✓ |
| 76 桥本宇太郎 | 桥本宇太郎 ✓ | HOLD | 橋本宇太郎 ✓ | HOLD | Hashimoto Utaro ✓ |
| 77 山城宏 | 山城宏 ✓ | HOLD | 山城宏 ✓ | 야마시로 히로시 ✓ | Yamashiro Hiroshi ✓ |
| 78 谢赫 | 谢赫 ✓ | 謝赫 ✓ | 謝赫 ✓ | 셰허 ✓ | Xie He ✓ |
| 79 党毅飞 | 党毅飞 ✓ | 黨毅飛 ✓ | 党毅飛 ✓ | 당이페이 ✓ | Dang Yifei ✓ |
| 80 许皓鋐 | HOLD | 許皓鋐 ✓ | 許皓鋐 ✓ | 쉬하오훙 ✓ | Xu Haohong ✓ |
| 82 藤泽里菜 | 藤泽里菜 ✓ | 藤沢里菜 ✓ | 藤沢里菜 ✓ | 후지사와 리나 ✓ | Fujisawa Rina ✓ |
| 83 李轩豪 | 李轩豪 ✓ | 李軒豪 ✓ | 李軒豪 ✓ | 리쉬안하오 ✓ | Li Xuanhao ✓ |
| 84 芝野虎丸 | 芝野虎丸 ✓ | 芝野虎丸 ✓ | 芝野虎丸 ✓ | 시바노 도라마루 ✓ | Shibano Toramaru ✓ |
| 86 村川大介 | 村川大介 ✓ | HOLD | 村川大介 ✓ | 무라카와 다이스케 ✓ | Murakawa Daisuke ✓ |
| 87 王磊 | 王磊 ✓ | HOLD | 王磊 ✓ | 왕레이 ✓ | Wang Lei (b) ✓ |
| 88 赖均辅 | HOLD | 賴均輔 ✓ | 賴均輔 ✓ | 라이쥔푸 ✓ | Lai Junfu ✓ |

来源层面五格全PASS的8人：申旻埈、罗洗河、林立祥、谢赫、党毅飞、藤泽里菜、李轩豪、芝野虎丸。

## 修正与限制

- **王磊**四格已绑定GoRatings **ID69 / DOB1977-12-26**：王磊、王磊、왕레이、Wang Lei (b)。原引用 **ID72 / DOB1986-10-11** 对应王雷 / 왕레이(雷) / Wang Lei (s)，明确排除。保留WikidataQ6134696同名、围棋职业、出生日期对应证据；这不签本地原始姓名属于哪个人。
- 日本新增三格PASS：羅洗河（Igo-Kifu日文参赛名单）、謝赫（日本棋院日文应氏杯报告）、李軒豪（Igo-Kifu棋士422）。Igo-Kifu是围棋专业出版站，不冒称棋院官方；李页面Person JSON-LD的1995-02-01对应GoRatings1175，其九段标题/七段旧简介不用于段位审批。
- 台湾新增10格实际来自8份海峰棋院正文，**9 PASS /1 HOLD**。村川大介只出现在日文代表简介，含1990.12.14/兵庫県/主要成績/優勝；虽然与GoRatings913生日对应，zh-tw外壳仍不足以签严格台湾中文用名。藤沢里菜确实出现在中文赛果正文，保留原字沢，不另转写。其余新闻/名单通常没有DOB或GoRatings ID，只签明确职业/国家/赛事语境中的发布用名。
- 继续HOLD：cn林君谚、於之莹、Kitani Minoru、许皓鋐、赖均辅；tw片冈聪、桥本宇太郎、山城宏、王磊，以及新增村川大介；ko桥本宇太郎。CWA两份958-byte app shell没有姓名正文；韩文PDF未留存，不能用搜索摘要或Latin fallback补格。於姓未被判为错误。
- GoRatings四种语言仍属同一发布方；多locale不等于多个独立来源。新文章不具备生日/外部profile ID时不声称身份强校验，更不据此批准raw owner映射。

## 冻结文件

保护目录：`~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/next20-player-primary-corrected-independent-review-sol/`，目录0700、文件0400。`input.frozen/`保留审查输入，`matrix.independent-review.csv`和`review-record.json`逐格记录；`signed-source-decisions.json`绑定79个精确PASS及11个HOLD。签署是独立代理审查声明，不是密码学身份认证。

- 输入bundle SHA-256：`f9dc0a92ff4b2c65fcfa162c7778261bef4279178c086f649b57f3a8fcccf752`
- 输入matrix SHA-256：`7db3ebe57328ee85579d2dd77c33278db68f9cdda03ea986f2fbecf12f9f0d05`
- 复审record SHA-256：`5f56216fa948ba1b98b72759d45292985df5af64a2d9a121e1b4a4ab59fcd922`
- signed-source-decisions SHA-256：`f7da3ea40244b9d04102a1a7f2008dd979851ac83956df505a4d743e11fcfde5`
- artifact-manifest SHA-256：`2a3d0cafb4089b33c5efe92e07fb0ed2e5498f2d670354838e579181f1fba079`

父代理已将制包目录/文件权限从0755/0644修正为0700/0600；字节和hash未变。本复审未修改制包输入，未连接或写数据库/clone，未改应用代码、未commit、未追加来源研究。次语言及后续制包继续pending。
