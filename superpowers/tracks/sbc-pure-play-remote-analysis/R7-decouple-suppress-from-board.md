# R7 · 把 eval抑制 从 board 远程瘦客户端开关里解耦

> Track: `sbc-pure-play-remote-analysis` · 分支 `feature/rk3588-ui`
> 2026-06-08 由 RK3562 实机验收(MANUAL-TESTING 2b)阻塞推导。补充需求,供本仓库 Claude Code 实现。

## 1. 现象(实机阻塞)

把 `KATRAIN_MODE=board` 下到 RK3562 想验收 R1(对弈抑制 per-node eval)时,
**`admin/admin` 登录直接失败**。日志:

    auth.py:98  remote_data = await remote_client.login(...)
    remote_client.py:105 _request → httpx ConnectError(连接异常)

## 2. 根因(源码级耦合)

`KATRAIN_MODE == "board"` 这一个开关同时驱动了两件**本应正交**的事:

1. **eval 抑制(R1,纯引擎本地)** — `katrain/web/interface.py:139`
   `self.suppress_auto_eval = _settings.KATRAIN_MODE == "board"`
2. **board=远程瘦客户端架构** — `katrain/web/server.py` `_lifespan_board()`
   创建 `RemoteAPIClient(base_url=settings.REMOTE_API_URL)` 并挂到 `app.state.remote_client`;
   于是 `auth.py:95 if remote_client is not None:` 把**登录/对局/棋谱**全部转发给云端。

物理板上 `REMOTE_API_URL=""`(云服务器尚未建),登录被转发到空地址 → 连接失败。
本地 SQLite 里 admin 用户(id=1)其实正常,只是 board 模式根本不查本地库。

**后果**:R1 抑制本来是离线可跑的引擎行为,却因为绑在 board 开关上,
被未建成的云端架构连坐,导致**整机对弈无法登录、R1 无法验收**。

## 3. 需求

**R7** 抑制 eval 必须能在**不依赖远程云端**的前提下独立开启。

- R7.1 `config.py` 增独立设置 `SBC_PURE_PLAY: bool = False`,
  来源 `os.getenv("KATRAIN_SBC_PURE_PLAY")`(`"1"/"true"` 为真)。
- R7.2 `interface.py:139` 抑制门控改为:
  `self.suppress_auto_eval = _settings.SBC_PURE_PLAY or (_settings.KATRAIN_MODE == "board")`
  即 board 仍隐含 pure-play;但 pure-play 也能在 `server` 模式下单独打开。
- R7.3 不动 board/远程瘦客户端代码路径(留给未来云端联调);
  只是**不再把它作为 pure-play 的前置条件**。
- R7.4 galaxy/服务器默认(两个开关都不设)行为零变化(回归)。

## 4. 板上落地(R5 实现后)

板子改用:`KATRAIN_MODE=server`(本地 SQLite 登录可用)+ `KATRAIN_SBC_PURE_PLAY=1`(抑制生效)。
→ 离线整机对弈打通,admin/admin 本地登录正常,且对局只发 genmove。
对应 systemd drop-in 去掉 `KATRAIN_MODE=board`,加 `KATRAIN_SBC_PURE_PLAY=1`。

## 5. 验收(修订版 2b,离线可测)

1. 板 `server`+`SBC_PURE_PLAY=1`:admin/admin **本地登录成功**;对拟人 AI 落子;
   `journalctl -u smartbox-katrain | grep "Sending KataGo HTTP analysis query"`
   **只见 genmove(无 priority-1002 eval)**;AI 每步 ≤ ~2s。
2. galaxy 默认(两开关皆空):对局/分析回归一致。
3. board 远程模式(`KATRAIN_MODE=board`+真 `REMOTE_API_URL`)未来云端就绪后仍可用。

## 6. 备注

- 这是 plan v2 阶段 1(R1,commit `fb4d2fc2`)遗留的耦合:R1 当时图省事复用了 board 开关。
- 与既有 R3「kiosk 范围/配置开关、不改 galaxy」一致——R5 正是补上那个独立开关。
- billing(阶段2)/排位封口(阶段4a)是 server 模式测项,与本离线 2b 无关。
