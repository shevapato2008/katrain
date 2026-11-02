# Max 开放与会员提示修订发布回执

2026-11-02（约 11:54 收尾）：本轮阶段 A 功能、Web 软件发布与临时资源清理完成。用户已授权 Max 开放、双端展示 30 天总量及钱包确认最高扣费；本修订取代旧 Max 独立停售决定，不重新核算成本。

## 发布版本

- feature：`f23b013055aa6580e8494037416df4e91efff4b1`。
- develop / 两端实际新 Web 软件：`7f2ff0c65381250e41a9dc959d8cac9201c3a86b`。
- smartbox-software 父 main：`daef1180ddfeb4780782ec7db0f4fd278897a6c1`，submodule 指向上述软件提交。

已按四步集成、先 TEST 后新 PROD 发布；后续仅 docs 收尾提交不等于镜像软件版本变化。

| 环境 | 实际新 Web container ID | immutable image ID |
| --- | --- | --- |
| TEST home-ubuntu | `268448f27a1a4a590062cc4cc46ee4d341edef2f497f64fa8b6540d44046aac1` | `sha256:794c86edb6e25c6bd792ec87f908e5a48be0c29c43d93f2f1fd50b1dae17c0e8` |
| PROD 117.50.177.254 | `fd45629f641651c00ceed19bcf8bf99b8a8a5f76470f60ba89d70db6c34ba24b` | `sha256:ddc38046071462fd6f05f49c285cb02c04df75a5dfb69e3b8359ed6383fedee2` |

TEST Web HTTP 200、restart 0；12 个其它服务（含 Cron）未变。PROD Web healthy、HTTP 200、restart 0；17 个其它服务（含 Cron）未变。两端发布源码校验全匹配；PROD Web 候选包补齐 4 个已发布共享 Cron 模块，实际 Cron 未重启，code/调度未改。

## 生效内容与边界

两端 env 与实际 Settings 的 `MEMBERSHIP_MAX_SALE_ENABLED=true`，运行时 `is_plan_sellable('max')=true`。Max 199 元、72240 / 24080 整数预算及 30 天约 240 盘、每周最多约 80 盘不变；Plus/Pro 价格与规则不变。

双端套餐卡直接显示“30天共约30／90／240盘”；钱包来源确认显示服务端签名报价的最高扣费，不新增额度或改变整次扣费来源。真实 HTTP catalog、[TEST Galaxy 1440×900](../../output/playwright/membership-max-clarity-20261102/test-live-galaxy-plans.png)及[PROD Kiosk 1024×600](../../output/playwright/membership-max-clarity-20261102/prod-live-kiosk-plans.png)已以真实 fan 账号核对，无 route mock，均为全局 paused 真实态；钱包确认来自四张 Vite 隔离预览，不是实际消费。

主 TEST / PROD 仍为 paused、payments disabled、billing enforced=true、Free=0，OpenAPI 无 mock 支付路由。Max 独立配置开放不代表当前已能真实下单付款；正式商户收款仍未实现/开通，阶段 B 继续等待实际前置。

## 验证与运维证据

相关真实 PG / 后端 69 通过、UI 36 通过、Vite 代表用例 2 通过，普通与严格 Kiosk 构建通过；[独立 Astra 审核](../superpowers/reviews/2026-11-02-membership-max-clarity-astra.md) Approved，0 未解决 Critical / Important，独立复验 23 Python / 32 UI 通过，四张代表图视觉通过。

[代表性截图](../../output/playwright/membership-max-clarity-20261102)仅覆盖本轮新增展示；未新增 GPU 或真实支付请求、容量压测、成本计算或全功能回归。

发布 helper SHA256 `98e816acbe780baf95e8f8168073ba2894efe852bb0bd3c0b454264e89027108`，仅将旧强制 Max false 改为显式 true/false，其余安全边界不放宽，已独立定向通过。旧 Web stopped backups 保留，未删除资产。

[TEST public receipt](../../output/releases/membership-max-20261102/test-public.json) / [PROD public receipt](../../output/releases/membership-max-20261102/prod-public.json)已保存。私有回执目录为 TEST `/tmp/membership-max-private-7f2ff0c65`、PROD `/var/tmp/membership-max-private-7f2ff0c65`，凭据/config 不进入文档或 Git。

本轮临时 PG `membership-max-validation-20261102` 已正常 stop 并 auto-remove，无残留；自建 release Chrome 已执行关闭，18979 / 18980 两条 SSH 隧道已关闭，既有主服务保持。

本回执只记录本轮修订；完整会员阶段 A 的历史账务/真实引擎验收见[上一轮发布回执](membership-release-2026-11-02.md)。
