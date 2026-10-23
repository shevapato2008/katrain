# 星阵小时棋谱同步修复与恢复说明

> 这是 10 月 23 日本地交付时点的说明。10 月 24 日获准后的双云部署、真实 20 盘新谱、旧 78 盘续验、重复轮次与后续独立流程审核见[发布恢复记录](releases/2026-10-24-golaxy-hourly-recovery/README.md)。下文的“未部署”描述保留原时点含义。

本轮为本地代码修复和独立审核。**没有推送、合并、部署、改生产队列、补跑真实导入或调用付费模型。** 生产 cron 在部署后才会使用新逻辑，不能把本地测试当作线上已恢复。

最终代码 `22fff109ea98f495c36cd527c0a28e941b5cb0c9` 已获另一位独立 Astra Max **Approved／无必须修复项**；聚焦回归 **295 passed**。参见 [整体审核](../superpowers/reviews/2026-10-23-golaxy-hourly-final-astra-review.md) 与 [本地验证记录](../superpowers/reviews/2026-10-23-golaxy-hourly-local-verification.md)。

## 小时范围

小时任务不再推进历史 rolling cursor。默认从第 0 页读取 5 个最新列表页（每页 20 条），最多允许配置 10 页；先发现，再处理，旧下载失败和旧包验证不能挡住第 0 页。

仅检查比赛时间落在近期窗口的条目，默认过去 7 天、硬上限 14 天。源 `playTime` 有 date/time，但没有时区；按产品约定解释为北京时间。官方前端只使用 page、size、game_type、username，尚无已验证的时间过滤或排序契约。因此扫描不会因一条旧谱提前结束，也不声称源站提供“过去一小时更新”的准确时间戳。

每小时以持久化的稳定元信息和 SGF 指纹比较变化。新候选优先，近期已见条目按最久未检查顺序复核；不在本轮头部的复核最多 20 条，也占用同一 SGF 预算。准备资格要求已查明发布状态且本轮 SGF 复核成功。未轮到的待办保留到下轮；已发布不变条目不重复翻译或入库。

同 ID 元信息或内容变化会保存差异证据并隔离，保留原 SGF、原元信息和原发布状态。元信息已变化而尚未下载 SGF 时，证据明确标记 `raw_status=not_fetched`。隔离不是自动覆盖原棋谱的许可。

分页、SGF、HTTP 或时间触顶会报告覆盖受限。五页样本曾含 100 个唯一 ID、近七天 69 条，这只是默认值依据；高峰和更长窗口不保证完整。可在相同硬上限内调整页数观察，不自动加深历史游标。超窗停机补录和古老赛事补传走独立人工入口。

所有下列配置使用 `CRON_KIFU_INGEST_` 前缀；升级后会约束旧环境中的过大值，例如 `SOURCE_SECONDS=1800` 的实际值变为 600。

| 后缀 | 默认值 | 硬上限 |
| --- | ---: | ---: |
| `WINDOW_DAYS` | 7 天 | 14 天 |
| `HEAD_PAGES` | 5 页 | 10 页，每页 20 条 |
| `MAX_REQUESTS` | 160 次 HTTP（含重试） | 240 |
| `MAX_GAMES` | 100 次 SGF 尝试／最多 100 个准备候选 | 100 |
| `MAX_RECHECKS` | 20 个不在当前头部的近期已见条目 | 20，包含在同一 SGF 预算中 |
| `SOURCE_SECONDS` | 600 秒 | 600 |
| `RECOVERY_SECONDS` | 300 秒 | 300，所有历史包共享 |

零预算会关闭相应阶段；窗口至少为 1 天。`ENABLED`、`INTERVAL` 和名称／UTC 日 token 账本沿用原有控制，不因修复放宽。检查点位于 stage 下 `api-verification/`，隔离的变更证据位于 `source-changes/`。

## 故障与已发布包

- SGF/shared 的业务 7004 为条目级终止；保留业务码、原消息、尝试次数和原数据。
- 普通临时错误有有限 HTTP 重试、逐条冷却和累计失败隔离；不会因五个坏项结束整个最新发现。
- 429 保持整源 Retry-After，不能通过跳到另一条棋谱绕过。
- 无效 SGF、黑白姓名冲突保留严格验证并隔离当条。
- 已有原生 PROD 发布回执的 78 盘恢复验证，不重复发布、导入或翻译。全部五语、SGF、姓名、来源和中文公开卡片验证通过后才能成为 `prod_synced`。

近期已冻结但尚未 PROD 的包可以继续原完整发布流程，但原 Stage 指纹、本轮观察指纹和冻结 manifest 必须全部存在且相同。缺失原始基线或版本变化会保留回执并隔离，不能为了续跑自动补写一个“原始”指纹。历史包只有 TEST 回执时最多续到 TEST 验证，不自动执行超窗历史 PROD 补录。

来源阶段 600 秒与旧包 API 验证尾段 300 秒使用真实网络截止。既有 3300 秒全轮设置是协作预算；同步 DB、SGF 缓存预热和发布线程仍可能超出，不能把取消 await 说成取消写线程。写线程尚未结束时不得启动第二个发布写入者。

## 获准发布后的有限恢复

1. 按正式发布流程部署代码和重建 cron 镜像，核对实际版本与挂载；本修复不包含 RK、Smartbox 或其他棋类操作。
2. 维护旧 stage 前，停止旧版 cron 写入者。新版小时任务和维护 CLI 使用同一 `.writer.lock`，但旧镜像不识别此锁。保留独立 stage 备份和运行记录，不删除失败项或冻结包。
3. 在正确挂载环境预览七个明确坏项的迁移：

   ```sh
   python -m katrain.kifu_ingest.maintenance migrate-7004 --staging-root /app/data/kifu_ingest
   ```

   仅匹配固定七个 ID 且原错误准确等于 `source business error: 7004` 的 failed 记录。确认输出后，获准的维护执行才加 `--apply`；保存返回的 audit 路径、pre/post SHA 和 before 备份。此迁移不标成功，也不是小时任务避开 2021 坏项的前提。

4. 如需回滚，先 dry-run：

   ```sh
   python -m katrain.kifu_ingest.maintenance rollback --staging-root /app/data/kifu_ingest --audit /app/data/kifu_ingest/maintenance/EXACT.audit.json
   ```

   仅当前 manifest 仍等于迁移 post SHA 才能加 `--apply`，否则拒绝覆盖后续有效进度。单 ID 人工恢复使用 `restore-item --external-id ID`，也默认 dry-run 并保留审计；恢复只解除重试隔离，不自动批准变更版本。

5. 恢复调度，观察一轮真实第 0 页扫描、窗口/覆盖日志和合法新谱完整 TEST → 验证 → PROD → 验证旅程。若 `91571067` 仍存在黑白冲突，应保留隔离；选择实际仍在窗口内的合法样本核对双库、source link 和公开 API。重放不应新增重复行或重复名称模型调用。
6. 单独观察 78 盘原生回执后的检查点进展与最终验证结果。未完成验证不得手工改为 `prod_synced`；若底层 API 继续慢或错误，应保留准确异常与未完成状态。

历史采集示例必须使用独立根目录，并给出有限 pages、max-downloads、max-requests、seconds；`collect-history` 不包含模型、准备或发布。其结果不应搬回小时热队列冒充最近更新。
