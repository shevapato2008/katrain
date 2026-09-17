import { useCallback, useEffect, useRef, useState } from 'react';
import { Icon } from '../../shell/icons';
import { KioskFold } from '../../shell/KioskFold';
import { KioskActions, type KioskAction } from '../../shell/KioskActions';
import { GoEvalGraph, goEvalSummary } from './GoEvalGraph';
import { localizedRank } from '../../../utils/rankUtils';
import { isRankedGameType } from '../../../features/aiLadder/gameType';
import { autoCountEligible } from '../../hooks/useAutoCount';
import type { EngineItemCounts, GameState, PlayerInfo } from '../../../api';
import { useGoClock } from './goClock';
import { isFreeVsAi } from './gameKinds';
import { useTranslation } from '../../../hooks/useTranslation';
import { useSound } from '../../../hooks/useSound';
import { computeClock, type ClockView } from '../../../utils/gameClock';

interface Props {
  gameState: GameState;
  onAction: (action: string) => void;
  onNavigate: (nodeId: number) => void;
  analysisToggles: Record<string, boolean>;
  onToggleAnalysis: (key: string) => void;
  /**
   * A18:轮到的一方时间耗尽。GamePage 决定发不发 `/api/timeout`(升降级 AI 回合、引擎停摆时不发)。
   * 只在开局设置配过时限的局里会被调用(`timer.configured`)。
   */
  onTimeout?: (color: 'B' | 'W') => void;
  onHint?: () => void;
  hintEnabled?: boolean;
  isGameOver?: boolean;
  /**
   * 升降级对弈。**不是只把请求掐掉,是整块不渲染** —— 规范 §8:
   * 「禁的时候整块不渲染,不要渲成灰的或显示『—』,那是在提示『这里本来有个东西,你没资格看』」。
   * 上一版前端只是 `isRankedGameType` 早退不去请求,面板照样渲染,画出来是一条全 `—` 的空图。
   */
  isRanked?: boolean;
  /**
   * 这一局的分析**服务端根本不交付** —— 无人认领的会话(未登录游客建的那种)。
   * 判据取服务端那一句(`get_state` 的 `analysis_delivered`),不是本地有没有 token:
   * 决定交不交付的是「这个会话有没有主人」,而一个登录用户照样可能打开一个无主会话。
   *
   * 与 `isRanked` 分开:后者连悔棋一起禁(反作弊),而游客的悔棋是通的,
   * 只有三个分析键点了没用。合在一起就会为了关掉分析顺手把能用的也关掉。
   */
  analysisRequiresLogin?: boolean;
  /** Golaxy 人机对弈: replace the local analysis toggles with star阵 tunnel controls. */
  engineMode?: boolean;
  activeEngineKind?: 'area' | 'options' | 'judge' | 'variation' | null;
  onEngineAnalysis?: (kind: 'area' | 'options' | 'judge' | 'variation') => void;
  /** Remaining-uses badges for the three engine buttons; null/undefined → "—" (unknown). */
  engineItemCounts?: EngineItemCounts | null;
  /**
   * 硬件出故障时那一句(摄像头 / 标定 / LED)。**没故障时是 `null`,不是空字符串** ——
   * 它和「数子还差几手」共用开关排右端那一格,故障优先。
   * 上一版这些是顶条上三颗常亮的灯;§5 说状态显示归 L1 镜像栏,L3 上没它们的位置,
   * 但撤了灯就等于撤了 LED 掉线在这一屏唯一的信号,所以留下**只在出事时说话**的这一句。
   */
  hardwareFault?: string | null;
  /** 实体盘等待用户摆上 AI 落子时的坐标提示；不使用故障色。 */
  physicalStatus?: string | null;
  /**
   * 本地对局、设了用时,**轮到的一方**的钟走到 0(主时间 0 且读秒次数用满)的那一刻调一次。
   * 边沿触发:钟停在 0 不会连调;服务端回 409 带来新状态、钟重新有了余量,再走到 0 才会再调。
   * 判负与否由服务端核实(`/api/timeout`),这里只负责「屏上算出来到点了」。
   */
  onTimeExpired?: () => void;
  /** 自动数子正在进行中(F1)。进行中不能重复按「数子」——按了会撞后端「这一局已经结束了」。 */
  counting?: boolean;
  /** 右栏状态条(F4:设计稿位置是「开关行之上」,不是压在玩家卡上方)。GamePage 传 `null` 时不占地方。 */
  statusSlot?: React.ReactNode;
}

/**
 * 把主线着法叠成「一行 = 一个黑白回合」。
 *
 * ⚠️ **不按手数奇偶判黑白** —— 让子局第一手就是白,连着两手同色(让子、连续虚手之后的实战)
 * 也真会出现。判据只认后端给的 `player`:同一列已经占了就另起一行,所以让子那几手会各占一行的
 * 黑格,白格空着 —— 那正是围棋棋谱的写法。
 *
 * `history[0]` 是**根节点**,没有着法(`move`/`player` 都是 null)⇒ 第 n 手落在 `history[n]`,
 * 而 `current_node_index` 用的也是这套下标,两者能直接比。
 */
interface MoveRow { n: number; b: string | null; w: string | null; bAt: number; wAt: number }

function toMoveRows(history: GameState['history'] | undefined): MoveRow[] {
  const rows: MoveRow[] = [];
  (history ?? []).forEach((h, i) => {
    if (!h.move || !h.player) return;   // 根节点
    const black = h.player === 'B';
    let tail = rows[rows.length - 1];
    if (!tail || (black ? tail.b : tail.w) !== null) {
      tail = { n: rows.length + 1, b: null, w: null, bAt: -1, wAt: -1 };
      rows.push(tail);
    }
    if (black) { tail.b = h.move; tail.bAt = i; } else { tail.w = h.move; tail.wAt = i; }
  });
  return rows;
}

/**
 * 棋谱一格。**不可点** —— 屏 16/18 那两处 `.mvrows` 是回放,点哪手跳哪手是它们的主要交互;
 * 这一屏是**正在下的一局**,跳到中间那一手会让屏幕和对面的星阵各说各的
 * (隧道那边只认当前局面)。稿子这一屏也没画任何可按的样子。
 */
function MoveCell({ label, at, now, nowRef, passLabel }: {
  label: string | null; at: number; now: number;
  nowRef: React.MutableRefObject<HTMLSpanElement | null>; passLabel: string;
}) {
  if (label == null || at < 0) return <span className="mv" />;
  const isNow = at === now;
  return (
    <span ref={isNow ? nowRef : undefined} className={isNow ? 'mv now' : 'mv'}>
      {label.toLowerCase() === 'pass' ? passLabel : label}
    </span>
  );
}

/**
 * 一整行 = 三个**平铺的** span。`.mvrows` 是 `grid-template-columns: 30px 1fr 1fr`,
 * 包一层 `<div>` 就会变成「一行只占一格」—— 列全塌。用 Fragment。
 */
function MoveCellRow({ row, now, nowRef, passLabel }: {
  row: MoveRow; now: number;
  nowRef: React.MutableRefObject<HTMLSpanElement | null>; passLabel: string;
}) {
  return (
    <>
      <span className="n">{row.n}</span>
      <MoveCell label={row.b} at={row.bAt} now={now} nowRef={nowRef} passLabel={passLabel} />
      <MoveCell label={row.w} at={row.wAt} now={now} nowRef={nowRef} passLabel={passLabel} />
    </>
  );
}

const formatTime = (seconds: number) => {
  const total = Math.ceil(Math.max(0, seconds));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
};

/** 本地对局钟的读数:分钟也补两位(`09:42`、`00:24`),照 spec §3.3 那张表。 */
const formatClock = (seconds: number) => {
  const total = Math.ceil(Math.max(0, seconds));
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
};

/**
 * 「上一份服务端状态到现在,客户端过了几秒」。
 *
 * **按快照对象的身份归零,不按某个数归零。** 服务端每推一次状态(WS、HTTP 返回体、409 附带的状态)
 * 都是一个新的 `timer` 对象,里面的已用时间已经包含了到那一刻为止的流逝 —— 不归零会把同一段时间算两遍。
 * galaxy `PlayerCard` 只在 `main_time_used` 变化时归零,读秒阶段那个数不变,于是会重复计时;这里不照抄。
 * 归零不在 effect 里 `setState(0)`(`react-hooks/set-state-in-effect`):记下这次计时属于哪个快照,
 * 快照换了就当 0 返回,等下一拍再写新值。
 */
function useClientElapsed(snapshot: object | undefined, running: boolean): number {
  const [tick, setTick] = useState<{ snapshot: object | undefined; elapsed: number }>({ snapshot: undefined, elapsed: 0 });
  useEffect(() => {
    if (!running) return;
    const startedAt = Date.now();
    const id = window.setInterval(() => {
      setTick({ snapshot, elapsed: (Date.now() - startedAt) / 1000 });
    }, 200);
    return () => window.clearInterval(id);
  }, [snapshot, running]);
  return running && tick.snapshot === snapshot ? tick.elapsed : 0;
}

/**
 * 玩家卡(稿子 `.pcard`)。提子挂在副行上 —— galaxy 就是把它印在玩家卡里的,
 * 不是另起一块面板;规则和贴目同理,它们是**这一局开局时定死的**,写在页控条副标里
 * 一次就够。两处都占 0 高度,这正是右栏 516 能装下胜率块的原因。
 */
function PlayerRow({ color, info, captures, turn, state, clock, lang, t }: {
  color: 'B' | 'W';
  info: PlayerInfo;
  captures: number;
  turn: boolean;
  state: string;
  clock: { value: string; label: string; phase?: 'byoyomi' | 'expired' } | null;
  lang: string;
  t: (key: string, fallback?: string) => string;
}) {
  // 段位:阶梯 AI 的段位是 `rank_display` 里的字符串,其他人走数值 `calculated_rank`。
  const rawRank = info.rank_display ?? localizedRank(info.calculated_rank, lang);
  const rank = !rawRank || rawRank === 'No Rank' ? null : rawRank;
  // ⚠️ 这里是**人名缺席时的占位**,站的是「谁在下」那个位置,不是「哪一方的子」。
  // 屏 04 对同一个位置承诺的是「黑方」(`PvpLocalSetupPage.tsx:227`,用的是自铸的
  // `setup:black_side`),而那一屏的注释白纸黑字写着「**和对局屏上那两张卡的回落值是同一句话**」。
  // 而 PO 里的 `Black` 是「黑棋」—— 说的是**子**(`PlatformTimer.tsx:105` 那两个计时侧标
  // 用它是对的)。同一个 msgid 背两个意思,正是「一个 key 兼管两件事」那一族。
  // ⇒ 铸 `game:black_side` / `game:white_side`,和屏 04 用同一个词。
  // (2026-08-26 一度把 fallback 改成「黑棋」去迁就 PO —— 那是把这处不一致钉死了:
  //  设备上设置页承诺「黑方」、对局页给「黑棋」,而注释说它们是同一句话。)
  const name = info.name || (color === 'B' ? t('game:black_side', '黑方') : t('game:white_side', '白方'));
  return (
    <div className={turn ? 'pcard turn' : 'pcard'} data-testid={`player-card-${color}`} data-clock={clock?.phase}>
      <span className={color === 'B' ? 'disc b' : 'disc w'} />
      <div>
        <h4>{rank ? `${name} · ${rank}` : name}</h4>
        <p>
          {state} · {color === 'B' ? t('game:plays_black', '执黑') : t('game:plays_white', '执白')}
          {' · '}{t('game:captures', '提子')} {captures}
        </p>
      </div>
      {clock && (
        <div className="clock">
          <b>{clock.value}</b>
          <span>{clock.label}</span>
        </div>
      )}
    </div>
  );
}

/**
 * 一方的玩家卡 + 时钟(A18)。时钟跟着本地时间走,所以 hook 挂在每张卡自己身上 ——
 * 放在父组件里算,每 250ms 一次的重渲会把胜率图、棋谱一起带着重画。
 */
function SeatRow({ gameState, color, turn, state, untimed, lang, t, onTimeout }: {
  gameState: GameState;
  color: 'B' | 'W';
  turn: boolean;
  state: string;
  /** 这一局不计时时那一格写什么(原来的「第 N 手 · 不限时」/「本局已下」)。 */
  untimed: { value: string; label: string } | null;
  lang: string;
  t: (key: string, fallback?: string) => string;
  onTimeout?: (color: 'B' | 'W') => void;
}) {
  const onExpired = useCallback(() => onTimeout?.(color), [onTimeout, color]);
  const { play: playSound } = useSound();
  const lastCountdownSecondRef = useRef<number | null>(null);
  const reading = useGoClock(gameState, color, onExpired);
  const countdownSecond = reading?.byoLeft == null ? null : Math.ceil(reading.byoLeft);
  const clockActive = turn && !gameState.end_result && !gameState.terminal_result
    && (gameState.children?.length ?? 0) === 0;
  useEffect(() => {
    const shouldPlay = clockActive
      && gameState.timer?.paused === false
      && gameState.timer.settings.sound === true
      && !reading?.expired
      && countdownSecond !== null
      && countdownSecond >= 1
      && countdownSecond <= 5;
    if (!shouldPlay) {
      lastCountdownSecondRef.current = null;
      return;
    }
    if (lastCountdownSecondRef.current === countdownSecond) return;
    playSound('countdownbeep');
    lastCountdownSecondRef.current = countdownSecond;
  }, [clockActive, countdownSecond, gameState.timer?.paused, gameState.timer?.settings.sound, playSound, reading?.expired]);
  const clock = reading === null ? untimed
    : reading.expired ? { value: '0:00', label: t('game:time_up', '超时') }
    : reading.byoLeft === null ? { value: formatTime(reading.mainLeft), label: t('game:time_left', '剩余') }
    : {
      value: formatTime(reading.byoLeft),
      label: t('game:byo_left', '读秒 · 剩 {n} 次').replace('{n}', String(reading.periodsLeft)),
    };
  return (
    <PlayerRow
      color={color} info={gameState.players_info[color]} captures={gameState.prisoner_count[color]}
      turn={turn} state={state} clock={clock} lang={lang} t={t}
    />
  );
}

/**
 * 对局屏右栏(稿子 `data-screen="game"` / `data-screen="platform-game"`)。
 *
 * **返回的是 Fragment,不是一个包住一切的 `<div>`** —— 这些块必须是 `.kiosk-rail` 的
 * 直接子元素,否则共享 `tokens.css` 的 `.kiosk-rail .kiosk-actions { margin-top: auto }`
 * 选不中,「动作区永远贴右栏底」当场失效。页控条由 `GamePage` 渲染(退出确认和重置识别
 * 都在它手里),排在本组件前面。
 *
 * 右栏 516 的账(自由对弈):44(页控条)+ 60 + 60(玩家卡)+ 126(胜率块 30+96)
 * + 40(两个显示开关)+ 111(七个键 52×2 + 7)+ 5×12(缝)= 501,余 15 落在动作区上面。
 *
 * 本地对局:44 + 60 + 60 + 40 + 52(三个键一行)+ 4×12 = 304,余 212 **全落在动作区上面**
 * —— 这个数只在真浏览器里量,见 `tests/kiosk-screen-05-game.spec.ts` 的本地对局那几条。
 */
const GameControlPanel = ({
  gameState, onAction, onNavigate, analysisToggles, onToggleAnalysis, onHint, hintEnabled = false,
  isGameOver = false, isRanked = false, analysisRequiresLogin = false, engineMode = false,
  activeEngineKind = null, onEngineAnalysis, engineItemCounts = null, hardwareFault = null, physicalStatus = null, onTimeExpired,
  onTimeout, counting = false, statusSlot = null,
}: Props) => {
  const { t, lang } = useTranslation();

  // 数子闸照抄 galaxy(`RightSidebarPanel`):后端 `/api/count/request` 在 count_min_moves
  // 之前一律拒,所以键灰着 —— 而**灰而不说原因**是这份稿子在别处专门骂过的事,
  // 理由写在开关排右端那句 `.ghint` 上。
  const countMin = gameState.count_min_moves ?? 100;
  const moves = gameState.history?.length ?? 0;
  // N 取服务端下发的 `count_min_moves`(S2a 起按路数缩放:19 路 100 / 13 路 47 / 9 路 22);
  // `?? 100` 只兜「老服务端不带这个字段」,不是前端自己的门槛。
  // 双 pass 之后后端在等数子(`awaiting_count`),`/api/count/request` 跳过手数门槛 ⇒ 键跟着亮。
  // 只认自动数子那两种局(大厅 / 星阵局后端也可能报这个位,但数子在那儿是另一条协议)。
  const awaitingCount = !!gameState.awaiting_count && autoCountEligible(gameState, engineMode);
  const canCount = !isGameOver && !counting && (awaitingCount || moves >= countMin);

  // 本地对局(两个人面对面)。v2 D1:**不接引擎辅助** ——「领地」「AI 支招」整颗撤掉(不是灰着:
  // 开局就定死没有,永久不可用 → 撤掉)。后台分析照跑、只给数子用,见 `GamePage` 的 `wantAnalysis`。
  const localGame = gameState.game_type === 'pvp_local';

  // 这一局是不是**人机自由对弈**。规范 §8 那张「按对弈方式判」的表只有一句话:
  // 自由对弈能用的,另外四种(升降级 / 本地两人 / 在线大厅 / 星阵人机)一概不能。
  //
  // 升降级这一档**两个操作数都读**:`isRanked` 是调用方给的,`game_type` 是这一局自己带的。
  // 只认前者的话,少传一次 prop 就等于把闸打开 —— 而这里挂着的是「悔棋能不能按」,
  // 升降级局里那是反作弊的一环(后端 `handleAction` 也拒,但界面不该先摆出来邀请他点)。
  const rankedGame = isRanked || isRankedGameType(gameState.game_type);
  const freeVsAi = isFreeVsAi({ gameType: gameState.game_type, engineMode, isRanked: rankedGame });

  // 胜率块:自由对弈可开;升降级 / 本地两人 / 在线大厅 / 星阵人机一律**整块不渲染**。
  const evalAllowed = freeVsAi;
  const showScore = evalAllowed && !analysisRequiresLogin && !!analysisToggles.score;

  /** 本地局只有人机自由对弈允许悔棋；星阵机器人页在 engineMode 分支中单独保留灰色平台按钮。 */
  const undoAllowed = freeVsAi;

  /**
   * 棋谱与胜率块共用同一段高度;胜率块不在的局(星阵 / 升降级 / 本地对局 / 关掉图表)都显示棋谱。
   * 数据来自 `history` 的 `move`/`player`(2026-08-25 后端在**已有的那个主线循环**里加的两个键);
   * ⚠️ 不许改用 `stones`:它带 `move_number` 但**不含被提掉的子**,拼出来的谱会缺手。
   */
  const showMoves = engineMode || !showScore;
  const moveRows = showMoves ? toMoveRows(gameState.history) : [];
  const nowIndex = gameState.current_node_index ?? 0;
  const nowRef = useRef<HTMLSpanElement | null>(null);
  // 跟到当前那一手。live 那一屏(`LiveMatchPage.tsx:110`)同一句 —— 对局中「当前」永远是最后一行,
  // 不跟的话下到第十手以后屏上就一直停在开头几手。`block: 'nearest'` 只在滚出视野时才动。
  useEffect(() => { nowRef.current?.scrollIntoView({ block: 'nearest' }); }, [nowIndex]);

  const toMove = gameState.player_to_move === 'B' ? 'B' : 'W';
  const isAiSeat = (c: 'B' | 'W') => {
    const pt = gameState.players_info[c].player_type;
    return pt === 'player:ai' || pt === 'ai' || c === gameState.platform_engine_color;
  };
  const stateWord = (c: 'B' | 'W') =>
    isGameOver ? t('game:ended', '本局结束')
      : c !== toMove ? t('game:played', '已落子')
      : isAiSeat(c) ? t('game:thinking', '思考中')
      : t('game:your_turn', '轮到你');

  // ── 本地对局的钟(spec §3.3)────────────────────────────────────────────
  // 只有 `pvp_local` 走共享的 `computeClock`;自由对弈 / 升降级 / 星阵的钟栏一字不改(见 `clockFor` 后半段)。
  // 不限时那一档服务端写的是 main_time=0 / byo_length=0,`computeClock` 判 `showTimer: false`,同样落到后半段。
  const timer = gameState.timer;
  const localClockOn = gameState.game_type === 'pvp_local' && !!timer;
  const ticking = localClockOn && !isGameOver && !awaitingCount && !timer?.paused;
  const clientElapsed = useClientElapsed(timer, ticking);
  const localClock = (c: 'B' | 'W'): ClockView => computeClock({
    settings: localClockOn ? timer?.settings : null,
    mainTimeUsed: gameState.players_info[c].main_time_used,
    periodsUsed: gameState.players_info[c].periods_used,
    // 服务端只下发**轮到的一方**的本节点已用;另一方下一手从一段完整的读秒开始。
    nodeTimeUsed: c === toMove ? (timer?.current_node_time_used ?? 0) : 0,
    active: ticking && c === toMove,
    clientElapsed,
  });

  // 到点那一刻调一次。回调走 ref:调用方每次渲染都给一个新函数,放进依赖会让「停在 0」连调。
  const timeExpired = !isGameOver && !awaitingCount && localClock(toMove).phase === 'expired';
  const onTimeExpiredRef = useRef(onTimeExpired);
  const onTimeoutRef = useRef(onTimeout);
  useEffect(() => { onTimeExpiredRef.current = onTimeExpired; });
  useEffect(() => { onTimeoutRef.current = onTimeout; });
  // F3:到点后**一直重试**直到状态变化(判负成功 → isGameOver 变真;409 带回新 state → 钟重算,
  // timeExpired 翻假),不是只发一次。timeoutRequestRef(GamePage 那边)已经防了并发调用,
  // 这里只负责「网络抖一次不会让钟永远停在 00:00、局却判不了负」。
  useEffect(() => {
    if (!timeExpired) return;
    const notify = () => onTimeExpiredRef.current?.() ?? onTimeoutRef.current?.(toMove);
    notify();
    const id = window.setInterval(notify, 5000);
    return () => window.clearInterval(id);
  }, [timeExpired, toMove]);

  // 时钟栏(本地对局直接使用；其它对局不计时时作为 SeatRow 的回落)。`main_time_used`
  // 只有在真配了时限时才累加，那时才有「本局已下」可写。没有时限时,这一栏唯一为真的量是
  // **当前是第几手**,而那是**局面的量、不是某一方的量** ⇒ 只挂在轮到的那张卡上,
  // 另一张卡的时钟栏不渲染。两张都写「不限时」是把同一句话说两遍;
  // 写 `0:00 本局已下` 更糟 —— 那不是「用了 0 秒」,是「压根没在计」。
  const clockFor = (c: 'B' | 'W'): { value: string; label: string; phase?: 'byoyomi' | 'expired' } | null => {
    const lc = localClock(c);
    if (lc.showTimer) {
      if (lc.phase === 'expired') return { value: formatClock(0), label: t('game:clock_timeout', '超时'), phase: 'expired' };
      if (lc.phase === 'byoyomi') {
        return {
          value: formatClock(lc.byoyomiLeft),
          label: t('game:clock_byo_left', '读秒 · 剩 {n} 次').replace('{n}', String(lc.periodsLeft)),
          phase: 'byoyomi',
        };
      }
      return {
        value: formatClock(lc.mainTimeLeft),
        label: t('game:clock_byo_spec', '读秒 {len}秒×{n}')
          .replace('{len}', String(timer?.settings.byo_length ?? 0))
          .replace('{n}', String(timer?.settings.byo_periods ?? 0)),
      };
    }
    const used = gameState.players_info[c].main_time_used;
    if (used > 0) return { value: formatTime(used), label: t('game:spent_this_game', '本局已下') };
    if (c !== toMove || isGameOver) return null;
    return {
      value: t('game:move_n', '第 {n} 手').replace('{n}', String((gameState.current_node_index ?? 0) + 1)),
      label: t('game:untimed', '不限时'),
    };
  };

  /* 游客(无主会话)那一句。**灰而不说原因是这份稿子在别处专门骂过的事**,而
     galaxy 那边把它挂在 tooltip 上 —— 那条在这里不成立:**这是 7 寸触屏,
     悬浮提示够不着**。所以走 kiosk 自己那套:`reason` 上 `title`/`aria-description`,
     屏上那句落在开关排右端的 `.ghint`(见下)。
     **不整组隐藏**:隐藏之后登录用户和游客看到的键不一样多,而用户无从知道少了什么;
     稿子骂的是「一排点不动的键」——那说的是终局时**四个键同时死掉且不可恢复**,
     这里三个键灰着但**去登录就能用**,原因说得出来。 */
  const guestAnalysisReason = t('play:analysis_requires_login', '登录后可用');

  // N14:升降级局整块不渲染「领地」「AI支招」;按需分析已由页面与服务端禁止。
  const analysisActions: KioskAction[] = engineMode || localGame || rankedGame ? [] : [
    {
      key: 'ownership', icon: 'grid-nine', label: t('Territory', '领地'),
      pressed: !analysisRequiresLogin && !!analysisToggles.ownership,
      onClick: () => onToggleAnalysis('ownership'),
      disabled: analysisRequiresLogin,
      reason: analysisRequiresLogin ? guestAnalysisReason : undefined,
    },
    {
      // AI 支招 = 一次性动作(顶部 N 个候选点,实体盘上白闪),**不是开关** ——
      // 所以它没有 `pressed`。原来那个独立的顶栏支招键在 kiosk-ui-redesign 里已经并进来了。
      key: 'hint', icon: 'lightbulb', label: t('Hints', 'AI支招'),
      onClick: () => onHint?.(), disabled: !hintEnabled || analysisRequiresLogin,
      reason: analysisRequiresLogin ? guestAnalysisReason : undefined,
    },
    ...(evalAllowed ? [{
      key: 'score', icon: 'trend-up' as const, label: t('Chart', '图表'),
      pressed: !analysisRequiresLogin && showScore,
      onClick: () => onToggleAnalysis('score'),
      disabled: analysisRequiresLogin,
      reason: analysisRequiresLogin ? guestAnalysisReason : undefined,
    }] : []),
  ];

  // 终局之后这四个键**全都是死的**(数子要 `!isGameOver`,悔棋/停一手/认输都 `disabled={isGameOver}`)——
  // 稿子对「一排点不动的键」的原话:「要画就得先加那一屏,不是在这一屏塞一排点不动的键」。
  // ⇒ 终局时它们整组不渲染,位置让给真正能用的着法导航。
  const playActions: KioskAction[] = isGameOver ? [] : [
    {
      key: 'count', icon: 'squares-four', label: t('Score', '数子'),
      onClick: () => onAction('count'), disabled: !canCount,
      reason: t('game:count_min', '数子要下满 {n} 手').replace('{n}', String(countMin)),
    },
    ...(undoAllowed ? [{
      key: 'undo', icon: 'arrow-counter-clockwise' as const, label: t('Undo', '悔棋'),
      onClick: () => onAction('undo'),
    }] : []),
    { key: 'pass', icon: 'hand-pointing', label: t('game:pass', '停一手'), onClick: () => onAction('pass') },
    { key: 'resign', icon: 'flag', label: t('Resign', '认输'), onClick: () => onAction('resign'), danger: true },
  ];

  const actions = engineMode
    ? (isGameOver ? [] : [
      {
        key: 'undo', icon: 'arrow-counter-clockwise' as const, label: t('Undo', '悔棋'),
        onClick: () => undefined, disabled: true,
        reason: t('game:golaxy_engine_no_undo', '星阵机器人对局暂不支持悔棋'),
      },
      { key: 'pass', icon: 'hand-pointing' as const, label: t('game:pass', '停一手'), onClick: () => onAction('pass') },
      {
        key: 'judge', icon: 'squares-four' as const, label: t('Score', '数子'),
        onClick: () => onEngineAnalysis?.('judge'), pressed: activeEngineKind === 'judge',
      },
      { key: 'resign', icon: 'flag' as const, label: t('Resign', '认输'), onClick: () => onAction('resign'), danger: true },
    ])
    : [...analysisActions, ...playActions];

  // 角标三态:数字 = 还剩几次;`0` 红底**不灰掉**(去星阵 App 充了值马上又能用);
  // `—` = 这一次没取到数。⚠️ `?? null` 不是多余的:上一版写的是
  // `engineItemCounts ? engineItemCounts.area : null` —— 接口回了个 `{}`(真发生过,
  // 探针里就是)时对象**是真值**,`.area` 却是 `undefined`,`undefined === null` 为假,
  // 于是 React 把 `undefined` 渲成**空**:角标那一格什么都不写。
  // 「没取到数」和「这一格不存在」在屏上长得一样,而前者本来是要说话的。
  const items: { kind: 'area' | 'options' | 'variation'; icon: 'grid-nine' | 'lightbulb' | 'trend-up'; label: string; count: number | null }[] = [
    { kind: 'area', icon: 'grid-nine', label: t('Territory', '领地'), count: engineItemCounts?.area ?? null },
    { kind: 'options', icon: 'lightbulb', label: t('Suggest', '支招'), count: engineItemCounts?.options ?? null },
    { kind: 'variation', icon: 'trend-up', label: t('Variation Line', '变化图'), count: engineItemCounts?.variation ?? null },
  ];

  return (
    <>
      {localGame ? (
        <>
          <PlayerRow
            color="W" info={gameState.players_info.W} captures={gameState.prisoner_count.W}
            turn={toMove === 'W' && !isGameOver} state={stateWord('W')} clock={clockFor('W')} lang={lang} t={t}
          />
          <PlayerRow
            color="B" info={gameState.players_info.B} captures={gameState.prisoner_count.B}
            turn={toMove === 'B' && !isGameOver} state={stateWord('B')} clock={clockFor('B')} lang={lang} t={t}
          />
        </>
      ) : (
        <>
          <SeatRow
            gameState={gameState} color="W" turn={toMove === 'W' && !isGameOver} state={stateWord('W')}
            untimed={clockFor('W')} lang={lang} t={t} onTimeout={onTimeout}
          />
          <SeatRow
            gameState={gameState} color="B" turn={toMove === 'B' && !isGameOver} state={stateWord('B')}
            untimed={clockFor('B')} lang={lang} t={t} onTimeout={onTimeout}
          />
        </>
      )}

      {/* 棋谱 —— 胜率块不在的局都有(星阵屏稿子 `:1833`;A11 扩到升降级 / 本地对局 / 关掉图表)。`grow` 让它吃掉这一栏剩下的高度:
          在此之前 engineMode 下右栏中段是**空着约 148px** 的,登记在 scope.md 屏 10。
          `scrollbar` 是显式画的那根 —— `.kiosk-fold__body.mvrows` 把原生条宽度设成 0
          (460 的算术不许被滚动条改),所以「能滚」这件事得自己说出来。 */}
      {showMoves && (
        <KioskFold
          fold="moves"
          grow
          scrollbar
          testId="game-moves-fold"
          title={t('game:moves_title', '棋谱 · 交叉点坐标')}
          value={t('game:move_n', '第 {n} 手').replace('{n}', String(nowIndex))}
          bodyClassName="mvrows"
        >
          {moveRows.length === 0 ? (
            // `n--empty` 横跨三列 —— 不加它这句话会掉进第一列那 30px 里竖着排。
            <span className="n n--empty">{t('game:no_moves', '这一局还没有着法')}</span>
          ) : moveRows.map((r) => (
            <MoveCellRow key={r.n} row={r} now={nowIndex} nowRef={nowRef} passLabel={t('kifu:pass', '虚手')} />
          ))}
        </KioskFold>
      )}

      {showScore && (
        <KioskFold
          fold="eval"
          title={t('game:eval_title', '胜率 · KataGo 原生通道')}
          value={goEvalSummary(gameState, t)}
        >
          <GoEvalGraph gameState={gameState} onNavigate={onNavigate} />
        </KioskFold>
      )}

      {statusSlot}

      {/* 纯显示开关。`role="switch"` 不是 `aria-pressed`:后者是「这个按钮此刻被按住」,
          而这两个是**状态** —— 开着就一直开着。长相跟 galaxy 那两个 `<Switch size="small">` 走
          (Fan 2026-08-22:「galaxy 界面里都是开关这种形式,kiosk 也改成一样的」),
          轨和珠是 `.gtoggles button` 的两个伪元素,不加新标签。
          右端说明优先显示硬件故障，其次说明星阵数子的语义。 */}
      <div className="gtoggles gtoggles--switch" role="group" aria-label={t('game:display', '显示')}>
        <button type="button" role="switch" aria-checked={!!analysisToggles.coords} onClick={() => onToggleAnalysis('coords')}>
          {t('Coordinates', '坐标')}
        </button>
        <button type="button" role="switch" aria-checked={!!analysisToggles.numbers} onClick={() => onToggleAnalysis('numbers')}>
          {t('Move Numbers', '手数')}
        </button>
        {/* 右端说明按故障、实体盘摆子、星阵动作、游客限制、数子手数的顺序显示:
              ① `hardwareFault` —— 故障,最急,而且要用红。
              ② `physicalStatus` —— AI 落子后等待实体盘同步的坐标。
              ③ 星阵人机 —— 数子是只读形势判断，不会结束对局。
              ④ 游客 —— 三个键**不登录就永远不会亮**;这一句在触屏上是它们唯一的解释
                 (`reason` 落在 `title`/`aria-description` 上,手指够不着)。
              ⑤ 数子 —— 只关一个键,而且**下满手数它自己就好了**。
            ⚠️ 代价说清楚:游客在前 100 手看不到「数子要下满 N 手」那句。可以接受 ——
            数子键到时候自己会亮,而三个分析键不会。反过来排的话,游客整局都不知道
            那三个键为什么是灰的。 */}
        <i className="ghint" data-fault={hardwareFault ? 'true' : undefined}>
          {hardwareFault
            ?? physicalStatus
            ?? (engineMode
              ? (isGameOver ? '' : t('game:golaxy_judge_hint', '数子只查看当前形势，不结束对局'))
              : analysisRequiresLogin && analysisActions.length > 0
                ? t('play:analysis_requires_login_hint', '领地 / 支招 / 图表 登录后可用')
                // F4:双 pass 之后(awaitingCount)不再说「数子要下满 N 手」—— 门槛已经满足了。
                : awaitingCount && !isGameOver
                  ? t('game:both_passed', '双方都停了一手')
                  : !isGameOver && !canCount
                    ? t('game:count_min', '数子要下满 {n} 手').replace('{n}', String(countMin))
                    : '')}
        </i>
      </div>

      {engineMode ? (
        // 所有点击按钮连续摆放；坐标/手数滑动开关留在上面的独立组。
        // 两行共用四列网格，因此三颗道具与四颗对局操作都是同一尺寸。
        <div className="engine-button-cluster" data-testid="engine-button-cluster">
          <div className="items" role="group" aria-label={t('game:golaxy_items', '星阵道具 · 每按一次扣一次')}>
            {items.map((it) => (
              <button
                key={it.kind}
                type="button"
                aria-pressed={activeEngineKind === it.kind}
                onClick={() => onEngineAnalysis?.(it.kind)}
              >
                <span className={it.count === 0 ? 'cnt zero' : 'cnt'} data-testid="item-badge">
                  {it.count === null ? '—' : it.count}
                </span>
                <Icon name={it.icon} />
                {it.label}
              </button>
            ))}
          </div>
          <KioskActions
            actions={actions}
            ariaLabel={t('game:actions', '对局操作')}
            testId="game-actions"
          />
        </div>
      ) : (
        <KioskActions
          actions={actions}
          className={actions.length > 4 ? 'gacts' : undefined}
          ariaLabel={t('game:actions', '对局操作')}
          testId="game-actions"
        />
      )}

      {/* 着法导航只在**终局之后**出现:对局中它整排是灰的(`disabled={!isGameOver}`),
          而稿子对一排点不动的键的判词是「不是在这一屏塞一排点不动的键」。
          终局后上面那四个动作键整组撤掉,位置正好归它。
          `±10 手`那两个键没了:`.kiosk-movenav` 是 4 列,而 Phosphor 里没有对应的图标 ——
          登记为欠账,不拿别的图标凑一个意思不对的。 */}
      {isGameOver && (
        <div className="kiosk-movenav" data-testid="nav-controls">
          <button type="button" aria-label={t('game:first_move', '第一手')} onClick={() => onAction('start')}><Icon name="caret-double-left" /></button>
          <button type="button" aria-label={t('game:prev_move', '上一手')} onClick={() => onAction('back')}><Icon name="caret-left" /></button>
          <button type="button" aria-label={t('game:next_move', '下一手')} onClick={() => onAction('forward')}><Icon name="caret-right" /></button>
          <button type="button" aria-label={t('game:last_move', '最后一手')} onClick={() => onAction('end')}><Icon name="caret-double-right" /></button>
        </div>
      )}
    </>
  );
};

export default GameControlPanel;
