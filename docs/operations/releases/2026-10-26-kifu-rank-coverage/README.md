# 2026-10-26 棋谱等级覆盖发布与真实纠正

本次针对 Galaxy 公开棋谱库截图中的等级缺失，完成泛化身份消费者、有限 rank-only 纠正与两云后台发布。原谱明确等级仍优先；缺失时仅用已绑定同一棋手、具有职业身份证据的库内最新明确等级，作为「最新已知资料」快照，不声称是当局等级或真实升段日期。未知项继续为空。

## 发布版本与范围

| 组件 | 已发布 / 实际运行 |
| --- | --- |
| feature / develop | `e9b4d3ecce03b3269f12922a476fd6d6c6545547` |
| Smartbox main / gitlink | `8ca18de325a74dba376baa4fefe7c57c4312b2b9` / `e9b4d3ecce03b3269f12922a476fd6d6c6545547` |
| TEST web | `sha256:85391af74060372fb0558ca35703f9b1fad16f23cea681cc7f4e6e67073c816e` |
| TEST cron | `sha256:9604d05e4e096b4c97966e6c850492c87d60fe9fff1039c3fe94f67af081c08d` |
| PROD web / receiver | `sha256:f90b1526e8ec9375e3f0021a478b7a546fbf3026f6268b2b331adf97289b5355` |
| overlay bundle | `0aa8696e6a0fcdacac034da3623656b742f92a52af54c3eb61fb1ebfd0830590` |

本轮仅替换 14 个后台文件；两云静态资源完整映射及当前入口依赖图保持发布前的 `93f2038a0` 资源，未重建 UI。RK 沿用另一个已完成图标发布的 `4691484225b47fca7c6c7f8c8faa6edf6426a23d`，本轮未重启、切模式或导航设备。PROD 原分析 cron 未动，不启用第二套抓取/翻译。GPU、数据库、MinIO、配置、预算和持久 stage 均保留；本轮既有 rank schema 仅只读核对，没有 DDL 或授权变更。

云端镜像、实际文件 SHA、静态图、HTTP 200、原 compose 和其他容器保护见 [TEST web](cloud/web-deployed.filtered.json)、[TEST cron](cloud/cron-deployed.filtered.json)、[PROD web](cloud/prod/web-deployed.filtered.json)。

## 原因和改动

四个红框棋手都有唯一身份绑定及库内明确等级，但旧消费者仅接受初始六人的官方主体。其原导入包为 v1，当时没有 rank 阶段；原 run 成功、error_count=0、source 已 `prod_synced`、last_error=null。上线 fallback 后，已发布/已打包的谱不会自动重新 prepare，初始三 ID 纠正也没有覆盖它们。这里是资格/范围遗漏，没有相应异常堆栈，不是 API 缓存或 CSS 丢值。[原调查与日志](../../rank-coverage-20261026/README.md)。

本轮删除六人白名单，按既有批准证据精确解析日本棋院、韩国棋院、中国名录及海峰棋院的主体和身份；只接受同 owner 审核过的 exact 名字/alias，不做模糊认人，不取亲属、教师或正文邻人的等级。官网等级不直接生成新事实。已有官方主体明确比库内最新旧等级更高时，fallback 返回冲突，避免把已知陈旧的一段当最新值；原谱等级和已冻结历史不受此限制。

纠正 CLI 接受 1–20 个明确 source ID 的不可变 scope，同时 pin 每条原 SGF 与原包 manifest SHA。冻结后仍经原生 rank-only CAS 和当地身份核验进入 TEST、PROD。原 INFO 新增固定 lookup reason 计数和最多 200 个公开 source/side，cached unknown 记录为 `frozen_unknown`。实现、聚焦测试和独立审核见 [计划](../../../superpowers/plans/2026-10-26-rank-coverage-gap.md)、[代码审核 Approved](../../../superpowers/reviews/2026-10-26-rank-coverage-astra-code.md)。

## 四位截图样本已上线

| 棋手 | source ID / TEST / PROD | 库内明确等级依据 | 当前 display |
| --- | --- | --- | --- |
| 於之莹（原官方主体於之瑩） | `91635363` / 179081 / 178745 白 | `90638040`，2026-10-03 八段 | `8p` |
| 芮乃伟（繁体显示芮迺伟） | `91634842` / 179080 / 178744 白 | `91284543`，2026-10-15 九段 | `9p` |
| 党毅飞 | `91632021` / 179079 / 178743 黑 | `90903437`，2026-10-09 九段 | `9p` |
| 辜梓豪 | `91632021` / 179079 / 178743 白 | `85428764`，2026-07-19 九段 | `9p` |

本次原 SGF 的 BR/WR 仍为空，API raw rank 仍为 null；display 来自冻结 `library_current` 快照，保留 source、as-of、observed/matched time、fact/snapshot SHA，`valid_from=null`。两库五语言、SGF、姓名、赛事、公开卡片及 rank provenance 均真实验证，详见下列回执。

## 有限纠正与幂等

| 冻结包 | 盘数 / 新可靠侧 | TEST / PROD native batch | canonical manifest SHA |
| --- | --- | --- | --- |
| `rank-only-page-coverage-20261026-v1` | 18 / 32 | 938 / 931 | `7abc3136e13992127caf98bf670f6aa92e72b6651ca2f5092c3add8b9d549f44` |
| `rank-only-current-page-tail-20261026-v1` | 5 / 8 | 939 / 932 | `133dc7ae199afd5a3b692a45d2edff05480709753c910652354aeb45438254ce` |

第一包覆盖固定初始页面和候选（18 个 source，见 [scope](main/scope.json)）；等待旧 writer 时新到的当前页面，另用五 ID 冻结包覆盖（见 [tail scope](tail/scope.json)），没有持续扩展全库回扫。完整 manifest 留在 TEST 持久 stage 的 `rank-corrections/coverage-20261026/manifest.json` 与 `rank-corrections/coverage-tail-20261026/manifest.json`，本目录只收有限公开证据。

18 盘在 TEST 完成 90 条五语言详情和 18 条公开卡片验证，PROD 同样完成；五盘完成各 25 条详情和五条卡片。第一包 TEST 验证 41.86 秒、PROD 82.38 秒，第二包分别 16.61/34.12 秒。两个包 TEST/PROD 精确重放分别 31.72/30.71 秒，均复用同 native batch、receipt 字节一致，没有重复插入或翻译。

- 第一包：[冻结摘要](main/freeze-summary.json)、[TEST](main/test-verification.json)、[PROD receipt](main/prod-receipt.json)、[PROD 验证](main/prod-verification.json)、[精确重放](main/replay-result.json)。
- 第二包：[冻结摘要](tail/freeze-summary.json)、[TEST](tail/test-verification.json)、[PROD receipt](tail/prod-receipt.json)、[PROD 验证](tail/prod-verification.json)、[精确重放](tail/replay-result.json)。
- 两段维护内两库 album_count 始终 176884；history 6→38→46，snapshot 22→54→54。原 album 全字段/原 SGF hash、source links、原 native 包/receipt、StateStore 已同步进度不变，stage 原包与当日实际模型用量 ledger hash 不变。[第一包 TEST](main/test-integrity.json)、[PROD](main/prod-integrity.json)、[尾包 TEST](tail/tail-test-integrity.json)、[PROD](tail/tail-prod-integrity.json)。恢复正常小时任务以后产生的新数据或用量不属于此冻结比较。

尾包中 `91741775`、`91742836` 原先停在 `prod_published`，先用其已有 receipt 和完整原包恢复五语言/公开卡片续验，10 条详情及两卡通过后真实进入 `prod_synced`；发布和翻译调用均为 0，原包/receipt 不变。原 publication key `19x19-batch-19caaa5732be98c16944f87e`，SHA `5e89c7bd689de0fd9453301f4322c67a2156819572a5959b4826497a03ce52bd`。[续验回执](tail/original-recovery-result.json)。这不是重置状态假标成功。

## 当前有限覆盖和保留为空的原因

10:42 UTC 实际公开第一页 20 盘/40 侧：**34 侧有段位、6 侧为空**，raw 源等级均为空；有值侧均为明确来源的冻结 fallback。[逐条 API 结果](current-public-page.json)。这是有限当前页面覆盖，不是全七天或全部历史。

| 当前空侧 | 原因 |
| --- | --- |
| `91740310` 金泽秀男 黑 | album 的黑方 player FK 未绑定，不能仅靠名字补身份 |
| 同盘 孙喆 白 | 本人有库内八段依据，但现行 rank-only 工具要求整盘双方稳定绑定；黑方未绑定使该盘未纳入。不能描述为孙喆无等级。 |
| `91737274` 萧钰洋 白 | 未找到当前可复用的已审核官方职业主体 capture |
| `91634488` 李小溪94 黑 | 无可验证的绑定原谱等级，不与李小溪05混同 |
| `91741775` 仲邑菫 白 | 姓名有五语言已审记录，但当前证据无可复用官方主体 source-check capture；姓名审核不等于职业身份验证 |
| `91742836` 池本辽太 黑 | 同上，保留 unknown |

此外，已移出当前第一页但在第一冻结包内：鸟井裕太仍缺职业证据；李小溪05 的库内最新明确原谱是 2020 年一段，而同 owner 已审官方主体明确六段，故为 `official_grade_above_library_grade` 冲突，未用过时一段补值，也未凭官网字段直接写六段。相关未知和冲突不会阻断同盘可靠侧或其它合法棋谱。六个当前空位仍是具体数据/身份边界，不能称本轮已实现百分百等级覆盖。

## 调度与维护恢复

旧 run77679 在 08:13→09:09 UTC 实际成功结束后才执行切换，未取消同步线程或并发写。维护使用现有 1800 秒入口和同一 stage writer inode，分为两个有界窗口；第一阶段模型容量中断曾延长等待，随后先核对并恢复原控制前像，再重新取得合法新窗口，没有放宽 TTL。两次窗口均在验证后恢复为原本无控制行，holder 移除。

10:42 UTC：control=[]、enabled=true、interval=3600、heartbeat 新鲜、0 consecutive failures，自然小时 run77942 已于 10:41 启动。独立审核随后只读核实该轮于 **10:44:21 success/error_count=0**，10:57 控制仍为空且 heartbeat 新鲜。[phase2 恢复](cloud/maintenance-phase2-ready.filtered.json)、[phase3 恢复](cloud/maintenance-phase3-ready.filtered.json)、[10:42 调度](cloud/final-schedule.json)、[独立后续核对](astra-live-audit.md)。维护私有控制前像仅保留服务器0600文件，没有提交值或凭据。

原有小时边界保留：比赛窗口默认7天、硬上限14天；head 5×20（硬上限10页）、HTTP160（硬上限240）、SGF100、source600秒、recovery300秒、tokens100000，无 rolling 历史推进。3300秒是协作预算，无法取消的同步写线程不能当硬截止；旧轮约56分钟和下层冷路径尚未在本轮优化。缺少源站可靠 updated_at、有限 head 覆盖不足等原有边界继续如实记录，不承诺全库或精确最近一小时更新时间。

原 v2 unknown 快照经显式纠正后被新快照替代，旧 v2 包重新发布会因 snapshot 不同而拒绝；这是阻止旧包覆盖新纠正的 fail-closed 边界。原 artifact/receipt/原谱/ID/进度保留，当前 correction 的精确重放已验证。不宣称所有旧包在纠正以后仍可照原 snapshot 重发。

本轮真实资料旅程是原源等级缺失→库内匹配→新冻结 rank-only 包→TEST→同包 PROD→公开 API；没有为演示强造一盘新棋谱或强制翻译。新版本自然小时轮已成功，但本轮没有把全新 source 首次插入后的完整旅程作为额外已证结果。独立审核另核原谱明确三段的现有样本仍 `origin=source`，未被库内当前四段覆盖。

## 最终独立验收

本轮独立代码审核已 Approved。部署和所有真实有限纠正完成后另派 fresh Astra Max，在 10:49–11:01 UTC 仅只读独立核实当前镜像/文件、两库原始等级事实与原生 receipts、公开 API、剩余未知原因及调度状态。最终结论：**Approved，本轮 23 盘纠正和有限页面范围无 must-fix**。[完整独立实机报告](astra-live-audit.md)。

审核还记录：PROD health 一次返回 local engine=unreachable，单次有界复查已恢复 reachable，期间棋谱 API 成功；TEST 两项初次网络错误各重试一次均200。没有操作 GPU、重启其它服务或重复设备视觉检查，不将瞬时问题掩饰为全程无误，也不将此批准扩大为全部历史、未来所有新源或百分百段位覆盖。
