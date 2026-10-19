# 李昌镐 ID 143：五槽位 v2 最终载荷独立批准

审核者 `/root/lee_link_scope_astra`，调度模型 **`gpt-6-astra`，推理强度 `max`**；独立于草案生产者／前像绑定者 `/root/lee_five_bundle_draft`（`gpt-6-luna`）及十一语原来源生产者。真实签署时间 **`2026-10-02T05:12:33.913649Z`**。对照草案提交 `ee307238` 和[先前五槽位身份决定 `4de8d3f6`](kifu-name-lee-143-finite-link-scope-review-2026-10-02.md)；离线校验时仓库 HEAD 为 `b9ac7143f541809e567f7ff29e94ef1fdcbb8ac0`。

**PASS：已独立签署五个精确身份关联及十一条完成真实前像绑定的名称候选。** 实际落盘包通过当前离线 CLI：`ready=true`、`write_ready=true`、11 approved、0 pending/rejected/missing，`errors=[]`、`write_errors=[]`。批准只属于此确定载荷；下一步可按既有流程进入生产等价隔离演练。本次没有数据库写入、部署、全库完成认定或生产发布授权。

## 范围、来源与前像核查

五个槽位仍严格为 `40212/black`、`64489/black`、`83228/black`、`97368/white`、`98003/black`，均为 `NULL → player:143`。没有新增身份、别名、赛事关联、非空 FK 纠错或元数据修正。完整 `李昌镐` 原文范围仍是 2,140 个槽位，2,135 个 HOLD 项与此前决定完全相同；98115、98268 及其余异常未被纳入。

独立检查了草案七个文件的实际字节哈希、全部十一条研究记录、原来源审核候选与 provenance；其值均与[草案记录](kifu-name-lee-143-five-link-v2-draft-2026-10-02.md)相符。每条候选的显示文字、原生产者、研究哈希、俄语排除项及裁决都与真实来源审核行相同；草案仅新增前像绑定并移除旧签名。本次没有把旧来源批准时间挪到修改后的候选上。

我在正式库 `ucloud-v100 / katrain-ucloud-postgres-1 / katrain_prod_20260725` 开启独立 `REPEATABLE READ READ ONLY` 事务，快照时间 `2026-10-02T05:08:51.65031+00:00`，捕获结束 `05:10:17.966207+00:00`，最后 `ROLLBACK`。重新读取并按当前导入器的行序列化规则计算了完整 inventory：173,025 条 album、173,034 条 source link；又按固定表序及 ID 顺序计算六张 catalog 表：棋手 876、赛事 22、棋手别名 23、赛事别名 8、两张 raw value 表均 0。两个整体现时哈希均与冻结包相同。保存了该次完整哈希输入行、SQL 和核对结果，可在仓库外复算，而非只信任生产者报告。

同一只读事务中重新读取五份生产 SGF 和 player 143 的全部名称行：五份 SGF 的 UTF-8 字节哈希均等于原身份审核、草案和包内 `production_sgf_sha256`；五盘完整 association 哈希与 expected 上下文均吻合。`cn/en/jp/ko/tw` 五个旧名称完整行哈希均匹配；`de/es/fr/ru/tr/ua` 六语确实仍缺行，对应显式 `null`。重新核对了目录目标前像、精确 canonical 唯一性及无该身份别名状态。

五盘身份依据仍是已审的韩国棋院人物档案与日本棋院 2009／2010 富士通杯具体成绩记录；保存的日本棋院响应体 SHA-256 为 `1e99d71bbc5f73f80c92785257d7ab8808d90a33f4bef56b5e44c430a1fddc47`，与包内来源核对相同。来源记录的日期、对手、先番三角标记、结果及源 SGF 对应关系见先前身份备忘录，本次逐条核对载荷沿用了相同五项。没有将同名或目录唯一性单独当作身份依据。

## 十一语与签名时间

| 语言 | 批准显示 |
| --- | --- |
| `en de es fr tr` | `Lee Chang-ho` |
| `cn` | `李昌镐` |
| `tw jp` | `李昌鎬` |
| `ko` | `이창호` |
| `ru` | `Ли Чханхо` |
| `ua` | `Лі Чхан Хо` |

本次是最终载荷及绑定复核：名称用法的原独立来源审批保留在[十语来源批准](kifu-name-lee-player-143-source-approvals-2026-10-02.md)和[俄语修订二批准](kifu-name-lee-player-143-ru-corrected-v2-independent-review-2026-10-02.md)，我核对了其真实签名行、文件哈希、研究内容及导入器验证；不声称本轮重新抓取了每一种语言网页。十一条研究均在固定 registry `2026-10-02.3` 下通过 `validate_research_record`，状态为 `found`。这个包不要求也不宣称负面检索范围已经闭合。

俄语明确采用 `Ли Чханхо`；`Ли Чхан Хо`、`Ли Чангхо` 两个已见异写及原 Sol 裁决完整保留。本次另复核保留的俄语档案、维基响应及韩国棋院正文哈希。RusGoLib 的时间仍仅被接受为已披露的本地归档 mtime 界限，不伪装为经认证的 HTTP 请求时间；专门围棋资料站用法不被描述成官方统一命名裁定。乌克兰语仍基于所录文章图注及围棋语境，不升级为专门人物传记证据。新签名明确保留这些限制，也不批准搜索别名。

时间链为：十语来源批准 `04:09:17Z`、俄语来源批准 `04:28:11Z` → 名称前像捕获 `04:42:14.526646Z` → 独立生产者绑定／范围冻结 `04:59:27.004972Z` → 本审核者现时只读复核 → 实际签署 `05:12:33.913649Z`。所有新的审核时间晚于相关来源捕获、候选生产、前像绑定和范围冻结，审核者不同于来源生产者与绑定者。

保留所有冻结输入字段，包括原生产者的 `identity_basis` 草案说明；其“尚未批准”描述的是原草案状态。真正的最终决定是本次新增的 `review_conclusion`、`status=approved`、审核者和时间，不改写先前生产历史。五个 `identity_review` 使用同一独立决定；只增加真实批准签名并重算依赖它的 link-set 哈希。十一条名称也只修改 review 状态并添加本次签名，未改显示文字、研究、前像或绑定者。

## 已签工件及校验结果

受控输出目录为 `/Users/fan/.local/share/kifu-name-audit/2026-10-02/lee-143-v2-reviewed/`，目录 `0700`、全部文件 `0600`。原 `lee-143-v2-pending/` 未修改。该目录包含可独立执行离线验证的 `bundle-reviewed.json`、inventory、research，另保留 `signed-candidates.jsonl`（11 条）、`signed-identity-reviews.jsonl`（5 条）、原来源候选及 provenance、审核者生产捕获与 manifest。

| 核对对象 | SHA-256 |
| --- | --- |
| 原待审 `bundle.json` 文件 | `7652d7a20b76e9f677651d0ea081acde64acf8449cd232ece6a242b08e87d00c` |
| 固定 scope，签署前后未变 | `221bb5180b81db45b44ea4f70bd56a5e052312b4713dddc5d4baa936c1b1668b` |
| inventory 内部／現时重算 | `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3` |
| catalog 現时重算 | `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09` |
| owner set | `8c0cc7e543e422e43c95ba6b686ee468acdd7555b14177a06117459c2bde51d4` |
| member set | `2e9d6aa213b65ec4b4646065c0e49fd8384a377fd66f266b7e08cd24310f2003` |
| 已签 link set | `06aec13ed0f7d9ce0da74caac6bb4249cc0f8d7dd32c3cf7643a476694bf027e` |
| 已签十一候选数组 canonical 哈希 | `f826dcafe1d1f6bca42699250b5739ad6266734512b90aba010f936a5f3cf1fe` |
| **已签 bundle canonical 哈希（导入器使用）** | **`cb0bb519a39583120b8872322ead962cd52faeed8975527c0d6a864ffb583c39`** |
| `bundle-reviewed.json` 完整文件 | `6d7b9f5fdbe16cea483f071cf58f61b4a53067cd1af548411f7cb0749e4de99a` |
| `signed-candidates.jsonl` | `5c7407fcaf422c0b27a3f2b5fcb85bd8e3135c4e535a70dc6f715fed1e87a775` |
| `signed-identity-reviews.jsonl` | `f2d0618c0dbd22f89cd682ec21284c1a84551100984e6cdef8ab4ddd04cda2ac` |
| `review-manifest.json` | `c0539b82b934b8d14bae3cd9e79065155e23a1cda942939109406f0d5e2a26a4` |

`scope`、owner、member、link、候选数组和 bundle 使用现有 `canonical_sha256`；完整文件哈希包括尾换行。每条已签候选行哈希、所有输出文件哈希、实际签署时间和输入文件哈希均在 `review-manifest.json` 中。完整 scope 中的 `raw_scope_sha256` 仍为 `43b19733404467dbe5300258627767d32ecd13138de7ac81d26a5a720acac9ec`。

实际从磁盘运行 `scripts/kifu_name_candidates.py validate`，显式使用 registry `docs/resource/kifu-name-source-registry-2026-10-02.3.json` 及本输出目录的 inventory／bundle／research，退出码 **0**，结果如文首。没有通过伪造 inventory 成员资格取得通过；player 143 由包内五条真正获批链接进入候选适用范围。该 `write_ready` 只证明有限离线包满足结构与审批约束；实际 apply 仍必须在锁／事务内重新核对 inventory、catalog、名称前像及 SGF 哈希，并遵循现有隔离演练和生产发布门槛。
