import { useEffect, useRef } from 'react';
import { Icon } from '../../shell/icons';
import { KioskFold } from '../../shell/KioskFold';
import { KioskActions, type KioskAction } from '../../shell/KioskActions';
import { GoEvalGraph, goEvalSummary } from './GoEvalGraph';
import { localizedRank } from '../../../utils/rankUtils';
import { isRankedGameType } from '../../../features/aiLadder/gameType';
import type { EngineItemCounts, GameState, PlayerInfo } from '../../../api';
import { useTranslation } from '../../../hooks/useTranslation';

interface Props {
  gameState: GameState;
  onAction: (action: string) => void;
  onNavigate: (nodeId: number) => void;
  analysisToggles: Record<string, boolean>;
  onToggleAnalysis: (key: string) => void;
  onHint?: () => void;
  hintEnabled?: boolean;
  isGameOver?: boolean;
  /**
   * 升降级对弈。**不是只把请求掐掉,是整块不渲染** —— 规范 §8:
   * 「禁的时候整块不渲染,不要渲成灰的或显示『—』,那是在提示『这里本来有个东西,你没资格看』」。
   * 上一版前端只是 `isRankedGameType` 早退不去请求,面板照样渲染,画出来是一条全 `—` 的空图。
   */
  isRanked?: boolean;
  /** Golaxy 人机对弈: replace the local analysis toggles with the three star阵-tunnel buttons. */
  engineMode?: boolean;
  activeEngineKind?: 'area' | 'options' | 'variation' | null;
  onEngineAnalysis?: (kind: 'area' | 'options' | 'variation') => void;
  /** Remaining-uses badges for the three engine buttons; null/undefined → "—" (unknown). */
  engineItemCounts?: EngineItemCounts | null;
  /**
   * 硬件出故障时那一句(摄像头 / 标定 / LED)。**没故障时是 `null`,不是空字符串** ——
   * 它和「数子还差几手」共用开关排右端那一格,故障优先。
   * 上一版这些是顶条上三颗常亮的灯;§5 说状态显示归 L1 镜像栏,L3 上没它们的位置,
   * 但撤了灯就等于撤了 LED 掉线在这一屏唯一的信号,所以留下**只在出事时说话**的这一句。
   */
  hardwareFault?: string | null;
}

/** 两个人面对面下的局:胜率图整块不渲染(规范 §8 那张「按对弈方式判」的表)。 */
const TWO_HUMAN_GAME_TYPES = new Set(['pvp_local', 'pvp_online']);

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
  clock: { value: string; label: string } | null;
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
    <div className={turn ? 'pcard turn' : 'pcard'} data-testid={`player-card-${color}`}>
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
 * 对局屏右栏(稿子 `data-screen="game"` / `data-screen="platform-game"`)。
 *
 * **返回的是 Fragment,不是一个包住一切的 `<div>`** —— 这些块必须是 `.kiosk-rail` 的
 * 直接子元素,否则共享 `tokens.css` 的 `.kiosk-rail .kiosk-actions { margin-top: auto }`
 * 选不中,「动作区永远贴右栏底」当场失效。页控条由 `GamePage` 渲染(退出确认和重置识别
 * 都在它手里),排在本组件前面。
 *
 * 右栏 516 的账(自由对弈):44(页控条)+ 60 + 60(玩家卡)+ 126(胜率块 30+96)
 * + 40(两个显示开关)+ 111(七个键 52×2 + 7)+ 5×12(缝)= 501,余 15 落在动作区上面。
 */
const GameControlPanel = ({
  gameState, onAction, onNavigate, analysisToggles, onToggleAnalysis, onHint, hintEnabled = false,
  isGameOver = false, isRanked = false, engineMode = false,
  activeEngineKind = null, onEngineAnalysis, engineItemCounts = null, hardwareFault = null,
}: Props) => {
  const { t, lang } = useTranslation();

  // 数子闸照抄 galaxy(`RightSidebarPanel`):后端 `/api/count/request` 在 count_min_moves
  // 之前一律拒,所以键灰着 —— 而**灰而不说原因**是这份稿子在别处专门骂过的事,
  // 理由写在开关排右端那句 `.ghint` 上。
  const countMin = gameState.count_min_moves ?? 100;
  const moves = gameState.history?.length ?? 0;
  const canCount = !isGameOver && moves >= countMin;

  // 这一局是不是**人机自由对弈**。规范 §8 那张「按对弈方式判」的表只有一句话:
  // 自由对弈能用的,另外四种(升降级 / 本地两人 / 在线大厅 / 星阵人机)一概不能。
  //
  // 升降级这一档**两个操作数都读**:`isRanked` 是调用方给的,`game_type` 是这一局自己带的。
  // 只认前者的话,少传一次 prop 就等于把闸打开 —— 而这里挂着的是「悔棋能不能按」,
  // 升降级局里那是反作弊的一环(后端 `handleAction` 也拒,但界面不该先摆出来邀请他点)。
  const rankedGame = isRanked || isRankedGameType(gameState.game_type);
  const freeVsAi = !engineMode && !rankedGame && !TWO_HUMAN_GAME_TYPES.has(gameState.game_type ?? 'free');

  // 胜率块:自由对弈可开;升降级 / 本地两人 / 在线大厅 / 星阵人机一律**整块不渲染**。
  const evalAllowed = freeVsAi;
  const showScore = evalAllowed && !!analysisToggles.score;

  /**
   * 悔棋 —— Fan 2026-08-25 亲裁:「**只有人机对弈的自由对弈允许悔棋**;升降级对弈、
   * 对战大厅、跨平台对弈等都不允许,悔棋按钮可以撤销。」
   *
   * **两个名字引同一个判据,不是其中一个引另一个**:胜率图和悔棋今天恰好落在同一张表上,
   * 但它们不是同一件事(一个是「能不能看」,一个是「能不能改」)。哪天有一种只让其一,
   * 改的是这一行,不用先把两者拆开。
   *
   * 撤掉而不是灰着,依的是本屏那条判据:**永久不可用 → 撤掉;暂时不可用 → 灰着**。
   * 这四种里悔棋是**开局就定死的没有**(`game_type` 一局之内不变),不是过一会儿会回来的状态,
   * 所以留一颗永远灰的键只是噪声。上一版还把星阵「算招期间」也塞进同一个开关
   * (`disableUndo={isRanked || !!platformPendingMove}`)—— 那是**暂时**的,四颗变三颗
   * 会让「认输」在用户手指底下左右挪;现在星阵整局都没有这颗键,那条来回翻的路径不存在了。
   */
  const undoAllowed = freeVsAi;

  /**
   * 棋谱(星阵屏)。稿子只在这一屏画它 —— 屏 05 那块地方归胜率图,两者共用同一段高度。
   * 数据来自 `history` 的 `move`/`player`(2026-08-25 后端在**已有的那个主线循环**里加的两个键);
   * ⚠️ 不许改用 `stones`:它带 `move_number` 但**不含被提掉的子**,拼出来的谱会缺手。
   */
  const moveRows = engineMode ? toMoveRows(gameState.history) : [];
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

  // 时钟栏。kiosk 的局**不设时限**(开局设置里没有时间控件),`main_time_used` 只有在
  // 真配了时限时才累加 —— 那时才有「本局已下」可写。没有时限时,这一栏唯一为真的量是
  // **当前是第几手**,而那是**局面的量、不是某一方的量** ⇒ 只挂在轮到的那张卡上,
  // 另一张卡的时钟栏不渲染。两张都写「不限时」是把同一句话说两遍;
  // 写 `0:00 本局已下` 更糟 —— 那不是「用了 0 秒」,是「压根没在计」。
  const clockFor = (c: 'B' | 'W'): { value: string; label: string } | null => {
    const used = gameState.players_info[c].main_time_used;
    if (used > 0) return { value: formatTime(used), label: t('game:spent_this_game', '本局已下') };
    if (c !== toMove || isGameOver) return null;
    return {
      value: t('game:move_n', '第 {n} 手').replace('{n}', String((gameState.current_node_index ?? 0) + 1)),
      label: t('game:untimed', '不限时'),
    };
  };

  const analysisActions: KioskAction[] = engineMode ? [] : [
    {
      key: 'ownership', icon: 'grid-nine', label: t('Territory', '领地'),
      pressed: !!analysisToggles.ownership, onClick: () => onToggleAnalysis('ownership'),
    },
    {
      // AI 支招 = 一次性动作(顶部 N 个候选点,实体盘上白闪),**不是开关** ——
      // 所以它没有 `pressed`。原来那个独立的顶栏支招键在 kiosk-ui-redesign 里已经并进来了。
      key: 'hint', icon: 'lightbulb', label: t('Hints', 'AI支招'),
      onClick: () => onHint?.(), disabled: !hintEnabled,
    },
    ...(evalAllowed ? [{
      key: 'score', icon: 'trend-up' as const, label: t('Chart', '图表'),
      pressed: showScore, onClick: () => onToggleAnalysis('score'),
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
    ? [
      // 悔棋不在这里 —— 跨平台对弈**整局都没有**这颗键(见上面 `undoAllowed`)。
      // 稿子 `:1851` 画的是 `<button disabled>悔棋</button>`,理由「灰在这儿比点了被拒好」;
      // 那条理由只对「等一会儿就回来」成立,而这儿是永久没有。**实现反过来纠正稿子。**
      { key: 'pass', icon: 'hand-pointing' as const, label: t('game:pass', '停一手'), onClick: () => onAction('pass'), disabled: isGameOver },
      {
        key: 'count', icon: 'squares-four' as const, label: t('Score', '数子'),
        onClick: () => onAction('count'), disabled: !canCount,
        reason: t('game:count_min', '数子要下满 {n} 手').replace('{n}', String(countMin)),
      },
      { key: 'resign', icon: 'flag' as const, label: t('Resign', '认输'), onClick: () => onAction('resign'), danger: true, disabled: isGameOver },
    ]
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
      <PlayerRow
        color="W" info={gameState.players_info.W} captures={gameState.prisoner_count.W}
        turn={toMove === 'W' && !isGameOver} state={stateWord('W')} clock={clockFor('W')} lang={lang} t={t}
      />
      <PlayerRow
        color="B" info={gameState.players_info.B} captures={gameState.prisoner_count.B}
        turn={toMove === 'B' && !isGameOver} state={stateWord('B')} clock={clockFor('B')} lang={lang} t={t}
      />

      {/* 棋谱 —— 只有星阵屏有(稿子 `:1833`)。`grow` 让它吃掉这一栏剩下的高度:
          在此之前 engineMode 下右栏中段是**空着约 148px** 的,登记在 scope.md 屏 10。
          `scrollbar` 是显式画的那根 —— `.kiosk-fold__body.mvrows` 把原生条宽度设成 0
          (460 的算术不许被滚动条改),所以「能滚」这件事得自己说出来。 */}
      {engineMode && (
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

      {engineMode && (
        // 星阵道具:**每按一次从账上扣一次**,所以既不与动作区并排、也不与显示开关并排。
        // 角标 `0` 用红底**不灰掉**(去星阵 App 充了值马上又能用);`—` = 这一次没取到数。
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
      )}

      {/* 纯显示开关。`role="switch"` 不是 `aria-pressed`:后者是「这个按钮此刻被按住」,
          而这两个是**状态** —— 开着就一直开着。长相跟 galaxy 那两个 `<Switch size="small">` 走
          (Fan 2026-08-22:「galaxy 界面里都是开关这种形式,kiosk 也改成一样的」),
          轨和珠是 `.gtoggles button` 的两个伪元素,不加新标签。
          右端那句写「为什么数子是灰的」;数子能按了就空着,但这个格子**一直在**。 */}
      <div className="gtoggles gtoggles--switch" role="group" aria-label={t('game:display', '显示')}>
        <button type="button" role="switch" aria-checked={!!analysisToggles.coords} onClick={() => onToggleAnalysis('coords')}>
          {t('Coordinates', '坐标')}
        </button>
        <button type="button" role="switch" aria-checked={!!analysisToggles.numbers} onClick={() => onToggleAnalysis('numbers')}>
          {t('Move Numbers', '手数')}
        </button>
        <i className="ghint" data-fault={hardwareFault ? 'true' : undefined}>
          {hardwareFault
            ?? (!isGameOver && !canCount
              ? t('game:count_min', '数子要下满 {n} 手').replace('{n}', String(countMin))
              : '')}
        </i>
      </div>

      <KioskActions
        actions={actions}
        className={actions.length > 4 ? 'gacts' : undefined}
        ariaLabel={t('game:actions', '对局操作')}
        testId="game-actions"
      />

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
