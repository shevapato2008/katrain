# r4 healthcheck 验收辅助脚本独立复核

**PASS — 可按 `verify` 阶段使用补充辅助脚本。** 本复核仅覆盖 Docker healthcheck 验收条件的修改，不构成新增产品审核、数据库批准或部署执行。

核对对象：`/tmp/kifu-reader-r4-root-20261009/deploy-r4.py` 与 `verify-r4-runtime.py`。差异仅替换原第 84 行的 healthcheck 断言；用原断言替回后，两份源码完全相同。

- 容器必须仍在运行。
- 当前容器 `Config.Healthcheck` 必须与固定 r3 image ID 的配置完全一致；配置漂移会失败。
- 配置了非 `NONE` 探针时，仍要求 `State.Health.Status == healthy`。
- 未配置或明确 `NONE` 时，要求 `State.Health` 缺省或为 `None`，符合 root 报告的 TEST r3/r4 实际状态；不会凭没有探针而强求不存在的 `healthy` 状态。
- 原有运行 image ID、其他容器 ID 集合、运行文件哈希及 HTTP health 请求/JSON 读取检查均原样保留。

聚焦验证：Python 语法编译通过；独立运行修改片段的 8 个内存场景全部符合预期（无探针、NONE、healthy 通过；unhealthy、starting、停止、意外 Health 状态、配置漂移拒绝）。没有运行完整脚本、Docker、SQL 或部署。

边界：这里比较的是固定 r3 **镜像** 的 healthcheck 配置；实际 before-container 若存在 Compose 覆盖，脚本会严格拒绝差异。它不会静默放过该情况。root 提供的 TEST before-image/before-container 均无探针与此条件一致；实际 TEST/PROD 运行验收结果仍由 root 执行取得。

原脚本 SHA-256：`af988123382a07860e9ddb030e8901a57c953da92d3f83dfe872caf60a2db03c`。补充脚本 SHA-256：`01e0fd5adf99461d0314c4a0f42e706c1bf8b75cd561e23420db1a1b09688591`。
