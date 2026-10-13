# generic49 名称碰撞的有限决策 — 2026-10-06

**决定：不放宽本次碰撞门禁；先交付其余 48 raw / 547 局 / 240 个名称，暂缓 `全国围棋个人赛` 的 10 局、5 个名称。** 已完成的 generic49 owner 审批保持有效，名称子集重新绑定、签署即可，不需要新增 owner profile。

## 实际证据

- 当前 TEST dry-run 明确拒绝 `cross-bundle normalized name collision: cn:全国围棋个人赛`。
- 已独立读取 root 最新只读捕获 `/tmp/kifu-event-title-generic49-20261006/{TEST,PROD}/live-collision-capture.json`：两库均为 **event owner 72** 的名称行 **id 240**，cn、`全国围棋个人赛`、`conventional`、`verified`、`generation_rule_version=none`、revision 1；evidence_id 分别为 TEST 497 / PROD 502。两库待写 literal raw owner 均为 **72432**。这已确认是赛事名称碰撞，不能归为两个 raw 描述之间的碰撞。
- 当前源码 `classification-v2` 的 cn `individual_event` 模板是 `个人赛`，并非 `全国围棋个人赛`；旧 legacy generic reader 还要求 exact raw `个人赛` 与 exact 模板一致。因此没有证据支持将当前报错直接归入合格 generic 分类描述共享文字。
- 对当前 245 个候选和上述本地 catalog 做有限比对，只发现这一 cn 与 event 72 的名称碰撞；这不替代后续正式子集 dry-run。

## 为什么不加 writer 例外

`name_batch._check_cross_bundle_collisions` 目前只豁免两个通过现有审核的 literal raw 描述之间的文字相同。事件 owner 72 不在此边界，不能借 generic-category 分支跳过；也不应修改旧名称、证据或给新标题加无来源的字词规避报错。

即使另一项真实案例是 generic raw + literal raw，仅放宽 writer 也不足以保持既定搜索行为：strict `strict_matching_names` 与 legacy `reviewed_raw_event_search_clause` 都只对全部 `translated` 的多 raw 组做精确并集。混合 generic/translated 会被视为歧义并退回既有原文/全文匹配；strict generic 搜索分支本身也不是 literal 的 NULL-event/no-selection 条件。因此本轮不批准这种泛化例外，也不为了当前一项碰撞引入新搜索规则。赛事、棋手、raw-player、alias 的限制保持现状。

## 最小交付动作

1. 暂缓 exact raw `全国围棋个人赛`，两库 raw owner 均为 `72432`，全 occurrence 为 10。保留其五种已经研究出的真实名称及原始证据待后续处理，不伪造替代显示名，不新增 identity link。
2. 以原 generic49 名称包的其余 48 个完整 raw owner 组成新的有限 bundle：**547 局，240 个名称，format 2 / inventory 4，album_links=[]**。sorted raw-set canonical SHA-256 为 `26d7786cc5315fff1d962046c81a34bfef09afe50ca147993d5410b0a7eb4c4a`。
3. `owners`、`members`、`candidates` 一致排除该 raw 的五项名称；保留每个剩余 owner 的全部 occurrence。刷新实际 inventory/catalog/name 前像绑定、member/owner/bundle hashes 及独立签署。允许复用未变的已捕获来源，不可剪掉成员后仍沿用旧的整包 SHA/审批。
4. generic49 owner profile 已完成 49 owner 审批，其固定范围没有被改写。名称 bundle 可以在这些已批准 owner 中声明有限子集；不需撤销 owner110，也不需为了 48 个名称 owner 新增或篡改 ownerCLI profile。
5. 正式 dry-run 通过后按原事务与核验流程交付此子集。剩余 10 局明确记作“owner 已审核、名称因已存在赛事名碰撞而暂缓”，不计入新增五语言覆盖。

本轮只读本地代码与既有捕获、写本决策文件；没有 DB、SSH、代码修改或整包复审。
