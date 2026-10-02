# 丁波 37 槽十一语 v2 独立审核

2026-10-03；审核者 `/root/dingbo_37_sign_review_astra`。任务指定 Astra/max；运行时仅声明 GPT-6，未独立认证底层子型号。审核与生产者 `/root/raw31_bundle_producer` 独立；没有生成后自行批准业务候选。本备忘录当前记录第一阶段结果，后续锚点、批次、候选及隔离克隆验收尚未完成。

**第一阶段 PASS：批准精确 37 槽 raw 显示范围、六语转写规则、`readable_unlinked` 分类，以及隔离 registry 中 `taiwango-blog-tw` 的繁中围棋专业来源登记。尚未批准整个包写入。** 2026-10-02T22:24:16.656746+00:00 写入真实审核签署；没有修改生产者的待签文件，没有生产或现役测试库写入。

逐项 SHA-256 复核了[生产者交接包](kifu-name-raw-player-dingbo-37-v2-producer-2026-10-03.md)全部 29 份工件和 10 项依赖。重新从 173,025 条 inventory association 构建完整“丁波”出现集合，确为 37 个不同 album 的 37 个槽，无多余、重复或遗漏。每槽 `CONTEXT_FIELDS` 全字段与冻结预览一致，目标人物 FK 全为 NULL；37 槽均属于[独立适用性审核](kifu-name-raw-player-31-display-applicability-independent-review-sol-2026-10-03.md)的十一语 PASS 集合。槽集合规范 hash 为 `c0255b07ef6d20bcdac2e64983f1144c5e157121bff6eb4e407746817bd47251`。原谱时间范围为 1989–1999 年；原有四、五、六段记录的差异保留。这些差异没有提供另一字形或读音的证据，也没有被用来证明所有棋谱属于同一人物。

来源审核实际读取了保留的完整正文，并按来源记录重算 hash。中国围棋协会 1,062 人名册中精确“丁波”仅一条，编号 CWA000274、生日 1971-01-24；该原文字形与中文 GoRatings 729 页面相符，英文同编号页面使用 `Ding Bo`，生日相同。四个 GoRatings 页面实际有中文、英文、日文、韩文正文标题和数据栏，H1 分别为 `丁波`、`Ding Bo`、`丁波`、`딩보`。繁中原文为台湾围棋报道，正文队名“新天一江蘇省棋協”下明确写有“領隊：朱建平 教練：丁波”。它支持本次精确原文字形显示，不建立棋谱人物身份，也不被标作协会官方来源。registry 以 `.7` 为基线只新增该一项及版本号，其他来源、语言范围不变。

六语规则没有依赖目标语言不存在惯用名的假设。实际重读 LOC 英文姓名分词说明、RAE 西文罗马字姓名保留原则、俄文 Palladius 表及乌克兰语学术转写 PDF。重新从 PDF 原字节抽取的表项为 `ding → дін`、`bo → бо`，俄文原 HTML 的对应项为 `ding → дин`、`bo → бо`。原锚点发表拼法 `Ding Bo` 的两词两音节为 `[[ding], [bo]]`，本批原文没有另见个人特选拼法或异读。四个拉丁语只按已审 Roman 词边界生成转写；实际来源语言保留 en/es，未冒标 de/fr/tr。六个规则的输出逐项机械重算一致，五个正面研究记录通过当前 validator。

| 语言 | 本次显示值 | 决策路径 |
| --- | --- | --- |
| cn、tw、jp | 丁波 | 各语言正面来源 |
| en | Ding Bo | 英文正面来源 |
| ko | 딩보 | 韩文正面来源 |
| de、es、fr、tr | Ding Bo | `transliterated`，复制 Roman 词边界 |
| ru | Дин Бо | `transliterated`，俄文音节表 |
| ua | Дін Бо | `transliterated`，乌克兰语音节表 |

当前隔离克隆也已重新核对：仅启动 `kifu-raw31-clone-20261003`，连接限定 `127.0.0.1:55433/kifu_raw31_clone_20261003`，驱动设置 `default_transaction_read_only=on`。重新构建 inventory、catalog、approved-name snapshot 并 SELECT 真实 raw 前像：inventory hash `f4907ffbe70d62b4b77f6d3bf5ba7ed789f2685f46eff7ffdfe080f2abc4bab1`、catalog hash `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09` 均与生产者 capture 相同；173,025 album、876 player，raw value/name、batch、research、change 均为 0。“丁波” raw owner 不存在，十一语名称前像均为 null。代码 HEAD 为 `0e56058b0b4ef503db831bffe787a6e98ddd5b69`，实际模块 hash 记录于复算工件。

受控目录 `~/.local/share/kifu-name-audit/2026-10-03/raw-player-dingbo-37-v2-independent-review-astra/` 为 0700、文件为 0600。`phase1-verification.json` 记录实际复算结果；`raw-display-scope.approved.json` 的规范 JSON hash 为 `5e9fbb5b309d6b9d3850b062c0b43abe4f12b01c0094f18e3114478c99c0a1de`，`rules.approved.json` 的规范 JSON hash 为 `129f6ee2bb0c0e25b76e5c5626bfe93903a5640e1a7d80f18f1f6b57ada7355b`。另含独立分类和 registry 审核及六条规则各自的 hash。第一阶段 manifest 文件 hash 为 `4034fd4c876529419442f53339853e20b7556903108bd191fefe5b51bf26aa01`。

下一步由原生产者按已签 scope 和实际时间重绑新的 raw v3 锚点及五语研究；保留旧人物来源批准的原字节。待独立批准新锚点后，再按规则审核之后的真实生产时间重产六个有限批次，并完成候选的真实前像绑定，之后独立签署。最终包仍须 `validate_bundle`、唯一隔离克隆 dry-run/apply/replay/undo/reapply 及十一语显示、搜索、覆盖核对。当前没有已发生显示增益，潜在上限为 407 个姓名语言槽，人物身份增量固定为 0；任何第一阶段 PASS 都不能代替上述后续验收。
