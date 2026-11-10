# 棋谱库回填与小时增量：验收记录

## 最新状态 · 2026-10-20 14:44 CST（06:44 UTC）

- **A 已完成：** 原始5,536条来源中5,279条接受，257条隔离；合格来源随后在两库各55包全部verified，每库实际新增5,276、精确复用3。first-pass就绪与实际入库分别计数，隔离条目不公开。
- **B 修正72盘真实闭环完成：** 同一不可变包 `0f64c2b366a0d9ba59b452d4aac4148dc5609d19c57c6befa1deacde06459e67` 在TEST883、PROD876均实际applied（各72新增、0复用）；两端各360项五语详情及相应公开列表验证通过，StateStore批次与72条目均为 `prod_synced`。恢复运维会话67907正常退出0并保存实际summary；它不是新增的CronRun编号。
- **最终版本已部署，正常轮次验收进行中：** 两端Web和TEST cron实际运行 `e23ac4105ad6ec770c4ebedf03e389b20768ee6c`；feature/develop同版本，父仓库main为 `0e0a53ef628846c737caa14840ab6747ba44e439`。健康、完整配置仅镜像/build SHA变化及其他容器未重启检查通过；两站Galaxy/Kiosk HTML、资源、公开列表和俄语英语回退通过。受限生产身份入口实际109条指令全部qualified、0模型调用。已仅恢复本会话维护暂停，命令2实际启动正常调度运行62158；其结束状态仍待验收。发布脚本经独立Astra审核APPROVE。
- **恢复证据已持久化：** 最终运维脚本、真实回执/验证及失败历史已私有归档到两主机任务Stage，737,280字节，SHA256 `96b6c8a2bc59cae29e3c8069793ffcd5221d2844c10fcfe1869a8ead1e1f9ad6`。原冻结包和旧TEST880/881/882真实undo记录均保留，不重复计算旧72盘。
- **独立1,000盘深度分析：** UTC06:19实际400完成、400双库同步、0失败，与A/B入库数量分开报告。

### 当前双口径（A完成基线＋实际B新增72）

| 环境 | 总盘数 | 公开完整卡片 | fixedwide | strictcomplete |
|---|---:|---:|---:|---:|
| TEST |176,621|176,362|160,333 / **90.7780%**|176,362 / **99.8534%**|
| PROD |176,621|176,362|160,847 / **91.0690%**|176,362 / **99.8534%**|

两种比例的分母均为目录总数176,621，不能解读为权威译名核实率。沿用原生基线与实际插入/绑定核对：TEST wide160,261+72；PROD wide160,775+72；总盘176,549+72，公开完整卡片176,290+72。此为基线加实际合格增量，不是新增后fresh全库重扫。先前B单盘已在基线内，不再重复加1。

### 实体五语与公开范围（14:51开始的独立只读快照）

| 环境 | 棋手P5 / 全部棋手 | 赛事E5 / 全部赛事 | 公开卡片完整率 |
|---|---:|---:|---:|
| TEST |3,838 / 3,865（99.3014%）|84 / 85（98.8235%）|176,362 / 176,362（100%）|
| PROD |3,663 / 3,689（99.2952%）|84 / 85（98.8235%）|176,362 / 176,362（100%）|

P5/E5使用未修改的原生名称资格函数新读取，分别耗时57秒/92秒；没有重复扫描全库卡片。它们表示实体五语资格，不表示全是权威通行译名。两端目录均含重复9盘、隐藏250盘，两类无交集，共259盘不公开。TEST任务表在该快照有268条隔离（A257＋其他11）；任务隔离不等同隐藏棋谱，PROD本地任务表不镜像TEST隔离。正常运行62158之后产生的隔离另按新快照统计。

原始统计及方法见 [TEST](canonical-metrics-e23/TEST.json)、[PROD](canonical-metrics-e23/PROD.json)、[方法](canonical-metrics-e23/method.json)。

## 历史记录说明

下列原进展按当时状态保留；其中“目前”“当前”“待完成”等表述只指相应历史检查点，最新状态以上文为准。

## 历史交付检查点（A完成与914发布时）

- 原始5,536盘已逐项处理：合格5,279盘（95.36%）在测试、正式两库均55包verified；各新增5,276盘、精确复用3盘；257盘隔离并保留原因。
- 已提供164种棋手原文、1,890种赛事原文的五语言显示值。这是原文显示键数量，不等于新增独立棋手或赛事实体数，也不宣称全部是权威既有译名。
- 两端Web源码914527449保持运行；TEST cron已部署b9d8bb901的复用译名元信息约束修复。feature/develop已推送至823ef149f，smartbox-software/main的submodule更新为1bb48f15。
- 2026-10-20 11:08启用测试机全天每小时任务：抓取、清洗、复用或补齐cn/tw/jp/ko/en、测试库及API验证、同包正式同步及验证。其他界面语言显示英语名称。
- 每UTC日最多100,000 token，每轮最多100盘/20个新名称；账本、队列、断点与unless-stopped均持久化。命中合格实体且五语齐全时0模型调用。正常分析固定GPU1:8002，1,000盘分析继续独立运行。

## 历史基线：双口径统计（A回填完成点）

| 环境 | 目录总盘数 | 既定译名口径 fixedwide | 五语完整卡片 strictcomplete |
|---|---:|---:|---:|
| 测试 |176,549|160,261 / 90.77%|176,290 / 99.85%|
| 正式 |176,549|160,775 / 91.07%|176,290 / 99.85%|

公开列表176,290盘均符合完整卡片资格。两种百分比使用同一总盘数、不同资格谓词，不能互相比较进度。fixedwide沿用旧口径：有关联赛事ID时要求两位棋手及赛事的实体五语，否则采用完整卡片资格。这些数值不代表权威译名核实率。

依据是fresh原生只读快照，加每批已通过原生资格检查的实际新增回执，再读取实际ID绑定核对fixedwide增量；不是声称回填后又全库重扫。TEST快照171,272盘，加5,277条已验证新增（含先前B单盘）；PROD快照171,293盘（已含pilot20和B单盘），加5,256条后续新增，均到176,549。PROD长扫描于2026-10-20 09:53完成，同一repeatable-read快照始于2026-10-19 23:08（北京时间）。详细原值与增量见JSON报告。

## 既有实际验证（A完成与914发布时）

- 两库55包、5,279个唯一来源的摘要、成员、完整SGF和名称及来源绑定均按每批原生流程验证；旧038/046/050回滚不计成功。
- 最终两端各12盘、60次五语详情及公开卡片有限HTTP抽检通过，覆盖新增、复用及canonical/raw棋手和赛事，包含五个数据修正回归；不声称最终重复HTTP检查了全部5,279盘。
- 两端Galaxy/Kiosk HTML及入口JS/CSS、五语详情、ru英语名称回退通过；吴清源与Go Seigen均1,231盘且首屏ID一致。公网两域名各health/Galaxy/Kiosk六个端点均200。此为实际HTTP验收，不是浏览器渲染或20次P95基准。
- 正式镜像完整依赖环境激活旧MDApp构造耦合导致Exit102，已先回滚恢复业务再修复。删除无后续消费者的GUI注册，聚焦回归2 passed，独立Astra max APPROVE。正式修复镜像在无网络、凭据、业务挂载条件下真实构造、JP/CN字体切换、NullEngine开局落子及状态读取通过，最终新Web健康。
- 正式教程表已备份并完成所合并develop必要的加法迁移，3,935个原图及棋局数量不变。两端55份receipt、55份verified与实际ops/helper已保存到服务器私有持久目录。

## 历史：持续任务首轮故障与恢复

先前单盘TEST→PROD真实闭环、幂等重放及cron重建恢复已通过。11:09开始的首次持续运行61788下载100条来源，72盘形成发布包，但11:35在名称依据一致性校验失败。实际核对两库均无该包和72来源记录，未冒称入库。

根因为“姜勋”本次生成的原语言、日文方法标记与保留的既有依据不同。修复在独立审核前约束完整模板；84项聚焦测试及独立Astra审核通过，仅更新TEST cron。原生校验、正常GPU1分析及两端Web保持不变。

只对决策17进行真实Qwen生成与独立审核，保留其他17个决策、72盘棋谱和原冻结包。额外2次调用、1,296 token，当日累计34,282 token/44次调用。恢复工具经10项测试与独立Astra审核；默认dry-run及实际切换均通过，旧包隔离，新包72项仍为真实names_ready，无伪造发布回执。已恢复原暂停配置并请求调度器运行61884，目前继续核对真实同步结果。

本轮新9条metadata/SGF差异已只读核实：6条黑白对调、2条姓名用字不同、1条SGF字段损坏，均非干净段位或空格差异，不放宽身份比较；另2条翻译未通过数字或姓名方法校验，均隔离并保留原文件，其余队列继续。

257条A隔离已写入TEST StateStore，无虚假published/verified字段，Stage manifest及目录数量不变。另四条旧prompt-only失败只恢复downloaded，仍需走正常解析、翻译和审核，不作成功入库计数。

## 文件

- [机器可读验收与原始统计](release-acceptance-20261020.json)
- [A隔离原因清单](first-pass-isolations-20261020.md)
- [实施计划及历史执行记录](../plan.md)

## Historical recovery checkpoint: 2026-10-20 13:20 CST (then in progress)

The prior enabled run61884 failed after actual TEST880 publication and 360 detail checks. PROD receiver returned exit2, with no native receipt for that digest. The old receiver discarded its specific JSON guard error; no unsupported cause is claimed.

Independent semantic review identified 8 event decisions to correct. Only future kifu_ingest scheduling is paused. Native TEST undo succeeded for batches880/881/882 (461 reverted after-images), restoring176549 total /176290 public. Original publish, verification and undo receipts and all72 SGFs remain intact. The temporary72 increment is excluded from current coverage. Current two metrics are the A closepoint table above.

Changed8 decisions require real new producer and exact independent review; the other10 decisions remain unchanged. A distinct immutable package and native TEST then PROD verification are still pending. Code389b56702 and parentmain b27724c5 are published; its cron image is built, not yet selected. Safe diagnostic and narrow known-event guards passed103 focused tests and independent Astra review. Native identity/source/collision guards remain in place.
