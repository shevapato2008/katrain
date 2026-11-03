# 会员软件发布回执：2026-11-02

**阶段 A（开发、隔离 TEST 与两端软件发布）完成；阶段 B（正式收款）未完成。** TEST 与新 PROD 主服务均保持 `MEMBERSHIP_MODE=paused`、`PAYMENTS_MODE=disabled`，不销售会员、不接受新付费授权。本文取代[发布前预检](membership-release-preflight-2026-11-02.md)和交接文件中的“尚未发布”历史状态。

## 已发布提交与实际软件版本

| 发布对象 | 已发布 SHA |
| --- | --- |
| feature/membership-recharge | `10f29db703783a00602038587c09235ac33011d3` |
| develop / 两端实际部署软件 R | `7fb94dce9f3d4e36835843cc8b828eb59245f6f1` |
| smartbox-software 父 main | `aa84764f1b73a8fadb9c6e4d46c26b77f07f208b`，`vendor/katrain` 指向 R |

已按 feature 合入最新 develop 并推送 → merge/push develop → 更新并推送父 main submodule → TEST 后新 PROD 的顺序完成。后续仅文档的收尾提交不等于重新构建镜像；实际部署软件版本仍以 R 与下表 immutable image 为准。

## 实际运行与发布保持项

| 环境 / 服务 | 完整 container ID | immutable image ID |
| --- | --- | --- |
| TEST `katrain-web` | `958d345111abb5097787cf0d6870b4bde2896f3bef37a9486323e6e408bd5cfa` | `sha256:8fb924354acbacd7d982f8a86c75d6a51958ac870a7aaa0da148d74234d79b01` |
| TEST `katrain-cron` | `e1b52cd907265099a0ca01557027a26b31710f0efa61eb885f2fd90e1f9dc083` | `sha256:ec4d98cc22523f1ae585b1d8b763a9f44589d54ec96829b7c05ddc437acf76e3` |
| PROD `katrain-ucloud-katrain-web-1` | `bac3487b51d85c1f05b2d3d449e2478a5dea877d70c13d77868840d5ef936286` | `sha256:4a2e6ef0fa23735092fca3b09cf46fe2bc96e34cd96dc286068c160e2c882988` |
| PROD `katrain-ucloud-katrain-cron-1` | `6464417453a7852b39cf7528c06ba37a6be5eed9d2b92a17c74fb18b665a3453` | `sha256:7750282292e8759b68453a68a8756ead474fdfd7c03dde831e958a00e973c8d6` |

- TEST 为 `home-ubuntu`；Web/Cron 均运行、restart 0，Web health HTTP 200，loops heartbeat 新鲜、error 0。7 项 pause 控制以 CAS 恢复，11 个无关服务身份/状态未变。
- 新 PROD 为 `ucloud-v100` / `117.50.177.254`；Web/Cron 均 healthy、restart 0，7 项 pause 恢复且 0 冲突，17 个无关服务未变，collector=false。未操作旧 183 入口。
- 两端主库 URL 未更换、余额未 rescale；TEST / PROD 的环境分别为 `test` / `production`，均明确 `paused`、`disabled`、`BILLING_ENFORCED=true`、`FREE_WEEKLY_REPORTS=0`、Max false。两端 OpenAPI 不注册 mock 支付路由；TEST 新 quote 实际返回 503。
- 原 env、网络/aliases、mounts、user、healthcheck、端口、资源和原任务数据按 fresh inspect/CAS 保留。native helper 最终 SHA256 为 `5ed0a19c737804dcad0357a25447a90c2e87bb32625eec8afbbd000826006a53`，独立审核 Approved；Mounts 仅按 Destination 规范顺序，完整内容校验没有放宽。
- 原 Web/Cron 备份均 stopped retained。首次财务发布失败采用停住 candidate、保留旧 stopped backup 的 forward-fix 策略；不回滚启动不懂 activation/v3 守卫的 f43，不清 activation、不切回 legacy。

私有发布回执保留在 TEST `/tmp/membership-release-private-7b7139cbe` 与 PROD `/var/tmp/membership-release-private-7fb94dce9`。这些目录内含私有配置，不进入 Git，不在本文复制 env、凭据或 token。

最终只读核对再次确认两端 Web/Cron 的软件 R 与 paused/disabled 配置正确；非敏感机器回执保存为 [TEST public receipt](../../output/releases/membership-20261102/test-public.json) 与 [PROD public receipt](../../output/releases/membership-20261102/prod-public.json)。

## 实际 TEST、页面与审核结果

隔离 TEST 使用专用 PostgreSQL `katrain_membership_test_20261102`、非 superuser app role 与独立 owner 建立的只读 control marker，未把主 TEST 现有数据库自标为 mock 库。在 `7b7139cbe1abf1f335563f431028e3110cfa54ef` 同版隔离应用上，真实 HTTP 验收完成：

- 真实账号密码登录/JWT、admin HMAC mock 事件、Pro 订单 9900 分与履约；本期/本周额度分别 27090 / 9030。
- 一次 9×9 两手 position、同 key 重放与已拥有结果读取；三位置报告按 0、1、2 完整 N+1 交付，由真实 worker 手动处理，未启动 scheduler。
- 共四次实际 8002 b11 引擎查询；实际模型 SHA256 `93bdb63a3bfae4a70db0cb5265287495ecfc10b1ba1cc6814feeba1cdf055871`，root visits 均为 503，满足请求 500 visits 的严格门槛。
- 最终 used=4、reserved=0，钱包 137 credits 不变，两条 operation 均 committed，重放没有重复扣费；报告三位置完整发布。

R 相比该实测版本仅追加一位小数折扣修复及上游 pinyin 合入；38 项聚焦检查通过，小修已获 Astra 定向 Approved，前端实现/产物未变。不能将这次 9×9、四查询的有限验收称为 Max 多棋局容量或生产 SLA 证明。

已在实际部署页面以真实 `fan` 账号查看 Galaxy 1440×900 与 Kiosk 1024×600，未使用 route mock。截图在 [membership-deployed-20261102](../../output/playwright/membership-deployed-20261102)，包含主 TEST / PROD 诚实暂停页面与隔离 TEST usage。这是浏览器页面验收，**不是 RK 实物硬件验收**。

此前开发验证与[全功能 Astra 终审](../superpowers/reviews/2026-11-02-membership-final-astra-r1.md)保持有效：最终代码检查点 `952580756fae2c64d2ce05695c98c3e3313c5ac8`，0 未解决 Critical / Important；组合后端 571 passed / 1 历史跳过、修复后聚焦 UI 212 通过、普通/严格 Kiosk 双构建和同尺寸视觉已完成。发布收尾未重复全量测试或重拍全部状态。

## 停机边界与清理

PROD 旧 translate 长批次通常约 138 分钟。切换时只有这一项非资金 translate 在途，其余在途均为 0；经独立 Astra Max 与发布 reviewer 核对后使用正常 SIGTERM，不发 SIGKILL、不并行启动第二实例。新 Cron 于 `04:17:32` 将旧 run 诚实标为 failed、写入 finished 时间及 interrupted 原因，reviewer 已独立只读确认；此前逐条提交的名称保留，当前名称可能重试并产生少量供应商成本，没有把中断漂白为成功。

本地临时 PostgreSQL 容器 `membership-validation-20261102-9f746279` 已停止。远端隔离 mock 实例 `69512…` 已正常停止、ExitCode 0；专用 TEST DB 与私有回执保留，不删除账务/验收证据。

## 仍关闭的正式前置

官方商户 adapter、真实验签/查单、小额支付与退款尚未实现/验收；P3 可信身份及注册限流没有可信提供者；Max 容量未验证。因此正式支付、Free 正式领取和 Max 销售均保持关闭。软件发布完成不能表述为正式收款完成；后续只有这些实际前置具备并完成相应验收后，才进入阶段 B。
