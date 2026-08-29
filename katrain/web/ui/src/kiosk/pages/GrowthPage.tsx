import { useEffect, useState } from 'react';
import { KioskStatusCells } from '../shell/KioskStatusCells';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../hooks/useTranslation';
import { useTsumegoProgress } from '../../context/TsumegoProgressContext';
import { useAiLadderStatus } from '../../features/aiLadder/useAiLadderStatus';
import { getGrowthSummary, rankedWinrate, type GrowthSummary } from '../api/growthApi';

/**
 * 屏 22 · 成长(L1 两栏)。
 *
 * ## 稿子这一屏有四处说的不成立 —— 都不照搬
 *
 * 稿子中间那一大块是道歉:「段位的算法是全的,接线断在一个词上 —— 写段位的分支只认
 * `game_type == "rated"`,而人机升降级写的是 `"ranked"`,所以打完永远不动段位;
 * 真正会改段位的只有在线大厅的定级队列」。**2026-08-25 逐条核过,四处都已经不是这样:**
 *
 * ① **那条 `rated` 计数已经被换掉了。** `server.py` 里那段注释白纸黑字写着替换理由:
 *    「Formerly a count of finished `game_type == "rated"` games, which nothing ever wrote
 *    for an AI game」⇒ 现在的闸是 `ai_ladder_repo.has_ladder_rank()`。
 *    `count_completed_rated_games` 如今**零调用者**,是死代码。
 * ② **升降级对弈真的会动段位。** `katrain/core/ladder.py` 有完整的 41 档,
 *    `ai_ladder_ranked.py` 有 `PLACEMENT_GAMES = 5`、`ai_ladder_rung`、`net_score`,
 *    升降由 `step_playable_rung(±1)` 写。`/api/v1/ai-ladder/status` 早就把这些吐出来了,
 *    **而且 kiosk 已经在用**(`useAiLadderStatus`)。⇒ 左栏画真数据,一行后端都不用加。
 * ③ **「上封 12 段」不存在。** 41 档是 20级…1级 / 准1段…9段 / 职业水平 / 职业顶尖 / 超越人类,
 *    全表里没有「12 段」这个词。屏上写的是**实际的上下界**。
 * ④ **「按对手强度」不用等。** `ai_ladder_game_ledger` 每一行都带 `opponent_rung` /
 *    `opponent_rank_name`,而且 `ck_ai_ladder_ledger_decision` 强制 counted 的行必须有档位 ——
 *    也就是**已计入的局一局都不会漏**。稿子写「还没有战绩」是因为它以为没这张账本。
 *
 * 留下的只有「能力诊断」那一块:它要拿**已经跑过报告**的对局算,那是另一条链(复盘屏),
 * 稿子的诚实空态原样照搬。
 *
 * ## 胜率为什么只算升降级局
 *
 * `user_games.result` 存的是**哪一方赢**(`"B+R"`),表里**没有任何一列记这个用户坐的是哪一方**
 * (测试里对着 `__table__.columns` 断言过)。拿玩家名去猜就是在编。
 * `ai_ladder_game_ledger` 有 `user_color`,`result` 本身就是从这个用户视角写的 ——
 * 所以这一格的标签必须写明「升降级」,不能写成光秃秃的「胜率」。
 */

/** 稿子那三条升降规矩。①② 与 `formatNetScoreValueText`(±3)一致;③ 是**改过的**:稿子写「上封 12 段」。 */
const LADDER_RULES = (t: (k: string, d: string) => string) => [
  t('growth:rule_up', '净胜 3 盘升一档'),
  t('growth:rule_down', '净负 3 盘降一档'),
  // 41 档的两端。稿子写的「上封 12 段」在 `katrain/core/ladder.py` 里根本不存在。
  t('growth:rule_bounds', '下封 20 级 · 上封 超越人类'),
];

const pct = (v: number) => `${Math.round(v * 100)}%`;

/** 净胜 / 净负多少盘升降一档。与 `formatNetScoreValueText`(ladder copy)的 ±3 同源。 */
const NET_STEP = 3;

const GrowthPage = () => {
  const { t } = useTranslation();
  const { token } = useAuth();
  const ladder = useAiLadderStatus(token ?? undefined);
  const { progress, serverLoadFailed } = useTsumegoProgress();
  const [summary, setSummary] = useState<GrowthSummary | null>(null);
  const [summaryFailed, setSummaryFailed] = useState(false);

  useEffect(() => {
    const ac = new AbortController();
    getGrowthSummary(token ?? undefined, ac.signal)
      .then((s) => { setSummary(s); setSummaryFailed(false); })
      // 失败就是失败:**不退回 0**。「一局没下」和「没读到」在屏上必须是两句话
      //(`summaryFailed` 那条 setnote)。abort 不算失败 —— 那是我们自己取消的。
      .catch(() => { if (!ac.signal.aborted) { setSummary(null); setSummaryFailed(true); } });
    return () => ac.abort();
  }, [token]);

  const solvedCount = Object.values(progress).filter((p) => p?.completed).length;
  /**
   * ⚠️ **「一题没做过」和「没读到」是两句话。**
   *
   * 服务端那次读失败、而本机缓存也是空的 —— 这时候写 `0` 是在替用户断言
   * 「你一题都没解过」,而我们根本不知道。这一屏自己头上就写着这条规矩
   * (拿不到就写 `—` 并说一句),四个格里只有这一格原来漏了:
   * 另外三格的数来自 `summary`,取不到时是 `undefined` ⇒ `num()` 自己会写 `—`;
   * 而这一格是**本地 `.length` 算出来的,永远是个数字**,失败也照样是 0。
   *
   * 本机有数就照常显示:那至少是个真实下界,不是猜的。
   */
  const solved = serverLoadFailed && solvedCount === 0 ? null : solvedCount;

  const status = ladder.status;
  const placement = status.view_state === 'ready' ? status.placement_state : null;
  const net = status.view_state === 'ready' ? status.net_score : 0;
  const rankText = placement === null
    ? t('growth:rank_unknown', '—')
    : placement.phase === 'placed'
      ? placement.rung.rank_name
      // **不写「20 级」** —— 那是出厂值,把它当实力显示出来就是在编(稿子这句是对的)。
      : t('growth:rank_unplaced', '未定级');
  const placementLine = placement !== null && placement.phase === 'placement'
    ? `${placement.completed_games} / ${placement.total_games}`
    : t('growth:placement_done', '已完成');

  /**
   * 大字底下那条进度。稿子只画了**未定级**那一态(定级局 n/5 加一条 bar);
   * 定级之后它那儿是空的 —— 而空的那块正是四图上左栏那道缝。
   *
   * 定级之后该填什么,答案就在这一屏自己写的规矩里:**净胜 3 盘升一档**。
   * `net_score` 是 −2…+2(到 ±3 当场升降并清零),`/api/v1/ai-ladder/status` 本来就在给。
   * ⇒ 两态各一条:未定级看「还差几局」,定级后看「离升/降还差几盘」。
   *
   * **不给方向着色。** 净胜分是负的时候那是「离降级近了」,画成红的等于替用户下判断;
   * 这一屏其他地方也没有一处替他判断。
   */
  const metric = placement === null ? null
    : placement.phase === 'placement'
      ? {
        label: t('growth:metric_placement', '定级局'),
        value: `${placement.completed_games} / ${placement.total_games}`,
        ratio: placement.completed_games / placement.total_games,
      }
      : {
        label: t('growth:metric_net', '净胜分'),
        // 正负都写出来 —— `+1` 和 `-1` 是两件事,只写 `1` 就把方向丢了。
        value: `${net > 0 ? '+' : ''}${net} / ${NET_STEP}`,
        ratio: Math.abs(net) / NET_STEP,
      };

  // 数没取到就是没取到。**四格一个都不许写 0** —— 「没下过」和「没读到」在屏上是两句话。
  const dash = t('growth:no_data', '—');
  const num = (v: number | undefined) => (v === undefined ? dash : String(v));
  const wr = summary ? rankedWinrate(summary) : null;

  const stats: { v: string; k: string; good?: boolean }[] = [
    { v: num(summary?.games_in_window), k: t('growth:stat_recent', '近 30 天对局') },
    {
      v: wr === null ? dash : pct(wr),
      // 口径必须写在标签里(共享外壳 §5 的原话:「一个光秃秃的 58% 谁也不知道是哪来的」)。
      // 「升降级」三个字是**承重的**:只有那一种对局的胜负是从这个用户视角记下来的。
      k: t('growth:stat_winrate', '升降级胜率 · 近 30 天'),
      good: wr !== null && wr >= 0.5,
    },
    { v: solved === null ? dash : String(solved), k: t('growth:stat_solved', '累计已解题') },
    { v: num(summary?.ranked_total), k: t('growth:stat_ranked', '升降级局 · 累计') },
  ];

  return (
    <div className="kiosk-layout-l1" data-testid="growth-page">
      {/* 左栏 296:段位。这一栏**不是实体盘镜像栏** —— 这一屏和盘没关系。 */}
      <div className="panel gsec" data-testid="growth-rank">
        <h3>
          {t('growth:rank_title', '盒内段位')}
          <em>Rank</em>
        </h3>
        <div className="grank" data-testid="growth-rank-value">{rankText}</div>

        {metric && (
          <div className="gmetric" data-testid="growth-metric">
            <span>
              <b>{metric.label}</b>
              <i>{metric.value}</i>
            </span>
            {/* 条子只走**绝对值** —— 它说的是「离下一次变动还有多远」,不是方向。 */}
            <div className="gbar"><span style={{ width: pct(Math.min(1, metric.ratio)) }} /></div>
          </div>
        )}

        <h3 className="gsec__h">{t('growth:rules_title', '升降的规矩')}</h3>
        <div className="grules">
          {LADDER_RULES(t).map((rule, i) => (
            <div className="grule" key={rule}>
              <span className="lead">{i + 1}</span>
              <b>{rule}</b>
            </div>
          ))}
        </div>

        {/* 两格变体 —— 共享外壳给这一屏预留的那个(`tokens.css` 里注释原话:
            「两格变体:**成长左栏底部**的『本月 / 最高』」)。这一屏用的是定级局 / 已解题。
            定级局那格**不给灯色**:`tone` 是灯,而「还差几局」不是故障也不是正常。 */}
        <KioskStatusCells
          cells={[
            { label: t('growth:cell_placement', '定级局'), value: placementLine },
            { label: t('growth:cell_solved', '已解题'), value: solved === null ? dash : String(solved), tone: 'good' },
          ]}
        />
      </div>

      {/* 右栏 680:数据条 → 权威口径 → 两块诊断 */}
      <div className="gcol">
        <div className="kiosk-stats" data-testid="growth-stats">
          {stats.map((s) => (
            <div className="kiosk-stat" key={s.k}>
              <div className={s.good ? 'kiosk-stat__v is-good' : 'kiosk-stat__v'}>{s.v}</div>
              <div className="kiosk-stat__k">{s.k}</div>
            </div>
          ))}
        </div>

        {/* 这一条**只在有话要说时出现**。稿子那块道歉式的大空态已经不成立(见文件头),
            剩下真正要交代的只有两件:数没取到、或者这几个数出自本机缓存。 */}
        {summaryFailed && (
          <p className="setnote" data-testid="growth-summary-error">
            {t('growth:summary_failed', '这几个数没取到 —— 不是「一局没下」。稍后再看一次。')}
          </p>
        )}
        {summary?.authority === 'local_cache' && (
          <p className="setnote" data-testid="growth-local-note">
            {t('growth:local_note_a', '这几个数是')}
            <b>{t('growth:local_note_b', '本机记录')}</b>
            {t('growth:local_note_c', '。账在云端,盒子上这一份可能少几局。')}
          </p>
        )}

        <div className="gdiag">
          <div className="panel gsec">
            <h3>
              {t('growth:diag_title', '能力诊断')}
              <span className="wip have">{t('growth:diag_wip', '后端已有 · 界面未接')}</span>
            </h3>
            <div className="empty">
              <h4>{t('growth:diag_empty_h', '样本 0 局')}</h4>
              <p>{t('growth:diag_empty_p', '诊断要拿已经跑过报告的对局算——报告在后端有,界面还没读(见复盘屏)。够 30 局之前结论会抖,到时候也得把样本量写在旁边。')}</p>
            </div>
          </div>

          <div className="panel gsec" data-testid="growth-by-rung">
            <h3>{t('growth:rung_title', '按对手强度')}</h3>
            {summary && summary.by_opponent_rung.length > 0 ? (
              <div className="grungs">
                {summary.by_opponent_rung.map((r) => (
                  <div className="grung" key={r.rung}>
                    <b>{r.rank_name ?? `#${r.rung}`}</b>
                    <span>
                      {t('growth:rung_w', '{n} 胜').replace('{n}', String(r.wins))}
                      {' · '}
                      {t('growth:rung_l', '{n} 负').replace('{n}', String(r.losses))}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty">
                <h4>{t('growth:rung_empty_h', '还没有战绩')}</h4>
                {/* 稿子这句留着 —— 它说的是**滑条调的是对手强度不是你的段位**,这条没变。 */}
                <p>{t('growth:rung_empty_p', '开局设置里那根滑条调的是对手有多强,不是你的段位。打过哪一档就列哪一档——没打过的不列,不摆一排 0 胜 0 负。')}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default GrowthPage;
