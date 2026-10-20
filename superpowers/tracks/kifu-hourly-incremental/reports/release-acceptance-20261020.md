# 棋谱库回填与小时增量：验收记录

## 已交付

- 原始5,536盘已逐项处理：合格5,279盘（95.36%）在测试、正式两库均55包verified；各新增5,276盘、精确复用3盘；257盘隔离并保留原因。
- 已提供164种棋手原文、1,890种赛事原文的五语言显示值。这是原文显示键数量，不等于新增独立棋手或赛事实体数，也不宣称全部是权威既有译名。
- 两端Web源码914527449保持运行；TEST cron已部署b9d8bb901的复用译名元信息约束修复。feature/develop已推送至823ef149f，smartbox-software/main的submodule更新为1bb48f15。
- 2026-10-20 11:08启用测试机全天每小时任务：抓取、清洗、复用或补齐cn/tw/jp/ko/en、测试库及API验证、同包正式同步及验证。其他界面语言显示英语名称。
- 每UTC日最多100,000 token，每轮最多100盘/20个新名称；账本、队列、断点与unless-stopped均持久化。命中合格实体且五语齐全时0模型调用。正常分析固定GPU1:8002，1,000盘分析继续独立运行。

## 双口径统计（A回填完成点）

| 环境 | 目录总盘数 | 既定译名口径 fixedwide | 五语完整卡片 strictcomplete |
|---|---:|---:|---:|
| 测试 |176,549|160,261 / 90.77%|176,290 / 99.85%|
| 正式 |176,549|160,775 / 91.07%|176,290 / 99.85%|

公开列表176,290盘均符合完整卡片资格。两种百分比使用同一总盘数、不同资格谓词，不能互相比较进度。fixedwide沿用旧口径：有关联赛事ID时要求两位棋手及赛事的实体五语，否则采用完整卡片资格。这些数值不代表权威译名核实率。

依据是fresh原生只读快照，加每批已通过原生资格检查的实际新增回执，再读取实际ID绑定核对fixedwide增量；不是声称回填后又全库重扫。TEST快照171,272盘，加5,277条已验证新增（含先前B单盘）；PROD快照171,293盘（已含pilot20和B单盘），加5,256条后续新增，均到176,549。PROD长扫描于2026-10-20 09:53完成，同一repeatable-read快照始于2026-10-19 23:08（北京时间）。详细原值与增量见JSON报告。

## 实际验证

- 两库55包、5,279个唯一来源的摘要、成员、完整SGF和名称及来源绑定均按每批原生流程验证；旧038/046/050回滚不计成功。
- 最终两端各12盘、60次五语详情及公开卡片有限HTTP抽检通过，覆盖新增、复用及canonical/raw棋手和赛事，包含五个数据修正回归；不声称最终重复HTTP检查了全部5,279盘。
- 两端Galaxy/Kiosk HTML及入口JS/CSS、五语详情、ru英语名称回退通过；吴清源与Go Seigen均1,231盘且首屏ID一致。公网两域名各health/Galaxy/Kiosk六个端点均200。此为实际HTTP验收，不是浏览器渲染或20次P95基准。
- 正式镜像完整依赖环境激活旧MDApp构造耦合导致Exit102，已先回滚恢复业务再修复。删除无后续消费者的GUI注册，聚焦回归2 passed，独立Astra max APPROVE。正式修复镜像在无网络、凭据、业务挂载条件下真实构造、JP/CN字体切换、NullEngine开局落子及状态读取通过，最终新Web健康。
- 正式教程表已备份并完成所合并develop必要的加法迁移，3,935个原图及棋局数量不变。两端55份receipt、55份verified与实际ops/helper已保存到服务器私有持久目录。

## 持续任务首轮故障与恢复

先前单盘TEST→PROD真实闭环、幂等重放及cron重建恢复已通过。11:09开始的首次持续运行61788下载100条来源，72盘形成发布包，但11:35在名称依据一致性校验失败。实际核对两库均无该包和72来源记录，未冒称入库。

根因为“姜勋”本次生成的原语言、日文方法标记与保留的既有依据不同。修复在独立审核前约束完整模板；84项聚焦测试及独立Astra审核通过，仅更新TEST cron。原生校验、正常GPU1分析及两端Web保持不变。

只对决策17进行真实Qwen生成与独立审核，保留其他17个决策、72盘棋谱和原冻结包。额外2次调用、1,296 token，当日累计34,282 token/44次调用。恢复工具经10项测试与独立Astra审核；默认dry-run及实际切换均通过，旧包隔离，新包72项仍为真实names_ready，无伪造发布回执。已恢复原暂停配置并请求调度器运行61884，目前继续核对真实同步结果。

本轮新9条metadata/SGF差异已只读核实：6条黑白对调、2条姓名用字不同、1条SGF字段损坏，均非干净段位或空格差异，不放宽身份比较；另2条翻译未通过数字或姓名方法校验，均隔离并保留原文件，其余队列继续。

257条A隔离已写入TEST StateStore，无虚假published/verified字段，Stage manifest及目录数量不变。另四条旧prompt-only失败只恢复downloaded，仍需走正常解析、翻译和审核，不作成功入库计数。

## 文件

- [机器可读验收与原始统计](release-acceptance-20261020.json)
- [A隔离原因清单](first-pass-isolations-20261020.md)
- [实施计划及历史执行记录](../plan.md)

## Current recovery status: 2026-10-20 13:20 CST (in progress)

The prior enabled run61884 failed after actual TEST880 publication and 360 detail checks. PROD receiver returned exit2, with no native receipt for that digest. The old receiver discarded its specific JSON guard error; no unsupported cause is claimed.

Independent semantic review identified 8 event decisions to correct. Only future kifu_ingest scheduling is paused. Native TEST undo succeeded for batches880/881/882 (461 reverted after-images), restoring176549 total /176290 public. Original publish, verification and undo receipts and all72 SGFs remain intact. The temporary72 increment is excluded from current coverage. Current two metrics are the A closepoint table above.

Changed8 decisions require real new producer and exact independent review; the other10 decisions remain unchanged. A distinct immutable package and native TEST then PROD verification are still pending. Code389b56702 and parentmain b27724c5 are published; its cron image is built, not yet selected. Safe diagnostic and narrow known-event guards passed103 focused tests and independent Astra review. Native identity/source/collision guards remain in place.
