# R8 · HTTP 引擎后端"每条查询 spawn 一个子进程" → 每步落子多 ~9s(RK3562 实测)

> Track: `sbc-pure-play-remote-analysis` · 分支 `feature/rk3588-ui`
> 2026-06-08 RK3562 实机验收 2b(AI≤2s)时定位。这是拖慢落子的**真正主因**,优先级高于 R1。

## 1. 现象

board 模式、humanv0、`max_visits=1` 下,每步白棋(AI)落子 wall-clock **10–12s**。
katrain 日志:`[11.0s][HTTP:1][done] ... 1 visits` / `[10.5s][HTTP:2][done]` / `[11.3s]`。

## 2. 定位(逐层实测,已排除其它)

- 抑制**已生效**:对局只发 `priority:10002` genmove,无 `priority:1002` eval(R1 OK)。
- 引擎不慢:直接 `curl :8000/analyze` 同一 genmove(1 visit + humanSLProfile)**稳定 1.2s,连发 8/8 全 ~1.2s**。
- katago 推理本身 ~1s(`:8000` 日志 `Processing batch of size 1` 到完成 ~1s);GPU load=0;CPU 88% idle。
- **9s 的空档在 katrain→:8000 之间**:katrain 打印 `Sending HTTP:1`(17:43:55)后,realtime_api 直到 17:44:**04** 才打印 `Analysis request HTTP:1`,中间 ~9s。
- 9s 里 katrain 冒出**新进程**(`python[19421/19476/19609...]`,每手一个)在 `Database: Using SQLite` + `<frozen runpy> 'katrain.web.server' found in sys.modules`——即 **re-import 整个 server 入口**。

## 3. 根因(代码级,精确到行)

`katrain/core/engine.py` 的 HTTP 后端 `_post_json()`(约 L714):

    def _post_json(self, payload):
        url = f"{self.base_url}{self.analyze_path}"
        ctx = multiprocessing.get_context("spawn")
        parent_conn, child_conn = ctx.Pipe(duplex=False)
        p = ctx.Process(target=do_request, args=(url, payload, self._headers, self.http_timeout, child_conn))
        p.start()
        ...

每发一条 analyze 查询,就用 `multiprocessing spawn` **起一个全新 Python 进程**去跑 `core/http_worker.do_request`(`requests.post`)。
`http_worker.py` 虽刻意不 import katrain/kivy(轻量),但 **`spawn` 在 Linux 下会重新 exec 解释器并 re-import 入口模块 `katrain.web.server`**(连同其全部依赖 + SQLite 初始化)——轻量优化被 spawn 本身抵消。RK3562 上每次 fork+spawn+re-import ≈ **9s**。

**与 board/server、远程同步均无关**:任何走 HTTP backend 的查询都付这个成本。R1 抑制只减少**查询条数**,不降低**每条**的 spawn 成本。这也解释了 06-05 的 ">10s"(那时 eval 洪水 × 每条 9s spawn,雪上加霜)。

## 4. 需求

- **R8.1** `_post_json` 不再 per-query spawn 进程。改用**线程**(`requests.post` 跑在 `ThreadPoolExecutor` 或 engine 现有 worker 线程里同步调用)或 **async `httpx`**。目标:一次 HTTP POST = 一次网络往返,**零进程创建、零 re-import**。
- **R8.2** 保留超时/可取消语义(原 spawn 是为了 `p.terminate()` 超时硬杀):线程版用 `requests(timeout=)`,async 版用 `httpx` timeout 即可。
- **R8.3** `http_worker.py`(spawn-safe 轻量模块)在改线程/async 后可弃用或留作 fallback。
- 不改 galaxy 行为(galaxy 同走 engine.py;线程化对两端都是纯加速,回归对齐)。

## 5. 验收

1. 板 humanv0 1visit:每步 AI 落子 wall-clock **≤ ~2s**;katrain 日志 `[Xs][done]` 的 X≈1–2s。
2. `:8000` 的 `Analysis request` 紧跟 katrain `Sending`(**无 8–9s 空档**)。
3. 对局期间**不再有 per-move 子进程**(日志不再出现每手一次的 `katrain.web.server found in sys.modules` / SQLite init)。
4. galaxy 对局/分析回归一致。

## 6. 取证命令

    journalctl -u smartbox-katrain   | grep -E "Sending|done\]"           # 每步 [Xs][done]
    journalctl -u smartbox-katago-api| grep "Analysis request"            # :8000 何时真正开工
    journalctl -u smartbox-katrain   | grep -E "Using SQLite|frozen runpy"# 每手一次=spawn 重 import

## 7. 关系

- 与 R1(抑制 eval)互补:R1 减条数、R8 降单条成本,**两者都到位**才能稳定 ≤2s。
- 与 R7(抑制解耦 board)正交。R8 是引擎层、两模式共用。
