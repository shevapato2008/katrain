# 五位 CN-origin 棋手全十一语：独立审批与隔离演练 PASS

日期：2026-10-03。Reviewer：`/root/freq41_60_95_review_sol`；真实运行模型 `GPT-6`（未另行声称 subtype）。Producer：`/root/anchor_format4_impl_sol`。**25 个主五来源/候选、6 个完整次六 batch、30 个次六候选及有限 CWA registry 新项均 PASS；HOLD 0。仅批准 raw_value-scoped 名称显示，person FK/alias 0。**

## 来源、范围与时间

输入 manifest `41f0fcd3a617c57bdaaa7d63fced0374e56e1dbb40f8c4a54b71146df694c1c0` 的全部 75 文件逐一复验。25 source cells 的原始字节 SHA、连续 excerpt、exact span、HTTP receipt、目标 locale、同 profile ID/DOB 与官方 CWA 唯一行均核对。25 source-facts 对应 19 个不同 body；15 行复用真实旧 receipt，9 次新 HTTP capture，另有唐日语真实 Wikipedia capture。source-facts.reviewed.json 保留逐格 body 路径/hash、语言、来源与结论。

| raw_value | 精确槽数 | cn | tw | jp | ko | en |
| --- | ---: | --- | --- | --- | --- | --- |
| 唐韦星 | 858 | 唐韦星 | 唐韋星 | 唐韋星 | 탕웨이싱 | Tang Weixing |
| 杨鼎新 | 864 | 杨鼎新 | 楊鼎新 | 楊鼎新 | 양딩신 | Yang Dingxin |
| 檀啸 | 911 | 檀啸 | 檀嘯 | 檀嘯 | 탄샤오 | Tan Xiao |
| 胡耀宇 | 868 | 胡耀宇 | 胡耀宇 | 胡耀宇 | 후야오위 | Hu Yaoyu |
| 连笑 | 857 | 连笑 | 連笑 | 連笑 | 롄샤오 | Lian Xiao |

以上 25 格均 PASS。唐 jp 按用户明确选择日本 Wikipedia **唐韋星**，实抓 revision `103506819`，H1 无空格，原文日本语、1993-01-15 与中国职业棋手导言匹配 CWA000040；body SHA `bcf4a67f0668716bee4e3ba35fe18eb3d7147d7e204d4d0a149b63f7fff4c4c8`。oldid 链接仅为版本引用。杨 jp 为日本棋院三星杯正文的「楊鼎新九段」，仅去段位，2019-09-04/05/06 三番胜负与 GoRatings 1193 同 DOB 的比赛历史吻合；未增加空格归一化。其余 24 来源选择未因 Wikipedia 偏好重做。

Hu 官方 CWA 原 JSON `18ba2a04efdca69d47528cbe703d9c54e1005b7f986af782434cbc3f1dd316f9` 真实 locator 为 `data.Z08[10]`，已签锚 full canonical `c4a9f2341449c7d4586718e30dcc4895c0ebf809645a50e7868df49bd2a63172`；其他四已签锚独立保留。五 scope/category、六 rule、六 batch content、输出/成员均与上一签包逐字一致；总计 **4,358 槽、4,238 albums**，无范围扩张。

新增 registry 仅 version 与 `cwa-professional-api-cn`：真实 HTTPS host/path `wqapi.cwql.org.cn/playerInfo/professional/list`、cn、found、这五 raw owners。canonical SHA `9982bac257df241d5982b0ea67490aab61a11953dff6932a26af8366a756a553`，byte SHA `51b3e3397aa3e2a3fb9ea3bbc3b550ab4fcf966ca628bba40b49f531156cd684`。旧 entries 与 language_scopes 不变；附加声明字段没有被冒充成新增运行时强制能力，批准不推广为整个 host 或未来 scope 的许可。文件版本保留 producer 原始 pending 字符串，独立批准状态在 registry-approval.json。

实际独立 reviewed_at **`2026-10-03T03:47:08.841989+00:00`**，晚于 producer 冻结 `2026-10-03T03:35:07.424483+00:00`、capture `03:34:54.904919+00:00` 与全部 bound_at。25 主五候选据已核正文签署；六完整 batch 更新真实 reviewer/time，再机械重绑 30 次六候选。全部 55 原始 `source_candidate_sha256`、`bound_at` 与完整 preimage_binding 保留且逐一验算；未倒填时间或 producer 自批。research 记录保持原 pending 研究状态，审批在候选和独立记录中。

## 完整已签 batch hashes

| lang | signed record canonical SHA-256 |
| --- | --- |
| de | `9264220fd9b98e26b118bd6bc931f010444c8b14feeeaa5d5ee061dd6a267d2e` |
| es | `eaf11ca603484153bc70f14f4d509938dbb0863ad3c75ec311d0fd6f916c78f8` |
| fr | `1925dbad84fb2e62bdd8dd02c40a8754bf78b6049535c4b9b869b0bec8b15340` |
| ru | `8928a5bff8995afb397d2663cfc3fed9bc4b24240d7b728e07fa67f7cf266d34` |
| tr | `255a566bbbcb99470c1505b196a0cfbecf4136ff2988b3c17fee2ca96860fe7b` |
| ua | `7ab5890ef2a2c9b53227c9e527988dffd4b7f8d0c739a0acf38d2619305c9fa1` |

## 实际校验与隔离 clone

`validate_bundle`：55 approved，missing/rejected/errors/write_errors 均 0，**ready=true / write_ready=true**。独立 readonly dry-run：4,238 albums、115 estimated undo rows、SQL writes 0。只连接获准的历史 clone `127.0.0.1:55439/kifu_raw31_clone_20261003`，container `kifu-five-main11-pending-sol-20261003`；重复 REPEATABLE READ preflight 核 inventory/catalog/五 owner与全部11语空前像及4,358完整context，不声称当前生产新鲜度。

实际 clone 演练 `2026-10-03T03:51:27.886184+00:00` 至 `2026-10-03T03:53:29.022029+00:00`：

- apply batch_id **6**：115 changes = 5 raw owner + 55 name + 55 evidence。
- 4,358×11 = **47,938/47,938** 精确显示格通过实际 strict display/slot approvals；主五 21,790、次六 26,148。每个显示值的实际 strict search 返回准确签署 cohort。
- replay：already_applied、change_count 0、SQL 写语句 0，读回状态不变。
- conditional undo：115 reverted、already_reverted 0、skipped 0；所有业务表 hash/目标完整 album rows 与撤销前基线一致，逐槽显示/审批恢复基线。
- 全部 **173,025** album SGF/FK SHA 保持/恢复 `18d4ff1a39aaeaa60280ace733c643c665fa2c3772d08c012195f35c8643817a`。batch/change/registry 审计记录按正常撤销保留，不将其称作全部数据库字节恢复。
- 限制写表为 raw owners/names、name evidence/batches/changes/registry；没有 album/person/event/FK/alias 写入。固定代码文件 hash 演练前后相同；clone 已停止、Running=false。

## 冻结产物

审批目录：`/Users/fan/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-main11-independent-review-sol`。演练目录：`/Users/fan/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-main11-clone-rehearsal-sol`。目录 0700，冻结文件 0400。

| 文件 | 字节 SHA-256 |
| --- | --- |
| approval manifest.json | `819682d6faa96c67176960dfb68a9ea11786dc49122a208db83e5f33f8a66940` |
| bundle.reviewed.json | `9c1e9f451f4235e1fc6698b22fa299fd50587a32b9303589839a34a2fb4aae35` |
| candidates.primary-five.reviewed.json | `7d1bcbed19d529f0ae79cc2297d1fa5518582c5424b27aa8b5b201a67394864f` |
| candidates.reviewed.json | `1ab8c11165c31717718ca1704f17a20b1e1f75c1a540537448ef24185e47c132` |
| transliteration-batches.approved.json | `08af294dd6048b2ac882d5fdd87f36684203b2298f85d89d9f0fcad144a9d494` |
| review-record.json | `3c531c01c7e8ab148693197f060142fe5514547d1fd93458041eb6dc4ecaf1f1` |
| rehearsal manifest.json | `29b114e493127aa36514dcc4ee2bac92fe983eba9fe02a3c558bfb60723b9cd2` |
| rehearsal-result.json | `9bac30b9c6e8c7e9f4eb79011f03664bbbb4bf3d8e3f8dffbbaed1aba88eee4d` |

最终 bundle canonical SHA：**`64e399b7c5f010012448b0e6ba189593f390da43d005825dcf9bd3fe031bfbfa`**。完整 body/record/code/runtime/SQL/stop receipt 哈希由两个 manifest 冻结。没有修改 producer、旧签包或应用代码；没有 live test/prod 连接/写入，没有 Git commit。本批准和演练仅适用于这份精确有限历史 scope；不是 person identity/FK、全目录十一语覆盖或生产发布批准。
