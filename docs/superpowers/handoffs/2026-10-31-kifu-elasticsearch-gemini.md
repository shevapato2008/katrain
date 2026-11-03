# Gemini 接手 Prompt：棋谱库 Elasticsearch 搜索

请在当前新 worktree 中继续现有实现，完成开发、审核、集成、TEST/PROD 部署和验收。用户已授权这些工作，无需重新询问是否开始。不要从头重写或再次扩张架构。

## 工作目录和分支

- 唯一后续开发目录：`/Users/fan/Repositories/katrain-elasticsearch`
- 新分支：`feature/kifu-elasticsearch-gemini-20261031`
- 原目录：`/Users/fan/Repositories/katrain-kiosk-debug`，分支 `fix/kiosk-ui-debug`。
- 原分支已从 `09ee7f59f` 快进至本次 fetch 的 `origin/develop=07d1ddce9e8808fa6c7b840e1a0cd928048ac4bd` 并推送；没有合并冲突。
- 新分支包含这个 develop 基线，以及原 ES 专用分支六个提交，止于 `4e3dcfb46bba1cb8cd9e5344a1bf44c3384cdb2f`；其后的交接提交保存尚未完工的草稿和本说明。
- 原 ES worktree `/Users/fan/.config/superpowers/worktrees/katrain-kiosk-debug/kifu-elasticsearch-20261030` 保留供参考，后续不要同时在那里写入。

先读取 `AGENTS.md`、`GEMINI.md`，检查 `git status`、`git log` 和实际代码。不要使用 reset/clean 丢弃用户或其他会话改动。新会话开始时重新 fetch 并核实远端，不把本记录当成永远最新的版本。

## 权威文档

以下都是当前 worktree 内的相对路径：

1. `docs/superpowers/plans/2026-10-30-kifu-elasticsearch-search.md`：主计划，第 0.1 节是五语分词最终决策。
2. `docs/superpowers/plans/2026-10-30-kifu-multilingual-analysis.md`：分词补充计划。
3. `docs/superpowers/research/2026-10-30-kifu-multilingual-analyzers.md`：分词调研依据。
4. `docs/superpowers/research/2026-10-30-kifu-elasticsearch-index-storage.md`：索引与存储预算。
5. `docs/superpowers/reviews/2026-10-30-kifu-elasticsearch-plan-r1.md` 和 `...-r2.md`：原两轮 Astra Max 评审，第二轮 Approved。
6. `docs/operations/kifu-elasticsearch.md`、`docs/operations/kifu-elasticsearch-cases.json`：操作顺序和契约用例。

五语配置在原计划两轮评审之后并入，实际实现必须纳入独立代码和发布审核，不能冒称已经获得原评审背书。历史暂停已被用户恢复实施的指令撤销。文档中的旧分支名称用于追溯，不表示应回到旧 worktree 开发。

## 实际接手停点

已保存的工作包括 ES HTTP 传输/索引管理、名称投影/查询、现有业务提交后的增量同步，以及 API 读路径与旧方案退役草稿。迁移时验证了原工作区的完整 tracked diff 与五个 untracked 文件逐字节一致，原工作区未被修改。

交接提交是 **WIP 保存点，不是完成声明**。尚需逐项确认和完成：真实 ES/PG 集成、五语插件安装和切词效果、接口完整契约、写入失败恢复、独立 Astra Max 审核、正式资源测量、四步发布、两端数据切换和正式环境性能验收。不要把已有纯代码测试或旧 PostgreSQL 压测数字称为 ES 已上线达标。

本机私有冻结 oracle 位于 `/Users/fan/.local/share/kifu-elasticsearch-20261030/oracles`，如可用请核实快照与当前数据是否一致；不可将完整 SGF/私有响应、凭据或环境变量全文提交到 Git。需要新快照时使用有界只读操作，不更改旧预期掩盖回归。

## 必须保持的设计

- PostgreSQL 是业务权威，ES 仅是可重建的搜索索引。不新增 Redis、Kafka、CDC、outbox 平台或通用依赖框架。
- 姓名保持 keyword/ID 精确路径和原字面子串能力，不拆姓名，不按 BM25 改变原日期/id排序。
- 赛事：cn/tw 使用 IK（索引 `ik_max_word`、查询 `ik_smart`）；jp 使用 Kuromoji；ko 使用 Nori（索引 mixed、查询 discard）；en 使用 standard、无停用词/词干化。
- 组合语义：同一赛事语言字段内 AND，五语字段之间 OR；UI 语言不限制输入语言。繁体、日语专名/全半角和韩语复合词必须实测。
- 先校验固定版本镜像/插件、真实 `_analyze` 和正反例，再用同一批 1000 盘量资源，最后只做一次最终全量构建。
- API、精确 total、可见性/身份 scope、稳定排序、任意页分页、段位、报告判定和每个非空页首盘 preview 均保持。支持原 11 个 UI 语言入参。ES 不存 SGF、分析 moves 或审核证据全文。
- 在线请求只读取已整理的搜索文档，不重复跑全套名称审核。当前页必要 SGF/段位/报告继续有限批读 PG。
- 首次全量一次，此后沿现有发布批次增量，不每小时全库扫描。保持既有签名 manifest/receipt 与受限 TEST→PROD receiver，不开放跨环境 DB/ES 访问。
- 落实原 writer 锁、已提交事实、幂等恢复、pending/ready 和同一具体索引的单调 epoch；请求结束也检查 epoch，防止 ABA/混合版本。故障显式报告，不能用空成功或隐藏慢回退掩盖。

## 清理和资源

用户明确要求删除被替代的旧 prepared 代码、四进程 reader、旧 CLI 和纯旧测试，不长期保留两套优化系统；保留业务资格、段位、报告、分析和前端竞态修复。

实际 Web/cron/receiver 切换并验收后，再按白名单用 RESTRICT 退役旧六张派生表、40 个触发器及函数，不用 CASCADE，不动原业务表/receipt/rank/report。只删除明确属于本任务且未被引用的临时文件、容器和镜像，禁止 `docker system prune`、业务 `VACUUM FULL` 或删除 WAL。

遵守主计划资源预算：ES 2GiB RAM/1GiB heap/CPU 2、单主分片零副本；index store 2GiB、额外峰值 10GiB、剩余空间 15GiB 是停止/报告阈值。不要重复下载、全量试建或自动扩盘。新 worktree 不复制 node_modules、虚拟环境或构建产物。

## 开发与审核

使用 `subagent-driven-development`，只并行互不冲突的任务。复用现有实现与检查，按实际风险做必要验证，不增设与交付无关的平台或测试体系。

完成实现后交给独立 Astra Max agent 做代码和发布边界审核，包含新增分词配置；修复直至通过。若环境无法调用 Astra Max，交付可审核成果并明确报告“待审核”，不得伪称通过或越过发布门槛。

## 四步发布

1. fetch 最新 develop，合入本新分支，解决冲突、验证、提交并 push 本新分支。
2. 将本分支合入 develop 并 push develop。
3. 将 `smartbox-software/vendor/katrain` 更新到已发布 develop 提交，提交并 push 父仓库 main，保留无关改动。
4. 先 TEST `home-ubuntu`，后新 PROD `ucloud-v100`（`117.50.177.254`），执行实际切换与验收。

禁止使用旧正式 IP `117.50.183.169`。新正式环境现有 Web/PG 是原生 Docker 管理，先 inspect 原配置，不照搬旧 Compose 示例重建无关服务。ES 端口仅私网/loopback。不得在 RK3562 部署 ES。

## 验收与汇报

硬指标是 **真实正式环境**稳定 ready 窗口下 100 固定 QPS、30 秒、3000 次完整 HTTP 请求，**每请求 ≤200ms**，错误/超时/缺失响应/语义差异均为 0。遵守主计划到达率、inflight 和 drain 约束，报告客户端位置/网络路径、发送/完成/实际到达数、p50/p95/p99/max 和超标数量。

不能用 TEST、ES took、P95、ASGI 内部时间或换成 ID 查询代替；不能删除响应字段或 preview 来达标。1QPS/20ms 仅诊断，不是硬门槛。发布 pending 的短时 503/恢复与稳定窗口压测分开报告。

公网及实际浏览器另测“王星昊”“吴清源”首次/重复查询：API、传输、列表和正确棋盘展示耗时，以及响应大小/Content-Encoding。新增赛事多词正反例与原 exact oracle 分开，不弱化原契约。

开始时汇报实际接手状态和剩余清单；阶段变化及至少每 30 分钟汇报当前步骤、已完成项、阻塞和预计剩余时间，汇报不暂停主线。最终给出审核结论、feature/develop/Smartbox SHA、两端实际部署版本、正式压测、浏览器体验、增量/恢复和磁盘清理结果。只有全部满足才能声明完成。

## 本次交接验证记录

- 在新 worktree 复用 `/Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python`，未安装或复制依赖；关闭 bytecode 和 pytest cache 写入。
- 对 documents、ES transport、publication、完整响应契约、retirement、load gate、HTTP timing 七组测试执行一次：**132 passed in 7.08s**。
- 这仅是交接时的聚焦代码检查，不代表真实 ES/PG 集成、插件效果、独立 Astra Max 代码审核、部署或正式性能验收完成。

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/fan/Repositories/katrain-elasticsearch CI=true \
/Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest -p no:cacheprovider \
tests/web_ui/test_kifu_search_documents.py tests/web_ui/test_kifu_search_es.py \
tests/web_ui/test_kifu_search_publication.py tests/web_ui/test_kifu_es_contract.py \
tests/web_ui/test_kifu_search_retirement.py tests/web_ui/test_kifu_search_load.py \
tests/web_ui/test_kifu_http_timing.py -q
```
