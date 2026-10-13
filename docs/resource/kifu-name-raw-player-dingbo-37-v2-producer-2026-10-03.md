# 丁波 37 槽十一语 v2 待独立签署工件

2026-10-03；生产者 `/root/raw31_bundle_producer`，运行时模型标识 GPT-6，未独立认证具体子型号。按 [raw 显示政策](kifu-name-raw-player-display-policy-astra-2026-10-03.md)及 [31 名独立适用性审核](kifu-name-raw-player-31-display-applicability-independent-review-sol-2026-10-03.md)，选定最小且完整十一语通过的丁波：37 PASS 槽、37 album、0 HOLD。新工件只授权原文字面显示范围的后续审核；所有人物 FK 继续 NULL，`album_links=[]`，身份增量 0。

保护目录 `~/.local/share/kifu-name-audit/2026-10-03/raw-player-dingbo-37-v2-producer/`（0700，文件 0600）含 bundle_format 2 / inventory_format 4 草案、37 槽 raw scope、新 v3 原文读音锚点、5 条新 raw 正面研究、6 条规则和有限批次、真实名称前像、全部验证日志和交接说明。全部新签署保持 pending；旧人物来源批准保留原字节，没有移植旧 owner 签署。

待签 bundle 规范 JSON SHA-256 `eb4acf470103289bfa9e8fee2cf9e5caa7a7810cba76e76a5853eca9636eeaef`；克隆 inventory SHA-256 `f4907ffbe70d62b4b77f6d3bf5ba7ed789f2685f46eff7ffdfe080f2abc4bab1`，基础 hash `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`；catalog SHA-256 `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09`；名称前像 capture 规范 hash `8f1544ed555faacde34bb4c81c7f89a5404d479a511ad1370c2958d3f2eb87c8`。签署会改变包及依赖 hash，这些是待签稿 hash，不能用作最终 apply hash。

十一语值为 cn/tw/jp 丁波；en/de/es/fr/tr Ding Bo；ko 딩보；ru Дин Бо；ua Дін Бо。规则决定保留 `transliterated`，五语走正面来源采用。最多新增 407 个实际姓名语言显示单元，尚未发生任何实际显示增益。

现有 raw_display_scope 协议能表达本范围。制包时发现拉丁复制规则的来源语种闸与已审规则不一致：LOC 为真实英文、RAE 为真实西文，旧 helper 对 de/es/fr/tr 规则要求每个来源属于目标语，报 `transliteration source provenance or language invalid`。保存了最小真实 fixture；主代理负责最小 test-first 修复和独立审核。仅重抓四个原规则引用端点以补齐缺失 provenance，全部 HTTP 200；ru/ua 表字节 SHA 与旧独立审核一致。保护目录中的 proposed registry 副本只拟新增实际繁中来源 taiwangorg.blogspot.com，未改共享默认 registry。

在当前工作区新来源分支上重新核对：六语 rule source provenance 6/6 PASS，五语 research 5/5 PASS，六语输出机械复算 6/6 匹配旧审核矩阵。完整 validate_bundle 实际 `ready=false/write_ready=false`，三个根错误均为未签 scope/anchor/规则的 exact approval 缺失，其余为未签 scope 导致 owner/member/candidate 依赖拒绝；provenance 错误 0。日志 `validation.after-latin-source-fix.json` 记录实际代码 HEAD `11bb4bf3281c1f1c3ab57a41a9f7e91de15de00a` 和结果；最终演练须重新核对代码提交与工作区文件 hash。

所有 DB 读操作只访问原隔离 clone，前后目录 hash 和表计数相同；173,025 album、876 player，raw value/name/batch/research/change 仍均为 0。没有生产或现役测试库写入，没有自行 Git 提交；克隆容器已停止。独立签署前未执行 importer dry-run/apply。后续须按交接说明先签 scope/rules，再由实际生产者重绑 v3 anchor/研究和批次；尤其 batch 必须重新生产于规则审核之后，不能直接给现稿补签并伪造旧时间。

## 第二阶段：已签范围与规则后的锚点/五语研究重产

按 [Astra 第一阶段独立 PASS](kifu-name-raw-player-dingbo-37-v2-independent-review-astra-2026-10-03.md)于真实时间 `2026-10-02T22:29:32.368505+00:00` 重新生产 raw v3 anchor 和五语研究；生产者仍为 `/root/raw31_bundle_producer`。新工件绑定已签 scope 规范 hash `5e9fbb5b309d6b9d3850b062c0b43abe4f12b01c0094f18e3114478c99c0a1de`，已签 rules 集规范 hash `129f6ee2bb0c0e25b76e5c5626bfe93903a5640e1a7d80f18f1f6b57ada7355b`；未沿用旧 draft scope hash 或生产日期。

保护子目录 `raw-player-dingbo-37-v2-producer/phase2-anchor-research/` 中的新 `source-raw-anchor-v3.pending.json` 规范 hash 为 `5492f42e079f82205494d2c66f2af8a8204953a6fed3c4871fff590971389ddc`，内容 hash 为 `61dc5b19d8c8864e42c2a8f707535f7df3c9f5e9a791b2e3af1bb27d5133cff8`。五语研究为 `five-primary-research.pending.jsonl`，联合证据为 `evidence.pending.jsonl`，日志为 `validation.producer.json`。修正 `source_link.review_basis` 不再声称音节待定；明确已审 `ding / bo`，来源记录人物对应与精确 37 raw 槽读音适用性是分别审核的决定，不建立 album 人物归属。

验证：签 scope 的全部成员与原 inventory 完整对应，双出版方来源记录结构一致，5/5 新 research 通过 validator；原来源事实、旧人物 anchor、五语来源记录和真实前像保留原字节，前像仍明确引用原捕获时间，不伪称本阶段重新查询。新 anchor 的完整 validator 按预期报 `transliteration content lacks exact approval`，留给 Astra 独立签署。本阶段无数据库连接、无新审核签名、无新候选或批次。原 `manifest.json` 保持原字节；新 `manifest.phase2.json` 冻结本阶段文件，阶段一 memo 原字节另存子目录，便于核验历史 hash。

## 第三阶段：签后锚点依赖的待审批次与候选

Astra 于真实时间 `2026-10-02T22:32:37.298471+00:00` 签署新 raw v3 anchor，规范 hash 为 `54778896d12031859791485d791b486d1327ef1abe53787a16780312be309324`。本生产者随后只读重查唯一隔离 clone，实际前像捕获时间 `2026-10-02T22:36:33.107109+00:00`；连接显式 `postgresql_readonly=True` 并核实 `transaction_read_only=on`。inventory/catalog 仍与签 scope 对应，精确 raw owner 和十一语名称行确实不存在，已批准名称快照仍为空。旧前像文件原样保留，新前像写入阶段三目录，未把旧查询伪称新捕获。

真实新生产时间 `2026-10-02T22:36:36.148331+00:00`，晚于 scope/rules/anchor 的全部审核时间。保护子目录 `raw-player-dingbo-37-v2-producer/phase3-batches-candidates/` 中新增六个单成员 `transliteration-batches.pending.json` 和十一语 `candidates.pending.json`，全部 pending、无新 reviewer；完整 `bundle.pending.json` 为原协议 v2、空 album_links，绑定已签 scope、rules、anchor、category 及已独立审核的 registry。规范 bundle hash `ee9a072eccd4a96d136e0cb86214ebb2e167d15ea736f85039ed0cf5e529a4db`。五语研究保持阶段二已逐语审核的原字节和实际生产日期。

实际 `validate_bundle` 为 11 members、11 candidates、0 missing、`ready=false/write_ready=false/write_errors=[]`。唯一根错误为六个待签 batch 的 `transliteration content lacks exact approval`；六语候选不能取得已签 member context，及新 raw 尚缺相应获准显示值，是该 pending 状态的派生拒绝。没有额外范围、来源、拼写、碰撞或前像格式错误。生产者日志逐一列出原始错误；最初日志断言漏列 signed-member-context 这一预期派生错误，保留实际报告后补齐核对，没有修改业务产物来绕过门禁。

前后 table counts/catalog 完全相同，未写隔离 clone 或现役测试/生产库，未自签候选或批次，未执行 importer apply。原 manifest 和阶段二 manifest 保留原字节；`manifest.phase3.json` 冻结本阶段工件及第二阶段 memo 的未改副本。下一步由 Astra 独立签署六语批次，并让对应六语候选继承真实批次签署字段/签后 hash；五语候选独立签署，之后才能重新 validate 和执行唯一隔离 clone 演练。潜在显示收益仍为 407 单元，当前已发生收益仍为 0，人物身份增量为 0。
