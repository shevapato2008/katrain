# 赵治勋 252 个机械清洁位置：独立来源与身份抽查

2026-10-02；审核者 `/root/zhao_252_evidence_sol`（Sol）。结论：**HOLD，不批准 252 个身份关联，不生成写入载荷**。本次只读核对受控行、仓库及本机采集副本，并查询外部公开页面；未访问或修改数据库。

## 冻结范围及来源链

读取生产者[批量审计](kifu-name-zhao-608-cwi-bulk-scope-producer-2026-10-02.md)的 `rows.jsonl`，独立重算 SHA-256 为 `ddbd25fe2323e96a6eff1c6a1c782d2f68236cbb06d2cf4546d71a370e4330e4`。1,949 行中 `clean_mechanical` 为 **252** 行；本审核以这 252 行为总体，没有把其余 1,697 行算作已清洁或已审。原生产者的指纹、同色和字段规则仍按其文档解释；本次未重算 CWI 棋步指纹。

找到了更具体的本机采集链：`/Users/fan/Repositories/go-topic-collections/19x19/scraper.py` 的当前文件从 `https://api.19x19.com/api/engine/games/0086-golaxy_public` 分页取 game ID，用 `POST https://api.19x19.com/api/engine/games/shared/{id}` 取得 SGF，随后插入 `GN`、`SO[https://19x19.com]`、`DT`、`GC`，按 `{id}.sgf` 存在 `19x19/data/kifu/`。其 `config.yaml` 固定 API base、列表路径、`game_type=2` 和公共账号。采集仓最近相关提交为 `f2ba72410f3ade0233e5470c75e87c042a35cec7`（2026-01-30）；当前 `progress.json` 记录截至 2026-03-01 的累计进度，但不是逐条原始 API 响应或固定批次清单。以上是本机代码及文件证据，不把它写成 API 运营方对历史人物的官方认证。

用受控行提供的 **252 个确切源文件名**，逐一比较采集副本 `/Users/fan/Repositories/go-topic-collections/19x19/data/kifu/{id}.sgf` 的原始字节 SHA-256 与行内 `source_sgf_sha256`：**252/252 存在且相等，0 缺失，0 不同**。例如 album `1034` 的 `21604167.sgf` 两份字节哈希同为 `685e7802849300c1f04872ee87903ad623fbf56a58c4bed95e6603d51d5ba43f`。原分区另记录本机 `data/kifu-album/19x19/` 源 SGF 经解析序列化后与生产 SGF 相等。仓库的 `scripts/import_kifu.py` 当前按相对 `source_path` 读取 SGF、序列化 `sgf_content`，并在未有审定别名时不猜测 player FK；`katrain/web/kifu/provenance.py` 按目录将来源归类为 `19x19`。这让 **采集副本 → 本机导入源文件 → 已捕获生产 SGF** 的内容对应关系比原生产者文档更具体，但当前脚本不证明历史上实际运行的脚本版本和批次。

这 252 行的源 SGF 根属性中 `SO` 均有 `https://19x19.com`（249 行单值、3 行另带空值）；根 `EV`、`GN` 均缺失。该网址可由采集脚本插入，因此不能作为独立人物归属或赛事出处。仍缺生产 `kifu_album_sources` **同时点完整捕获**、生产导入运行/版本清单、原始 API 列表与 SGF 响应及每个 game ID 的绑定、19x19 历史棋谱上游的出版/审核规则。CWI 与 19x19 可能从共同上游取得棋谱；不同站点及完整落子相同不足以证明来源独立。当前采集仓的文件相等也不能补这些缺项。

## 官方人物锚点

[日本棋院棋士资料](https://www.nihonkiin.or.jp/player/htm/ki000004_2.html)明确为 `趙 治勲`、读音 `チョウ チクン`、1956-06-20 生、韩国釜山出身、日本棋院东京本院九段；[韩国棋院棋士资料](https://www.baduk.or.kr/record/player_view.asp?pkey=20000020)以 `조치훈 (趙治勳)`、同一出生日期和日本所属交叉确认这个职业棋手。此人物锚点支持 **Cho Chikun/赵治勋这个目标人的跨语身份**，但不能单独认证本批任一 SGF 的黑白棋手。生产 ID `608` 的本环境绑定仍以既有冻结目录证据为准；不可移植到测试库 ID。

## 盲化抽查及实际结果

先固定审阅顺序种子，后看所抽行：种子文本 `zhao-252-independent-review-2026-10-02:/root/zhao_252_evidence_sol`，UTF-8 SHA-256 `9b8a1b3de8114b55ac34ca37a506dc14d4351e3ae9fe29c6efb5f90616cb06ff`；以该十六进制整数给 Python 3.13.11 的 `random.Random` 初始化，对按 `album_id` 升序的 252 行用 `sample(..., 8)` 无放回抽取。抽中顺序如下。先按采集行的原姓名、日期和执色找外部比赛记载，再与 CWI 元数据对照。Go4Go 是另一公开棋谱目录，但其 SGF 上游未核实独立于 CWI/19x19；因此表中“外部匹配”只是交叉线索，不计作满足来源独立门槛。

| 顺序 / album | 原槽位与日期 | 外部核查 | 状态 |
|---|---|---|---|
| 1 / `138255` | 赵治勋黑、王立诚白；1992-03-15；第 39 回 NHK 杯决赛 | [日本棋院历届记录](https://archive.nihonkiin.or.jp/match/nhk/)确认该届冠军赵、对手王；但其[冠军决定局日期清单](https://archive.nihonkiin.or.jp/joho/pressroom/newsrelease/20070319.htm)给 **1992-02-17**，与源谱/CWI 的 1992-03-15 不同。[GoRatings 王立诚记录](https://www.goratings.org/ja/players/71.html)列 1992-03-15 王执白负赵，但标示链接到 Go4Go。录制与播出日期解释尚无证据。 | **日期冲突待解**；人物/对手/赛事部分相符 |
| 2 / `141181` | 赵黑、武宫正树白；1997-12-13 | [Go4Go 双人对局表](https://www.go4go.net/go/games/twoplayer/98/82)列同日、第 17 期 NEC 杯第 2 轮、同色、黑胜。 | 外部目录吻合；上游独立性未证 |
| 3 / `125534` | 赵黑、清成哲也白；1996-04-18 | 检索仅得到 [CWI 十段战页](https://homepages.cwi.nl/~aeb/go/games/games/Cho_Chikun/tournaments/Judan.html)与[另一爱好者索引](https://rongen17.home.xs4all.nl/Cho/Tourn/Judan.html)的同日/对手/同色记录；后者数据来源未明。 | **独立赛事来源未核实** |
| 4 / `141368` | 武宫黑、赵白；1984-07-26 | [Go4Go 双人对局表](https://www.go4go.net/go/games/twoplayer/98/82)列同日、第 32 期王座战半决赛、同色、白胜；CWI 标 `Round 3`，阶段命名需核。 | 外部目录吻合；轮次文字待核，上游独立性未证 |
| 5 / `114068` | 赵黑、柳时熏白；2017-11-02 | [Go4Go 棋手页](https://go4go.net/go/games/byplayer/98/180)列同日、第 43 期碁圣战首轮、同色、白胜。 | 外部目录吻合；上游独立性未证 |
| 6 / `142602` | 小林光一黑、赵白；1975-05-15 | [Go4Go 双人对局表](https://www.go4go.net/go/games/twoplayer/98/50)列同日、第 19 期首相杯第 3 轮、同色、黑胜，且段位与 CWI 的 7p/6p 相同。 | 外部目录吻合；上游独立性未证 |
| 7 / `128504` | 山城宏黑、赵白；2003-06-26 | [CWI 王座战页](https://homepages.cwi.nl/~aeb/go/games/games/Cho_Chikun/tournaments/Oza.html)列同日、第 51 期第 2 轮、山城执黑；本轮未取得可确认上游独立的逐局资料。 | **独立赛事来源未核实** |
| 8 / `138466` | 王立诚黑、赵白；2000-10-23 | [Go4Go 棋手页](https://www.go4go.net/go/games/byplayer/98/960)列同日、第 48 期王座战第 1 局、同色、白胜；[日本棋院王座战历届记录](https://archive.nihonkiin.or.jp/match/oza/)确认当届王立诚对赵治勋的最终 3-1。 | 外部目录吻合；上游独立性未证 |

**抽样分母是 8/252，而非 252/252。** 5/8 有另站逐局目录与日期、双方、执色及赛事大体吻合（第 2、4、5、6、8 行）；1/8 有官方同届对手确认但精确日期冲突（第 1 行）；2/8 在本轮没有合格独立逐局资料（第 3、7 行）。即使那 5 条目录线索最终被证明来源独立，剩余 244 个未抽位置也不能由 8 个样本直接逐盘批准。按生产者提出的 **252/252 全量零误配、零未解决** 计划，本轮结果是 **0/252 已完成该门槛**；不能把五个交叉线索写成五个身份批准。特别要保留 1992 日期冲突，不能用两个衍生棋谱站点的相同日期覆盖官方记录。

## 闸门裁决

本机发现的采集仓使 252 条文件的 19x19 API *路径假说*得到字节级支持，但仍没有每条 API 响应、生产来源关系同时点快照和历史上游归属/版本链。官方人物锚点已找到；抽查却出现一个具体日期冲突，另有未核实行。故 **来源适用性、独立逐局检查及完整异常处置均未满足**，252 条及其余 1,697 条全部保持 pending。下一步应先捕获/核对上述来源链，解释 NHK 日期差，再以固定范围逐项完成独立审阅；如仅部分行满足，应重新冻结更小集合并另行签署。本备忘录不是 `identity_review`、十一语批准或数据库写入授权。
