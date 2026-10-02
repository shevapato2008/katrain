# 现代日本 Meijin：五语核心候选与有限棋谱范围（HOLD）

2026-10-03，只读研究。冻结 `event-components-v4` 中精确核心 `Meijin` 覆盖 **927 盘、45 种原始写法**。这只是待审核心，**不**批准赛事实体、名称、轮次/届期模板或生产链接。

## 先分清系列

[CWI 专业棋谱目录](https://homepages.cwi.nl/~aeb/go/games/games/Meijin/)明确区分读卖新闻赞助的 **Old Meijin（1962–1975）** 和朝日新闻赞助、1976 年重置届数的 **Meijin**；[海峰棋院历史文章](https://www.haifong.org/news/content/A429C5FC8ED05AA62145B0C5CDCC90E6)独立叙述旧赛 14 届后改由朝日主办并重新编号，还列出台湾、中国、韩国各自的名人赛。因此 `Meijin`、`Old Meijin`、各国「名人」均不能凭词干相同合并。[日本棋院历代记录](https://www.nihonkiin.or.jp/match/meijin/archive.html)列现代第 1 期决赛年为 1976；创设于 1974 与第 1 期此前预选可以并存，日期不是编号生成器。

| 冻结原文语法 | 棋谱 | 精确原文 | 例子 |
| --- | ---: | ---: | --- |
| 核心后逗号届期 | 706 | 26 | `Meijin,2nd`、`Meijin,14th` |
| 届期空格核心 | 193 | 4 | `1st Meijin`、`4th Meijin` |
| 届期紧连核心 | 28 | 15 | `10thMeijin` |

全部 45 种仅标第 1–26 期；原文的逗号、空格、无空格、`st/nd/rd/th` 和数字是**届期组成部分**，不能由日期或显示语反写 SGF。`round_name` 只在 193 个 CWI 槽有值，含 2nd/3rd/Last Preliminary、League 等；其余 734 个 19x19 槽为空。所有 `event_id` 和 `duplicate_of_id` 为空。源键分布为 CWI 193、19x19 734。

## 逐盘只读核源和 HOLD 队列

公开 CWI `games.tgz` SHA-256 `935522a59817c12b37227e843cd3b4bc8d702e32e0e6fbc80b66d828dbbffcad` 复读 193 个来源 SGF；此前生产只读 dump 的隔离副本以 `READ ONLY` 事务复读 734 个 19x19 SGF。**927 盘**的 SGF 根 `EV/GN`、`DT`、`PB`、`PW`、`RO` 与冻结 inventory 对应字段逐项相同，零缺失或不符。该一致性只证明数据库字段忠实导入了 SGF，不能独立证明真实赛事归属；隔离容器随后已停止。

| 层级 | 棋谱 | 待审结论 |
| --- | ---: | --- |
| `CWI_1950_1978/Meijin/<届期>/` 路径与原文数字同届 | **183** | **有限范围 PASS-CANDIDATE**：4 种 `1st`–`4th Meijin` 原文，1974-11-28–1978-11-23，公开 SGF 根字段与 inventory 完全一致，可送独立事件归属审核；还不是正式 PASS 或链接许可。 |
| CWI `Cho_Chikun/` 个人目录 | **10** | **HOLD**：SGF 根字段吻合、年份与早期现代赛兼容，但未从系列目录直接确认；需用 CWI 人物赛事索引及日本棋院逐局资料交叉核对。 |
| 19x19，届期年或前一年 | **733** | **HOLD**：原 SGF `GN` 与 inventory 对应，日期粗筛可相容，但无独立来源目录或赛事逐局表核其归属。不得因字符串与年份相合整体通过。 |
| 19x19 明显日期冲突 | **1** | **HOLD**：album **63983**，`GN[Meijin,14th]`，`DT[1974-01-16]`，黑 `TakagiShoichi`、白 `赵治勋`；第 14 期现代赛对应 1989，原 SGF 自身带冲突，不能据此改日期或届期。 |

以 `1975 + 届期` 只作异常扫描，602 盘日期在同年、322 盘前一年、2 盘提前两年、上述 1 盘提前 15 年。提前两年的两个第 1 期预选为 album 157690（CWI 个人目录 HOLD）及 161366（CWI 同期目录有限候选）；日本棋院列创设于 1974，这两盘不因粗筛即作错年结论。不同路径/阶段仍要逐盘核实。

## 五语来源姓名候选

下表仅为**来源层候选**，保留专业来源所见的地域/赛种限定；期号、预选、循环圈、挑战赛留在独立组成部分。

| 语种 | 直接来源用语 | 待审显示核心 |
| --- | --- | --- |
| 简中 | [野狐围棋第 34 期报道](https://www.foxwq.com/news/4601.html)写 `日本第34期名人战`，同文明确称林海峰早年的是 `旧名人战`。 | `日本名人战`；是否加「围棋」待编辑审核。 |
| 繁中 | [海峰棋院日本第 44 期赛事页](https://www.haifong.org/news/content/ABC908ABE427697ABC7F960615286E8C)写 `日本「第44期圍棋名人戰」`，另称 `日本圍棋名人賽`；历史页明示台湾本地名人赛和日本旧/新赛。 | `日本圍棋名人戰`；「戰/賽」取舍待审核。 |
| 日文 | [日本棋院历代记录](https://www.nihonkiin.or.jp/match/meijin/archive.html)标题 `名人戦`，新赛第 1 期为 1976。 | `名人戦`，只配已确认的现代日本系列 ID。 |
| 韩文 | [Tygem 专业围棋报道](https://tygem.game.naver.com/news/news/view.asp?find=&findword=&gubun=&pagec=500&seq=185)写 `제26기 일본명인전`，2001 年依田纪基对林海峰赛果与现代第 26 期相合。 | `일본명인전`；别与韩国名人战混用。 |
| 英文 | [日本棋院英文系列页](https://archive.nihonkiin.or.jp/match/meijin/index-e.html)列 `Meijin Title`、1976 年创赛；CWI 以朝日赞助和重置届数明示现代 `Meijin`。 | `Meijin Title` 或 `Meijin` 待审核；须与 `Old Meijin` 分开。 |

受控目录 `~/.local/share/kifu-name-audit/2026-10-03/meijin-core-pending/` 为 `0700`、文件 `0600`。逐盘范围 `slot-context.pending.jsonl` SHA-256 `76cefee12f9efefc457f3aa3ddd35135d4743a33b7e400a5c62ef657b023d6d3`；193 盘公开 CWI 根字段 `cwi-root-evidence.pending.jsonl` SHA-256 `0f6ef9ef2b795b791bcb0e5cedff418a224fdc0a674a437dd56aa82de0bf9e97`；734 盘隔离副本根字段 `clone-19x19-root-evidence.pending.jsonl` SHA-256 `4826ef0a0212d057274494fe6af8dc6255936d0ce3853976006c6fb7f078dc42`；183 盘子集 `direct-path-candidate.pending.jsonl` SHA-256 `e5c8b8bda14f9e51a2fb849bbc372d425d981c2ee0b80a5e74110119e76ff3e2`；45 原文/异常汇总 `scope-summary.pending.json` SHA-256 `0a9f3febcfbc19e755942103e12f334f688ab42464b450817bac286db947e768`。七份五语与系列边界 HTTP 200 原文的 URL、时间、SHA-256 见 `source-manifest.pending.json`，其 SHA-256 为 `740cfef3828d07cebaf9bd8060842fd3e000ade06afc6db4d30ef1b9b8f3e021`。

**下一步**：对 183 盘有限候选做独立赛事身份审核；对 10 盘个人目录与 733 盘 19x19 寻逐局外证，对 63983 核日期/届期来源；五语名称另做独立编辑审核。所有范围按实际导入前像重算。本次无生产 DB 写入、候选 apply、代码变更或 Git 提交。
