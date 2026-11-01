import { useState, useCallback, useRef, useMemo, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import LiveBoard, { type AiMoveMarker } from '../../components/live/LiveBoard';
import { KioskPagebar } from '../shell/KioskPagebar';
import { KioskOptSeg } from '../shell/KioskOptSeg';
import { AiRecommendRows } from '../components/report/AiRecommendRows';
import { KioskFold } from '../shell/KioskFold';
import { KioskActions, type KioskAction } from '../shell/KioskActions';
import { Icon } from '../shell/icons';
import { colsFor, rowsFor } from '../shell/goBoard';
import { useResearchBoard, type BoardTool } from '../hooks/useResearchBoard';
import { useSound } from '../../hooks/useSound';
import { isReplayStoneMove } from '../../hooks/useReplayStoneSound';
import { useTranslation } from '../../hooks/useTranslation';
import { ruleNameOf } from '../utils/setupOptions';
import { useAuth } from '../../context/AuthContext';
import { movesToSGF } from '../../utils/sgfSerializer';
import { whenLabel } from '../utils/whenLabel';
import { KifuAPI } from '../../api/kifuApi';
import { UserGamesAPI } from '../../api/userGamesApi';
import { getCurrentKioskActivityStorage } from '../storage/kioskActivityStorage';

import { usePaidPosition } from '../../features/analysis/usePaidPosition';
import { useReportTasks } from '../../features/report/useReportTasks';
import { ConsumptionQuoteDialog } from '../../features/membership/ConsumptionQuoteDialog';

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
 * 稿子把返回键写死成「← 棋谱」,可这一屏有**三个入口**,回去的地方各不相同,
 * 而且棋谱详情和复盘报告两条的 URL 形状完全一样(都带 `?user_game_id=`)、反推不出来。
 * ⇒ 稿子这里不成立,改成跟着入口走。三个调用点都带着 `&from=`。
 *
 * ⚠️ 2026-08-25 去掉了第四条 `history`(`/kiosk/play/pvp/history`):那是 27 屏改造
 * **之前**的对局历史屏,改造后它的活由屏 19 复盘接了过去,而它自己的路由**没有任何入口**
 * —— 从 UI 上走不到。页面已删,这条出处跟着删。
 */
const BACK: Record<string, { path: string; label: string }> = {
  kifu: { path: '/kiosk/kifu', label: '棋谱' },
  report: { path: '/kiosk/report', label: '复盘' },
  game: { path: '/kiosk/play', label: '对弈' },
};
const BACK_FALLBACK = { path: '/kiosk/play', label: '对弈' };

const ResearchPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { t, lang } = useTranslation();
  const { token, isAuthenticated, identityKey, status } = useAuth();
  const board = useResearchBoard();
  const { play } = useSound();
  const [confirmClear, setConfirmClear] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [reportBusy, setReportBusy] = useState(false);
  const positionSgf = useMemo(() => movesToSGF(board.moves.slice(0, board.currentMove), {
    boardSize: board.boardSize, komi: board.komi, rules: board.rules, handicap: board.handicap, playerBlack: '', playerWhite: '',
  }, board.stoneColors.slice(0, board.currentMove)).sgf, [board.moves, board.currentMove, board.boardSize, board.komi, board.rules, board.handicap, board.stoneColors]);
  const positionKey = positionSgf;
  const paid = usePaidPosition({ token, status, identityKey, snapshotKey: positionKey, input: { sgf: positionSgf } });
  const { createReport, pendingQuote: reportQuote, quoteBusy, confirmQuote, cancelQuote, error: reportError } = useReportTasks(token, isAuthenticated, identityKey, status);
  const mover: 'B' | 'W' = board.currentMove > 0 && board.stoneColors[board.currentMove - 1] === 'B' ? 'W' : 'B';
  const rows = paid.result ? toRows(paid.result.moves.map((move) => ({ ...move, winrate: move.winrate, scoreLead: move.score_lead })), mover) : null;
  const rowsError = paid.error;
  const showTerritory = paid.showOwnership && !!paid.result;
  const ownership = paid.result?.ownership.length === board.boardSize * board.boardSize ? { key: positionKey,
    grid: Array.from({ length: board.boardSize }, (_, y) => paid.result!.ownership.slice(y * board.boardSize, (y + 1) * board.boardSize)) } : null;
  const moveNo = Math.max(0, board.currentMove - board.handicapCount);
  const totalMoves = Math.max(0, board.moves.length - board.handicapCount);
  const markers: AiMoveMarker[] | null = rows?.slice(0, 3).map((r, i) => ({ move: r.move, rank: i + 1, visits: r.visits, winrate: r.winrate, score_lead: r.scoreLead })) ?? null;
  const headValue = rows && rows.length > 0 ? `${mover === 'B' ? t('research:black', '黑方') : t('research:white', '白方')} ${(rows[0].winrate * 100).toFixed(1)}%` : '—';
  const liveIdentity = useRef(identityKey);
  liveIdentity.current = identityKey;
  const handleCreateReport = useCallback(async () => {
    if (!isAuthenticated || status !== 'authenticated') { setSaveError('请先登录后创建报告'); return; }
    if (reportBusy) return;
    const requestedIdentity = identityKey;
    setReportBusy(true); setSaveError(null);
    try {
      const { sgf } = board.serializeToSGF();
      const game = await UserGamesAPI.create(token, { sgf_content: sgf, source: 'research', category: 'game',
        player_black: board.playerBlack || undefined, player_white: board.playerWhite || undefined,
        board_size: board.boardSize, rules: board.rules, komi: board.komi, move_count: totalMoves });
      if (liveIdentity.current !== requestedIdentity) return;
      const task = await createReport({ userGameId: game.id, totalMoves: game.move_count });
      if (task && liveIdentity.current === requestedIdentity) navigate('/kiosk/report');
    } catch (error) { if (liveIdentity.current === requestedIdentity) setSaveError(error instanceof Error ? error.message : '创建报告失败'); }
    finally { setReportBusy(false); }
  }, [board, createReport, identityKey, isAuthenticated, navigate, reportBusy, status, token, totalMoves]);
  const editGuard = useCallback((fn: () => void) => fn(), []);
  const onIntersection = useCallback((x: number, y: number) => {
    if (board.handleIntersectionClick(x, y)) play('stone');
  }, [board, play]);
  const goToMove = useCallback((move: number) => {
    const clamped = Math.max(0, Math.min(board.moves.length, move));
    if (clamped === board.currentMove) return;
    board.handleMoveChange(clamped);
    if (clamped > 0 && isReplayStoneMove(board.moves[clamped - 1], board.boardSize)) play('stone');
  }, [board, play]);
  // ── 出处与返回 ─────────────────────────────────────────────────────────────
  const [provenance, setProvenance] = useState<Provenance | null>(null);
  const from = searchParams.get('from');
  const backTo = (from && BACK[from]) || BACK_FALLBACK;
  // 只收数字 id —— 查询值原样拼进路由会被注入(`?task=..%2F..%2Fplay` 能把「返回」
  // 带去任意路由),认不出这个形状就退回上面那张常量表,不让 URL 自己决定去哪。
  const taskParam = searchParams.get('task');
  const kifuIdParam = searchParams.get('kifu_id');
  const backPath = from === 'report' && taskParam && /^\d+$/.test(taskParam)
    ? `/kiosk/report/${taskParam}`
    : from === 'kifu' && kifuIdParam && /^\d+$/.test(kifuIdParam)
      ? `/kiosk/kifu/${kifuIdParam}`
      : backTo.path;

  const kifuRef = useRef<string | null>(null);
  const kifuRequestRef = useRef(0);
  const lastKifuPlayersRef = useRef<{ id: string; black: string; white: string } | null>(null);
  const currentPlayersRef = useRef({ black: board.playerBlack, white: board.playerWhite });
  useEffect(() => {
    currentPlayersRef.current = { black: board.playerBlack, white: board.playerWhite };
  }, [board.playerBlack, board.playerWhite]);
  useEffect(() => {
    const id = searchParams.get('kifu_id');
    if (!id) return;
    const request = ++kifuRequestRef.current;
    KifuAPI.getAlbum(Number(id), lang).then(async (album) => {
      if (request !== kifuRequestRef.current) return;
      const firstLoad = kifuRef.current !== id;
      if (firstLoad && album.sgf_content) {
        const r = board.loadFromSGF(album.sgf_content);
        if (!r.success) { console.error('Failed to load kifu for deep link:', r.error); return; }
        kifuRef.current = id;
      }
      const black = album.display_player_black ?? t('game:black_side', '黑方');
      const white = album.display_player_white ?? t('game:white_side', '白方');
      const previous = lastKifuPlayersRef.current;
      if (firstLoad || previous?.id !== id || currentPlayersRef.current.black === previous.black) board.setPlayerBlack(black);
      if (firstLoad || previous?.id !== id || currentPlayersRef.current.white === previous.white) board.setPlayerWhite(white);
      lastKifuPlayersRef.current = { id, black, white };
      const head = album.display_event
        ? `${album.display_event}${album.display_round_name ? ` · ${album.display_round_name}` : ''}`
        : `${black} vs ${white}`;
      setProvenance({
        label: `${t('research:from_kifu', '棋谱库')}：${head}${album.date_played ? ` · ${album.date_played}` : ''}`,
        backPath: `/kiosk/kifu/${id}`, backLabel: t('kifu:title', '棋谱'),
      });

    }).catch((err) => {
      if (request === kifuRequestRef.current) console.error('Failed to load kifu for deep link:', err);
    });
    return () => { kifuRequestRef.current += 1; };
  }, [searchParams, lang]); // eslint-disable-line react-hooks/exhaustive-deps

  const userGameRef = useRef(false);
  useEffect(() => {
    const id = searchParams.get('user_game_id');
    // ⚠️ 判 `isAuthenticated`,不判 `token`:盒上严格 SSO 的 token 恒为 null(凭据在 HttpOnly
    // cookie 里),判 `!token` 等于把每个已登录的人都当成未登录。屏 20「去研究」是全仓唯一
    // 带 `user_game_id` 进来的入口,盒上打开的就是一块空盘(2026-09-14 调研 S1)。
    if (!id || userGameRef.current || !isAuthenticated) return;
    userGameRef.current = true;
    // 谱是空的、`loadFromSGF` 解析失败、或者请求本身就没成 —— 三条路都不留一块没有解释的
    // 空盘,说的是同一句(取不到就说取不到,和 kifu_id 那条分支同一个说法)。
    const failProvenance = () => setProvenance({
      label: t('research:user_game_failed', '这一局读不到'),
      backPath, backLabel: backTo.label,
    });
    UserGamesAPI.get(token, id).then(async (detail) => {
      if (!detail.sgf_content) { failProvenance(); return; }
      const r = board.loadFromSGF(detail.sgf_content);
      if (!r.success) {
        console.error('Failed to load user game for deep link:', r.error);
        failProvenance();
        return;
      }
      const head = detail.title
        || `${detail.player_black ?? t('research:black', '黑方')} vs ${detail.player_white ?? t('research:white', '白方')}`;
      const stamp = detail.game_date ?? detail.created_at;
      const when = stamp ? Date.parse(stamp) : NaN;
      setProvenance({
        label: `${t('research:from_my_games', '我的对局')}：${head}${Number.isNaN(when) ? '' : ` · ${whenLabel(when, t)}`}`,
        // `backPath` 不是 `backTo.path`:从屏 20 进来时带着 `task`,返回要回**这一份报告**而不是列表。
        // 盒上以前 provenance 永远是 null、返回键碰巧走的就是 `backPath`;这里修通后不许把它退回列表。
        backPath, backLabel: backTo.label,
      });

    }).catch((err) => {
      console.error('Failed to load user game for deep link:', err);
      failProvenance();
    });
  }, [searchParams, token, isAuthenticated]); // eslint-disable-line react-hooks/exhaustive-deps

  // 对局刚结束的「复盘本局」:`GamePage` 用 sessionStorage 交接(那局刚在本机下完,没有 id)。
  // key **进来就删** —— 所以**刷新之后这一支不再成立**:盘是空的、出处也没有,
  // 那时候还写「刚下完的这一局」就是假的,`provenance` 保持 null、副标题整行不渲染。
  const reviewRef = useRef(false);
  useEffect(() => {
    if (reviewRef.current) return;
    if (searchParams.get('user_game_id') || searchParams.get('kifu_id')) return;
    const store = getCurrentKioskActivityStorage();
    const sgf = store.getItem('kioskReviewSgf');
    if (!sgf) return;
    reviewRef.current = true;
    store.removeItem('kioskReviewSgf');
    board.loadFromSGF(sgf);
    // 这一条**只能**是 effect:出处的唯一来源是 sessionStorage 里那把随读随删的钥匙,
    // 渲染期读它就是在渲染期写外部状态。挂载时同步跑一次是对的。
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setProvenance({
      label: t('research:from_last_game', '刚下完的这一局'),
      backPath: '/kiosk/play', backLabel: t('play:title', '对弈'),
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const TOOLS: { value: BoardTool; label: React.ReactNode }[] = [
    { value: 'alternate', label: <><Icon name="arrows-clockwise" />{t('research:alternate', '交替')}</> },
    { value: 'black', label: <><span className="disc b" />{t('research:place_black', '摆黑')}</> },
    { value: 'white', label: <><span className="disc w" />{t('research:place_white', '摆白')}</> },
    { value: 'delete', label: <><Icon name="trash" />{t('research:delete', '删除')}</> },
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
  /* 规则名走查表,**未知值原样回显**。
     原来是一条三元链:非 japanese/korean 一律说「中国规则」—— 所以今天一局
     `RU[aga]` 早就被显示成「中国规则」了,而这一屏上那句话的全部意义就是
     「AI 是按什么规则算的」。加了 AI 赛规则(`RU[aga-button]`)之后只会更错。
     `ruleNameOf` 顺带做 wire → key 的反查:写进 SGF 的是 `aga-button`,
     表里的 key 是 `button`,只有这一条两边不同名。 */
  const rulesName = ruleNameOf(t, board.rules);
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

  const actions: KioskAction[] = [
    { key: 'open', icon: 'upload-simple', label: t('research:open', '打开'), onClick: board.openLocalSGF },
    { key: 'save', icon: 'floppy-disk', label: t('research:save', '保存'), onClick: board.saveLocalSGF },
    { key: 'pass', icon: 'hand-pointing', label: t('research:pass', '停一手'), onClick: board.handlePass },
    { key: 'clear', icon: 'eraser', label: t('research:clear', '清空'), onClick: () => setConfirmClear(true) },
    { key: 'report', icon: 'magnifying-glass', label: t('research:create_report', '创建复盘报告'), disabled: reportBusy, onClick: () => void handleCreateReport() },
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
            rejectOccupiedIntersections={board.boardTool !== 'delete'}
            nextColor={board.nextColor ?? undefined}
            /* 推荐和领地共用当前已确认结果，只切换显示。 */
            aiMarkers={markers}
            showAiMarkers={paid.showHints}
            showTerritory={showTerritory}
            /* 只有**这个局面自己**那张地图才画得出去。全局分析跑完之后会话里没有
               per-move 的 ownership ⇒ 这里恒为 null,而不是一路沿用开扫那一刻的那张。 */
            ownership={showTerritory && ownership?.key === positionKey ? ownership.grid : null}
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
        {(saveError || reportError) && <p role="alert">{saveError || reportError}</p>}
        <KioskPagebar
          testId="research-pagebar"
          backLabel={provenance?.backLabel ?? backTo.label}
          onBack={() => navigate(provenance?.backPath ?? backPath)}
          title={t('research:move_title', '研究 · 第 {n} 手').replace('{n}', String(moveNo))}
          sub={provenance?.label}
          /* §11 的那**一颗**页级图标键。领地是盘面视图叠加,和「翻转棋盘/全屏」同族。 */
          action={{
            icon: 'map-trifold',
            label: t('research:territory', '领地'),
            pressed: showTerritory,
            onClick: () => { void paid.toggle('ownership'); },
          }}
        />

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

        <KioskFold
          fold="ai"
          grow
          /* 表里 24 个候选而视口只露 8 行 —— 没有条子,后面那 16 行在触摸屏上就是不存在的。 */
          scrollbar
          bodyClassName={rowsError || !rows || rows.length === 0 ? undefined : 'aitab'}
          testId="research-ai"
          title={t('research:ai_after_move', 'AI 推荐 · 第 {n} 手之后').replace('{n}', String(moveNo))}
          value={headValue}
        >
          {rowsError ? (
            <div className="empty" data-testid="research-ai-error">
              <h4>{t('research:analysis_failed', '这一手算不出来')}</h4>
              <p>{rowsError}</p>
              <button type="button" className="kiosk-btn--pill" style={{ height: 44, fontSize: 20, marginTop: 8 }} disabled={paid.busy} onClick={() => { void paid.toggle('hints'); }}>{t('common:retry', '重试')}</button>
            </div>
          ) : rows === null ? (
            <div className="empty" data-testid="research-ai-pending">
              <h4>{paid.busy ? t('research:analyzing_move', '正在分析当前局面') : t('research:analysis_on_request', '按需分析当前局面')}</h4>
              <button type="button" className="kiosk-btn--pill" style={{ height: 44, fontSize: 20, marginTop: 8 }} disabled={paid.busy} onClick={() => { void paid.toggle('hints'); }}>{t('research:suggestions', '支招')}</button>
            </div>
          ) : rows.length === 0 ? (
            <div className="empty" data-testid="research-ai-none">
              <h4>{t('research:no_candidates', 'AI 没有给出候选着法')}</h4>
            </div>
          ) : (
            <>
              <button type="button" className="kiosk-btn--pill" style={{ height: 44, fontSize: 20, gridColumn: '1 / -1', marginBottom: 8 }} aria-pressed={paid.showHints} onClick={() => { void paid.toggle('hints'); }}>{t('research:suggestions', '支招')}</button>
              <AiRecommendRows rows={rows} />
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

      <ConsumptionQuoteDialog kiosk quote={paid.pendingQuote} busy={paid.busy} error={paid.error} onCancel={paid.cancel} onConfirm={() => void paid.confirm()} />
      <ConsumptionQuoteDialog kiosk quote={reportQuote?.quote ?? null} busy={quoteBusy} error={reportError} onCancel={cancelQuote}
        onConfirm={() => { void confirmQuote().then((task) => { if (task) navigate('/kiosk/report'); }).catch(() => undefined); }} />

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
