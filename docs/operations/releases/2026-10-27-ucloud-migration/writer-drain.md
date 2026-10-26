# 旧→新最终停写窗口：只读核对与最小动作（2026-10-27）

本次仅执行源码读取、Docker inspect/ps/help、显式 PostgreSQL READ ONLY 聚合；没有暂停、触发、停止、发信号、改业务状态、改 DNS，未写新机。本报告中的变更命令均**未执行**。唯一实际写入为本 Mac 报告文件。

## 立即结论

1. **旧 PROD 报告无业务在途**：2026-10-26 17:49:57 UTC（上海 10-27 01:49:57）report_tasks 仅 completed=21；pending=0、running=0、authorizing=0、其它状态=0，max(updated_at)=2026-10-23 13:14:04 UTC。17:53:00 UTC heartbeat 的 report_analyze loop_stats 为 in_flight=0、capacity=3、errors_total=0，heartbeat_at=17:52:58，loop_iteration_at=17:52:57。不需要等待不存在的“3 个活跃报告”。
2. **但整个旧 cron 不是仅报告分析**！实际 image `sha256:9b28e8be9b77deb63f99cac2b076aac9df584a521f9b00989d6cc2bc920adb79` 的当前环境导入 config：ANALYZE/CLEANUP/FETCH_LIST/FETCH_UPCOMING/PANDANET/POLL_MOVES/TRANSLATE/TUTORIAL_BACKUP 均 true；KIFU_ANALYZE=false；YIKE/XINGZHEN=true。只有显式 Env CRON_REPORT_ANALYZE_ENABLED=true，并不表示其它默认关闭。当前旧 cron 无 kifu_ingest 注册，也没有该部署的小时 collector。
3. **17:53:40 UTC translate 仍 running**：start=16:04:40、此前 finished=16:03:47；cron_job_runs 中有1条 running/finished_at NULL。poll_moves 为短周期任务，状态也可能 running，但不为每次运行写 run 行。不能只查 cron_job_runs 后宣称 cron 全空闲。
4. 两个常驻循环在17:53:28 UTC均 in_flight=0：analyze容量16，report_analyze容量3。live_analysis 仅 success=48075、failed=5；pending/running=0（17:54 左右读数）。
5. **TEST collector 可复用已证1800秒维护 holder**：本轮 db-status：paused=false，finished_not_before_started=true，advisory_lock=false，running_run_count=0；control_sha256=74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b（JSON null，原行不存在）。这只是读数，不预留空闲窗口。
6. **Pitch 可按“空闲停用”收敛**：17:55:26 UTC exact eligible_expiry=0、eligible_moderation=0；所有相关 claimed/processing/lease=0，支付和通知 runtime disabled。它没有自定义 graceful handler，不能把停用称作活跃业务 drain。

## A. 实际旧 image 的报告/cron 控制入口与退出事实

直接读取旧运行容器 `katrain-ucloud-katrain-cron-1:/app`，没有用本地 e9 源码替代。

- `katrain/cron/controls.py` 文件注释及 ControlPoller：pause **只作用于 interval**；POLL_S=10。paused 映射写入 recorder；常驻 loop 不经过 recorder.run。
- `scheduler.py:_run_analyze_loop` 直接 await job.run()，无 paused 检查。
- `jobs/report_analyze.py:run/_claim_pending_task` 每轮补足3个 worker；只按 report_tasks.status=pending 查询再更新 running；**没有 pause/drain-claims 的现成入口**。
- `ReportAnalyzerJob.stop()` 仅设置 _running=false；worker 每手开始都查这个标志并直接 return，可能留下 running 行，不是“跑完整份报告”的 drain。
- `__main__.py:_main` 为 SIGINT/SIGTERM 安装 scheduler.shutdown 的异步 task；`scheduler.py:shutdown` set shutdown event、APScheduler shutdown(wait=False)、cancel loop/heartbeat/health/control task。报告 child workers 不在该 await 列表；asyncio.run 退出时会取消剩余 task。**不能在报告/直播/interval业务活跃时用 SIGTERM 当作完整业务 drain。**
- 报告启动恢复会把所有 running 重置 pending；resume 从最后已存 move+1续跑；运行期也会重排 updated_at 超过30分钟的 running；失败最多3次（不足3次回 pending）。这属于事故恢复，不能据此声称停机中没中断业务。
- cron ErrorCollector 是 daemon 线程；stop() 设置 event、join(timeout=10)、最后 write()。health/control 使用 to_thread。scheduler 的 shutdown task 与 start() 由同一个 event 唤醒，源码没有“所有子业务与诊断线程完成”的统一确认。最终应以业务空闲前提+**容器实际 exited、无任何旧相关进程**作为无存活 writer证据，而不是 await取消成功。

### 最小可执行控制顺序（由迁移 controller 执行）

Owner：当前主迁移 controller。每次窗口记录 UTC start、绝对 deadline（建议 start+1800秒）、旧容器 image/id 和控制前像。超过 deadline 不强杀、不自动恢复旧入口；保持 fence，controller 决定继续等或回滚。

1. 先封住旧公网、gateway、VPN及内部调用的新业务入口。报告最小新增入口是旧 Web `POST /api/v1/reports/` 与 `POST /api/v1/reports/{id}/retry`（真实 `endpoints/reports.py:233,405`）；二者都可产生 pending。全站迁移应封全部新写请求，不只这两条。已有请求必须正常返回；原有 WebSocket 断开可能触发结算/存谱，断开后也要等待。
2. 保存并暂停旧 cron 的**全部7个实际 interval 控制行**：fetch_list、poll_moves、poll_pandanet、translate、fetch_upcoming、cleanup、tutorial_backup。17:54本轮 SELECT 中这7行全部不存在。切窗时必须重新读前像，不能直接沿用本次空值。用既有 cron_job_controls 的 paused=true、changed_by=唯一owner、reason=迁移窗口ID+绝对deadline；单短事务读前像 FOR UPDATE/插入并保存 after-image 到0600私有文件。不要写 loop 假暂停，不触 cron_job_commands/run_now，不改任何 job/业务状态。
3. ControlPoller 10秒后会阻止未来 interval触发；**不取消当前 run**。等待每个已开始的 interval `last_finished_at >= last_started_at`，last_status!=running；同时 cron_job_runs 的真实 running归零。对2秒级 poll_moves等必须看 status表，因为其run不逐次记行。暂停产生的 skipped/paused行不会抹掉当前真实状态。
4. 此时等待已有 live_analysis 与 report_tasks 的 pending/running/authorizing归零，heartbeat新鲜且两个 loop in_flight=0。report没有独立claim暂停，但入口+上游采集已封，现存队列可以自然跑完。不要通过锁 pending行、改队列状态、SIGSTOP或cancel阻断，否则同步DB可卡住同一事件循环、妨碍已有worker完成。
5. 只有上述成立，才可对旧 cron 做空闲正常退出（不是活跃任务drain）：

```sh
# 只在 controller 完成上述 gates 后，旧机执行；未执行
sudo docker stop --signal SIGTERM --timeout -1 katrain-ucloud-katrain-cron-1
sudo docker inspect --format '{{.State.Running}} {{.State.Status}} {{.State.ExitCode}}' katrain-ucloud-katrain-cron-1
```

旧机 Docker `stop --help` 已实际读取，参数为 --timeout。官方文档明确 --timeout=-1 不升级 SIGKILL，daemon无限等待：
https://github.com/docker/docs/blob/main/data/cli/engine/docker_container_stop.yaml
**该参数只消除自动SIGKILL；不会让没有handler的程序变成可drain程序。** 不使用有限 timeout的docker stop/compose down/recreate来跨过活跃writer。

### 当前 translate 的实际边界

`jobs/translate.py:run` 顺序 await _translate_players/_translate_tournaments，分别遍历全部live/upcoming待翻译名字，每项成功后commit，finally关闭Session。实际 translator为async httpx（wiki10秒、LLM30秒单请求），未见整job deadline，未用后台模型to_thread；pause只会禁止下一轮，当前轮继续自然结束。17:54聚合PG还有2个 idle in transaction，最长约2h19m，**没有输出SQL/棋局内容，也不能把该聚合直接归因到某一进程**。剩余缺翻译数量的额外只读SSH查询发生连接关闭，未继续排障；目前只确认当前run仍有未收尾记录，不伪称idle。若deadline到仍running，保持暂停与fence，不取消其await或杀进程；由controller明确处理真实剩余运行窗口。

### 恢复前像 / 全站单写

保存original+paused完整行（含changed_at/reason/changed_by），恢复时 SELECT FOR UPDATE，逐行比较current==paused；任意他人变更则拒绝覆盖。original不存在则DELETE本窗口新增行；original存在则恢复所有原值，包含原changed_at。只在选定权威host恢复：成功迁移后在最终新PROD库恢复这些控制行，旧cron与旧入口保持停用；回滚才在旧侧恢复，而且必须先确认新侧全部写入口/worker禁用。不能在新旧两库都恢复并启动。

## B. TEST唯一小时 collector：精确复用现有1800秒guard

已验证实际文件：
- `/mnt/disk1/fan/kifu-rank-coverage-e9b4d3ecc-20261026/maintenance.py` SHA256 `953791eace80880418c4151cae2a52f326f9f44588e22e62e23345d24b0a0e4e`
- 同目录 `cloud_overlay.py` SHA256 `0d03529e22c2103c977581309fd95af82fa53e0e100905a183a5bd5537efcbd4`
- Mac副本位于 `/private/tmp/kifu-rank-coverage-release-20261026/`，相同hash。
- 当前TEST cron image：`sha256:9604d05e4e096b4c97966e6c850492c87d60fe9fff1039c3fe94f67af081c08d`。不得用README历史d67f镜像代替。
- 固定stage：`/mnt/disk1/fan/kifu-hourly-incremental-20261019/ingest-stage`。

实际TEST源 `jobs/kifu_ingest.py:561-578`：await asyncio.to_thread(_run_lock)；线程持PG session advisory lock+staging_writer_lock，再运行自己asyncio.run。取消外层await不停止线程。sync实际 `send_verified_manifest(... timeout=None)`，注释明确“杀SSH不能取消远端Docker writer”，锁必须保持到native receipt回传。总3300秒是协作入场预算，不是安全强杀期限。

`maintenance.py hold` 的真实行为：
- 保存kifu_ingest控制完整before/after到600私有状态文件；只暂停future interval；
- 最多等待min(600,max_seconds-30)秒，要求finished>=started、无advisory lock、running run=0，且本机receiver_idle；
- 以当前cron实际image启动network=none/read-only纯lock holder，复用同一stage/.writer.lock inode；flock失败退出75后重试，不强抢；
- 获取flock后再次检查DB和receiver；ready中有owner PID、container ID/PID、inode、绝对expires_unix，锁TTL上限1800；
- 失败/超时**保留paused**，holder按TTL自行退出，不自动恢复前像。max_seconds包含前面等待时间，ready剩余窗口可能小于1800；
- 放行信号只能是相同SHA+bounded_passed；先CAS精确恢复控制前像，再停止纯lock容器。原脚本对**纯锁且无业务/网络的容器**使用stop --time2，不应用于业务容器，不需要为此改整个工具。

controller在home-ubuntu普通SSH用户会话中执行以下已存在入口；本调查未执行：

```sh
cd /mnt/disk1/fan/kifu-rank-coverage-e9b4d3ecc-20261026
# 新鲜且不存在的三个路径；不要沿用昨日ready/release/private文件
TASK_WINDOW=/mnt/disk1/fan/ucloud-migration-writer-window-20261027
mkdir -m 700 "$TASK_WINDOW"
python3 maintenance.py hold \
  --sha e9b4d3ecce03b3269f12922a476fd6d6c6545547 \
  --go APPROVED:e9b4d3ecce03b3269f12922a476fd6d6c6545547 \
  --db-container katrain-cron \
  --lock-image sha256:9604d05e4e096b4c97966e6c850492c87d60fe9fff1039c3fe94f67af081c08d \
  --max-seconds 1800 \
  --private-state "$TASK_WINDOW/control.private.json" \
  --ready "$TASK_WINDOW/ready.json" \
  --release-file "$TASK_WINDOW/release.json"
```

进入最终快照前重新用 `cloud_overlay.maintenance_gate(ready,sha)` 核验holder身份/锁inode/期限/DB闲置/本机receiver。此外必须在旧PROD检查实际接收进程已结束（TEST脚本只证明本机receiver idle，不能代替远端检查）。不要删除stage、改prod_synced、补写receipt、手动重发或触发job。

成功切换并验证**唯一TEST producer仍为原home-ubuntu collector、目标接收地址/known_hosts/受限key均指向新PROD、旧receiver已封、旧业务writer已退出**后，controller才写同SHA的release.json：

```sh
# 仅完成迁移后有限验证才执行；不要提前放此文件
python3 - "$TASK_WINDOW/release.json" <<'PY'
import json,os,sys
p=sys.argv[1]
with open(p,'x') as f:
 json.dump({'source_develop_sha':'e9b4d3ecce03b3269f12922a476fd6d6c6545547','verification':'bounded_passed'},f)
os.chmod(p,0o600)
PY
```

若controller超时、进程失联或TTL耗尽，先保留pause，确定业务/receiver完全空闲及最终唯一writer后再使用同一private-state：

```sh
python3 maintenance.py restore-private \
  --sha e9b4d3ecce03b3269f12922a476fd6d6c6545547 \
  --go APPROVED:e9b4d3ecce03b3269f12922a476fd6d6c6545547 \
  --db-container katrain-cron \
  --private-state "$TASK_WINDOW/control.private.json"
```

restore-private本身只恢复控制行，不检查迁移是否完成，也不释放仍活跃的holder；controller必须先完成上述唯一writer/锁状态检查。成功恢复原像本轮预期是删除维护新增的kifu_ingest行，不是强行设paused=false。

## C. 其它旧写者：封入口、当前工作边界、再停用

### Pitch worker/API

实际 `pitch-booking-worker-1:/app/backend/app/worker.py`：
run()是同步 while True → run_once → time.sleep(60)，无SIGTERM/SIGINT handler、无stop event。不要给它套用“收到TERM会等run_once完”的说法。实际解释器 `/app/.venv/bin/python`，系统python无pydantic。

实际Settings：app_env=staging，mock_payment_provider_enabled=false，payment_provider=disabled，wechat_payment_configured=false，open_game_notification_provider=disabled；因此run_once没有payment/refund recovery对象、无微信通知对象。profile_moderation=true（只输出是否配置，不输出key）。

17:55:26 UTC有限READ ONLY聚合：
- content_moderation_jobs：COMPLETED2；PENDING/CLAIMED0；claim_token/lease_until非空0；源码 _claim_next 的 exact next_run_at+pending/expired-lease predicate eligible=0。
- notification outbox空、claim/lease非空0。
- payments SUCCESS2、refund_attempts SUCCESS2；reconcile claim/lease非空均0。
- orders CONFIRMED6、REFUNDED2、COMPLETED1、EXPIRED2；PENDING_PAYMENT0；按源码“到期pending且无blocking payment”exact eligible_expiry=0。

因此先封Pitch API、管理提交、支付回调等所有新写入口，等待当前HTTP结束；复查上述eligible/claimed/pending仍0后，worker可按**空闲停用，无自定义graceful handler**处理。不是仅凭瞬间DB无TX。若moderation claimed>0等，等待其自然完成/持久终态，不能盲用SIGTERM。已有lease恢复只是恢复策略，不等于在途已结束。Pitch API启动命令含alembic upgrade head，恢复启动是写边界，不在最终快照后继续旧侧启动。

### Platform与Go Web

- platform actual entrypoint执行alembic再exec python -m platform_app.main。平台有内存session与background reaper/SSO cleanup；仅封HTTP入口不会停后台。
- 实际 `lobby_api/main.py:lifespan` shutdown对reaper和cleanup cancel并await，随后shutdown adapters；reaper可能await存谱/结算。不能仅凭数据库无活跃TX认定没有待存谱的内存session。先停止新对局/新动作，等待当前请求、WS断开后的持久化/结算、pending finalize完成，再正常退出并观察进程/DB边界。
- Go Web实际 `katrain/web/server.py` 有pvp bots/live service、cleanup、AI heartbeat、report settlement、health/ErrorCollector。lifespan会stop bots/live、to_thread collector.stop，并cancel若干background loop。report_settlement/reaper中存在to_thread；不能用cancel外层await作为同步写线程已完成的证据。先封入口和内部回调，完成现有请求/持久化，正常退出并等**容器exited及所有原相关进程消失**后再最终PG dump/卷快照。进程仍活着则不认为停写成功。
- Go admin与unified admin也是写入口，含audit卷；必须一同封入口、待请求结束并停用，不能只停Web。
- 不用有限docker timeout把WebSocket/模型/数据库收尾强杀过去；无限等待也必须先满足实际业务空闲前提。

### 国象kifu API与MinIO

- smartbox-kifu-api-1和api-b-1实际同image，`kifu_api/routes.py`只有GET health/readiness/search/games；`main.py:create_app`明确不init_db、不写schema，构造不可变catalog。历史init/importer都exited，保持不启动。
- kifu API在lifespan启独立admin Uvicorn；finally设置admin_server.should_exit=true并await admin_task。先阻断两个API入口/直接VPN调用，等待当前GET结束，再无SIGKILL升级地退出两实例，保留共享work卷。不能错误启动prestart/importer“补齐迁移”。
- MinIO要在所有对象写客户端/教程管理/媒体上传/预签名PUT/VPN直接入口关闭、现有multipart/上传请求自然结束、其它应用writer停止后最后退出；**单看PG idle不能证明S3闲置**。本调查没有读取对象内容/私钥、没有声称已量测MinIO所有在途请求。只读服务正常退出后再做最终完整对象卷（含.minio.sys）差分；应用先停再MinIO，可阻止退出期间又收到新对象写。MinIO不能用在线目录拷贝已完成替代最终停写一致性证明。

## 最终handoff闸

- 全站旧入口+内部/VPN/receiver新写请求被封，现有请求/WS触发收尾完成；
- TEST guard处于paused_idle_lock_held且未到expires；旧远程receiver无进程；
- 旧cron全部interval已自然结束、loop队列与in_flight=0；Pitch exact eligible/claimed=0后空闲停用；
- 旧Web/admin/platform/kifuAPI/MinIO所有相应容器实际exited，无残余旧模型/接收/写线程；没有借助SIGSTOP、cancel-await假完成或有限stop超时；
- 完成最终数据/对象同步验证，随后只激活新PROD业务入口和writer；TEST仍是唯一collector，仅指向新receiver；旧端保持停写；
- 最后恢复**选定权威侧**各控制前像。任何控制行与paused-after-image不相等都拒绝覆盖，交owner处理。

所有读数均为采样时点；执行者必须在真正切窗后复查。本轮未对新host写入任何内容。

## 追加核对：translate当前实际边界与cron可写层（18:10—18:11 UTC）

本次复查通过已授权的 Mac→新机ubuntu→sudo SSH→旧机VPC链，只读命令；新机未写文件、控制、DB或服务。容器时区实测UTC。

### translate不是仅旧状态行：当前仍在尝试

- 18:10:23 UTC：last_started_at=16:04:40.357757、last_finished_at=16:03:47.329720、last_status=running，heartbeat=18:09:58.996305。状态行本身不能单独证明当前仍有业务调用。
- 另取最近30分钟、最多5000行容器日志，仅在内存解析后输出计数和时间，没有输出玩家/赛事名字或日志正文：player attempt=20，最后18:10:04；APScheduler因translate max_instances而skip=15，最后18:10:40。结合源代码，这是进程仍在玩家翻译迭代中的证据，而不是仅据两小时旧running行判断。
- 按实际live/upcoming去重谓词分别COUNT：**待玩家90，待赛事137**。玩家取live双方（不额外过滤live原值）并union upcoming非空且非空字符串的双方；赛事union两表非空且非空字符串；分别left join现有翻译，排除source=manual，保留无行或en/cn/tw/jp/ko任一NULL。SQL用IS DISTINCT FROM 'manual'，保持Python对source=None仍可处理的语义。仅返回计数，未返回名字。
- player_translations max(updated_at/created_at)=06:45:57.211062 UTC；tournament_translations=05:59:58.986773 UTC。近期尝试没有对应的近期表更新时间，不能称为已成功落库进展。

### 真实timeout/retry/max-items与预计边界

- **实际旧cron LLM key配置bool为false**（没有输出key），因此translator.py:239—241直接返回None，当前不会发起付费LLM调用。
- 玩家Wikipedia查en/ja/ko/zh四种语言，查询变体数3+2+2+2，最多9次搜索，找到页面时可再取一次langlinks。每请求httpx timeout=10s；异常继续后续查询变体，没有对同一请求无限retry。请求timeout不是整item或整job的硬deadline。
- key配置存在时：LLM请求timeout=30s，失败/无效JSON记录后返回None，无显式请求重试；玩家最多一次extract加一次fallback，赛事一次调用。配置llm_concurrency=3，但本TranslateJob逐项await，并没有三玩家同时消费。
- jobs/translate.py每item尝试后commit；单item失败可使整轮退出并进入跨轮circuit breaker；LLM返回None则仍可能提交原样/部分结果，所以缺项可保持不变。没有max-items、整job deadline、持久游标或“当前剩余迭代位置”字段。
- **90/137是库里仍缺数量，不是当前for循环尚未尝试数量。** 当前key缺失可使本轮尝试后依旧缺项，后续轮次继续重试。不能将90×10秒等当可靠ETA，也不能保证未来“缺项归零”。真正当前轮收尾条件仍是当前task完成、记录finished>=started；先暂停future，再等本轮自然结束，不要求先把这些翻译缺项做成0。禁止取消await/停线程来伪造收尾。

### 无挂载cron实际可写业务文件必须保留

对同一个旧cron执行docker diff元数据核对，过滤__pycache__/pyc，不读取任何SGF目录或棋局。非cache业务写文件仅发现教程备份；另有部署manifest。对cron实际.py文件AST仅定位open/write/mkdir/unlink等写入口，唯一业务文件写入口是jobs/tutorial_backup.py；BaseJob仅日志/抽象run，无用量账本。

- 必须保留：**/app/data/tutorial_backups/** 内14个现有gzip JSON，合计**15,937,335字节**，均root:root、0644。实际文件：backup_20261013_180441、14_180441、15_180440、16_180440、17_180440、18_180441、19_180443、20_180442、21_180442、22_180442、23_180442、24_180442、25_180442、26_180441，均带.json.gz后缀（14—26缩写日期前缀均为backup_202610）。仅读取stat，未打开或解压备份内容。
- 源码TutorialBackupJob每天导出tutorial_books/chapters/sections/figures/training_samples到上述目录，retention=14天且会unlink旧档。**最终copy应在暂停future tutorial_backup且旧cron正常退出后进行**，避免rotation遗漏；当前PG备份不能替代这些历史导出文件。主controller已确认保留到新cron同路径及离机Mac，不需要新增volume平台。
- /tmp/play-release-manifest.json：3767字节，SHA256=3a41eb7cf2b19f65c146dcf358d5c3008f9e62000bcba565dca54f65d8ba5be9；只检查JSON root keys，均为cron源码路径→hash的部署凭证，不是业务进度/paid usage。可随迁移证据保留，无须把它当运行状态恢复入口。
- 当前旧image没有kifu_ingest/本地Qwen ledger模块；在本轮限定的实际cron源写入口+实际writable diff中**未发现其它本地预算、paid usage或业务进度文件**。报告/live/kifu分析状态、翻译结果、cron runs/controls均由现有PG模型写入；本轮不据此泛化到TEST新版本或其它容器。

## 追加：TEST同镜像重建的完整任务范围（18:28:01 UTC）

仅补读一次home-ubuntu当前实际config/status快照，无控制操作：**TEST不是hourly-only override**。ANALYZE、CLEANUP、FETCH_LIST、FETCH_UPCOMING、PANDANET、POLL_MOVES、REPORT_ANALYZE、TRANSLATE、TUTORIAL_BACKUP、KIFU_INGEST、KIFU_INGEST_LLM均true，KIFU_ANALYZE=false（YIKE/XINGZHEN亦true）。DASHSCOPE_API_KEY配置presence=true，只读取bool，不输出值；不能把旧PROD免费Wiki任务的取消判断套用到TEST。

本次heartbeat=18:27:55：analyze in_flight=0/capacity16；report_analyze in_flight=0/capacity3。全部interval当时均last_finished>=last_started、last_status=success；cron_job_runs running/finished_at NULL聚合为空，所有paused控制聚合为空。kifu_ingest上一轮17:41:09→17:44:09，translate18:27:08→18:27:09，poll_moves18:27:59→18:28:00，均success。这证明**该采样时刻业务空闲**，不预留未来窗口，两个loop的常驻running状态不表示有in-flight。

因此改变TEST KIFU_INGEST_SSH_HOST并同image重建整个cron前，除了既有kifu_ingest holder，还应保存并暂停其它7个interval的future触发（fetch_list/poll_moves/poll_pandanet/translate/fetch_upcoming/cleanup/tutorial_backup），封住TEST新增report及内部analysis来源，再复核loop与interval仍空闲，才进行空闲重建。TEST translate配置可调用付费LLM，但该采样时刻没有活跃translate；kifu_ingest仍受to_thread实际writer与PG/flock双锁边界约束，绝不能以cancel外层await替代线程完成。迁移结束恢复全部原控制前像，仅保留原home-ubuntu唯一collector指向新PROD receiver。
