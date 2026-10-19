# 三个旧 HOLD 英文原文的有限槽复核

## 后续实际执行状态

2026-10-05 用户恢复开发后，root 已独立审阅固定执行器、完整前后像及上述身份决定，批准有限 690 行、700 槽。TEST、PROD 均完成 dry 回滚、apply、完整后像 verify；仅批准棋手 FK 改变。两库实际批准与执行收据见 `kifu-incremental-applied-2026-10-05/player-latin700-{TEST,PROD}.json.gz`。随后各捕获一次 post700 库存，未放松原前像检查。

以下“待 root 审核／未执行”的表述记录原交接时状态，并非当前执行状态。

独立语义判断：**GO，仅限本包700个精确槽（690局）**。执行仍待root审核批准；未写库、未改别名、未全局释放raw/HOLD。

| exact raw | 精确NULL槽 | PROD / TEST目标 | SGF日期范围 |
|---|---:|---|---|
| `Rin Kaiho` | 247 | 林海峰298 / 299 | 1952–1978 |
| `Takemiya Masaki` | 233 | 武宫正树490 / 491 | 1965–1978 |
| `Cho Chikun` | 220 | 赵治勋608 / 609 | 1962–1978 |

## 旧阻塞为何不再阻止此有限范围

已读取10月4日非汉字41–60、61–80审查原JSON及多ID家族审查。原HOLD主要是汉字变体目录、历史FK及并行家族批次重叠，不是否认这三个Latin姓名对应谁。多ID家族审查明确保留上述主ID。

当前两库主ID各有完整五语verified名字和独立approved证据；三条英文批准名与本次raw逐字相同。分别绑定[林海峯官方档案](https://www.nihonkiin.or.jp/player/htm/ki000009.htm)、[武宮正樹官方档案](https://archive.nihonkiin.or.jp/player/htm/ki000003.htm)、[趙治勲官方档案](https://www.nihonkiin.or.jp/player/htm/ki000004_2.html)，并保留实际发表英文名称的Wikipedia正文证据。此处复用已批准身份，不重新研究生日。

- 两库这三个exact raw的既有非NULL FK均为0，故没有与此次目标相异的既有关联。
- 林海蜂旧ID及趙治勲名誉旧ID当前均0引用。名誉旧ID还有未审核错误译名（如Cho Hun-hyun），本包未采用、未迁移该名字。
- 武宫秀树旧ID仍有1引用；现有已批准日文正文说明「秀樹」为武宫正树的本因坊号。本包仅指向已确认主ID，不重指该旧槽，不删除或合并任何旧ID。
- 所以可解决这700个明确原文槽的归属，无须先将全部旧变体清理完。旧HOLD的其他raw、赵治勋连写/截断异常及无空格`ChoChikun`均不在本包。

## 原SGF及时间判断

两库均只读抓取限定690局，完整SGF相同；700槽PB/PW与raw逐字一致，所有日期非空且无1900占位。来源为既有CWI/Go_Seigen档案，未发现跨人物或生涯年代实质冲突；未逐局补外部对阵表。

- 林海峰1952年两局对吴清源的六子棋及1954年三子指导棋属于童年/业余阶段。原始2d/2p与入段年代的段位疑点保留，只关联本人，不改段位。
- 武宫正树最早1965-04-14，SGF明确说明职业首局；后续日期、段位随生涯发展合理。
- 赵治勋1962年三局SGF明确是赴日前对赵南哲的送行让子棋，1965/1968早期棋谱明确为院生赛。职业入段日期不排除同一人物的儿童、业余棋谱。
- 157572的DT1968与文件名1969-01-00/刊载期别保持；157580仅关联明确的白方赵治勋，注释中不确定的黑方对手保持原样。局部年份、广播/发表日期和不全棋谱说明均不改。

## 交付与执行限制

包：`/tmp/kifu-player-latin700-review-20261005/`。

- `scope.json`：700个album/side/raw、source_path、日期、SGF SHA和根属性，绑定原HOLD文件及三个现有目标ID；只对这些槽给出语义GO。
- `{PROD,TEST}-capture.json`：完整album原SGF、source链接、原staging、相关目录/别名/名字/证据前像及引用计数。
- 各环境`plan.json`、`expected-after.json.gz`：完整前像与700个NULL→目标FK的预期；690局中10局有两个此次批准槽。均与post1117库存的association/source-link相符。
- Scope SHA：`6d305a276e9af7fc6a8d474c00080a65219cfe179fb91c6b1a3f483b76afd62f`。
- PROD plan：`33c44a43ac52b66c1e883cc579351849106509905de53f7eccb2d6b5a5389ab1`。
- TEST plan：`241ab8f8809719d42905158daddf07e2fd149a763ae21be8cb27a118c24a1daa`。

建议沿现有有限CAS执行方式逐album一次性更新该行批准的1或2个棋手FK；写前锁定并比较完整前像，目标原槽仍须NULL，事务内比对完整后像，先dry回滚再独立批准apply。只读捕获及本地检查已完成，未执行dry/apply。原文、SGF、日期、段位、赛事、staging、别名和隐藏250均保持。

## 执行器交接

固定执行器和transport已补入原包；TEST/PROD各一次只读check通过，690行/700槽前像完全匹配，0更新。完整操作命令、文件SHA及结果见包内README与manifest；原scope和plan未改。未执行dry/apply，执行批准仍由root独立提供。
