# 棋手预处理：非汉字名次 221–240 安全 18 项执行记录

2026-10-04 经独立审查批准，按[安全 18 项白名单](kifu-player-nonhan-ranks-221-240-safe18-exact-allowlist-2026-10-04.json)
先 TEST 后 PROD 执行。白名单 SHA-256 为
`aa1dbb9684c6fbca7d93a59b7adba745dd93cecf5189318faa4a9a3b983cb890`；
TEST 冻结计划 SHA-256 为 `1fce2efa729a1547a6f4a1071c13a84a597f71779443d17273002b984eef8209`，
PROD 为 `883450de60339f41763c049972ecf9c5f289edfd2e19f864a597d703541ddf7b`。
两库分别验证了计划与实时前像后，在各自单一事务提交。

| 环境 | 写入前已连席位／棋手 ID | 实际新增 FK（黑／白） | 新建 ID | 写入后已连席位／棋手 ID |
| --- | ---: | ---: | ---: | ---: |
| TEST | 264,787／3,798 | 839（481／358） | 7 | **265,626／3,805** |
| PROD | 266,392／3,620 | 839（481／358） | 7 | **267,231／3,627** |

每库均核验 18 个 exact raw／839 个目标席位的 FK 指向白名单对应目录 ID；
18 个原文审核行均已标记 `approved`，元数据中的目录 ID、白名单 SHA 与来源 URL
逐项一致。全量 173,025 盘的黑白原始姓名（346,050 个字段）与冻结 inventory
逐条相同。`KimHi-jun` 的 48 席和 `Tsuruoka Saburosuke` 的 45 席仍无 FK；
两项审核行保持 `pending`，元数据为空。

`Ito Matsujiro` 的 48 席复用 `Ito Showa` 已建的“伊藤松次郎”ID：
TEST `12441`、PROD `6672`。[CWI 丈和棋谱](https://homepages.cwi.nl/~aeb/go/games/games/ancient/Honinbo_Jowa/)
直接给出这两个罗马写法的同人对照。本批新建“安井算知（九世）”ID
为 TEST `12455`、PROD `6686`；后续涉及九世别名的批次应分别使用各库 ID。
未扩入 241–260 名次。
