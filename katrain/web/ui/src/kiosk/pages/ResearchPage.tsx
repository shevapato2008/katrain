import { useState, useCallback, useRef, useMemo, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import LiveBoard, { type AiMoveMarker } from '../../components/live/LiveBoard';
import { KioskPagebar } from '../shell/KioskPagebar';
import { KioskOptSeg } from '../shell/KioskOptSeg';
import { KioskFold } from '../shell/KioskFold';
import { KioskActions, type KioskAction } from '../shell/KioskActions';
import { Icon } from '../shell/icons';
import { colsFor, rowsFor } from '../shell/goBoard';
import { useResearchBoard, type BoardTool } from '../hooks/useResearchBoard';
import { useResearchSession } from '../../hooks/useResearchSession';
import { useTranslation } from '../../hooks/useTranslation';
import { useAuth } from '../../context/AuthContext';
import { API } from '../../api';
import { durationLabel } from '../utils/durationLabel';
import { whenLabel } from '../utils/whenLabel';
import { KifuAPI } from '../../api/kifuApi';
import { UserGamesAPI } from '../../api/userGamesApi';

/**
 * 屏 21 研究(L2 布局 A:盘 516 + 16 + 右栏 460)。
 *
 * ## 四个视图收成一屏四态
 *
 * 上一版是**四路 return**:①编辑 / ②分析中 / ③报告 / D失败,后三个整屏换掉,其中
 * ③ 用的是另一块盘(galaxy 的 `<Board gameState>`)和另一条 460→340 宽的右栏
 * (`ResearchAnalysisPanel`,879 行)。这一版四态共用同一条右栏,盘自始至终是同一块:
 *
 * | `scan` | 右栏 | AI 折叠块 | 第 5 颗动作键 |
 * |---|---|---|---|
 * | `none` | 稿子这一屏 | `quickAnalyze` 200 visits | 全局分析 |
 * | `running` | 分段与提示行不渲染(见下) | 进度 | 取消分析 |
 * | `done` | 同 `none` | 会话里扫完的 500 visits/手 | 重新分析 |
 * | `failed` | 同 `none` | `.empty` 三句 | 重试分析 |
 *
 * 三条理由,每条都能单独立住:
 *  ① **`ResearchAnalysisPanel` 装不进 460。** 它是玩家条 + 胜率条 + 推荐表 + 三个 Tab
 *    + 翻手条,原来靠 340 宽的独立面板和整屏换页才摆得下。
 *  ② **不能改成「跳去屏 20 复盘报告」。** `ReportsAPI.create` 只收 `user_game_id`
 *    (`src/api/reportApi.ts:88`),而这一屏的局面可以是**手搭的**、根本没有 game id;
 *    而且「全局分析」建的是会话内 scan(`API.analysisScan`),不是那条 cron 报告任务。
 *    改成跳屏是换后端,不是重画。**代价已登记**:比赛谱和手搭局面从此拿不到走势/重点手。
 *  ③ **`running` 那一态之所以敢把分段和提示行撤掉**,是因为扫描期间盘面本来就是冻的。
 *    想过「留着但全部灰掉」,`KioskOptSeg` 的契约挡住了:「**永远至少留一段能选** ——
 *    全灰掉的一组控件在屏上和一段读数没有区别」。全灰违约,不渲染才是这个外壳件的说法。
 *
 * ## 不再进沉浸
 *
 * 上一版 `setImmersive(isAnalyzing)`。`immersive` 在 `KioskLayout` 里**只干一件事**:
 * 把顶栏整块不渲染 —— 可 `.kiosk-content` 的 `top` 仍是 `var(--topbar-h)`
 * (`tokens.css:419`),于是屏顶留一条 **56 高的空黑带**,一个像素都没省下。
 * 规范 §5 防跳铁律 1 写死「顶栏永远占 y 0–56,任何层级、任何模块都不变高、不隐藏」,
 * 参考图 `shots/21-research.png` 顶栏也是在的。⇒ 这一屏不再调它。
 * 屏 17 摆谱、屏 18 直播、屏 20 复盘详情已各自还过一次,本屏还完只剩屏 14 做题一个现场。
 *
 * Dock 与本屏无关:`/kiosk/research` 不在 `DOCK_TABS` 里 ⇒ `dockLevelOf` 恒为 2 ⇒
 * **四态一律没有 Dock**,`immersive` 从来就不影响它(`KioskLayout.tsx:56-59`)。
 */

/** 扫描态。上一版那四路 return 折成这一个字。 */
type Scan = 'none' | 'running' | 'done' | 'failed';

/**
 * 表里一行。`quickAnalyze`(200 visits)和会话扫完的 `gs.analysis.moves`(500 visits)
 * 两种来源归一到这一个形状,表就只有一份画法。
 *
 * ⚠️ **口径:`winrate` / `scoreLead` 从后端来时是黑方视角**,上屏前按走子方翻转
 * (`toRows` 里做)。这是本仓既有约定,直播和复盘两屏都这么算。
 */
interface AiRow {
  move: string;
  /** 推荐度 = `psv` 占比;没有 `psv`(quickAnalyze 就没有)退回 `visits` 占比。 */
  share: number;
  /** 已按走子方翻转。 */
  scoreLead: number;
  /** 已按走子方翻转,0–1。 */
  winrate: number;
  /**
   * 盘上那三个标记会把它画出来(`drawAiMoveMarker` 收 rank/winrate/visits 三个数)。
   * ⚠️ **别在这儿填 0 充数** —— 四图上当场看见了:三个绿点下面各挂一个「0」,
   * 那是屏上的假数,和「真的算了 0 次」分不开。
   */
  visits: number;
}

/** 后端两种响应的公共子集。`psv` 只有会话那一路有。 */
interface RawMove { move: string; visits: number; winrate: number; scoreLead?: number; psv?: number }

/** 归一 + 换视角。`mover === 'B'` 时后端的数就是黑方视角,原样用。 */
function toRows(raw: RawMove[], mover: 'B' | 'W'): AiRow[] {
  const totalPsv = raw.reduce((s, m) => s + (m.psv ?? 0), 0);
  const totalVisits = raw.reduce((s, m) => s + m.visits, 0);
  const usePsv = totalPsv > 0;
  return raw.map((m) => ({
    move: m.move,
    share: usePsv
      ? ((m.psv ?? 0) / totalPsv) * 100
      : (totalVisits > 0 ? (m.visits / totalVisits) * 100 : 0),
    scoreLead: mover === 'B' ? (m.scoreLead ?? 0) : -(m.scoreLead ?? 0),
    winrate: mover === 'B' ? m.winrate : 1 - m.winrate,
    visits: m.visits,
  }));
}

/** 出处:四个入口各写各的,认不出来就整行不渲染(见 `PROVENANCE` 那段注)。 */
interface Provenance { label: string; backPath: string; backLabel: string }

/**
 * 返回去哪,由 URL 上的 `?from=` 决定,**目标路径查这张表、不收路径参数** ——
 * 收一个 back URL 就等于让调用方决定跳去哪,那是个能被注入的洞。
 *
 * 稿子把返回键写死成「← 棋谱」,可这一屏有**四个入口**,回去的地方各不相同,
 * 而且中间两条的 URL 形状完全一样(都是 `?user_game_id=`)、反推不出来。
 * ⇒ 稿子这里不成立,改成跟着入口走。四个调用点同一轮改成带 `&from=`。
 */
const BACK: Record<string, { path: string; label: string }> = {
  kifu: { path: '/kiosk/kifu', label: '棋谱' },
  history: { path: '/kiosk/play/pvp/history', label: '对局历史' },
  report: { path: '/kiosk/report', label: '复盘' },
  game: { path: '/kiosk/play', label: '对弈' },
};
const BACK_FALLBACK = { path: '/kiosk/play', label: '对弈' };

const ResearchPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { token } = useAuth();

  const board = useResearchBoard();
  const session = useResearchSession();

  const [scan, setScan] = useState<Scan>('none');
  const [progress, setProgress] = useState<{ analyzed: number; total: number } | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);
  const [etaSeconds, setEtaSeconds] = useState<number | null>(null);
  const [confirmScan, setConfirmScan] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);

  /**
   * 领地。**只 gate 渲染,不 gate 请求** —— ownership 和候选着法在**同一个**
   * `quickAnalyze` 响应里(下面那个 effect 一次取两样),所以开关它连一次请求都不多发。
   */
  const [showTerritory, setShowTerritory] = useState(false);

  /** `quickAnalyze`(200 visits)那一路的表。这一份是**取回来的**,所以是 state。 */
  const [quickRows, setQuickRows] = useState<AiRow[] | null>(null);
  const [ownership, setOwnership] = useState<number[][] | null>(null);
  const [rowsError, setRowsError] = useState<string | null>(null);

  const activeSessionIdRef = useRef<string | null>(null);
  const scanStartRef = useRef<{ time: number; analyzed: number } | null>(null);
  const pollFailRef = useRef(0);

  /** 轮到谁走。**跟工具无关** —— `board.nextColor` 是「摆黑/摆白」那个工具说了算的,
   *  而视角要的是这个局面本身轮到谁,所以在这儿按交替重算一次。 */
  const mover: 'B' | 'W' = useMemo(() => {
    const truncated = board.stoneColors.slice(0, board.currentMove);
    const last = truncated.length > 0 ? truncated[truncated.length - 1] : 'W';
    return last === 'B' ? 'W' : 'B';
  }, [board.stoneColors, board.currentMove]);

  // ── 出处与返回 ─────────────────────────────────────────────────────────────
  const [provenance, setProvenance] = useState<Provenance | null>(null);
  const from = searchParams.get('from');
  const backTo = (from && BACK[from]) || BACK_FALLBACK;
  const backPath = from === 'report' && searchParams.get('task')
    ? `/kiosk/report/${searchParams.get('task')}`
    : from === 'kifu' && searchParams.get('kifu_id')
      ? `/kiosk/kifu/${searchParams.get('kifu_id')}`
      : backTo.path;

  // ── 分析:跟着局面走,不跟折叠块走 ─────────────────────────────────────────
  //
  // 上一版是「建议 / 领地 两个开关都关着就不发请求」。这一版稿子把推荐点画成常亮的
  // (`data-ghost="R11,C7,Q6"`,没有任何开关管它),而折叠块默认展开、里面就是这张表 ⇒
  // 分析是这一屏的常态,不是一个可选项。
  //
  // **不做成「展开折叠块才算」**:`KioskFold` 的开合是它自己内部的 state,而那份文档
  // 明写「它是纯粹的视图偏好,没有任何别的东西依赖它」—— 那是一条不变式声明,不是管线
  // 偏好。而且折叠块硬性 2 要求「标题行右端那个当前值收起后照旧显示」,收起=停算的话那个
  // 值必然陈旧。解耦之后头部的值天然永远是活的。
  //
  // **防抖是必需的不是优化**:常亮之后每落一子都会触发一次 200-visit 请求;上一版没有
  // 防抖只是因为它默认关着。
  const positionKey = useMemo(
    () => `${board.boardSize}-${board.komi}-${board.rules}-${board.currentMove}-${board.moves.slice(0, board.currentMove).join(',')}`,
    [board.boardSize, board.komi, board.rules, board.currentMove, board.moves],
  );
  const rowsKeyRef = useRef('');

  useEffect(() => {
    // 扫完之后表的数据源换成会话里那份 500/手 —— 更准,不要再拿 200 的盖掉它。
    if (scan === 'running' || scan === 'done') return;
    const key = positionKey;
    rowsKeyRef.current = key;
    const handle = setTimeout(() => {
      const kataMoves = board.moves
        .slice(0, board.currentMove)
        .map((m, i) => [board.stoneColors[i], m]);
      API.quickAnalyze({
        moves: kataMoves,
        board_size: board.boardSize,
        komi: board.komi,
        rules: board.rules,
        max_visits: 200,
      }, token ?? undefined).then((result) => {
        if (rowsKeyRef.current !== key) return; // 陈旧
        const turn = result?.turnInfos?.[0] ?? result;
        setQuickRows(toRows((turn?.moveInfos ?? []) as RawMove[], mover));
        setRowsError(null);
        const raw = turn?.ownership;
        if (raw && Array.isArray(raw)) {
          const size = board.boardSize;
          const grid: number[][] = [];
          for (let y = 0; y < size; y++) grid.push(raw.slice(y * size, (y + 1) * size));
          setOwnership(grid);
        }
      }).catch((err: unknown) => {
        if (rowsKeyRef.current !== key) return;
        // 状态诚实:算不出来就说算不出来,**不留着上一手的数假装是这一手的**。
        setQuickRows(null);
        setRowsError(err instanceof Error ? err.message : String(err));
      });
    }, 400);
    return () => clearTimeout(handle);
  }, [positionKey, scan, token, mover]); // eslint-disable-line react-hooks/exhaustive-deps

  /**
   * 扫完之后表改从会话的当前节点读。
   *
   * 这一份**是算得出来的、不是要同步的** —— 写成 effect + `setRows` 会多一轮渲染,
   * 而且「会话已经换了节点、表还是上一节点的」这个中间态会真的上屏一帧。
   */
  const rows = useMemo(() => {
    if (scan !== 'done') return quickRows;
    const gs = session.gameState;
    if (!gs) return null;
    return toRows((gs.analysis?.moves ?? []) as RawMove[], mover);
  }, [scan, quickRows, session.gameState, mover]);

  // ── 全局分析 ───────────────────────────────────────────────────────────────
  /**
   * `explicitSgf` 是给两条深链用的。**它不是可选的优化,是那个 bug 的唯一修法** ——
   * `loadFromSGF` 之后立刻在同一段异步续体里 `board.serializeToSGF()`,读到的是**载入前
   * 的空盘**(setState 还没 flush),`createSession(undefined)` 于是静默什么都不做。
   * galaxy 的 `ResearchPage.tsx:187-199` 就栽在这儿。把刚取到的 `sgf_content` 直接串进来。
   */
  const startScan = useCallback(async (explicitSgf?: string) => {
    setConfirmScan(false);
    const { sgf } = board.serializeToSGF();
    const toLoad = explicitSgf ?? (board.moves.length > 0 ? sgf : undefined);
    const sid = await session.createSession(toLoad, {
      skipAnalysis: true,
      initialMove: explicitSgf ? undefined : board.currentMove,
    });
    if (!sid) {
      setScanError(t('research:session_failed', '无法创建研究会话，请重试'));
      setScan('failed');
      return;
    }
    activeSessionIdRef.current = sid;
    setProgress(null);
    setEtaSeconds(null);
    setScanError(null);
    scanStartRef.current = null;
    pollFailRef.current = 0;
    setScan('running');
    try {
      await API.analysisScan(sid, 500);
    } catch {
      setScanError(t('research:scan_failed', '启动分析失败，请重试'));
      setScan('failed');
    }
  }, [board, session, t]);

  /** 回到 `none`:销毁会话,表退回 `quickAnalyze`。**不还原盘面** —— 扫描期间本地盘
   *  一个字都没变过(上一版要还原,是因为那时候报告视图用的是另一块盘)。 */
  const dropScan = useCallback(async () => {
    activeSessionIdRef.current = null;
    await session.destroySession();
    setScan('none');
    setProgress(null);
    setEtaSeconds(null);
    setScanError(null);
    scanStartRef.current = null;
    rowsKeyRef.current = ''; // 让 quickAnalyze 那个 effect 重新取一次
  }, [session]);

  const retryScan = useCallback(async () => {
    const sid = activeSessionIdRef.current;
    // 会话还活着 ⇒ 增量续跑(`_do_analysis_scan` 只排 `!analysis_exists` 的那些),不销毁重建。
    if (!sid) { await startScan(); return; }
    setScanError(null);
    pollFailRef.current = 0;
    setScan('running');
    try {
      await API.analysisScan(sid, 500);
    } catch {
      setScanError(t('research:scan_failed', '启动分析失败，请重试'));
      setScan('failed');
    }
  }, [startScan, t]);

  // 进度轮询 + 实测 ETA。连续 5 次取不到才判失败(单次抖动不算)。
  useEffect(() => {
    if (scan !== 'running') return;
    const sid = activeSessionIdRef.current;
    if (!sid) return;
    const timer = setInterval(async () => {
      try {
        const p = await API.analysisProgress(sid);
        pollFailRef.current = 0;
        if (activeSessionIdRef.current !== sid) return;
        setProgress({ analyzed: p.analyzed, total: p.total });
        // ETA 是**实测**的:拿两次采样之间真的算了多少手去推,不写死每手多少秒。
        const now = Date.now();
        const start = scanStartRef.current;
        if (!start) {
          scanStartRef.current = { time: now, analyzed: p.analyzed };
        } else if (p.analyzed > start.analyzed) {
          const rate = (p.analyzed - start.analyzed) / ((now - start.time) / 1000);
          setEtaSeconds(rate > 0 ? Math.round((p.total - p.analyzed) / rate) : null);
        }
        if (p.total > 0 && p.analyzed >= p.total) setScan('done');
      } catch {
        pollFailRef.current += 1;
        if (pollFailRef.current >= 5) {
          setScanError(t('research:progress_lost', '连续 5 次读不到分析进度，连接可能已经断了'));
          setScan('failed');
        }
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [scan, t]);

  /**
   * 泄漏守卫:会话在服务端是有状态的,页面被关掉/刷新时得让它知道。
   * 依赖里带 `session.sessionId` 是**故意的** —— `[]` 依赖的清理函数捕获的是
   * `sessionId === null`,跑起来是个空操作。
   */
  useEffect(() => {
    const cleanup = () => {
      const sid = session.sessionId;
      if (sid) navigator.sendBeacon?.(`/api/v1/research/sessions/${sid}/close`);
    };
    window.addEventListener('beforeunload', cleanup);
    return () => { window.removeEventListener('beforeunload', cleanup); cleanup(); };
  }, [session.sessionId]);

  // ── 改盘面的动作:扫完之后先退回 `none` ───────────────────────────────────
  //
  // 扫描的结论钉在**那一份**着法序列上。改了盘还留着旧结论,表里的数就在骗人。
  const editGuard = useCallback((fn: () => void) => {
    if (scan === 'done' || scan === 'failed') { void dropScan(); }
    fn();
  }, [scan, dropScan]);

  const onIntersection = useCallback((x: number, y: number) => {
    if (scan === 'running') return; // 扫描期间盘面是冻的
    editGuard(() => board.handleIntersectionClick(x, y));
  }, [scan, editGuard, board]);

  const goToMove = useCallback((move: number) => {
    const clamped = Math.max(0, Math.min(board.moves.length, move));
    board.handleMoveChange(clamped);
    // 扫完之后会话也要跟着挪,否则 `gs.analysis` 说的还是上一个节点。
    if (scan === 'done' && session.gameState) {
      const node = session.gameState.history[clamped]?.node_id;
      if (node !== undefined) void session.onNavigate(node);
    }
  }, [board, scan, session]);

  // ── 入口:三条深链 ─────────────────────────────────────────────────────────
  //
  // 三条都用 ref 上闩、只跑一次。`?kifu_id` / `?user_game_id` 这两条**绝不能**在同一段
  // 异步续体里从 `board` 反推 SGF —— `loadFromSGF` 的 setState 还没 flush,读到的是载入前
  // 的空盘(galaxy `ResearchPage.tsx:187-199` 那个陈旧闭包 bug)。把刚取到的 `sgf_content`
  // 直接串进 `createSession`。
  const kifuRef = useRef(false);
  useEffect(() => {
    const id = searchParams.get('kifu_id');
    if (!id || kifuRef.current) return;
    kifuRef.current = true;
    KifuAPI.getAlbum(Number(id)).then(async (album) => {
      if (album.sgf_content) {
        const r = board.loadFromSGF(album.sgf_content);
        if (!r.success) { console.error('Failed to load kifu for deep link:', r.error); return; }
      }
      if (album.player_black) board.setPlayerBlack(album.player_black);
      if (album.player_white) board.setPlayerWhite(album.player_white);
      const head = album.event
        ? `${album.event}${album.round_name ? ` · ${album.round_name}` : ''}`
        : `${album.player_black} vs ${album.player_white}`;
      setProvenance({
        label: `${t('research:from_kifu', '棋谱库')}：${head}${album.date_played ? ` · ${album.date_played}` : ''}`,
        backPath: `/kiosk/kifu/${id}`, backLabel: t('kifu:title', '棋谱'),
      });
      if (searchParams.get('analyze') === '1' && album.sgf_content) await startScan(album.sgf_content);
    }).catch((err) => console.error('Failed to load kifu for deep link:', err));
  }, [searchParams]); // eslint-disable-line react-hooks/exhaustive-deps

  const userGameRef = useRef(false);
  useEffect(() => {
    const id = searchParams.get('user_game_id');
    if (!id || userGameRef.current || !token) return;
    userGameRef.current = true;
    UserGamesAPI.get(token, id).then(async (detail) => {
      if (!detail.sgf_content) return;
      board.loadFromSGF(detail.sgf_content);
      const head = detail.title
        || `${detail.player_black ?? t('research:black', '黑方')} vs ${detail.player_white ?? t('research:white', '白方')}`;
      const stamp = detail.game_date ?? detail.created_at;
      const when = stamp ? Date.parse(stamp) : NaN;
      setProvenance({
        label: `${t('research:from_my_games', '我的对局')}：${head}${Number.isNaN(when) ? '' : ` · ${whenLabel(when, t)}`}`,
        backPath: backTo.path, backLabel: backTo.label,
      });
      if (searchParams.get('analyze') === '1') await startScan(detail.sgf_content);
    }).catch((err) => console.error('Failed to load user game for deep link:', err));
  }, [searchParams, token]); // eslint-disable-line react-hooks/exhaustive-deps

  // 对局刚结束的「复盘本局」:`GamePage` 用 sessionStorage 交接(那局刚在本机下完,没有 id)。
  // key **进来就删** —— 所以**刷新之后这一支不再成立**:盘是空的、出处也没有,
  // 那时候还写「刚下完的这一局」就是假的,`provenance` 保持 null、副标题整行不渲染。
  const reviewRef = useRef(false);
  useEffect(() => {
    if (reviewRef.current) return;
    if (searchParams.get('user_game_id') || searchParams.get('kifu_id')) return;
    const sgf = sessionStorage.getItem('kioskReviewSgf');
    if (!sgf) return;
    reviewRef.current = true;
    sessionStorage.removeItem('kioskReviewSgf');
    board.loadFromSGF(sgf);
    // 这一条**只能**是 effect:出处的唯一来源是 sessionStorage 里那把随读随删的钥匙,
    // 渲染期读它就是在渲染期写外部状态。挂载时同步跑一次是对的。
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setProvenance({
      label: t('research:from_last_game', '刚下完的这一局'),
      backPath: '/kiosk/play', backLabel: t('play:title', '对弈'),
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── 屏上的数 ───────────────────────────────────────────────────────────────
  const moveNo = Math.max(0, board.currentMove - board.handicapCount);
  const totalMoves = Math.max(0, board.moves.length - board.handicapCount);

  /** 稿子的三个绿点。取**前 3** —— 盘上再多就盖住棋形了。 */
  const markers: AiMoveMarker[] | null = useMemo(() => {
    if (!rows) return null;
    return rows.slice(0, 3).map((r, i) => ({
      move: r.move, rank: i + 1, visits: r.visits, winrate: r.winrate, score_lead: r.scoreLead,
    }));
  }, [rows]);

  /** 折叠头右端那个值。**算不出来写「—」,不写 50%** —— 「真的均势」和「没有这个数」
   *  不能长成同一个样子(屏 18 已为同一件事判过一次)。 */
  const headValue = rows && rows.length > 0
    ? `${mover === 'B' ? t('research:black', '黑方') : t('research:white', '白方')} ${(rows[0].winrate * 100).toFixed(1)}%`
    : '—';

  const TOOLS: { value: BoardTool; label: React.ReactNode }[] = [
    { value: 'alternate', label: t('research:alternate', '交替') },
    { value: 'black', label: <><span className="disc b" />{t('research:place_black', '摆黑')}</> },
    { value: 'white', label: <><span className="disc w" />{t('research:place_white', '摆白')}</> },
    { value: 'delete', label: t('research:delete', '删除') },
  ];

  /**
   * `.kiosk-opthint` 写的是**当前选中项**(规范给这一行的定义),不是控件的设计说明。
   * 稿子那句「这四种互斥 —— 同一根手指点在盘上只能是其中一个意思,所以是分段不是开关」
   * 是写给读稿人的,收进这段注释、不上屏(Fan 2026-08-22:「不要写那么多解释文字,
   * 还都是小字,7 英寸屏看起来非常费劲」)。
   *
   * 腾出来的这一行拿去说**规则/贴目/让子** —— 那三个控件这一版删掉了(四个入口都自带这些
   * 值,`loadFromSGF` 会 set),但**删控件不等于可以不说值**:用户得知道 AI 是按什么规则算的。
   */
  const rulesName = board.rules === 'japanese' ? t('research:rules_japanese', '日本规则')
    : board.rules === 'korean' ? t('research:rules_korean', '韩国规则')
      : t('research:rules_chinese', '中国规则');
  const toolName = TOOLS.find((x) => x.value === board.boardTool)?.value === 'delete'
    ? t('research:delete', '删除')
    : board.boardTool === 'black' ? t('research:place_black', '摆黑')
      : board.boardTool === 'white' ? t('research:place_white', '摆白')
        : t('research:alternate', '交替');
  const hint = [
    toolName,
    rulesName,
    t('research:komi', '贴目 {komi}').replace('{komi}', String(board.komi)),
    board.handicap > 0 ? t('research:handicap', '让{handicap}子').replace('{handicap}', String(board.handicap)) : null,
  ].filter(Boolean).join(' · ');

  const fifth: KioskAction = scan === 'running'
    ? { key: 'cancel', icon: 'arrow-counter-clockwise', label: t('research:cancel_scan', '取消分析'), onClick: () => void dropScan() }
    : scan === 'failed'
      ? { key: 'retry', icon: 'arrows-clockwise', label: t('research:retry_analysis', '重试分析'), onClick: () => void retryScan() }
      : scan === 'done'
        ? { key: 'rescan', icon: 'magnifying-glass', label: t('research:rescan', '重新分析'), onClick: () => setConfirmScan(true) }
        : { key: 'scan', icon: 'magnifying-glass', label: t('research:full_scan', '全局分析'), onClick: () => setConfirmScan(true) };

  const actions: KioskAction[] = [
    {
      key: 'open', icon: 'upload-simple', label: t('research:open', '打开'),
      onClick: () => editGuard(board.openLocalSGF), disabled: scan === 'running',
    },
    // 保存**不跟着灰** —— 它只读,扫描期间存下当前这份谱没有任何危险。
    { key: 'save', icon: 'books', label: t('research:save', '保存'), onClick: board.saveLocalSGF },
    {
      key: 'pass', icon: 'skip-forward', label: t('research:pass', '停一手'),
      onClick: () => editGuard(board.handlePass), disabled: scan === 'running',
    },
    {
      key: 'clear', icon: 'arrows-clockwise', label: t('research:clear', '清空'),
      onClick: () => setConfirmClear(true), disabled: scan === 'running',
    },
    fifth,
  ];

  const boardSize = board.boardSize;

  return (
    <div className="kiosk-layout-a research-layout" data-testid="research-page">
      <div className="kiosk-board" data-testid="research-board">
        {/* 四条刻度带由**外壳**画(四棋类同一套几何),盘自己那一圈坐标因此关掉。 */}
        <div className="kiosk-board__ruler kiosk-board__ruler--top">
          {colsFor(boardSize).map((c) => <span key={`t${c}`}>{c}</span>)}
        </div>
        <div className="kiosk-board__ruler kiosk-board__ruler--left">
          {rowsFor(boardSize).map((r) => <span key={`l${r}`}>{r}</span>)}
        </div>
        <div className="kiosk-board__play">
          <LiveBoard
            moves={board.moves}
            stoneColors={board.stoneColors}
            currentMove={board.currentMove}
            boardSize={boardSize}
            showCoordinates={false}
            handicapCount={board.handicapCount}
            onIntersectionClick={onIntersection}
            nextColor={board.nextColor ?? undefined}
            /* 推荐点**常亮**,没有开关管它 —— 稿子 `data-ghost="R11,C7,Q6"` 就是这么画的。 */
            aiMarkers={markers}
            showAiMarkers
            showTerritory={showTerritory}
            ownership={showTerritory ? ownership : null}
            minContainerHeight={0}
          />
        </div>
        <div className="kiosk-board__ruler kiosk-board__ruler--right">
          {rowsFor(boardSize).map((r) => <span key={`r${r}`}>{r}</span>)}
        </div>
        <div className="kiosk-board__ruler kiosk-board__ruler--bottom">
          {colsFor(boardSize).map((c) => <span key={`b${c}`}>{c}</span>)}
        </div>
      </div>

      <div className="kiosk-rail">
        <KioskPagebar
          testId="research-pagebar"
          backLabel={provenance?.backLabel ?? backTo.label}
          onBack={() => navigate(provenance?.backPath ?? backPath)}
          title={t('research:move_title', '研究 · 第 {n} 手').replace('{n}', String(moveNo))}
          sub={provenance?.label}
          /* §11 的那**一颗**页级图标键。领地是盘面视图叠加,和「翻转棋盘/全屏」同族。 */
          action={{
            icon: 'grid-nine',
            label: t('research:territory', '领地'),
            pressed: showTerritory,
            onClick: () => setShowTerritory((v) => !v),
          }}
        />

        {/* 扫描期间盘面是冻的 ⇒ 编辑工具不渲染。**不是全部灰掉** ——
            `KioskOptSeg` 的契约写死「永远至少留一段能选」,全灰是违约。 */}
        {scan !== 'running' && (
          <>
            <KioskOptSeg
              testId="research-tools"
              ariaLabel={t('research:edit_tools', '编辑工具')}
              options={TOOLS}
              value={board.boardTool}
              onChange={(v) => board.setBoardTool(v)}
            />
            <p className="kiosk-opthint" data-testid="research-hint">{hint}</p>
          </>
        )}

        <KioskFold
          fold="ai"
          grow
          /* 表里 24 个候选而视口只露 8 行 —— 没有条子,后面那 16 行在触摸屏上就是不存在的。 */
          scrollbar
          bodyClassName={scan === 'running' || scan === 'failed' || rowsError || !rows || rows.length === 0 ? undefined : 'aitab'}
          testId="research-ai"
          title={t('research:ai_after_move', 'AI 推荐 · 第 {n} 手之后').replace('{n}', String(moveNo))}
          value={headValue}
        >
          {scan === 'failed' ? (
            /* 用户明确要过一次全局扫描而它没跑成 —— 这件事得自己说,不能因为 200 visits
               的快速分析恰好还能用就把它咽下去。盘一动 `editGuard` 就退回 `none`,表自然回来。 */
            <div className="empty" data-testid="research-ai-error">
              <h4>{t('research:scan_broke', '全局分析没跑完')}</h4>
              <p>{scanError}</p>
            </div>
          ) : scan === 'running' ? (
            <div className="aiscan" data-testid="research-scan">
              <h4>{t('research:analyzing_game', '正在分析棋局')}</h4>
              <div className="aiscan__bar">
                <i style={{ width: progress && progress.total > 0 ? `${Math.round((progress.analyzed / progress.total) * 100)}%` : '0%' }} />
              </div>
              {/* 三个数全是**实测**的。**没有「大概几分钟」** —— 开跑前没有校准过的每手速率,
                  那个数只能编;`预计剩余` 是拿两次采样之间真的算了多少手推出来的。 */}
              <dl className="aiscan__stats">
                <div><dt>{t('research:analyzed_moves', '已分析手数')}</dt><dd>{progress ? `${progress.analyzed} / ${progress.total}` : '—'}</dd></div>
                <div><dt>{t('research:eta_label', '预计剩余')}</dt><dd>{etaSeconds !== null && etaSeconds > 0 ? durationLabel(etaSeconds, t) : '—'}</dd></div>
              </dl>
            </div>
          ) : rowsError ? (
            <div className="empty" data-testid="research-ai-error">
              <h4>{t('research:analysis_failed', '这一手算不出来')}</h4>
              <p>{rowsError}</p>
            </div>
          ) : rows === null ? (
            <div className="empty" data-testid="research-ai-pending">
              <h4>{t('research:analyzing_move', '正在算这一手')}</h4>
            </div>
          ) : rows.length === 0 ? (
            <div className="empty" data-testid="research-ai-none">
              <h4>{t('research:no_candidates', 'AI 没有给出候选着法')}</h4>
            </div>
          ) : (
            <>
              <span className="hd">{t('research:col_move', '着手')}</span>
              <span className="hd">{t('research:col_recommendation', '推荐度')}</span>
              <span className="hd">{t('research:col_score_diff', '目差')}</span>
              <span className="hd">{t('research:col_winrate', '胜率')}</span>
              {/* 有几行画几行,**下面留白,不补空行也不补占位** —— `.aitab` 的
                  `align-content:start` 就是为这个写的。留白是真话:AI 只给出了这么多候选。 */}
              {rows.map((r, i) => {
                const best = i === 0 ? 'best' : '';
                // **负目差一律走 `.neg`,连首行也不例外** —— 绿色的负数是自相矛盾的。
                const scoreCls = r.scoreLead < 0 ? 'neg' : best;
                return (
                  <span key={r.move} style={{ display: 'contents' }} data-testid="research-ai-row">
                    <span className={best}>{r.move}</span>
                    <span className={best}>{r.share.toFixed(0)}%</span>
                    <span className={scoreCls}>{r.scoreLead >= 0 ? '+' : '−'}{Math.abs(r.scoreLead).toFixed(1)}</span>
                    <span className={best}>{(r.winrate * 100).toFixed(1)}%</span>
                  </span>
                );
              })}
            </>
          )}
        </KioskFold>

        <div className="kiosk-movenav" data-testid="research-movenav">
          <button
            type="button" aria-label={t('kifu:to_start', '回到开局')}
            disabled={board.currentMove === 0} onClick={() => goToMove(0)}
          ><Icon name="caret-double-left" /></button>
          <button
            type="button" aria-label={t('kifu:prev_move', '上一手')}
            disabled={board.currentMove === 0} onClick={() => goToMove(board.currentMove - 1)}
          ><Icon name="caret-left" /></button>
          <button
            type="button" aria-label={t('kifu:next_move', '下一手')}
            disabled={board.currentMove >= board.moves.length} onClick={() => goToMove(board.currentMove + 1)}
          ><Icon name="caret-right" /></button>
          <button
            type="button" aria-label={t('kifu:to_end', '跳到最后')}
            disabled={board.currentMove >= board.moves.length} onClick={() => goToMove(board.moves.length)}
          ><Icon name="caret-double-right" /></button>
        </div>

        <KioskActions actions={actions} testId="research-actions" ariaLabel={t('research:actions', '研究操作')} />
      </div>

      {/* 画布内弹层。MUI `Dialog` 会 portal 到缩放画布**外面**,那儿 `tokens.css` 的变量
          没有定义 —— 本 track 已有四处先例都走 `.cdlg`。 */}
      {confirmScan && (
        <div className="cdlg" role="dialog" aria-modal="true" data-testid="research-scan-confirm">
          <div className="cdlg__box">
            <h3>{t('research:full_scan', '全局分析')}</h3>
            {/* 只写**算得出来的**真话:手数是数出来的,500 是传给 `analysisScan` 的那个数。
                **不写「大概几分钟」** —— 开跑前没有校准过的每手速率。 */}
            <p>
              {t('research:scan_cost', '一共 {n} 手 · 每手算 500 次')
                .replace('{n}', String(totalMoves))}
              <br />
              {t('research:scan_freeze', '算完之前不能改盘面，可以随时取消')}
            </p>
            <div className="cdlg__acts">
              <button type="button" className="ghost" onClick={() => setConfirmScan(false)}>
                {t('research:cancel', '取消')}
              </button>
              <button type="button" className="main" onClick={() => void startScan()}>
                {t('research:scan_go', '开始算')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 清空补确认:上一版是**一点就把整盘擦掉、没有任何确认**,而「停一手」这个两下就能
          撤销的动作反倒弹确认框。轻重是倒置的,这一版扳回来(停一手的确认同时去掉)。 */}
      {confirmClear && (
        <div className="cdlg" role="dialog" aria-modal="true" data-testid="research-clear-confirm">
          <div className="cdlg__box">
            <h3>{t('research:clear_confirm_title', '清空整盘？')}</h3>
            <p>{t('research:clear_confirm_msg', '盘上 {n} 手会全部擦掉，这一步撤不回来。')
              .replace('{n}', String(totalMoves))}</p>
            <div className="cdlg__acts">
              <button type="button" className="ghost" onClick={() => setConfirmClear(false)}>
                {t('research:cancel', '取消')}
              </button>
              <button
                type="button" className="bad"
                onClick={() => { setConfirmClear(false); editGuard(board.handleClear); }}
              >
                {t('research:clear', '清空')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 19 路以外的谱被按 19 路载入了 —— 这是**改了用户给的东西**,必须说一声。 */}
      {board.lastLoadClamped && (
        <p className="setnote" data-testid="research-clamp">
          {t('research:only_19_supported', '仅支持 19 路，已按 19 路加载')}
        </p>
      )}
    </div>
  );
};

export default ResearchPage;
