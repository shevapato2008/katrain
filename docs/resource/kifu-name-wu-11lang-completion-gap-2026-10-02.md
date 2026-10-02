# 吴清源 player 1：十一语言名称与当前工件缺口

核对时间：`2026-10-02T04:04:50Z`。执行模型：`gpt-6-luna`；请求的 `gpt-5.6-luna` 不可用。本 memo 是有限只读核对，不构成新的来源/候选批准或生产写入许可。

## 结论

**十一语言的正向姓名候选已全部独立批准。** 现有批准文件分为九语和西语/乌克兰语两份，且分别有已完成的隔离库演练；按 `9 + 2` 顺序从同一备份导入后，隔离库核实了 `player:1` 的十一语言名称，再逆序撤销并保留原有六行。对于吴清源这个已关联实体的 **name-only exemplar**，现有工件足够，不需要重搜来源、重签候选或添加链接范围。

我从 `ucloud-v100 / katrain-ucloud-postgres-1 / katrain_prod_20260725` 只读查询了 `player_id=1` 的全部姓名行，并按导入器的完整行 canonical SHA-256 规则计算 preimage。现有六行 `cn/de/en/fr/jp/tw` 均与已签候选的 preimage **逐字节哈希相同**；其余五语 `es/ko/ru/tr/ua` 在当前库中均无行，和候选内的显式 `null` 一致。规范名仍为 `Go Seigen`。查询只读，没有事务写入。

## 十一语核对

“当前 preimage”是本次正式库只读查询结果；`null` 表示查询时该语种没有姓名行。来源 hash 为已审直接页面/固定版本的捕获值，不是本次重新抓取。

| 语种 | 已批准显示名 | 最佳已审直接来源及 body hash | 已签名工件 / 当前 preimage | 剩余正向姓名缺口；使该行可复用的单一动作 |
|---|---|---|---|---|
| `en` | `Go Seigen` | CWI Go games index；`94aeee554b7febf817478224e8dea105bd58990b65b91f36bac5fa67c3b491b6` | 九语 `.2`；签名 `gpt-6-luna`；`aa0abd1e03ae9ecbc2f7aa14f39584576fdf5dc4abf11d4a7e50331fb60daf28`，匹配 | 无；复用已批准九语 bundle。 |
| `cn` | `吴清源` | 中国国家体育总局讣闻；`93674aa5da2081f7cd5694fa631fa7d009558f63f6252967fbcc6a0b87f0624e` | 九语 `.2`；签名 `gpt-6-luna`；`61cde70d22f4b7a5df61973a66a478c1af8130daf2c75791486ec1fe5cbe831b`，匹配 | 无；复用已批准九语 bundle。 |
| `tw` | `吳清源` | Haifong Go Institute；`96129516105da3aaa815fea8ead6ded9eb5f255e27c276015ff4712287a8c69d`（PTS Taiwan 讣闻另证同名：`2e0cf533ed7bcb1d9b0b9657b9a1469f480f8b58788c2fdf019f00ab006c9aae`） | 九语 `.2`；签名 `gpt-6-luna`；`52954a64af7129dca71172735bb9bc50fd72219e4ff4faa334f66adafbf01315`，匹配 | 无；复用已批准九语 bundle。 |
| `jp` | `呉清源` | Nihon Ki-in 官方选手页；`2abec7ca3d6814e94ba6b1dd48e7952c3dfdec7ec210de90dd4520eb9e4a0e94` | 九语 `.2`；签名 `gpt-6-luna`；`8ccf7a89b98bed122fe13b4d1bc58895793b0ec2c23bd1e31d725ffcb45b58b2`，匹配 | 无；复用已批准九语 bundle。 |
| `ko` | `우칭위안` | 韩国棋院协会选手页；`1c46e4ae9f6f8588d274785685c797cf275ac2802e8ade94f914542abd533df2` | 九语 `.2`；签名 `gpt-6-luna`；当前不存在，`null` 匹配 | 无；复用已批准九语 bundle。 |
| `de` | `Go Seigen` | Deutscher Go-Bund，DGoZ 6/2014 PDF；`e7f87664142ef85cf8aa34784667515b5254c2d269637def2d379a562f3f1422` | 九语 `.2`；签名 `gpt-6-luna`；`4620d2079c9fe869ff3969ef1aee04b9ae489b51b0ee2ae90c6f7555b7a7fb77`，匹配 | 无；复用已批准九语 bundle。 |
| `es` | `Go Seigen` | Godokoro 西语围棋史文；`638db1fdfe0641afbeeb98ecfe786dd46c34c718628609890da791578dc9f990` | 两语 `.3`；签名 `gpt-6-astra`；当前不存在，`null` 匹配 | 无；复用已批准西语/乌克兰语 bundle。 |
| `fr` | `Go Seigen` | Belgian Go Federation，Belgo 46 PDF；`d93cd7e250d2dc85ce1e50b31d737acd6bf828246fa857be1ec3cd59ceea659d` | 九语 `.2`；签名 `gpt-6-luna`；`a74d7740ebc0c4e3439fc698487801f253ddbe9f61d1865819e3e7fb8085f3bf`，匹配 | 无；复用已批准九语 bundle。 |
| `ru` | `Го Сэйгэн` | Russian Go Library 人物页；`7cfff0ef48ae83fd5791880b42989531bd823956cfd77f7447458de4dcd080a7` | 九语 `.2`；签名 `gpt-6-luna`；当前不存在，`null` 匹配 | 无；复用已批准九语 bundle。 |
| `tr` | `Go Seigen` | Istanbul Go School 围棋文章；`b0447606605c3097445e1e50b5e580645d1eb91e695540ab6eb4abb5fdbecf2ae` | 九语 `.2`；签名 `gpt-6-luna`；当前不存在，`null` 匹配 | 无；复用已批准九语 bundle。 |
| `ua` | `Ґо Сейґен` | 乌克兰 Wikipedia 固定 revision `44688592`：提取 wikitext SHA-256 `1f7284814ad822a309459027b912e3418e475a0104376b4ddc215f110c302409`；其 revision API 响应 SHA-256 `d783edc24631b4b2a262800108c1c28faaabc9494f9c9c589220da21583e3543` | 两语 `.3`；签名 `gpt-6-astra`；当前不存在，`null` 匹配 | 无；复用已批准西语/乌克兰语 bundle。 |

九语签名候选文件 SHA-256 为 `d4b40556a2fb7ea934163c5c4de62c0a9153af069ade484eb112c73584a8bdbd`，bundle 为 `2172c77a48aec4e82da3b25cadff079855960382873ebfca13ef3733c319c890`。两语签名候选文件 SHA-256 为 `5aab0e1dc3c0e0e8428d08ae8674461ec271a9eb803ef6f41acde83e73c094ae`，bundle 为 `78608644d0044d02dabde91ba13e38441a09a5bf6dc949d1452986ccf947bf1a`。两份 bundle 都是 `bundle_format=1`、`inventory_format=2` 的有限 name-only 批次，没有 `album_links`。

## 快照、链接和 SGF 边界

既有生产 inventory gzip 文件 SHA-256 为 `518748084105398b4faeadc090d54f4a033b282a9402db20d2b0564fab465bd9`，内部 `inventory_sha256` 为 `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`，快照时刻 `2026-10-01T18:11:45.460901Z`。候选绑定文件 `wu-name-preimages-prod-20261002.json` SHA-256 为 `b1008149c2163938e31822119e38f5e5425b973517073a6aeb4a4f1ba605ea7b`。本次 live 复核重新确认了 **全部十一条姓名行前像**，但没有重新抓取全库 album/catalog inventory。

本次正式库只读分组复核了精确原值 `Go Seigen`、`吴清源`、`吴清源九段` 的黑/白槽位：黑方分别 412、49、59 条，白方分别 537、60、90 条；共 **1,207 个现有链接槽位，全部 FK=`player_id=1`，没有其他 FK**。10 月 1 日 pinned inventory 对同一精确子集复算出相同六个计数；按排序后的 `[album_id, side]` 对得到审计核对 hash `068b522e7db3180c81435f267f72756e2c6e7f0b1534a341f35ab52b8374a963`。这是已有 FK 的只读核验范围，不是新建链接、也不是新的独立身份范围批准。

本范围只更新 `player:1` 的十一条姓名决策，不新增身份、不改 PB/PW/EV、不改变任何 album FK；无需为 name-only bundle 选一组新链接。用户目标里提到的吴清源相关简单原始姓名及带段位写法已经关联到 player 1，不能再把它们称为待关联试点。现有两个 bundle 无 `album_links`，因此赵治勋精确关联裁决要求的逐链接 `production_sgf_sha256` 写前门禁不适用于这两个 name-only 批次；它仍是任何未来新增/变更 album link 的阻塞门槛。名称导入期间若需声明生产当前链接全集或要求当前 album/catalog 一致性，则应另取新清单，不能把 10 月 1 日的库存 hash 当作刚采集的全量快照。

隔离重放记录见 [clone rehearsal](kifu-name-wu-clone-rehearsal-2026-10-02.md)：相同生产备份快照恢复到独立序列库，按九语 `.2` 后两语 `.3` 顺序导入，核对十一语，再以 `2,1` 逆序条件撤销，`reverted=4/18`、`skipped=0`。因此已有记录足以证明 **11/11 name-only 集合可以在隔离库按两份原哈希工件重放**；它不是一个单体 11-member bundle。没有必要为了获得 11/11 exemplar 改写签名或重做演练。

来源 registry 的完整负面查证范围仍未全闭合，但这不撤销已经审过的十一条正向常规姓名。生产写入仍受 [既有 NO-GO 裁决](kifu-name-wu-prod-write-decision-2026-10-02.md)中全库覆盖及页面验收条件约束；本次核对没有改变该裁决。

本次没有新来源采集或受控 JSONL 修改，因此没有创建新的 `0700/0600` 证据 manifest。生产操作仅为 SELECT 和 schema 元数据查询；没有数据库写入、隔离库重放或部署。
