# 直播源「剩余时间」可得性探针(2026-09-22)

> PRD §3 L2:先验「源给不给剩余时间」,再决定要不要付「加列 + cron 写入 + 类型 + 屏 18 渲染」三层的钱。
> 探针时刻 2026-09-22 01:50–01:55 CST,本机(Mac)直连三家上游。原始响应只存在 scratchpad,**不入库**。

## 结论一句话

**只有 IGS(PandaNet)在协议里给剩余时间,但抓取代码把它丢了;星阵、弈客在已观测的响应里都没有。**
三处都有「未验证」的缺口,全部来自同一个原因:探针时刻是凌晨,**三家都没有职业对局在下**
(星阵 `/all` 为空、弈客进行中 0 场、IGS 113 局里职业转播 0 局)。

| 源 | 上游协议 | 抓取代码 | 库 | 直播态验过没有 |
|---|---|---|---|---|
| 星阵 | 已结束对局的响应里**没有** | 只读 `startTime` | 无列 | **未验证**(探针时无直播) |
| 弈客 | 已结束对局的响应里**没有**(`time_use` 字段在,20 条全是 `null`) | 不读 | 无列 | **未验证**(探针时无直播) |
| IGS | **有**:`moves` 表头每方 `(提子 剩余秒数 读秒剩余子数)` | **丢了**(`_MOVE_RE` 只认着法行) | 无列 | 业余局看到了;**职业转播(cron 只存这一类)未验证** |

按 PRD 的二选一,落在「**至少一个源给得出**」那一支 ⇒ 下面写了后续计划草案,**本轮不实现**。
但给得出的那一家是三家里最弱的一家(见「后续计划」前的三条保留),**开不开工请 Fan 定**。

## 星阵(xingzhen)

- 抓取代码:`katrain/cron/clients/xingzhen.py:119` `parse_match_to_row` —— 时间只读 `startTime`(`:144`),
  返回的字典里没有任何剩余时间 / 用时 / 读秒字段。
- 接口与真实响应(2026-09-22 01:50):
  - `GET /all` → `{"code":"0","msg":"","data":[]}` —— **此刻没有直播**。
  - `GET /history?page=0&size=3&live_type=TOP_LIVE` → 3 条。`liveMatch` 字段全集:
    `boardSize endTime gameId gameResult gameroomId handicap id komi liveExplain liveId liveOrder liveStatus
    liveType moveNum name pb pbCountry pbLevel pbPhotoFile pw pwCountry pwLevel pwPhotoFile rule sgf startTime
    type userCode winrate`。时间类只有 `startTime` / `endTime`(开赛与终局时刻,不是钟)。`sgf` 为空串。
  - `GET /situation/195344?no_cache=1`(已结束的一局)→ 顶层只有 `liveMatch` + `moves`(逗号分隔的落点序号);
    `liveMatch` 比上面多出 `clusterId engineIds gpuPlanId po`,仍无时间字段。
- 有没有剩余时间:**已结束对局的响应里没有;直播态未验证**。
- 没有在哪一层:上游(就已观测的响应而言)。直播态的 `/situation` 是否多带字段,要在有直播时复跑。

## 弈客(yike)

- 抓取代码:`katrain/cron/clients/yike.py:157` `parse_match_to_row` —— 时间只读 `game_date` / `broadcast_time`(`:181`)。
- 接口与真实响应(2026-09-22 01:52,用仓里 `YikeWeiQiClient` 自己的签名请求):
  - `GET /v1/golives?status=2&type=0` → **0 场进行中**。
  - 已结束 20 场,列表项字段全集:`auto_flag black_avatar black_grade black_name black_player black_player_id
    black_ranks black_support_times broadcast_time comment_fixed comment_times create_by create_time delete_flag
    enabled game_date game_location game_name game_result hall handicap hands_count id is_judge_line is_upload
    known_color live_member meta paste person_times player1_id player2_id pv remark room status study_flag
    time_use top_flag tour_location type ugc_flag update_by update_time uv version white_* …`
  - 唯一沾边的是 **`time_use`:20 条全是 `null`**。它是「总用时」还是「用时设定」,空值上看不出来。
  - `GET /v1/golives/195038`(详情)→ 多一个 `sgf` / `clean_sgf`。SGF 属性全集:
    `AP B CA FF GM HA KM PB PW RU SO SZ W` —— **没有 `BL` / `WL`(剩余时间)、`OB` / `OW`(读秒次数)、`TM` / `OT`(用时设定)**。
  - `meta`:`black_win_rate rate_hands_count realtime_analysis_flag …`,无时间。
- 有没有剩余时间:**已结束对局没有;直播态未验证**(`time_use` 在直播时是否有值是最值得复查的一格)。
- 没有在哪一层:上游(就已观测的响应而言)。

## PandaNet(IGS)

- 抓取代码:`katrain/cron/clients/pandanet.py:86` `get_moves` 发 `moves <id>`,逐行过 `_MOVE_RE`(`:203`),
  **只认 `15 N(B): Q16` 这种着法行**。
- 真实响应(2026-09-22 01:54,guest 登录,`games` 113 行解析出 71 局;挑手数最多的两局发 `moves`):

  ```
  15 Game 66 I: susu1183 (6 401 11) vs ok8040 (19 529 16)
  15 Game 109 I: Zvikush1 (33 483 15) vs sasha (16 531 17)
  ```

  这是 IGS 协议的对局表头,每方括号里三个数按协议的通常解读是 **(提子数 剩余秒数 本读秒周期剩余子数)**。
  两局都是 300 手左右、`BY`=10(每周期 10 分钟)的加拿大读秒局,401 / 529 秒落在一个周期之内,与这个解读吻合;
  **第三格的含义本探针没有逐一核实**(比如主时间阶段它写什么)。**`_MOVE_RE` 不匹配这一行 ⇒ 抓取代码把它整行丢了。**
- `pandanet.py:193` 的 `byo_time` 取自 `games` 列表的 `BY` 列,是**读秒设定**(每个周期几分钟),不是剩余时间。
- 保留:
  1. **cron 只存职业转播**(`poll_pandanet.py:30` `type == "P"`),而探针时 113 局里 P 类 **0 局**(112 局 I、1 局 R)。
     表头格式在业余局上看到了;**转播账号的钟是否跟实战同步,未验证** —— 转播员手工摆谱时这个数可能只是转播账号自己的钟。
  2. **轮询 300 秒一次**(`poll_pandanet.py:22`)⇒ 屏上的数最旧差 5 分钟,要画钟就得在盒上按「抓取时刻 + 轮到谁」往下走秒。
  3. PandaNet 源本身在屏上的分量:`current_winrate` 恒写 `0.5`(`pandanet.py:125`),锦标赛名恒为「Pandanet-IGS Professional Relay」
     —— 这一源整体就是三家里最薄的一家。

## 库与前端

- `katrain/web/core/models_db.py:327` `LiveMatchDB`:无任何时间列(2026-09-22 复核)。
- `katrain/web/ui/src/types/live.ts:6` `MatchSummary`:无。

## 后续计划草案(本轮不实现;开不开工请 Fan 定)

**开工前先做一件便宜的事**:在白天有职业直播时(北京时间 10:00–18:00)把本探针复跑一次 ——
星阵 `/situation/<直播中的 id>`、弈客直播详情的 `time_use`、IGS 的 P 类转播表头。三处任何一处翻盘都会改变下面的范围。

若复跑后仍只有 IGS 给得出:

1. `LiveMatchDB` 加两列可空列 `black_time_left` / `white_time_left`(秒)+ `clock_sampled_at`(仓里没有 alembic:
   在模型上加列,`katrain/web/core/migrations.py` 的 `add_missing_columns` 会补上)。
2. `pandanet.py` 解析 `15 Game N …: 白 (c t b) vs 黑 (c t b)` 表头写入;**给不出的源写 NULL**,不写 0。
3. `/live/matches*` 与 `types/live.ts` 加这三个字段;盒上代理原样透传。
4. 屏 18 玩家卡的 `.clock` **只对有数的源渲染**;按 `clock_sampled_at` 与轮到谁在盒上往下走秒,
   超过一个轮询周期没更新就标「可能不准」。**给不出的源一律不画钟** —— 画一个空钟比不画更坏。
