# 胡耀宇修锚后的六批：独立 batch 审核 PASS

2026-10-03；reviewer `/root/freq41_60_95_review_sol`，GPT-6 运行时身份（未独立认证子型号），与[producer](kifu-name-five-cn-origin-hu-batches-rebound-pending-sol-2026-10-03.md) `/root/anchor_format4_impl_sol` 分离。**只批准 de/es/fr/ru/tr/ua 六个有限 batch**；不签30 candidate、主五25 candidate、最终 bundle、人物 FK 或数据库操作。

## 精确复核

- Producer manifest SHA `7d21c35258b0408ebcbbbc9fbefee13632015c815e5c027b605cdebb0bb8f7e6` 及其全部文件 hash 相符。
- 五个已签锚集合及 bindings 与[修锚独立签包](kifu-name-five-cn-origin-hu-locator-independent-review-sol-2026-10-03.md)逐字节相同；五锚 validator 全通过，胡完整已签 hash 为 `c4a9f2341449c7d4586718e30dcc4895c0ebf809645a50e7868df49bd2a63172`。
- 五 scope/category 的 owners 文件与旧最终签包逐字节相同，SHA `fc3bdafda183dc98b493cac2fe9b435f8f383f3abf7fd2734c8d91fe2f26301b`；4,358 槽及原审批未变。六条 rule 的完整 content／approval 对象与旧最终签包完全相同，集合 canonical SHA `5a33c96164247852ebece329f30b7d2bdd626ea5302f332bdb5577d165d5b00e`；没有重签规则。
- **每个 batch content 唯一变化为胡成员 source_anchor_sha256：旧 `511c54…` → 新 `c4a9f2…`**。其余成员、owner、原名、scope、rule、读音、输出及 approved-name snapshot hash 均未变。五人×六语30输出逐值核对并重新计算一致；归一化碰撞0。
- 沿用的冻结 approved-name snapshot 实际为空，canonical SHA `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`；这是历史克隆范围的批次核对，不声明当前生产目录或前像仍相同。

真实 producer 时间 `2026-10-03T02:37:25.357621+00:00` 原样保留。真实独立签署时间 **`2026-10-03T02:41:53.667886+00:00`**，晚于新冻结生产及依赖审批。签前六批被 pending 审批门禁拒绝；签后实际 `validate_transliteration` **PASS：6批、30完整成员绑定**。验证使用原 pending candidate 的成员集合，没有修改或签署候选；另验证其30行全部仍被 `validate_transliterated_candidate` 的 approved 状态门禁拒绝。

## 新完整已签 batch canonical hashes

下游须使用下列完整已签 record hash，并继承确切 batch 审核字段；不能使用旧 batch 或 pending record hash。

| lang | 完整已签 SHA-256 |
| --- | --- |
| de | `38fa0f4300c94fea6f4fad6e22d5dd83e050878b7ef8f0d45fd41512ef6dbadf` |
| es | `4a834281b35704245d1e77acc778cd1ca047a8156d8d86544add02d22aced244` |
| fr | `61eeba56093b9eaae1d15e50655bf397528e4195523156b6c45fd2f228ccb981` |
| ru | `f759a1448540d8d30269347e18cc644f337692a121621f8c239950bcdb65346e` |
| tr | `4c91f13f20ebbd287b6fb3ac1afcb07b2569d27c4491503af4bd005d92c055bf` |
| ua | `d3c640e0f2dc8696bc6a7361e6a5b5418ba843f9c885550b3f692369ceaed200` |

独占受控目录 `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-hu-batches-independent-review-sol/`（0700、文件0400）：

- `transliteration-batches.approved.json` 字节 SHA **`169320542a662422c10d858726cf33e1b61f3ac0e42fb8e2deef611836aa5b78`**。
- `transliteration-section.batches-approved.json` 字节 SHA **`6b15c440f25a2eda23f8dd58072cdc51c2e0dd64432d0e086cf85ed69cc847bf`**，仅提供已签规则／批次 section，不是可执行最终 bundle。
- `batch-record-bindings.approved.json`、`review-record.json` 保存每批 content／pending／旧／新完整 hash、真实审核时间、全部输出、碰撞及 validator 结果；其字节哈希由新 manifest 固定。

30 candidate 的新完整 batch 绑定、确切审核字段及真实目标前像／最终审批，主五候选批准、新最终包克隆演练仍待完成；历史克隆回执不移用于新包。本次没有连接 DB、运行克隆、修改代码／producer／旧包或提交 Git。
