import { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';

import { useLiveMatch } from '../../hooks/live/useLiveMatch';
import LiveBoard, { type AiMoveMarker } from '../../components/live/LiveBoard';
import { useTranslation } from '../../hooks/useTranslation';
import { useSound } from '../../hooks/useSound';
import { colsFor, rowsFor } from '../shell/goBoard';
import { KioskFold } from '../shell/KioskFold';
import { KioskPagebar } from '../shell/KioskPagebar';
import { interpolate } from '../utils/interpolate';
import { liveSourceLabel } from '../../utils/liveSources';

/** 三个源在屏上叫什么。和 `components/live/MatchCard.tsx:14` 同一份口径。 */
/**
 * 屏 18 · 直播 · 观战 `/kiosk/live/:matchId` —— L2 布局 A(左盘 516 + 16 + 右栏 460)。
 *
 * **这一屏没有动作区** —— 你在看别人下棋,一个能改这盘棋的按钮都不该有。
 * 底下那一排全是开关(看什么),外加一颗「跟到最新」:往回翻过之后要能回到正在下的那一手。
 * 「试下」是唯一能动手的地方,而它动的是**一份复制出来的盘面**,不是直播的谱。
 *
 * ## 右栏正好摆满 516,一个像素的余量都没有
 *
 * 44(页控条) + 12 + 60(黑) + 12 + 60(白) + 12 + **234.2**(着法块) + 12 + 40(开关排)
 * + 12 + 17.8(那句话) = **516**。折叠头 30 ⇒ 着法视口 202.2,一行 24.4 ⇒ **8.28 行**。
 * 规范要求「固定部分之后剩 ≥3 行才让内层滚」⇒ 折叠块最低 121.2
 * ⇒ **还能再塞进来的东西上限是 101px**。下面三块删掉的东西都撞在这个数上。
 *
 * ## 删掉的三块,每一块都有独立于「稿子没画」的理由
 *
 * ① **`PlaybackBar`**(进度条式翻手)。它给的六件事里五件有落点:任意跳手 → 点着法表任一格
 *    (`.mvrows .mv[role=button]` 本仓早就写好了,屏 16 在用);跳到最新 → 「跟到最新」那颗键;
 *    手数 → 折叠头右端(收起也看得见);单步 → 点相邻那一格;自动播放 → **外壳里没有任何一屏有**
 *    (屏 16/20/21 全是四颗 `.kiosk-movenav`,一颗播放键都没有),删它是向三屏看齐。
 *    🔴 **但它藏着第六件事**:`useLiveMatch` 只在 `prev === null` 时设过一次 `currentMove`
 *    (`useLiveMatch.ts:50`),之后**再没有任何东西推进它** —— 让直播盘跟着长的是
 *    `PlaybackBar.tsx:50-53` 那个 effect。直接删组件,直播盘会**冻结在你进来时那一手而屏上
 *    毫无提示**。那套状态机搬到本页(下面 `followLatest`)。
 * ② **`TrendChart`**(胜率走势)。两条理由各自成立:**放不下**(屏 05 那个 eval 折叠块实测 128,
 *    上限 101,差 27;脱掉折叠头也要 108);而且**现实现在造假** ——
 *    `TrendChart.tsx:35-37` 给没算过的手一律 `winrates.push(50)`,而直播分析是一条稀疏且滞后的
 *    后台队列 ⇒ 屏上大半条是贴着中线的假平线。本仓已把这条禁令写成文字
 *    (`go-screens.css:461`:「不许画一条贴中线的平线冒充均势」)。
 *    **但胜率这个数是真的**(和 `top_moves` 是 `live_analysis` 同一行的两列),所以它没被丢掉:
 *    并进折叠头右端那个值,缺数时后半截**整个不出现**(不写 50%,也不写「—」冒充读数)。
 * ③ **`AiAnalysis`**(推荐列表,约 214px)。屏 20 已经这么判过一次并落地:
 *    「点一条推荐看它的后续」不跟着表一起没 —— 打开「AI 推荐」之后**点盘上那个标记就是选它**,
 *    再点别处收起。比一整块表少占一整块高度,手势还更直接。
 *
 * ## 沉浸模式撤了(同屏 17)
 *
 * `.kiosk-content` 全样式包里只有两条规则(`tokens.css:415` 的 `top:var(--topbar-h)` 无条件、
 * `:423` 只改 L1 的 `bottom`),**没有任何选择器能在 immersive 下改它的 top** ⇒ 顶栏不渲染
 * 只会在屏顶留一条 56 的空黑带。参考图那一帧顶栏在。
 * (2026-08-26:最后一个现场屏 14 也还完,`ImmersiveContext` 已删,这条开关不复存在。)
 * (顺带更正上一版那句注释:Dock **不归 immersive 管** —— `KioskLayout` 是
 * `level === 1 ? <KioskDock/> : undefined`,而这一屏 `dockLevelOf` 返回 2,本来就没有 Dock。)
 * **返回不加二次确认**:这一屏没有动作区、返回在左上角离那排开关最远,而且观众没有可损失的
 * 状态(退出再进 `useLiveMatch` 重拉)。返回去**棋谱**不是 `/kiosk/live` ——
 * 后者是个孤儿路由,全仓唯一入口是棋谱屏那几行(`KifuPage.tsx:397`),
 * 把人扔到一块没来过、没 Dock、自己也没返回键的屏上是上一版的 bug。
 *
 * ## 钟不画
 *
 * 链路上从头到尾没有这个字段:三个源客户端返回的字典里没有时间(`cron/clients/*.py`)、
 * `LiveMatchDB` 没有钟列、`types/live.ts` 也没有。⇒ `.clock` 整格不渲染。
 * **`current_winrate` 也不许上屏**:`pandanet.py:125` 无条件写死 `0.5`、
 * `xingzhen.py:191` 取不到时退回 `0.5` —— 「真的 50%」和「没有这个数」在数据里是同一个值。
 * 屏上那个胜率只认盒内 KataGo 算出来的 `analysis[n].winrate`。
 */
const LiveMatchPage = () => {
  const { matchId } = useParams<{ matchId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { play: playSound } = useSound();

  const [showAiMarkers, setShowAiMarkers] = useState(true);
  const [showMoveNumbers, setShowMoveNumbers] = useState(false);
  const [showTerritory, setShowTerritory] = useState(false);
  const [tryMoveMode, setTryMoveMode] = useState(false);
  const [tryMoves, setTryMoves] = useState<string[]>([]);
  const [activeMove, setActiveMove] = useState<string | null>(null);
  const nowRef = useRef<HTMLSpanElement | null>(null);

  const { match, loading, error, currentMove, setCurrentMove, analysis } = useLiveMatch(matchId);
  const isLive = match?.status === 'live';

  // 🔴 从 `PlaybackBar` 搬过来的那台状态机 —— 没有它直播盘会冻在你进来时那一手(见页面头注)。
  const [followLatest, setFollowLatest] = useState(true);
  const total = match?.move_count ?? 0;
  useEffect(() => {
    if (followLatest && isLive && currentMove < total) setCurrentMove(total);
  }, [followLatest, isLive, currentMove, total, setCurrentMove]);

  // 往回翻就自动松开跟随 —— 否则下一帧又被拽回最新,人会以为屏坏了。
  const goToMove = useCallback((move: number) => {
    setFollowLatest(false);
    setActiveMove(null);
    setCurrentMove(move);
  }, [setCurrentMove]);

  const prevMoveRef = useRef<number | null>(null);
  useEffect(() => {
    if (match && currentMove > 0 && prevMoveRef.current !== null && currentMove !== prevMoveRef.current) {
      playSound('stone');
    }
    prevMoveRef.current = currentMove;
  }, [currentMove, match, playSound]);

  useEffect(() => { nowRef.current?.scrollIntoView({ block: 'nearest' }); }, [currentMove]);

  const aiMarkers = useMemo((): AiMoveMarker[] | null => {
    const a = analysis[currentMove];
    if (!a?.top_moves || a.top_moves.length === 0) return null;
    return a.top_moves.slice(0, 3).map((tm, index) => ({
      move: tm.move, rank: index + 1, visits: tm.visits,
      winrate: tm.winrate ?? 0, score_lead: tm.score_lead ?? 0,
    }));
  }, [analysis, currentMove]);

  const ownership = useMemo(() => analysis[currentMove]?.ownership || null, [analysis, currentMove]);
  const pvMoves = useMemo(() => {
    if (!activeMove) return null;
    return analysis[currentMove]?.top_moves?.find((m) => m.move === activeMove)?.pv ?? null;
  }, [activeMove, analysis, currentMove]);

  const handleToggleTry = useCallback(() => {
    setTryMoveMode((on) => { if (on) setTryMoves([]); return !on; });
    setActiveMove(null);
  }, []);

  /**
   * 点盘:①试下态 → 落一颗试下的子;②盘上那三个 AI 标记之一 → **选中它,看后续**;
   * ③别处 → 收起预览。②这一半是屏 20 判过的那条(推荐列表不做,能力搬到盘上)。
   */
  const handleBoardClick = useCallback((x: number, y: number) => {
    if (tryMoveMode || !match) return;
    const coord = `${colsFor(match.board_size)[x]}${match.board_size - y}`;
    const hit = aiMarkers?.some((m) => m.move === coord);
    setActiveMove(hit ? coord : null);
  }, [tryMoveMode, match, aiMarkers]);

  if (loading || error || !match) {
    return (
      <div className="kiosk-layout-b" data-testid="live-match-page">
        <KioskPagebar
          testId="live-pagebar"
          backLabel={t('live:back_kifu', '棋谱')}
          onBack={() => navigate('/kiosk/kifu')}
          title={t('live:title', '直播')}
        />
        {loading ? (
          <div className="empty" data-testid="live-loading"><h4>{t('live:loading', '正在读这一局')}</h4></div>
        ) : (
          <div className="empty" data-testid="live-error">
            <h4>{t('live:load_failed', '没读到这一局')}</h4>
            {error?.message && <p>{error.message}</p>}
          </div>
        )}
      </div>
    );
  }

  const cols = colsFor(match.board_size);
  const boardRows = rowsFor(match.board_size);
  // **轮次按 `move_count` 的奇偶,不按 `currentMove`** —— 观众翻回第 55 手时,
  // 现实世界里仍然是那一方在想。翻棋谱不改变谁在下棋。
  const liveTurn: 'B' | 'W' | null = isLive ? (total % 2 === 0 ? 'B' : 'W') : null;
  const wr = analysis[currentMove]?.winrate;

  const player = (color: 'B' | 'W') => {
    const name = color === 'B' ? match.player_black : match.player_white;
    const rank = color === 'B' ? match.black_rank : match.white_rank;
    const turn = liveTurn === color;
    return (
      <div className={turn ? 'pcard turn' : 'pcard'} data-testid={`live-player-${color}`} data-turn={turn ? 'true' : 'false'}>
        <span className={color === 'B' ? 'disc b' : 'disc w'} />
        <div>
          <h4>{rank ? `${name} ${rank}` : name}</h4>
          <p>
            {isLive
              ? `${turn ? t('live:thinking', '思考中') : t('live:played', '已落子')} · ${color === 'B' ? t('live:as_black', '执黑') : t('live:as_white', '执白')}`
              : `${color === 'B' ? t('live:as_black', '执黑') : t('live:as_white', '执白')}${match.result ? ` · ${match.result}` : ''}`}
          </p>
        </div>
        {/* 稿子这儿有一个「28:14 / 剩余」—— **不画**:三个源客户端、数据库、类型三层都没有
            这个字段。盒子问不出来的数不上屏(同屏 24 的进度环、屏 06 的段位列)。 */}
      </div>
    );
  };

  // 着法表:一行一个回合。`match.moves` 是 GTP 串,`pass` 原样标出来。
  const rows: { n: number; b: string | null; w: string | null; bAt: number; wAt: number }[] = [];
  match.moves.forEach((mv, i) => {
    if (i % 2 === 0) rows.push({ n: rows.length + 1, b: mv, w: null, bAt: i + 1, wAt: -1 });
    else { const tail = rows[rows.length - 1]; if (tail) { tail.w = mv; tail.wAt = i + 1; } }
  });

  const toggles: [string, string, boolean, () => void, boolean][] = [
    ['try', t('live:try', '试下'), tryMoveMode, handleToggleTry, true],
    // ⚠️ **不许用 `live:territory` / `live:numbers`**:cn PO 里那两条是「领地」和「#」
    // (galaxy 在用),而 `t()` 是 `translations[key] || defaultText` —— **翻译表赢**,
    // 屏上会出现「领地」和一个光秃秃的「#」。稿子这一屏写的是「形势」和「手数」。
    // 四图第一版就是这么露出来的;换成这一屏自己的 key。
    ['territory', t('live:toggle_territory', '形势'), showTerritory, () => setShowTerritory((v) => !v), Boolean(ownership)],
    ['numbers', t('live:toggle_numbers', '手数'), showMoveNumbers, () => setShowMoveNumbers((v) => !v), true],
    ['ai', t('live:ai', 'AI 推荐'), showAiMarkers, () => setShowAiMarkers((v) => !v), true],
    // 稿子那一帧把它画成暗的,而视图正停在最新手 —— 自相矛盾。做成按下态:
    // 亮 = 正在跟着长;点了着法表里某一手就自动灭(`goToMove`)。
    ['follow', t('live:follow', '跟到最新'), followLatest, () => { setFollowLatest(true); setCurrentMove(total); }, isLive],
  ];

  return (
    <div className="kiosk-layout-a live-layout" data-testid="live-match-page">
      <div className="kiosk-board" data-testid="live-board">
        <div className="kiosk-board__ruler kiosk-board__ruler--top">
          {cols.map((c) => <span key={`t${c}`}>{c}</span>)}
        </div>
        <div className="kiosk-board__ruler kiosk-board__ruler--left">
          {boardRows.map((r) => <span key={`l${r}`}>{r}</span>)}
        </div>
        <div className="kiosk-board__play">
          {/* 刻度带由外壳画,盘自己那一圈关掉 —— 两边都画就是两套坐标。 */}
          <LiveBoard
            moves={match.moves}
            currentMove={currentMove}
            boardSize={match.board_size}
            showCoordinates={false}
            pvMoves={pvMoves}
            aiMarkers={aiMarkers}
            showAiMarkers={showAiMarkers}
            showMoveNumbers={showMoveNumbers}
            showTerritory={showTerritory}
            ownership={ownership}
            tryMoves={tryMoveMode ? tryMoves : undefined}
            onTryMove={tryMoveMode ? (move: string) => setTryMoves((prev) => [...prev, move]) : undefined}
            onIntersectionClick={handleBoardClick}
          />
        </div>
        <div className="kiosk-board__ruler kiosk-board__ruler--right">
          {boardRows.map((r) => <span key={`r${r}`}>{r}</span>)}
        </div>
        <div className="kiosk-board__ruler kiosk-board__ruler--bottom">
          {cols.map((c) => <span key={`b${c}`}>{c}</span>)}
        </div>
      </div>

      <div className="kiosk-rail">
        <KioskPagebar
          testId="live-pagebar"
          backLabel={t('live:back_kifu', '棋谱')}
          onBack={() => navigate('/kiosk/kifu')}
          // 标题是**赛事**不是两个人名 —— 选手已经在下面两张卡里了,一个值不摆两处。
          title={[match.tournament, match.round_name].filter(Boolean).join(' · ')}
          sub={interpolate(
            t('live:pagebar_sub', '来源：{src} · 第 {n} 手'),
            { src: liveSourceLabel(match.source), n: currentMove },
          )}
          status={isLive
            ? <span className="kiosk-tag kiosk-tag--live" data-testid="live-status">{t('kifu:live_now', '直播中')}</span>
            : <span className="kiosk-tag" data-testid="live-status">{t('live:ended', '已结束')}</span>}
        />

        {player('B')}
        {player('W')}

        <KioskFold
          fold="moves"
          grow
          testId="live-moves-fold"
          title={t('live:moves_title', '棋谱 · 跟着直播长')}
          // 胜率并在这儿(收起也看得见)。**算不出来时后半截整个不出现** ——
          // 不写 50%(那是源头硬编码的默认值),也不写「—」冒充一个读数。
          value={
            <>
              {interpolate(t('live:move_n', '第 {n} 手'), { n: currentMove })}
              {wr != null && ` · ${interpolate(t('live:black_wr', '黑 {v}%'), { v: (wr * 100).toFixed(1) })}`}
            </>
          }
          bodyClassName="mvrows"
        >
          {rows.length === 0 ? (
            <span className="n">{t('live:no_moves', '这一局还没有着法')}</span>
          ) : rows.map((r) => (
            <LiveMoveRow key={r.n} row={r} at={currentMove} nowRef={nowRef} onPick={goToMove} passLabel={t('kifu:pass', '虚手')} />
          ))}
        </KioskFold>

        {/* 这一屏没有动作区 —— 底下这排全是**开关**(看什么),外加一颗「跟到最新」。 */}
        <div className="gtoggles" role="group" aria-label={t('live:show', '显示')} data-testid="live-toggles">
          {toggles.map(([key, label, on, onClick, enabled]) => (
            <button
              key={key}
              type="button"
              aria-pressed={on}
              disabled={!enabled}
              title={!enabled && key === 'territory' ? t('live:no_ownership', '这一手还没算出形势') : undefined}
              onClick={onClick}
            >{label}</button>
          ))}
        </div>

        <p className="setnote">
          {t('live:ai_note_a', '「AI 推荐」是')}<b>{t('live:ai_note_b', '盒内 KataGo 现算的')}</b>
          {t('live:ai_note_c', '，和棋手看到的没有关系。')}
        </p>
      </div>
    </div>
  );
};

/** 着法表一行。整表可点 —— 这一屏删掉进度条之后,它是唯一的翻手界面。 */
function LiveMoveRow({ row, at, nowRef, onPick, passLabel }: {
  row: { n: number; b: string | null; w: string | null; bAt: number; wAt: number };
  at: number;
  nowRef: React.MutableRefObject<HTMLSpanElement | null>;
  onPick: (n: number) => void;
  passLabel: string;
}) {
  const cell = (label: string | null, moveNo: number) => {
    if (moveNo < 0 || label == null) return <span className="mv" />;
    const isNow = moveNo === at;
    return (
      <span
        ref={isNow ? nowRef : undefined}
        className={isNow ? 'mv now' : 'mv'}
        role="button"
        tabIndex={0}
        onClick={() => onPick(moveNo)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onPick(moveNo); } }}
      >
        {label.toLowerCase() === 'pass' ? passLabel : label}
      </span>
    );
  };
  return (
    <>
      <span className="n">{row.n}</span>
      {cell(row.b, row.bAt)}
      {cell(row.w, row.wAt)}
    </>
  );
}

export default LiveMatchPage;
