# 现代日本 Meijin 五语与有限范围：独立审核（sol）

2026-10-03，只读审核。审核对象为 [五语候选与范围 memo](kifu-name-modern-meijin-five-primary-scope-hold-2026-10-03.md) 及 `~/.local/share/kifu-name-audit/2026-10-03/meijin-core-pending/`。以下 PASS 仅涉及来源名称及明确列出的来源槽位；全量赛事实体、FK、DB 写入、届期/轮次模板均未批准。

**结论：source-name 五语 PASS；有限 raw scope 183 盘 PASS；其余 744 盘 HOLD。** 不能把四种通过的原文作为全库字符串替换规则：同样的 `1st/2nd/3rd Meijin` 在这批冻结数据中还有 10 盘个人目录 HOLD。

## 五语 source-name

独立读取七份 HTTP 原文，校验全部文件的 SHA-256 和字节数与 manifest 一致。日文与英文正文按 UTF-8、韩文按 EUC-KR 读取。名称判断结合来源所述期号、年份、棋手及赞助方，避免只凭「名人」字面定赛事。

| 语种 | 通过的显示核心 | 结论与依据 |
| --- | --- | --- |
| cn | `日本名人战` | **PASS**。[野狐报道](https://www.foxwq.com/news/4601.html)标题直接使用该词；正文第 34 期为张栩对井山裕太，并另称林海峰早年赛事为「旧名人战」。额外添加「围棋」无本次直接简中引文，不能标同等来源支持。 |
| tw | `日本圍棋名人戰` | **PASS（去除期号后的核心）**。[海峰赛事页](https://www.haifong.org/news/content/ABC908ABE427697ABC7F960615286E8C)标题为 `日本「第44期圍棋名人戰」`，2019 年张栩对芝野虎丸，并明确朝日新闻、日本棋院；核心是移除期号和引号所得。本文也直接出现 `日本圍棋名人賽`，可记来源别名；本次选择「戰」作显示核心。 |
| jp | `名人戦` | **PASS**。[日本棋院历代记录](https://www.nihonkiin.or.jp/match/meijin/archive.html)标题直接支持，记录现代第 1 期 1976、第 14 期 1989、第 26 期 2001。仅可配已确认的现代日本系列。 |
| ko | `일본명인전` | **PASS**。[Tygem 原报道](https://tygem.game.naver.com/news/news/view.asp?find=&findword=&gubun=&pagec=500&seq=185)直接写 `제26기 일본명인전`，发表日 2001-11-02，依田纪基对林海峰 4–2，与日本棋院现代第 26 期相合。保留「日本」限定。 |
| en | `Meijin Title` | **PASS**。[日本棋院英文页](https://archive.nihonkiin.or.jp/match/meijin/index-e.html)的 Tournament name 直接支持，并列朝日赞助和第 1 期 1976。[CWI 系列页](https://homepages.cwi.nl/~aeb/go/games/games/Meijin/)支持 `Meijin` 作为来源短称；本次显示核心选择官方页的 `Meijin Title`。 |

上述编辑选择没有建立数据库中的正式名称或 ID。另六语不在当前五语直接证据内；可明确记作「规则转写」候选，不得标为已独立核源 PASS。

## 新旧系列边界及日期限制

[CWI 系列页](https://homepages.cwi.nl/~aeb/go/games/games/Meijin/)明确：读卖赞助的 Old Meijin 为 1962–1975，朝日从 1976 接手并重新编号。[海峰历史页](https://www.haifong.org/news/content/A429C5FC8ED05AA62145B0C5CDCC90E6)独立支持旧赛 14 届后改朝日并重计届数，并另述台湾名人赛。不能将旧名人、现代日本名人、各国同名赛合并。

**证据修正：** 被审 memo 称「日本棋院列创设于 1974」，在其提供的 `jp_nihonkiin_modern.body` 中未找到相应文字；该文件为历代记录、首期决赛年 1976。受控英文页写 Year of founding 1976。1974 创设断言须另补来源或删去，不能把这七份受控原文当作其证明。

这不自动否定提前发生的预选：独立公网复读 [CWI `Meijin/01/R04.sgf`](https://homepages.cwi.nl/~aeb/go/games/games/Meijin/01/R04.sgf)，明确 `EV[1st Meijin]`、`RO[2nd Preliminary]`、`DT[1974-11-28]`，黑 Hane Yasumasa、白 Tsujii Ryotaro，正对应 album 161366。其来源系列目录和根字段支持有限来源归属；不能由决赛年反推每盘日期，也不在此裁决准确创设日。

## 逐盘范围核验

独立重读 JSONL，未沿用 producer 的比较布尔值或总数作为结论。927 个 album ID 唯一；按路径重新计算目录和届期，候选文件与完整槽位文件的对应行完全相同。CWI 根证据 193 与 19x19 根证据 734 的 ID 集合互斥且并集恰为 927；逐行重新比较事件（EV 优先、否则 GN）、日期、黑棋、白棋、轮次，**4,635/4,635 项一致**。这是根证据与 inventory 的一致性证明，19x19 仍缺独立赛事归属外证。

另外独立下载 [CWI 公共 archive](https://homepages.cwi.nl/~aeb/go/games/games.tgz)，46,246,395 字节，SHA-256 `935522a59817c12b37227e843cd3b4bc8d702e32e0e6fbc80b66d828dbbffcad`；逐一从 archive 取出这批 **193** 个成员，缺失 0，成员 SHA-256 与受控根证据不符 0。故 CWI 根证据没有仅依赖生产者的转录。[第 1](https://homepages.cwi.nl/~aeb/go/games/games/Meijin/01/index.html)、[第 2](https://homepages.cwi.nl/~aeb/go/games/games/Meijin/02/index.html)、[第 3](https://homepages.cwi.nl/~aeb/go/games/games/Meijin/03/index.html)、[第 4](https://homepages.cwi.nl/~aeb/go/games/games/Meijin/04/index.html)期公开页面确认这些目录位于现代 Meijin 系列。

| 冻结槽位范围 | 原文 | 棋谱 | 状态 |
| --- | --- | ---: | --- |
| `CWI_1950_1978/Meijin/01/` | `1st Meijin` | 89 | **有限 raw scope PASS** |
| `CWI_1950_1978/Meijin/02/` | `2nd Meijin` | 30 | **有限 raw scope PASS** |
| `CWI_1950_1978/Meijin/03/` | `3rd Meijin` | 32 | **有限 raw scope PASS** |
| `CWI_1950_1978/Meijin/04/` | `4th Meijin` | 32 | **有限 raw scope PASS** |
| CWI `Cho_Chikun/` | 上述前三种原文另 2／5／3 盘 | 10 | **HOLD**：个人路径未提供同等直接系列归属证据 |
| 19x19 日期相容组 | 其余紧连／逗号原文 | 733 | **HOLD**：日期和字符串不能替代逐局赛事外证 |
| 19x19 album 63983 | `Meijin,14th` | 1 | **HOLD**：原 SGF 自身年份冲突 |

有限 PASS 精确为 **album 161333–161515（183 个）**，每个路径的届期数字与 `EV` 相同；日期范围 1974-11-28–1978-11-23。集合运算证明 `183 + (10 + 733 + 1) = 927`，PASS 与 HOLD 交集为空、无遗漏。这是按槽位 ID 与来源路径冻结的许可范围，不能扩大到 193 个同字符串 CWI 槽位，更不能扩大到全部 927。

其余复算与被审 memo 一致：45 种原文；逗号后期号 706（26 种）、期号空格核心 193（4 种）、期号紧连核心 28（15 种）；年份粗筛差值同年 602、前一年 322、提前两年 2、提前十五年 1。提前两年中 album 161366 在有限 PASS，album 157690 仍在个人目录 HOLD。927 行 `event_id`、`duplicate_of_id` 均为空。

album **63983** 原根为 `GN[Meijin,14th]`、`DT[1974-01-16]`，黑 `TakagiShoichi`、白 `赵治勋`；日本棋院现代第 14 期为 **1989**。SGF 与 inventory 相同没有消除该冲突，也不能证明它是某届旧名人战。本次不更改日期、届期或归属。

## 冻结证据与授权边界

独立校验六份证据文件 SHA-256 均与被审 memo 相同。有限集合的冻结依据为 `direct-path-candidate.pending.jsonl`：`e5c8b8bda14f9e51a2fb849bbc372d425d981c2ee0b80a5e74110119e76ff3e2`；完整槽位为 `slot-context.pending.jsonl`：`76cefee12f9efefc457f3aa3ddd35135d4743a33b7e400a5c62ef657b023d6d3`；七页来源 manifest：`740cfef3828d07cebaf9bd8060842fd3e000ade06afc6db4d30ef1b9b8f3e021`。

仅新增本审核 memo；无代码、数据库、FK、候选 apply 或提交操作。后续任何实际导入仍需核对实时前像及单独授权；当前五语与 183 槽位的 PASS 不构成发布或写库许可。
