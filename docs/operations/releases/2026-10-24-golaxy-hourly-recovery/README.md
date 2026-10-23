# 星阵小时同步发布与真实恢复（2026-10-24，北京时间）

已部署并完成真实恢复：两个新包共 20 盘完成 TEST→PROD，旧 78 盘全部续验通过。部署后全新 Astra Max 首轮流程审核发现 4 个赛事原文／5 个日韩字段／6 盘的语义错误，已追加受控原生名称纠正及防复发 guard；原始包、SGF 和发布回执保留。纠正后的真实 run **71146 成功，221.734 秒、error 0**，3600 秒调度已恢复，无暂停控制、无重复模型调用或棋谱。最终独立实物复审 **Approved／无剩余 must-fix**，见 [Astra 最终报告](astra-deployed-flow-review-final.md)，首次 [Needs fix 报告](astra-deployed-flow-review-round1.md) 原文保留。本目录属于独立证据分支，不为记录移动已部署源代码版本。

## 发布版本与边界

最终已发布 **develop `4bf9a699a35ecdf025f5ec2f414425e3f2a13693`**，对应 **parent main `c4a31024095434b894beaad23995651cabf56b1d`**。名称质量功能分支 `fix/golaxy-event-name-quality-20261024` 为 `254dae25f96759fea590effe4fcade87be406d76`。最终聚焦回归 **368 passed in 15.32s**；名称与缓存续跑的独立 Astra 检查 **67 passed**。

历史链：初始功能 `109f0888af3c6630e9e9517d9ec59cb901714f5d` → develop `ef96a50a7e69e93e57e890cca837c9298f45f329`；远端接收边界补丁 `af0c72787` 经另一位 Astra Max Approved，合入最新 develop `b457347e1` 后，原功能分支到 `777e13c387d15e9351d776a8d9653ee931938414`，中间 develop 为 `662b6a25048ee2bb3752bdbf54fb3a927ab68084`、parent 为 `6469d9974f8423f003e6885cf5203a1522c38120`，该阶段 301 项回归通过。之后的有限名称 guard 同样独立 Astra Approved，再正常合入上述最终 develop 和 parent。

本次使用精确运行镜像作为 FROM，先叠加原 9 个同步 Python 文件，再叠加 3 个接收边界文件（重叠 2 个），最后叠加 `names.py`，共 **11 个同步模块**。`KATRAIN_BUILD_SHA=4bf9a699a…` 表示这组覆盖文件提取自已发布 develop，不表示其余后端或前端与 develop 整树相同。实际 hash、基础镜像和继承检查见过滤回执及 `final-post-correction-readonly-inventory.json`。最新 develop 含 OGS 课程模块，但本次未叠加其文件；也未部署未授权的图标、复盘设计、RK 或其他棋类。

| 运行服务 | 最终镜像 SHA256 |
| --- | --- |
| TEST `katrain-cron` | `9c414726fa56da734e7f47f6fb409d6373e747a9198c4c80bb31fc4606bccb98` |
| TEST `katrain-web` | `2eaccedb9fe74f51810b9e77e2367bf2cd40b0181b19719c9b33c568fde735d8` |
| PROD `katrain-ucloud-katrain-web-1` | `6ced68bdd5db0fde24838f384c450bcd7e329b681eaa40788578bc0a0c4042d2` |

PROD cron 未启用星阵采集；仅 TEST 执行来源抓取及必要名称模型调用。原 compose/env/mount/端口/user/cmd、stage、GPU、DB、MinIO、受限 SSH receiver wrapper 和大厅 API/静态 UI 保留。回执中的 env 仅保留摘要和必要非秘密预算，未包含凭据。

## 真实旅程与故障恢复

真实运行 70886 于 UTC 2026-10-23 16:34:39（北京时间 10-24 00:34:39）启动；先扫第 0–4 页，共 100 个唯一 ID，过滤窗口外 36 条。SGF 57 次、来源 HTTP 63 次（含重试），来源阶段约 236 秒，600 秒限额未触顶；rolling cursor 保持 1786。分页上限触发且末页所见均超窗，仍不声称源站按时间排序或已覆盖全部近期条目。

源没有可靠 updated_at；playTime 按产品约定解释为北京时间。默认滚动近 7 天比赛窗口（硬 14 天）和有限 head，再对近期已见条目轮换复核。每轮稳定元信息/SGF 指纹比较；同 ID 变化留证隔离，不自动覆盖。坏项 91571067、91465392、91496859 的黑白/源元信息冲突均单条隔离，没有放松验证。

首包 **`19x19-batch-fc134b52cd61f94092118e61`**，冻结 manifest **`72e6ee0fe9b6ec9d07db8fd10bfefcb67d68b800b8579cca165dfeae4af307e8`**，10 盘，TEST/PROD 各完整 50 项五语检查，最终 `prod_synced`。独立 DB+公开 API 样本 **91506543，比赛日期 2026-10-22**：TEST album 179050、PROD album 178714，两端公开来源匹配行各 1，SGF SHA 相同 `0b815c13fee8a9b5f811ceb171c5c6746ff4007b977763f34c55fc2607197515`。该组名称均已映射，复用而未为演示强制付费。

第二包 `19x19-batch-62854d648ca7b10ad8f3290d`（含 91574352，日期 10-23）在全轮剩余 494 秒时进入 PROD 发布，SSH 等待到期而远端 Docker 写者继续运行。调度仅暂停未来轮次，没有取消或重启该写者；其原生 batch 904 于 UTC 17:40:02 完成 10 盘发布，manifest `57a579a34b83134e7cca5fa51836e3cea4dfa69b00177d3cdf50abd4668a60c5`。修复后的重复轮次用同一 native batch 904 回执恢复，UTC 17:55:09 完成全部 50 项 PROD 检查并成为 `prod_synced`。TEST 日账本 19 次实际模型调用，token 上界记账 16,477，未提高原 100,000 限额。样本 91574352：TEST album 179060、PROD album 178724，两端公开来源对应各 1 条，日期均 2026-10-23，SGF SHA 均 `af20d037ed9429d753450982d49aafe1eb4359b1c27f036ae5806c4646d95e73`，中文姓名/赛事展示一致。

已审核的接收边界补丁让启动后的发布等到原生回执再释放本地锁，并以远端 PG session advisory guard 覆盖 SGF 预热和事务；断线后再试会在预热前拒绝第二个发布者。原生回执重放跳过全库预热，仍在原有写锁内复核完整 source/SGF/身份/公开和五语资格。两真实数据库的并发 guard 拒绝与释放后重入已验证，未执行业务发布。

## 七项迁移及旧 78 盘

固定旧坏 ID：7923089、7926016、7928067、7928304、7929649、7929673、7929683。停旧 cron 且确认无写者后先完整备份 stage，再预览/应用有限 7004 隔离并预览回滚。审计文件 `maintenance/7b8cfa20cb174f03ae9bd53e18aebc3b.audit.json`；迁移 pre SHA `e813643579e06382b47d7150ac2cdf7076ccc736a9b42684c699062bcd102918`，post `147536f1a7892dbf06001701f2b51a6603399356bb456e0105093fe256410a6d`。前五项 attempts=64、后两项=1 和原错误均保留，next_retry 为 null，分类 legacy_shared_7004；没有删除证据或假标成功。

旧 2/32/44 共 78 盘保持已有 PROD receipt，只调用正式验证函数续验。维护与小时任务同持 PG source session lock 和 stage writer lock；历史验证共享 300 秒网络期限和完整逐盘检查点。首次 300 秒维护完成 2/32 两包及 44 盘包的 8 盘检查点；真实重复轮次先做最新发现、恢复第二新包，再从检查点续完 44 盘包。最终三包全部 `prod_synced`，完整检查分别为 10/160/220，TEST 与 PROD 原生回执 hash 前后不变。见 `old78-bounded-recovery-first.json` 和 `state-before-run2.json` / `state-after-run2.json`。

重复轮次 71027（UTC 17:50:47–17:58:11）只请求 head 0–4 页、54 次 SGF、59 次来源 HTTP，rolling cursor 1786 未推进。七个 2021 坏项请求为 0、attempts 未变化，三个元信息冲突条目仍仅尝试一次且隔离。总数 176852、公开 176593、最新规范日期 2026-10-23 前后不变；UTC 日模型账本规范化 JSON SHA `409f9e1dc58b1046658958cfd7fed88416c5cdcf1dd0c21363355417db119370`、19 次 call 和 16,477 token 上界未变化。此后仅为审核发现的有限名称纠正再次暂停未来任务，无取消或遗留写线程；纠正后已恢复。见 `real-idempotency-and-recovery.json`、`run2.filtered.log`。

## 上线审核发现与受控名称纠正

审核没有把模型批准或五语一致性当作语义正确的证明，真实发现下列问题并据官方材料复核。纠正只涉及下列 5 个语言字段；其余字符、原始 raw event、棋谱、来源、黑白和日期不变。

| 目标 | 已核准纠正 |
| --- | --- |
| 王座挑战赛 jp，91574352 | `第74期王座戦挑戦手合5番勝負第1局` |
| 王座挑战赛 ko，91574352 | `제74기 왕좌전 도전5번기 제1국` |
| 国手山脉决赛 ko，91449763 | `이유청` → `리웨이칭` |
| 吴清源杯预选决赛 ko，91468818 / 91464854 / 91467988 | `우청원배` → `오청원배` |
| 吴清源杯预选第 2 轮 ko，91496863 | `우청원배` → `오청원배` |

统一逻辑规格 SHA **`6c9ed23d97b9fd0e787bdf4277d659e2a33c738fdcbca1ba304c7becf0bf57f6`**。使用既有 `name_batch.dry_run_bundle/apply_bundle` 及 `generated-raw-event-semantic-correction-v1`，保留各目标完整 owner/name/evidence/revision/prior candidate/batch/journal 前像。没有直接 SQL 改名、重抓、重译、重导或改原冻结包。

TEST 的独立 capture 和具体 bundle 审核、原生 dry-run 通过后，原生纠正 **batch 913** 应用 5 名称更新和 5 新证据；bundle SHA **`d05f9ebc2b2e348eb98a824bb3938c3f70f862f089b87f9b31d86bbfc7796c4c`**。随后全部 10 盘 fresh **50 五语／50 日期检查**通过，20.5 秒；独立 Astra 也重新请求了全 50 项。之后才批准并应用同规格 PROD **batch 906**，bundle SHA **`31d63f958bfbdb428f0b97d3c1e481c3d9d7cf5aa7e1c36af21f64d37ba21dc1`**；PROD fresh **50 五语／50 日期检查**通过，33.28 秒。两端原生重放均 `already_applied/change_count=0`。

API 复验使用单独的 `kifu-post-name-correction-api-expectations-v1`，不是新发布 manifest，也没有伪造原 Qwen 审批。原 10 盘 games 不变，只覆盖 5 个已审显示值，绑定原 manifest、纠正规格、各目标原生纠正 bundle 和批次；`checkpoint_dir=None` 强制新请求。TEST/PROD expectations SHA 分别为 `49e466814577cd8e6615997fb15e1fe5f0c3af5511bd88be8cf5e447baa5c4b9`、`f45d706b76d2350a4c9a90385591d22e94010bef8b52dd8a5d604dbad37873bd`。

两份原包 `57a579…` 的旧 API 检查点按 manifest／原 receipt／规范化 URL 精确匹配，在同 source PG＋stage writer 锁下迁出活跃目录并保留原字节，防止旧译文证明继续复用。归档审计及原字节 SHA 在 `name-corrections/checkpoint-archive-audit.json`；没有删除历史证据或改原成功状态。新证明、前像、bundle、research、原生回执、重放及操作脚本均在 [name-corrections](name-corrections/)。完整 inventory 及全部输入另持久备份在两云本轮 `native-name-correction-artifacts` 目录，未把全库元数据放进证据提交。

防复发 guard 只拒绝已证实的有限错误形式，并把相同规则交给 producer、repair、reviewer；没有扩展为全量词库或新平台。另一位 Astra 找出的多阶段番棋／一番棋及另一个明确韩文人名的误伤均在上线前修正，67 项独立聚焦测试通过。自动生成型名称仍不等于官方命名证明，此次未扩为全库语言校订。

纠正后的真实 **run 71146**（UTC 18:54:49–18:58:31）成功，**221.734 秒，error 0**。仍只读 head 0–4、54 SGF／59 来源 HTTP，七旧坏项 0 请求、attempts 不变，rolling 1786 不变；模型账本及双库数量不变，5 原包仍全部 `prod_synced`，新译文未被重放覆盖。当前启用 3600 秒间隔，控制表无暂停，下一轮 **UTC 19:54:49／北京时间 03:54:49**。见 `post-correction-real-idempotency.json`、`run3.filtered.log`、`state-after-run3.json`。

## 保留限制

3300 秒为协作预算；全库 SGF 规范化缓存预热和原生发布快照/校验仍可能耗时较长。本次真实 PROD 发布约 19–23 分钟，测量不能把全部时间归给某个单独慢查询。首次新包仍须走该路径，已发布重放已省去预热；未开展全库索引、长期缓存或队列平台改造。小时任务并发保护和原有 token/名称预算保持，超时不能假装取消远端写者。

有限 head 不保证发现未出现在这几页及近期已见集合中的所有新条目；源无更新时间/排序契约，不能声称精确按最近一小时更新时间过滤。coverage 日志保留分页/请求/SGF/时间触顶和新鲜度，必要时在现有硬上限内有限调整。超窗历史缺口只允许另行有限历史入口，小时任务不会自动深入历史库。

后台 `last_error` 保留上一轮错误文本，当前 run.error 为 null、last_status 为 success、失败计数为 0；这是“最近错误”历史字段的展示歧义，没有为本任务扩改全局 recorder。PROD 一次健康响应的 local engine 不可达已在独立复核恢复，未把其归因于同步或展开 GPU 排障。已观察真实恢复与两次幂等轮次，尚未等待下一自然轮或长期无人值守表现。
