# ret85 · 587 竹下奈那 · KO 单格决定

**PASS — 采用 `타케시타 나나`，`published_name / found`。**

Reviewer：`/root/ret77_ko_astra_decision`；委派配置 `gpt-6-astra / max`。实读记录 UTC：`2026-10-07T21:12:59.743808+00:00`。本次只读已有正文与 metadata 并独立重算 SHA，未联网抓取、SQL、Git、改代码或改冻结源。

## 来源与身份判断

Hangame 棋局 224022 的 h1、`playerbname` 和 SGF `PB` 三处实际刊载完整韩名 `타케시타 나나`，页面记载 2025-01-20 日本女流本因坊预选及对手 `스즈키 아유미`。它属于专业围棋棋局刊载，可沿用既有 `language_go` 来源资格。

官方本人页直接提供 `竹下　奈那（タケシタ　ナナ / TAKESHITA, Nana）`；Igo 日英本人页及 CWI 自身条目重复对应原字与完整姓名。完整读音及日本女子职业围棋语境足以支持本格刊载名选择。**这是有限跨来源对应推断**：Hangame 正文没有日本原字，未独立核对同场日文赛果，不伪写为单页原字直接对应。

## 实读捕获锚点

- [professional_game_publication](https://baduk.hangame.com/gibo.nhn?m=view&gseq=224022)：metadata 记录 HTTP 200，抓取 UTC `2026-10-07T21:06:43.787000+00:00`；正文 SHA `1d787ffa08c421a968a32f4ecb4c63b82f2d8606313a7929c7e7b448b914d5e5`。
  - 实际摘录：`playerbname: '타케시타 나나'; playerbseq: '4203.0'; playdate: '2025-01-20'; title: '[일본 여류본인방전] 예선'; playerwname: '스즈키 아유미'; PB[타케시타 나나]`。
- [official_player_profile](https://www.nihonkiin.or.jp/player/htm/ki000536.htm)：metadata 记录 HTTP 200，抓取 UTC `2026-10-07T21:05:16.289927+00:00`；正文 SHA `af925af39b2b2d9fc93274bb6ac88c72bdbc1e8bd7c0202e5ca128c7da1ccf16`。
  - 实际摘录：`竹下　奈那 （タケシタ　ナナ / TAKESHITA, Nana）`。
- [japanese_player_profile](https://www.igorating.com/players/nana-takeshita)：metadata 记录 HTTP 200，抓取 UTC `2026-10-07T21:05:06.595971+00:00`；正文 SHA `eb0b5abc536c29abbe41906a16de3ef5adf1dc1a68cc0b261e5b1c272780948b`。
  - 实际摘录：`竹下奈那（たけした なな）`。
- [english_player_profile](https://www.igorating.com/en/players/nana-takeshita)：metadata 记录 HTTP 200，抓取 UTC `2026-10-07T21:05:06.503189+00:00`；正文 SHA `a63139989d25e4ca1d30519ec127049cbf2342a7474c33f2d4fa924988ac6781`。
  - 实际摘录：`Takeshita Nana (竹下奈那)`。
- [professional_go_history_compilation_own_row](https://homepages.cwi.nl/~aeb/go/misc/progression.html)：metadata 记录 HTTP 200，抓取 UTC `2026-10-07T09:51:23.067128+00:00`；正文 SHA `67cb59e1110cb4c4c58c3822f54bd5f66ebb149d149fd282964b922e90c20567`。
  - 实际摘录：`竹下奈那 Takeshita Nana (0p) *2008-02-07 1p: 2024-04-01`。

## 正确限制

- `seq4203` 空 profile 不用于正面姓名、原字或生日支持；其 HTTP 200 不等于取得本人资料。正文 SHA `8df60c240b3194a7b887cb8616bab93bbc3160d328ed1cae0296c20e2b3c0b8f`。
- 不借对手、兄弟姓名、空生日、旧比赛段位、SGF BR/WR 代码或 CWI 段位字段建立身份/现段位结论。官方与 CWI 的本人生日一致仅支持这两份日文身份资料，不冒称 Hangame 生日匹配。
- 规范候选 `다케시타 나나` 仍正确，保留为未选规范方案；此次选择的是实际刊载 `타케시타 나나`，不称其为 NIKL 规范输出或唯一通行名。
- PROD 587 / TEST 588、29 SGF slots 是 root 提供的绑定上下文，本 reviewer 未重审数据库桥；binder 继续使用现有资格校验，不改变来源 grade 或代码。
- 当批四份新资料保留 source producer `/root/next_players_sources_resume` / `gpt-6.1-sol` 的原 capture actor/model/UTC；CWI 保留原 metadata 的 producer `/root/official_hanja_retention_impl` / `gpt-6.1-sol`。Astra 不是上述网络抓取者。

机器可读记录：`/tmp/kifu-player-next5retired85-20261008/587-ko-decision-astra-v1.json`。

随后形成的 source v1 矩阵：`/tmp/kifu-player-next5retired85-20261008/source-producer-frozen25-v1/source-matrix25.json`，独立重算 SHA `e6cfa0fddfa6c7d601ba22162d3aa6d2310ada2ff2e16564d25284532e0f1d8c`。这里只核对矩阵哈希作归档锚点，未扩审其余 24 格。
