# KataGo 单引擎并发与多服务比较

日期：2026-11-01。范围：官方文档/实现与本仓库部署文件、已有实验记录的只读调研。本轮没有启动或重启引擎、修改运行配置、清缓存、安装环境或新增 GPU 压测，也没有访问数据库、密钥或环境文件。

## 结论

**在同一张 V100、同模型和同总并发下，多开 KataGo 服务不保证更快。应先把单个 `analysis` 引擎的多局面并发配置和请求供给做好，再公平比较多个引擎进程。** KataGo 官方专门把跨局面 batching 作为 analysis engine 的优势；它本来就能异步接收多个查询，无须靠多进程才能并行。[官方分析协议](https://github.com/lightvector/KataGo/blob/v1.18.2/docs/Analysis_Engine.md)

现有证据支持“单引擎接收多个请求可以增加吞吐”，尚不能回答“同模型开两个进程是否比一个进程快”。保留不同模型或不同用途的服务，可以有隔离价值；不能把隔离收益直接换算成算力收益。

## 先区分三个层次

| 层次 | 实际变化 | 对速度的含义 |
| --- | --- | --- |
| 多个 HTTP 服务，共用一个引擎 | 增加 API 接入/路由进程，引擎计算资源不变 | 只有 API 层原先成为瓶颈时才可能改善接入吞吐，不能自动增加 GPU 计算能力。 |
| 多个 HTTP 服务，各起一个引擎进程 | 每个引擎有自己的搜索、推理队列、模型和缓存 | 可以分别调度、重启和限流，但多个进程仍争用同一张 GPU。 |
| 一个 `analysis` 引擎内多个查询 | 多个局面共享该模型的神经网络评估器和 batch 队列 | 原生支持；可以在一个进程内获得跨局面 batching 和缓存复用。 |

第三点有直接实现依据：v1.18.2 的 `analysis.cpp` 创建一个主模型 `NNEvaluator`，再把它交给每一个分析 worker；`nneval.cpp` 从共享评估队列中一次取最多一个 batch 的任务。因此同进程不同局面的网络评估能合批，而两个独立进程不会通过这个队列合批。[分析 worker 源码](https://github.com/lightvector/KataGo/blob/v1.18.2/cpp/command/analysis.cpp#L155)、[batch 队列源码](https://github.com/lightvector/KataGo/blob/v1.18.2/cpp/neuralnet/nneval.cpp#L836)

## 配置如何影响吞吐与延迟

| 参数 | 含义与取舍 |
| --- | --- |
| `numAnalysisThreads` | 同时搜索多少个局面。客户端只有一个在途局面时，设成 8 并不会凭空出现另外 7 个局面。 |
| `numSearchThreadsPerAnalysisThread` | 每个局面的 MCTS 搜索线程；旧分析配置中的 `numSearchThreads` 是它的别名。更多线程可能缩短单局面等待，但会增加同一搜索树的竞争。固定 visits 时，搜索轨迹和质量也不保证完全相同。 |
| 两者乘积 | 最大搜索线程数。批量分析通常倾向更多局面、每局面较少线程；交互分析则要兼顾单请求延迟。官方提醒最佳线程数可能超过 CPU 核数，不能机械按核数设上限。 |
| `nnMaxBatchSize` | 单 GPU 一次网络推理的最大 batch；这是上限，并不保证每批都满。官方通常建议 GPU 数×batch 上限不低于总搜索线程数，但显存预算和实际吞吐可以支持较小设置，应实测。 |
| `nnCacheSizePowerOfTwo` | 神经网络结果缓存的容量指数。一个引擎的查询可复用同一缓存；多个进程各自维护缓存。此缓存主要占主机 RAM，不能把它和 GPU 权重/推理工作区混为一谈。 |

上述调参方向来自[官方 v1.18.2 示例配置](https://github.com/lightvector/KataGo/blob/v1.18.2/cpp/configs/analysis_example.cfg#L90)。batch 上限的实际取用和缓存命中路径可见[评估器源码](https://github.com/lightvector/KataGo/blob/v1.18.2/cpp/neuralnet/nneval.cpp#L836)。

**对同一张 V100 的工程推断：**如果原先一个进程只接收串行查询，另开进程可能因增加在途搜索而显得更快；但让原进程接收相同数量的查询，也可能得到相同或更好的利用率。单进程已有足够在途工作时，多进程会把可合并的 batch 分成多条队列，还可能增加 CPU 调度和 GPU 上下文切换成本。另一方面，特定模型、后端和 CPU 配比下，多个推理流也可能填补空隙；不能只凭机制就宣称一定更慢。

多进程还会分别持有模型及 GPU buffers、分别建立缓存。官方 CUDA 实现允许同进程多个 NN server thread 在条件满足时共享权重；这不等于跨进程自动共享。模型重复、工作区和额外缓存的代价要计入比较。[CUDA 资源所有权源码](https://github.com/lightvector/KataGo/blob/v1.18.2/cpp/neuralnet/cudaandrocmbackend.inc#L429)、[ComputeHandle 与 buffers](https://github.com/lightvector/KataGo/blob/v1.18.2/cpp/neuralnet/cudaandrocmbackend.inc#L4930)

本轮未核验生产机的 CUDA MPS 状态。NVIDIA 说明 MPS 可改善 GPU 利用率并减少上下文切换；不能假设任意多个普通 CUDA 进程都能无成本并行。若将来考虑 MPS，它应是单独的实验变量，本轮不启用。[NVIDIA MPS 文档](https://docs.nvidia.com/deploy/mps/latest/index.html)

## 当前部署与已有数据

这些事实来自仓库配置与 2026-11-01 已有实验记录，本轮未重新 SSH 核验运行状态：

- 目标机是 `ucloud-v100`（`117.50.177.254`），单张 Tesla V100-PCIE-16GB。`:8000` 默认 `b28`，SHA-256 为 `798da8fe3e9819f09535240b1bc29cb3047a4fa981433c56c491e57007a3d3f0`；`:8002` 默认 `tf3-b11c768`，SHA-256 为 `93bdb63a3bfae4a70db0cb5265287495ecfc10b1ba1cc6814feeba1cdf055871`。两个 HTTP 服务下的引擎共享该 GPU。
- cron 的固定引擎版本为 KataGo `v1.18.2`，Git `fd0723fdbc0e9d82cf269c9630af8c27c57c07c4`。源配置为 `numAnalysisThreads=8,numSearchThreadsPerAnalysisThread=4,nnMaxBatchSize=16`：最多 8 个局面、32 个搜索线程，而单批上限为 16。这个比例是后续调参候选，不能据此认定当前错误或承诺改到 32 会加速。[部署说明](../../deploy/katago-cron/README.md)、[cron 源配置](../../deploy/katago-cron/config.yaml)
- 当前 wrapper 每个模型持有一个引擎子进程；多个 `query()` 可同时等待各自 Future，没有把整个搜索期包在串行锁里。所以单 HTTP wrapper 已具备转发并发请求的路径。[wrapper 实现](../../deploy/katago-cron/realtime_api/katago_wrapper.py)
- 已有实验最后一次 GPU 采样为利用率 97%、显存 1872 MiB。这只是单个采样，不是单引擎持续利用率、峰值显存或安全扩容空间的证明。

已有 HTTP 引擎实验如下，均为 19×19、500 visits、ownership 开启：

| 模型 / 同一引擎 | 请求数 | 总并发 | 总耗时 | 局面/秒 | 请求延迟中位数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| tf3-b11c768，串行 | 8 | 1 | 18.7268 s | 0.4272 | 2.3801 s |
| tf3-b11c768，并发 | 23 | 3 | 31.0027 s | 0.7419 | 4.0998 s |
| b28，串行 | 8 | 1 | 13.2067 s | 0.6058 | 1.6534 s |
| b28，并发 | 23 | 3 | 15.8876 s | 1.4477 | 2.2803 s |

来源：[engine-benchmark.json](artifacts/membership-cost-20261101/engine-benchmark.json)、[实验脚本](artifacts/membership-cost-20261101/bench.py)。这些组使用不同局面，串行与并发样本量不同，暖引擎且没有清 NN cache；同一盘棋的搜索可能复用先前评估。它们能说明现有路径确实接受并发，并提示吞吐与延迟的取舍，**不能把速率比当成严格加速比，不能把 b28 与 tf3 的差异归因于服务数量，更不是同模型多进程对照。** `rootInfo.visits` 也是搜索工作单位，不等于物理 GPU 推理次数。

## 对当前业务的建议

1. **整盘报告、后台分析先用现有单引擎的有界局面并发。** 同时分析多个独立局面才能产生跨局面 batching；可把总在途数 3 作为已有证据支持的实验起点，再在隔离环境测是否值得提高。一个报告内部的多个独立局面也可以供给这些并发，不必等多个用户同时提交。
2. **交互对弈/提示与后台报告按体验目标调度。** 后台吞吐变好，不代表用户点一次提示更快。限制后台在途数，观察交互 p95；同引擎 `priority` 只影响尚未开始的任务，不会抢占已开始的长搜索。[官方 priority 定义](https://github.com/lightvector/KataGo/blob/v1.18.2/docs/Analysis_Engine.md#queries)
3. **目前两个不同模型的端口可保留业务和故障隔离意义。** 拆进程可独立重启、排队、设置线程与深度；在同 GPU 上仍无硬算力隔离保证。若必须保障线上延迟，明确资源限额或独立 GPU 比单纯再加端口更有确定性。
4. **不要直接把整盘 `analyzeTurns` 列表塞进当前 HTTP wrapper。** 官方引擎支持一查询多响应，但当前 `_read_loop()` 在第一个同 id 响应时就弹出 Future。现阶段可使用唯一 id 的单局面查询做有界并发；多响应聚合需要另外实现和验收，本次不改。

## 最小公平 A/B，留待隔离窗口执行

先回答“相同总资源预算，两个进程是否更快”，再决定是否值得进一步调参。本轮只定义方法；不执行生产实验。

| 项目 | A：单进程 | B：双进程 |
| --- | --- | --- |
| GPU / 模型 / 后端 | 同一 V100、同一 tf3 文件 SHA、同一 KataGo/CUDA/FP16 设置 | 完全相同 |
| 分析/搜索线程 | `8 × 4` | 每进程 `4 × 4`，合计同为 8 局面、32 搜索线程 |
| batch 容量控制 | `nnMaxBatchSize=16` | 每进程 8，名义总上限同为 16；实际 batch 和调度行为需记录 |
| NN cache 预算 | 固定总容量 | 每进程分配总容量的一半；例如 A 指数 23，B 各 22，避免把额外缓存当进程收益 |
| 客户端总并发 | 先固定 3 | 总数仍为 3，不能每进程各 3；固定分发规则并记录 |

采用一份固定、带哈希的公开 SGF 局面清单（例如 100 个覆盖开中终盘的局面），A/B 使用完全相同的顺序、规则、贴目、历史、棋盘和请求字段。先测实际主档 `500 visits + includeOwnership=true`；如业务需要深分析，再独立测 `2000 visits`。`includePolicy`、`wideRootNoise`、`humanSLProfile`/附加人类模型等也必须一致。确认每条最终响应与模型 SHA、请求 id、局面号对应，记录实际 root visits，拒绝把超时、部分响应或降低工作量算作成功加速。

隔离环境先完成模型/内核预热，再分别测两种策略，结果分开报告：

- **NN 冷缓存：**无在途查询时，对测试实例清缓存并等待确认，再开始测量；不把模型加载/内核首次编译混入稳态时间。生产服务不清缓存。
- **暖缓存：**各方案运行同一预热局面清单后再计时。B 的分发策略固定；若按棋局保持进程亲和性，要在结果中说明。禁止让 A 承接冷请求而 B 使用 A 已跑热的数据，或在切换方案时保留不对称历史。

每种缓存策略以 `ABBA` 顺序起步，A/B 各两轮；结果接近或波动较大才增加轮次。主要报告总 wall time、成功局面/秒、端到端延迟 p50/p95、错误/超时、实际 visits、峰值 GPU 显存、GPU 利用率时间序列及 CPU 使用。端到端延迟应包含排队，不能只统计进入引擎后的搜索时间；计时在同一客户端进行。100 条样本的 p95 仍只是探索性指标，不能直接成为生产 SLA。

固定总并发 3 的结果若表明仍有明显空闲，再以相同方法测总并发 8；若想比较“各自最佳配置”，另开一轮允许调 batch/线程，并披露显存与缓存预算差异。一次只运行 A 或 B，隔离其他 GPU 负载，固定 CPU 配额/MPS 状态。不能让 A 与 B 同时抢 GPU 后把干扰当作架构差异。

只有在相同质量档、相同输入和同总并发下，多进程的吞吐提升可重复，且用户 p95、显存及稳定性仍满足目标，才值得为了速度增加同模型引擎实例。
