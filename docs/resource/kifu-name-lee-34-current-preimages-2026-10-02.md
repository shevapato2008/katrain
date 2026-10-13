# 李昌镐 ID 143：34 槽位现时前像捕获

> **更正结论：34/34 个 `association_sha256` 均匹配。** 早期临时检查把位置数组直接做 canonical hash；当前导入器先按 `association_columns` 把数组映射成具名对象再哈希。错误来自检查表示，不是草案字段或值不一致。下文的 unsigned 修订包已填入现时生产 SGF 前像并重算 link-set；没有签名或 apply。

2026-10-02 对正式库和隔离演练库进行了只读捕获；没有运行 apply、undo、迁移或任何数据库写入。完整 SGF、名称前像与行数据保存在仓库外 `0700` 目录 `/Users/fan/.local/share/kifu-name-audit/2026-10-02/lee-34-current-prod/` 和 `lee-34-current-clone/`，文件均为 `0600`。私有汇总 `summary.json` SHA-256：`3e43dd57ef60b2764e097e85f43d3a3e45fa86e892c1060545b1fbd63c41ef01`；其中登记逐项 SGF SHA-256、十一语名称行前像和捕获文件哈希。

## 正式库

`ucloud-v100 / katrain_prod_20260725` 的单个 `REPEATABLE READ READ ONLY` 事务时间为 **`2026-10-02T10:30:31.761425Z`**，结束后 `ROLLBACK`。同一事务捕获了完整 album/source 行、六张 catalog 表、player 143 名称行、全部 34 份生产 `sgf_content` 及选择表存在性。共 173,025 个 album、173,034 条 source link。重算 base inventory SHA-256 为 `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`；catalog SHA-256 为 `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09`；精确 `李昌镐` 黑白槽位 2,140 项，其 `raw_scope_sha256` 为 `43b19733404467dbe5300258627767d32ecd13138de7ac81d26a5a720acac9ec`。这些均与草案上下文一致。player 143 有一个精确 canonical、零个精确 alias。

34 个目标槽位的 raw 值、完整期望上下文和目标 FK（均为 `NULL`）全部匹配草案。现时每盘 SGF UTF-8 哈希和十一语前像见私有 `summary.json`；其中 `cn/en/jp/ko/tw` 五个现存名称行的哈希与先前记录相同，`de/es/fr/ru/tr/ua` 六语当前均无行（显式 `null`）。克隆捕获中同一 34 份 SGF 哈希及十一语前像均与正式库一致。

## 隔离克隆

`home-ubuntu / kifu_name_rehearsal_20261002` 的新 inventory 捕获时间为 **`2026-10-02T10:26:16.351327Z`**，格式 2，base SHA-256 同为 `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`。文件 SHA-256 为 `cf4f2a267885163d947cf668bcc5a83c8e6f9e4d474eec76329b8140bfe93595`。另一个 `REPEATABLE READ READ ONLY` 事务于 `10:32:09.195312Z` 捕获 34 项当前 album/source/SGF 行、player 143 目录/alias/name 前像及 event-selection 行数：34 个目标 FK 均为 `NULL`，选择行 0，selection batch 行 1；随后 `ROLLBACK`。

## 冻结阻塞

- **关联哈希无阻塞：** 34/34 个草案哈希与新鲜生产捕获及冻结 v2 inventory 的具名关联对象相符，原因见文末补充更正。
- **format-4 证据限制：** 正式库捕获事务中 `kifu_album_event_selections` 与 `kifu_event_selection_batches` 均不存在；正式 Web 容器也无法导入当前仓库的 `kifu_name_inventory` 模块。因此不能生成生产 format-4 selected-event supplement。当前包只含 player 黑白链接，已捕获的 format-2 完整 base inventory 可绑定这些链接。
- **克隆 format-4 证据限制：** 克隆库有上述两张选择表，但当前运行镜像的 `build_inventory(engine)` 不接受 `inventory_format=4`（远端模块 SHA-256 `ca94e5c230e1f43c4c3c632ba5faf97911e3f9bb07da6448b6c15de041818e42`）。本次获得完整 v2 base inventory；它不包含 selection supplement。若需证明完整 format-4 克隆状态，需运行时版本支持后再捕获。

本 memo 提供的是现时只读前像证据，不签署或冻结草案，也不构成任何写入授权。


## 补充更正：关联哈希表示与未签前像版

早先版本的本 memo 曾报告 34 个关联哈希不匹配。该结论是捕获后本地比对脚本的错误：我把 inventory 的位置数组直接传给 `canonical_sha256`。当前验证器先按 `association_columns` 将数组映射为具名对象，再对对象做规范哈希；JSON 对象键名会进入哈希，直接哈希数组自然得到不同值。字段和值的对应关系没有差异。按同一对象规则复算后，**34/34** 新鲜正式库关联对象与冻结 v2 inventory 完全相同，也与原草案 `association_sha256` 相符；34 个目标的期望上下文仍全部相同。该表示与五链接已签包的验证逻辑一致，例如 `27182` 的对象哈希为 `927383826884d8c1e579e7b7c6c68895b36a2ab6573377e497a80a3629142ec1`，与草案一致；已签五链接包中 `40212` 的对象哈希也与包内值相符。

我据现时生产事务为原草案生成了一份仓库外的 **unsigned / unfrozen / unapplied** 副本：`/Users/fan/.local/share/kifu-name-audit/2026-10-02/lee-34-current-prod/bundle-corrected-current-preimages-unsigned.json`，文件 SHA-256 `d6058561f8e8cc859bb5d784308efe887eda74729254146f2b7f7d11e4b06f13`，canonical bundle SHA-256 `215c28502d51ec0158c3f52723b8719db7a5fcdeb0ce9a8096c149e82be29af7`，更新后的 link-set SHA-256 `d6d9668bcd41895b9d8d50460718c3fcfec1769aeab53fc27ebc8d1e4700de4e`。34 个 `production_sgf_sha256` 来自该事务；关联 SHA 经同事务对象重算并保持原值。更新只涉及逐链接 SGF 前像、重算 link-set 摘要；原草案文件保留。身份复核仍为 pending，十一语名称前像与绑定仍为 null，没有 freeze、签名或 apply。逐项核对及文件哈希在同目录 `correction-record.json`（SHA-256 `e5ffcbf49109b2e513737b02d3e6ab82fe3f280cd482405448f0dd7bd49f5b7f`）。

