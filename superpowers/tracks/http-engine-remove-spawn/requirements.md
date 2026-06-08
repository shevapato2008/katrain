# Track: http-engine-remove-spawn · HTTP 引擎去掉"每条查询 spawn 子进程"

> 分支:`feature/rk3588-ui` · 创建 2026-06-08
> 类型:性能 / 扩展性缺陷修复(board + galaxy 共用引擎层)
> 来源:RK3562 实机验收 SBC 纯下棋(2b)时定位;原记录见
> `tracks/sbc-pure-play-remote-analysis/R8-http-engine-per-query-spawn.md`(本 track 为其独立化、加详)。

## 0. TL;DR(一句话)

`katrain/core/engine.py::KataGoHttpEngine._post_json()` 现在**每发一条 analyze 查询就用
`multiprocessing.get_context("spawn").Process` 起一个新 Python 进程**去做那一次 HTTP POST。
`spawn` 在 Linux 下会**重新 exec 解释器并 re-import 入口模块 `katrain.web.server`**(连同 SQLAlchemy/FastAPI/SQLite 初始化)。
要把它换成**直接在当前线程里 `requests.post`(或 async `httpx`)**,去掉一切 per-query 进程创建与框架重 import。
该方法**已经运行在每请求独立线程上**(见 §3),所以同步 `requests.post` 完全安全,改动小、风险低。

## 1. 背景(代码事实,均已核对)

- HTTP 引擎类:`katrain/core/engine.py` → `class KataGoHttpEngine(BaseEngine)`(约 L539)。
- 引擎工厂:同文件 `create_engine(katrain, config)`(约 L768):
  `backend in ["http","remote","cloud"]` → 返回 `KataGoHttpEngine`。
- 谁用它:`katrain/web/interface.py` 的 `KaTrainWeb`(**galaxy 与 kiosk 共用的 web 后端**)
  - 对局引擎:`self.engine = create_engine(self, self.config("engine"))`(约 L254、L1179)。
  - board 模式还会设 `{"backend":"http","http_url": remote_url}`(约 L223-224)。
  - 远程分析引擎(R6):`self.analysis_engine_instance = create_engine(self, remote_cfg)`(约 L233)。
- 板/kiosk 配置:`~/.katrain/config.json` → `engine.backend=http, http_url=http://127.0.0.1:8000`。
- 服务器/galaxy 配置:README「Deployment」用 `LOCAL_KATAGO_URL=http://127.0.0.1:8000`,
  `web/server.py`(约 L136-144)在 `backend=="http"` 时把 `engine/http_url` 同步成 `LOCAL_KATAGO_URL`。
  → **服务器按文档部署也是 http backend,同样命中 `KataGoHttpEngine`。**
- 仓库里**已存在**一个干净的 async httpx 客户端:
  `katrain/web/core/engine_client.py` → `class KataGoClient: async def analyze(...)`,
  `async with httpx.AsyncClient(...)`。这是 R8 应当收敛到的样板(见 §6)。
  ⚠️ 实现前需确认:galaxy 对局到底走 `KataGoHttpEngine`(需修)还是 `KataGoClient`(已干净)——见 §7 待确认项。

## 2. 现状代码(要替换的部分)

`katrain/core/engine.py`(约 L716-747):

    def _post_json(self, payload: Dict) -> Dict:
        url = f"{self.base_url}{self.analyze_path}"
        ctx = multiprocessing.get_context("spawn")
        parent_conn, child_conn = ctx.Pipe(duplex=False)
        p = ctx.Process(target=do_request, args=(url, payload, self._headers, self.http_timeout, child_conn))
        p.start()
        child_conn.close()
        try:
            if parent_conn.poll(self.http_timeout + 1.0):
                res = parent_conn.recv()
            else:
                if p.is_alive():
                    p.terminate()
                p.join()
                raise RuntimeError("HTTP request timed out or returned no data")
        except Exception as e:
            if p.is_alive():
                p.terminate()
            p.join()
            raise e
        finally:
            parent_conn.close()
        p.join(timeout=1.0)
        if p.is_alive():
            p.terminate()
            p.join()
        if "error" in res:
            raise RuntimeError(res["error"])
        return res["data"]

配套的子进程入口:`katrain/core/http_worker.py` → `do_request(url, payload, headers, timeout, conn)`
(里面就是 `import requests; requests.post(...)`,把结果经 `Pipe` 送回)。

## 3. 根因 + 为什么 spawn 是多余的(线程模型)

`KataGoHttpEngine` 的请求处理本来就**逐请求开线程**:

- `start()` 起一个 daemon worker:`self.worker_thread = threading.Thread(target=self._request_loop, daemon=True)`。
- `_request_loop` 取出队列项后:`threading.Thread(target=self._handle_request, args=(item,), daemon=True).start()`
  —— 注释原文:"Process in a separate thread to avoid head-of-line blocking"。
- `_handle_request`(约 L644)在**它自己的线程**里调用 `analysis = self._post_json(query)`(约 L659)。

也就是说:每条查询**已经隔离在独立线程**上了。`_post_json` 里再 `multiprocessing spawn` 一个进程,
是"线程隔离之上又叠了一层进程隔离",纯属多余;代价是每条查询 fork+exec+**重 import 整个 `katrain.web.server`**。

`requests` 已在 `engine.py` 顶部 import(L3),`http_timeout`/`_headers` 都是现成实例属性。
所以把 `_post_json` 体改成**当前线程同步 `requests.post`** 即可,语义不变、不阻塞 worker/事件循环。

## 4. 实测证据(2026-06-08,RK3562 board+humanv0,max_visits=1)

| 观测 | 结果 |
|---|---|
| 每步 AI 落子(改前) | `[11.0s]/[10.5s]/[11.3s][done]`,均 1 visit |
| 直接 `curl :8000/analyze` 同一 genmove | 连发 8/8 稳定 **~1.2s** |
| katago 自报推理 | `Processing batch of size 1` → 完成 ≈ **1s** |
| 9s 空档定位 | katrain 打 `Sending HTTP:N` 后,`:8000` 隔 ~9s 才打 `Analysis request HTTP:N` |
| 9s 里的动作 | 每手冒一个新 python 进程:`Database: Using SQLite` + `<frozen runpy> 'katrain.web.server' found in sys.modules` |
| GPU / CPU | Mali load=0;CPU 88% idle(load 6.4 是触摸 IRQ + Realtek WiFi 的 D 态假高) |
| 临时验证(把 `_post_json` 换成线程 `requests.post`) | 每步 `[1.3s][done]`,对局中 spawn 标记 **0**,白棋 ~1s 落子 |

结论:11s 全在 spawn+re-import,**不在引擎**。R1 抑制只减少查询条数,不降单条成本;**R8 才是落子延迟的主因修复**。

## 5. 需求

- **R8.1(必须)** `KataGoHttpEngine._post_json` 不再 per-query 创建进程。
  改为**当前线程内**直接发起 HTTP POST(`requests.post`,或迁移到 async `httpx`,见 §6),
  做到:一次 analyze = 一次网络往返,**零进程创建、零模块 re-import**。
- **R8.2(必须)** 保留超时语义:用 `requests(timeout=self.http_timeout)` /
  `httpx` timeout 取代原先靠 `p.terminate()` 的硬超时;超时/4xx/5xx 仍要抛出可被
  `_handle_request` 的 `except` 捕获并走 `error_callback` / `on_error` 的异常。
- **R8.3(必须)** 返回值保持等价:原 `return res["data"]`(即 `response.json()`)。
- **R8.4(应当)** `katrain/core/http_worker.py` 在迁移后**删除或保留为 fallback**;
  若删除,清掉 `engine.py` 顶部 `import multiprocessing` 等无用 import 及 `do_request` 的引用。
- **R8.5(应当)** 连接复用:用 `requests.Session` /
  `httpx.Client(限流连接池)` 复用 TCP(当前 `_headers` 是 `Connection: close`,每次新连);
  对服务器高并发尤其有意义。需评估线程安全(Session 跨线程)或每线程一个 client。
- **R8.6(必须·回归)** 不改变 galaxy / desktop 行为:`KataGoHttpEngine` 为三端共用,
  改动是纯传输层提速,对外行为(候选、visits、isDuringSearch、错误)需与基线一致。

## 6. 推荐实现方向(HOW 由开发侧定,这里给建议)

两条路,任选其一,优先 B:

- **A. 最小改动(线程同步 requests)**:直接把 `_post_json` 体换成
  `requests.post(url, json=payload, headers=self._headers, timeout=self.http_timeout)`,
  `raise_for_status` 或手动判 `>=400`,返回 `.json()`。因已在独立线程,安全。配 `requests.Session` 复用连接。
  —— 这正是 2026-06-08 板上临时验证用的版本(已证明 1.3s/步、spawn 归零)。

- **B. 收敛到现成 async 客户端(推荐,利于服务器规模)**:复用
  `web/core/engine_client.py::KataGoClient`(async httpx)的模式,
  让 HTTP 引擎走 async + 连接池;`_handle_request` 侧据 katrain 的线程/事件循环模型桥接
  (线程里 `asyncio.run` 单发,或把引擎请求并入服务端事件循环)。彻底去进程、去 `Connection: close`。
  注意:需确认 galaxy 实际引擎类(§7),避免两套 HTTP 客户端长期并存。

## 7. 约束、边界与待确认

- **待确认①(实现前先做)**:galaxy 对局/分析实际经过的引擎类——
  `core/engine.py::KataGoHttpEngine._post_json`(spawn,需修)还是
  `web/core/engine_client.py::KataGoClient.analyze`(已 async,无需修)?据此定收敛点。
  无论结论:board/kiosk 这条(`KataGoHttpEngine`)都必须去 spawn。
- **取消 / ponder**:原 spawn 用 `p.terminate()` 硬杀在途请求;`terminate_query`/`stop_pondering`
  目前主要是逻辑层(从 `self.queries` 摘除、忽略后续结果)。HTTP 是一次性 `/analyze`(无流式,
  见 README「HTTP KataGo Engine」),requests/httpx 用 timeout 即可;
  需保证 `terminate_query` 后即使响应回来也被忽略(`self.queries` 已无该 id → 现有逻辑已处理)。
- **isDuringSearch / reportDuringSearchEvery**:一次性 POST 只拿最终结果;
  保持现状即可(本 track 不引入流式)。
- **线程安全**:若引入 `requests.Session`/`httpx.Client` 复用,注意多线程共享;
  必要时每线程一个或加锁。
- **错误可用性**:`_handle_request` 依据异常设 `self._available=False` 并 `on_error`;
  新实现的异常类型/消息要能被其捕获(连接失败、超时、非 2xx)。

## 8. 验收标准

1. **板 humanv0 1visit**:每步 AI 落子 wall-clock **≤ ~2s**;`journalctl -u smartbox-katrain` 里
   `[Xs][done]` 的 X ≈ 1–2s。
2. `:8000` 的 `Analysis request HTTP:N` **紧跟** katrain 的 `Sending HTTP:N`(无 8–9s 空档)。
3. 对局期间**不再有 per-move 子进程**:`journalctl -u smartbox-katrain` 不再每手出现
   `katrain.web.server found in sys.modules` / `Using SQLite`。
4. **galaxy 回归**:对局、分析、错误处理与 develop 基线一致(无行为变化,仅更快)。
5. 单元/集成测试:为 `_post_json`(或其替代)新增测试——成功 200 返回 JSON、
   非 2xx 抛错、超时抛错;mock HTTP 服务,断言**不创建子进程**(可断言无 `multiprocessing` 调用)。
6. (若做 §6-B)galaxy 与 kiosk 收敛到同一 HTTP 客户端,无两套并存。

### 取证命令

    journalctl -u smartbox-katrain    | grep -E "Sending|done\]"            # 每步 [Xs][done]
    journalctl -u smartbox-katago-api | grep "Analysis request"             # :8000 何时真正开工
    journalctl -u smartbox-katrain    | grep -E "Using SQLite|frozen runpy" # 每手一次=还在 spawn

## 9. 影响面与优先级

- **板/kiosk(单用户、弱 ARM)**:延迟问题(~9s/步)。已用临时补丁验证修复。
- **服务器/galaxy(多用户、强算力)**:**扩展性**问题——每条查询都 fork+重 import 框架,
  成百上千并发棋局 = 每秒成百上千次进程创建(CPU 被 import 吃满、每进程数百 MB、PID/FD 压力)。
  O(查询数) 的进程创建反模式,强硬件只推迟撞墙。**故 R8 对服务器优先级高于板子。**

## 10. 关键文件

- `katrain/core/engine.py` —— `KataGoHttpEngine`(L539)、`_handle_request`(L644)、
  `_post_json`(L716,**改这里**)、`create_engine`(L768)、顶部 `import multiprocessing`(L2)。
- `katrain/core/http_worker.py` —— `do_request`(迁移后删/留 fallback)。
- `katrain/web/core/engine_client.py` —— `KataGoClient`(async httpx 样板,§6-B 收敛目标)。
- `katrain/web/interface.py` —— `create_engine` 调用点(L233/254/1179)、board 的 http 配置(L223)。
- `katrain/web/server.py` —— `LOCAL_KATAGO_URL` / backend 同步(L122/136-144/288)。

## 11. 与其它 track 的关系

- 与 `sbc-pure-play-remote-analysis` 的 **R1(抑制 eval)互补**:R1 减查询**条数**,R8 降**单条成本**;
  二者都到位才能稳定 ≤2s。
- 与该 track 的 **R7(抑制开关从 board 远程模式解耦)正交**:R8 在引擎传输层,三端共用。
- 板上现状:临时补丁已生效(`/root/smartbox-software/vendor/katrain/katrain/core/engine.py`,
  备份 `engine.py.r8bak`);R8 正式版合 develop 后按 submodule 流程拉回、再重新部署板子。
