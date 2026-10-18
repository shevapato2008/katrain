# 教材识别并行扩容实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development；在现有独立工作树执行，保持三个正在运行的单书进程。Steps use checkbox syntax.

**Goal:** 保留既有三路识别及缓存，先扩到六本/六个模型请求，再按实际表现扩到十本/十个请求，持续完成原23本核心教材。

**Architecture:** 复用现有单书 CLI、公共 flock 槽位、每书写锁及队列锁；配置新增进程可见的请求槽数和优先高位槽。旧进程继续使用原0–2槽；所有进程仍争用同一路径，不重启旧任务、不替换锁文件。TEST入库及验收继续串行。

**已核实锁路径（2026-10-18）:** 实际旧进程使用 `TMPDIR=/var/folders/wt/gws6wygd6ksbl8t3gppmy40h0000gn/T/`，锁目录真实路径为 `/private/var/folders/wt/gws6wygd6ksbl8t3gppmy40h0000gn/T/katrain-tutorial-gpt61sol/requests/`；原 `slot-0..2.lock` inode 分别为 `206248095`、`206248096`、`206248097`。此前决策中的 `/tmp` 为文档假设，不能据此迁移锁。新子进程显式使用已核实的原 TMPDIR；监督脚本本身的 stdout/stderr 写入文件，避免会话退出后断开输出管道。

**Tech Stack:** 现有Python、fcntl、subprocess、JSON队列和静态进度表，无新服务。

## 已完成的计划审核

- 独立GPT-6-Astra/max已只读审核，结论见本机私有目录 `curriculum-recognition-20261017/concurrency-decision.md`：同意下列最小方案，建议6→10分阶段观察。
- 原生Codex子智能体数量与识别子进程/模型请求数量分别控制；本次无需退出会话或修改用户Codex配置。

## Chunk 1：配置公共请求槽

APP工作树：`/Users/fan/.config/superpowers/worktrees/katrain-tutorial-module/tutorial-workbench-2026-10-14`。

- [ ] 修改 `scripts/recognize_tutorial_book.py::request_slot`：默认3；新增明确命名的进程环境配置（请求总槽数、优先扫描起点），正整数/有效范围校验。仍使用原 `slot-0.lock` 等文件，调用退出或异常均释放。新进程先尝试3以上槽，已运行旧进程不变。
- [ ] 先写聚焦失败测试，再实现；仅覆盖默认兼容、六/十槽上限与高位优先、异常释放/错误配置。用真实进程与flock验证共用0–2旧锁加新增槽不突破N；测试临时目录不得碰运行中的锁。
- [ ] 运行聚焦测试；独立Astra先核对规格，再核对代码/竞争风险，实际阻塞修到通过。

## Chunk 2：追加单书进程与报告

- [ ] 复用现有CLI，新增最小本地监督脚本；每书`workers=1`，600秒超时、最多两次尝试。启动前在 `DATA/queue-update.lock` 中重读并唯一领取仍为prepared的核心书，记录PID/日志/环境配置；保留单书写锁。启动失败释放本次领取，不能覆盖其他所有者状态。
- [ ] 先领取 `invasion`、`moyo`、`sakata-5`，请求槽上限6、优先起点3。确认三条新增进程及实际模型请求已运行，旧三进程保留。
- [ ] 每10页由现有JSON检查点报告并刷新HTML；进程结束即记录原退出状态，交根串行完成严格/来源复核和TEST验收，再立即领取下一未保留核心书。禁止凭进程exit0直接标成TEST完成。
- [ ] 更新 `update_progress.py` 中固定“三请求”和仅整书刷新文案，使用实际配置上限；保留既有书籍人工成果/媒体阶段。
- [ ] 独立Astra代码审核启动/领取/报告关键路径，聚焦验证不重复领取与失败回退，不新增通用任务平台。

## Chunk 3：六路观察后到十路

- [ ] 用实际成功请求、耗时、429/超时及页吞吐核对六路运行；若出现限流不盲目增加，不为观察超时重启活跃任务。
- [ ] 六路稳定后新增 `ko`、`simple-judgement`、`endgame`、`go-games`，上限10、优先新增高位槽；已有3槽/6槽进程继续使用原槽范围，总请求仍不超过10。
- [ ] 持续按原23本范围处理、每10页session+HTML报告、整书幂等TEST增量入库和独立SGF导出验收。无生产/RK写入、无自动人审或批量媒体。

## 不变的完成标准

并行进程数、请求上限、识别完成、机器契约通过、TEST验收与人工审核分别报告。来源歧义保留原证据，不能为提速降低独立棋图覆盖或编造手顺。新增并发控制不改变模型、提示词、缓存身份和既有棋图内容。
