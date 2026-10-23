**结论：Needs fix。同步、部署、幂等和恢复链路已得到现场证实，但新发布包存在真实译文错误，当前不能整体 Approved。**

审核时间为 UTC 2026-10-23 18:00–18:15，即北京时间 10 月 24 日 02:00–02:15。此次直接执行了 TEST/PROD 只读 SSH、只读数据库事务、有限 stage JSON、运行日志和公开 API 核查。未执行模型调用、导入、发布、调度、重启、业务写入或文件修改；未读取或列举 `data/kifu-album` 文件目录。

有三项需要修复，范围为 **4 个 raw_event、5 个语言单元、6 盘棋谱**：

| 问题 | 现场证据 | 影响与结论 |
|---|---|---|
| **P2：王座战挑战赛被译成挑战者决定赛** | source `91574352`，TEST `179060`、PROD `178724`。两端日语均为 `第74期王座戦挑戦者決定戦5番勝負第1局`，韩语均为 `제74기 왕좌전 도전자 결정전 5선승부 1국`。 | 该谱是 10 月 23 日福冈航太朗对一力辽的头衔挑战赛；“挑戦者決定戦”实际是 8 月 24 日福冈对井山裕太的另一阶段。韩语还将五番棋写成有“先赢五局”含义的形式。日本棋院的[当日比赛报道](https://www.nihonkiin.or.jp/match_news/match_info/74_1.html)及[挑战者决定赛报道](https://www.nihonkiin.or.jp/match_news/match_result/74_17.html)明确区分两者。 |
| **P2：赛事标题中的棋手名与同页权威显示不一致** | source `91449763`，TEST `179067`、PROD `178731`。同一韩语响应的 `display_player_white` 为 `리웨이칭`，`display_event` 却为 `제12회 국수산맥배 세계전 결승 신진서 VS 이유청`。 | `이유청` 错误替代了李维清已经核准的韩语名。韩国棋院[官方赛程](https://www.baduk.or.kr/record/schedule_in.asp)同样使用 `리웨이칭`。 |
| **P2：两个吴清源杯赛事译名使用错误韩语专名** | 国际预选决赛 raw_event 覆盖 `91468818`、`91464854`、`91467988`；预选第 2 轮覆盖 `91496863`。冻结决策及两端抽查 API 均使用 `우청원배`。 | 韩国棋院对应比赛记录使用 `오청원배`，包括同日王晨星对李书英的[官方记录](https://www.baduk.or.kr/record/diary_in.asp?foreignKey=10001366)。两个事件的韩语杯名应一致修正。 |

这些错误已经存在于第二冻结包的审核决策中，再被正确同步到两端。该包 9 个决策均有独立 producer/reviewer 请求及批准记录；`sources=[]` 本身符合现有生成型名称协议，并非协议违规，但不构成外部权威依据。

代码上的关键边界是：[names.py:332](/Users/fan/.config/superpowers/worktrees/katrain-kiosk-debug/golaxy-hourly-release-20261024/katrain/kifu_ingest/names.py:332) 的候选检查、[names.py:426](/Users/fan/.config/superpowers/worktrees/katrain-kiosk-debug/golaxy-hourly-release-20261024/katrain/kifu_ingest/names.py:426) 的赛事提示及模型审核，以及 [sync.py:174](/Users/fan/.config/superpowers/worktrees/katrain-kiosk-debug/golaxy-hourly-release-20261024/katrain/kifu_ingest/sync.py:174) 的 API 证据检查。后者证明 SGF、来源、原名和输出与冻结决策一致，不能证明冻结译文的语义正确。本次真实数据说明，单靠模型批准及五语一致性检查仍会漏过上述错误。

其余 5 个决策未发现同等置信度的阶段、对手或赛制错误：韩国女子国手战半决赛、玄乐杯决赛、75 期王座战预选 A、李书英、国手山脉 16 强。李书英的 `이서영` 有韩国棋院[李書英官方资料](https://www.baduk.or.kr/record/player_view.asp?pkey=10001366)支持，不能误当成另一位同音的李舒煐。此次没有扩大为全部惯用外文名称的母语编辑审核。

现场已证实的流程事实如下：

| 边界 | 独立核实结果 |
|---|---|
| 发布版本 | 远端 `develop` 为 `662b6a25048ee2bb3752bdbf54fb3a927ab68084`。TEST cron、TEST web、PROD web 的实际镜像 SHA 分别与记录中的 `85de7b1d…`、`21276479…`、`675a75f2…` 完整匹配；三处 10 个同步模块的实际文件哈希全部一致。 |
| 部署范围 | 确认是已有运行镜像上的 Python 文件覆盖；不能把 build SHA 理解为全部后端和静态前端都来自整树 `662b6a250`。三个服务均运行、restart count 为 0。 |
| TEST-only 采集和模型 | TEST cron 实际启用 ingest 和名称模型；两端 web 的 ingest/LLM 关闭。PROD cron 镜像没有 ingest 模块及相应配置，未注册第二采集器。 |
| 实际预算 | TEST：3600 秒间隔、7 天窗口、5 页、160 次 HTTP、100 次 SGF/候选、20 次离开头部复核、600 秒来源预算、300 秒历史验证预算、3300 秒协作预算、20 个新名称、100000 token 日上限。 |
| 最近一轮来源扫描 | 独立读取 Docker 原始日志得到 page `0,1,2,3,4`、54 次 shared SGF HTTP、59 次来源 HTTP。七个旧坏 ID 的来源请求为 0。coverage 明确记录 `head_page_cap=true`，没有声称完全覆盖近期来源。 |
| 日期窗口和旧队列 | 实际窗口为北京时间 `2026-10-17 01:50:51` 至 `2026-10-24 01:50:51`。rolling cursor 仍为 1786。没有继续历史 rolling。 |
| 坏项隔离 | 七个 2021 旧项的原错误、attempts `64/64/64/64/64/1/1` 保留，terminal 且无 next_retry。三个黑白冲突项均 attempts=1、terminal；双库对应 album/source link 均为 0。 |
| 七项维护证据 | 现场 audit 的 matched IDs 恰为七项；before backup 存在，其实际 SHA 等于记录的 pre SHA `e8136435…`。没有清空旧错误或假标成功。 |
| 两个冻结新包 | 直接读取远端完整包并重新执行纯校验 `_validate_manifest`；两包各 10 盘通过 SGF、元信息及决策绑定校验。文件 SHA、canonical manifest SHA 与证据一致。 |
| 双库内容 | 按原生回执读取全部 20 盘，TEST/PROD 的来源路径、SGF SHA、黑白、赛事、日期和公开状态逐项一致。两个代表来源各只有一条来源关联。 |
| 原生发布权威 | 双库五个包均有 `KifuNameBatch.status=applied`，bundle SHA、artifact manifest、receipt manifest 一致。第二包 PROD 原生 batch `904` 的实际 applied 时间仍为 UTC `17:40:02.312647`，没有用 TEST 调度表替代 PROD 权威回执。 |
| 调度状态 | TEST run `71027` 实际为 success，耗时 444285 ms、error_count=0、error=null；连续失败归零、控制表无暂停行，手动命令 4/5 均 done。心跳在审核时继续更新。 |
| 单写者 | 审核时两库 ingest/publisher advisory lock 均无占用，三运行服务均无 receive 进程。安装代码的 publication session guard 覆盖 warm-up 和事务；SSH 发布等待不再因剩余协作预算被主动终止。此次没有主动制造生产并发。 |
| 旧 78 盘恢复 | TEST 编排中的 2/32/44 盘包均 `prod_synced`，检查数为 10/160/220；其当前 native receipt SHA 与 run2 前后证据均一致，原生 applied 时间仍在 10 月 20–21 日。现场检查点分别存在 2/32/44 个完整完成记录，绑定 manifest、receipt、目标、算法和五语言。 |
| 重复轮次模型预算 | 当前账本仍为 19 个 call、57 个条目、16477 token 上界。规范化 JSON SHA 为 `409f9e1d…`，与 run2 前后快照一致。当前原始文件字节 SHA 为 `f1298062…`，mtime 为 UTC `17:20:07`。 |
| 公开服务 | 两端最新样本五语详情、首包中文详情及两个日期的公开列表均返回真实一致数据；Galaxy/kiosk 路径返回 200，静态 shell SHA 与部署记录一致。此项没有冒充设备端完整交互验收。 |

两端当前棋谱总数均为 **176852**，公开 **176593**，最新规范日期 **2026-10-23**。首包样本 `91506543` 对应 TEST `179050` / PROD `178714`，最新样本 `91574352` 对应 TEST `179060` / PROD `178724`。最新样本两端 SGF SHA 均为：

`af20d037ed9429d753450982d49aafe1eb4359b1c27f036ae5806c4646d95e73`

另有三项非阻塞记录：

- `cron_job_status.last_error` 仍保留旧超时错误；`last_status=success`、当前 run.error=null。原因是 [run_recorder.py:191](/Users/fan/.config/superpowers/worktrees/katrain-kiosk-debug/golaxy-hourly-release-20261024/katrain/cron/run_recorder.py:191) 成功分支未清该字段。现有健康计算按运行状态判断，后台显示列名是“最近错误”，因此这是历史错误展示的歧义，不是任务仍失败。
- 审核发现文档将 canonical ledger SHA 称为“全文 SHA”。实施者已经改为“规范化 JSON SHA”，并明确未捕捉 run2 前的原始字节 SHA；我已读取确认修正，不再将其视为未解决问题。
- PROD `/health` 一次返回 `local=unreachable`，UTC `18:07:48` 单次复核恢复为 `reachable`，TEST 始终正常。本次没有证据将这一瞬态归因于同步发布，未扩大 GPU 排障。

保留的实际限制是：3300 秒仍为协作预算；首次新包仍有全库 SGF 预热和发布快照成本，本次真实 PROD 发布约 19–23 分钟。无可靠 updated_at 和排序契约，有限 head 与近期已见集合不能保证发现所有近期新增棋谱。审核只观察到已完成的恢复轮次和当前已注册的下一次调度，尚未等待 UTC 18:50:47 的自然轮次或长期无人值守运行。

实施者随后提出的五个确切修正文案，**语义复核通过**：

| 目标 | 已核准的有限修改 |
|---|---|
| 王座战 jp | `第74期王座戦挑戦手合5番勝負第1局` |
| 王座战 ko | `제74기 왕좌전 도전5번기 제1국` |
| 国手山脉决赛 ko | 仅 `이유청` → `리웨이칭` |
| 吴清源杯预选决赛 ko | 仅 `우청원배` → `오청원배` |
| 吴清源杯预选第 2 轮 ko | 仅 `우청원배` → `오청원배` |

现有部署支持最小纠正路径：[name_batch.py:400](/Users/fan/.config/superpowers/worktrees/katrain-kiosk-debug/golaxy-hourly-release-20261024/katrain/web/kifu/name_batch.py:400) 的 `generated-raw-event-semantic-correction-v1`，通过 `scripts/kifu_name_batch.py` 的 validate/dry-run/apply，或对应公开 `dry_run_bundle` / `apply_bundle`。两端实际 `name_batch.py` SHA 均为 `c2ffaf49…`，与本地一致。该路径能绑定完整名称 preimage、旧 revision、candidate/evidence、batch/bundle 和原生 journal，适合单独产生新纠正批次。

原冻结 manifest、原生 receipt、原 SGF、来源、黑白和日期应保留；纠正后使用单独的新期望值及验证证据记录。当前尚未审核具体纠正 bundle 的哈希/preimage，也未核实其实际应用和新的双端五语验证，因此本次上线后流程审核的总裁定仍是 **Needs fix，等待上述有限纠正完成后的实物复核**。
