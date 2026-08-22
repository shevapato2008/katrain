import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import { BaipuAPI } from '../../api/baipuApi';
import { KifuAPI } from '../../api/kifuApi';
import { ReportsAPI, type ReportTaskMove, type ReportType } from '../../api/reportApi';
import { UserGamesAPI, type UserGameDetail, type UserGameSummary } from '../../api/userGamesApi';
import { useAuth } from '../../context/AuthContext';
import { toLibraryUserGameParams, toLocalUserGameParams } from '../../features/report/reportModel';
import { summarizeReportMoves, winrateSeries } from '../../features/report/reportStats';
import { useReportTasks } from '../../features/report/useReportTasks';
import { useTranslation } from '../../hooks/useTranslation';
import type { KifuAlbumSummary } from '../../types/kifu';
import { replayBaipuSteps, type BoardState } from '../../utils/baipuReplay';
import ReportImportMenu from '../components/report/ReportImportMenu';
import ReportLibraryImportDialog from '../components/report/ReportLibraryImportDialog';
import ReportLocalImportDialog, { type LocalImportPayload } from '../components/report/ReportLocalImportDialog';
import { ReviewWinratePlot } from '../components/report/ReviewWinratePlot';
import {
  outcomeLine, rowDisc, rowState, rowTitle, yourColor, type RowState,
} from '../components/report/reviewPresentation';
import { GoBoardSvg } from '../shell/GoBoardSvg';
import { Icon } from '../shell/icons';
import { KioskCard } from '../shell/KioskCard';
import { KioskConsoleRail } from '../shell/KioskConsoleRail';
import { KioskScrollZone } from '../shell/KioskScrollZone';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import type { StatusCell } from '../shell/KioskStatusCells';
import { interpolate } from '../utils/interpolate';
import { whenLabel } from '../utils/whenLabel';

/**
 * 屏 19 · 复盘 `/kiosk/report` —— L1 布局 A(镜像栏 296 + 16 + 右栏 680),**形态 2**:
 * 头尾固定,只有中间那条会长的「历史对局」自己滚。
 *
 * 这一屏是本轮改动最大的一屏:现状是**左盘 54% + 右列表 46%**,和稿子左右对调。
 *
 * ## 左栏装的不是实体盘镜像
 *
 * 规范 §5 的四个模块里,复盘这一格填的是「刚下完的那局是什么样」,不是「实体盘上正在
 * 发生什么」。所以它**不走 `KioskLayout` 的 `RAIL_ROUTES`** —— 那条路给的是共用的
 * `GoConsoleRail`(读 VisionContext),而这里的内容跟着页面里的选中状态走,外壳拿不到。
 * 两栏由本页自己拼,外壳只让路(`KioskLayout` 的 `SELF_LAYOUT_ROUTES`)。
 *
 * ## 三格是「妙手」不是「漏着」—— 2026-08-22 核过后端才敢这么写(计划 D4)
 *
 * 国象同一格 2026-07-28 把「妙手」撤成了「漏着」,理由是**它的分析跑在盒子自己身上**:
 * 单线程 12 万节点、13–16 层,同一局面能摆 45cp,噪声吃掉了判据。
 * **围棋这条线不是**:报告是 cron 离线跑的(`katrain/cron/jobs/report_analyze.py`),
 * 每手 500 或 2000 次计算,跟盒子算力无关;而且这个仓里已经有一份妙手口径
 * (`features/report/reportModel.ts:192`,`delta_score >= 2`),不用现发明。
 * ⇒ 照稿子写「妙手」。算式和出处见 `features/report/reportStats.ts`。
 *
 * ## 和稿子不一样的地方(每条都有理由,四图上会红)
 *
 * ① **行尾多了动作键。** 稿子的行尾只有一个状态标,而规范 §11 要求四种状态各有各的样子、
 *    且「开始 / 继续分析」要**就地干活不跳页**(Fan 2026-07-28)。国象稿子同一处画的就是
 *    「状态标 + 药丸键」。稿子这一屏是漏画,不是简化。
 * ② **组标题右端多了一个放大镜。** 稿子这一屏没画搜索,但**稿子自己的 `.sbox` 注释把复盘
 *    列进了「有搜索的四屏」**(`go-kiosk.tmpl.html:326`),而现状这条搜索是通的 ——
 *    是稿子漏画。常驻一条 44 的框会把列表视口从 168 压到 116,「露一半」当场破,
 *    所以做成开关:**收起时这一屏和稿子逐像素一样**。
 * ③ **第三张卡是能用的,不是「即将上线」。** 见 `ReportImportMenu` 头上那段。
 * ④ **选中的那一行有选中的样子。** 稿子没画,可稿子左栏写的是「选中这一局」——
 *    没有选中态,那三个字就没有出处。
 */

const PAGE_SIZE = 12;
const messageOf = (error: unknown, fallback: string) => (error instanceof Error ? error.message : fallback);

type ImportAction = 'save' | ReportType | null;

/** 存谱的时间戳。`created_at` 是这局什么时候记进库的 —— 列表按它倒序,行尾也念它。 */
const savedAt = (game: UserGameSummary): number | null => {
  const raw = game.created_at || game.game_date;
  if (!raw) return null;
  const ts = new Date(raw).getTime();
  return Number.isNaN(ts) ? null : ts;
};

export default function ReportsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { token, isAuthenticated, user } = useAuth();
  const { t } = useTranslation();
  const translationRef = useRef(t);
  translationRef.current = t;

  const page = Math.max(1, Number(searchParams.get('page')) || 1);
  const query = searchParams.get('q') || '';
  const [searchOpen, setSearchOpen] = useState(Boolean(query));
  const [searchInput, setSearchInput] = useState(query);

  const [games, setGames] = useState<UserGameSummary[]>([]);
  const [totalGames, setTotalGames] = useState(0);
  const [gamesLoading, setGamesLoading] = useState(Boolean(token));
  const [gamesError, setGamesError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const listRequestGenerationRef = useRef(0);

  const [selectedGameId, setSelectedGameId] = useState<string | null>(null);
  const [selectedGame, setSelectedGame] = useState<UserGameDetail | null>(null);
  const [board, setBoard] = useState<BoardState | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const detailRequestRef = useRef(0);

  const [moves, setMoves] = useState<ReportTaskMove[] | null>(null);
  const [movesLoading, setMovesLoading] = useState(false);
  const [movesError, setMovesError] = useState<string | null>(null);
  const movesRequestRef = useRef(0);

  const [localImportOpen, setLocalImportOpen] = useState(false);
  const [libraryImportOpen, setLibraryImportOpen] = useState(false);
  const [localImporting, setLocalImporting] = useState<ImportAction>(null);
  const [libraryImporting, setLibraryImporting] = useState<ImportAction>(null);
  const [localImportError, setLocalImportError] = useState<string | null>(null);
  const [libraryImportError, setLibraryImportError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const {
    reportStatesByGame, error: tasksError, clearError: clearTasksError,
    refresh: refreshTasks, createReport, retryReport,
  } = useReportTasks(isAuthenticated ? token : null);

  // ── 列表 ────────────────────────────────────────────────────────────────
  const loadGames = useCallback(async () => {
    const requestGeneration = ++listRequestGenerationRef.current;
    if (!token || !isAuthenticated) {
      if (requestGeneration === listRequestGenerationRef.current) setGamesLoading(false);
      return null;
    }
    setGamesLoading(true);
    setGamesError(null);
    try {
      const response = await UserGamesAPI.list(token, {
        page, page_size: PAGE_SIZE, q: query || undefined, sort: 'created_at_desc',
      });
      // 迟到的成功不许覆盖新结果 —— 搜索输入快过网络时,旧那批会盖掉刚回来的。
      if (requestGeneration !== listRequestGenerationRef.current) return null;
      setGames(response.items);
      setTotalGames(response.total);
      return response;
    } catch (error) {
      if (requestGeneration !== listRequestGenerationRef.current) return null;
      setGamesError(messageOf(error, translationRef.current('report:load_games_failed', '加载棋谱失败，请重试。')));
      return null;
    } finally {
      if (requestGeneration === listRequestGenerationRef.current) setGamesLoading(false);
    }
  }, [isAuthenticated, page, query, token]);

  useEffect(() => setSearchInput(query), [query]);
  useEffect(() => {
    void loadGames();
    return () => { listRequestGenerationRef.current += 1; };
  }, [loadGames]);

  useEffect(() => {
    if (games.length === 0) {
      setSelectedGameId(null);
      return;
    }
    setSelectedGameId((current) => (current && games.some(({ id }) => id === current) ? current : games[0].id));
  }, [games]);

  // ── 选中那一局:先拿 SGF,再让**后端**把它铺成一步一步 ───────────────────
  // 终局盘要减掉被提的子,而提子**不在前端算** —— `/baipu/load` 每一步给的 `removed[]`
  // 就是那份名单(`baipuApi.ts` 决定 ②)。屏 16 逐手回放用的是同一条路、同一个播放器。
  useEffect(() => {
    if (!token || !selectedGameId) return;
    if (selectedGame?.id === selectedGameId) return;
    const request = ++detailRequestRef.current;
    UserGamesAPI.get(token, selectedGameId)
      .then(async (game) => {
        if (request !== detailRequestRef.current) return;
        setSelectedGame(game);
        setDetailError(null);
        const size = game.board_size || 19;
        try {
          const loaded = await BaipuAPI.load({ sgf: game.sgf_content });
          if (request !== detailRequestRef.current) return;
          setBoard(replayBaipuSteps(loaded.steps, loaded.steps.length, loaded.board_size || size));
        } catch {
          // 谱读不出来时**画空盘并说明**,不要摆一盘不是这一局的子当装饰(D11)。
          if (request !== detailRequestRef.current) return;
          setBoard(null);
          setDetailError(translationRef.current('review:board_failed', '这一局的谱读不出来'));
        }
      })
      .catch((error: Error) => {
        if (request !== detailRequestRef.current) return;
        setSelectedGame(null);
        setBoard(null);
        setDetailError(messageOf(error, translationRef.current('report:preview_failed', '棋谱预览加载失败')));
      });
    return () => { detailRequestRef.current += 1; };
  }, [selectedGame?.id, selectedGameId, token]);

  // ── 选中那一局的报告逐手 ────────────────────────────────────────────────
  const selectedState: RowState | null = useMemo(() => {
    const game = games.find((g) => g.id === selectedGameId);
    if (!game) return null;
    return rowState(game, reportStatesByGame[game.id] || {});
  }, [games, reportStatesByGame, selectedGameId]);
  const completedTaskId = selectedState?.kind === 'analyzed' ? selectedState.taskId : null;

  useEffect(() => {
    if (!token || completedTaskId == null) {
      setMoves(null);
      return;
    }
    const request = ++movesRequestRef.current;
    setMovesLoading(true);
    ReportsAPI.getMoves(token, completedTaskId)
      .then((rows) => {
        if (request !== movesRequestRef.current) return;
        setMoves(rows);
        setMovesError(null);
      })
      .catch((error: Error) => {
        if (request !== movesRequestRef.current) return;
        setMoves(null);
        setMovesError(messageOf(error, translationRef.current('review:moves_failed', '报告读不出来')));
      })
      .finally(() => {
        if (request === movesRequestRef.current) setMovesLoading(false);
      });
    return () => { movesRequestRef.current += 1; };
  }, [completedTaskId, token]);

  // ── 左栏三格 ────────────────────────────────────────────────────────────
  const selectedSummary = games.find((g) => g.id === selectedGameId) ?? null;
  const mine = selectedSummary ? yourColor(selectedSummary, user?.username) : null;
  // 判不出「你」的时候按**黑方**算,并且把视角写进同步行 —— 不写的话
  // 「准确率 78%」说的是谁就成了一句谁也验证不了的话。
  const perspective: 'B' | 'W' = mine ?? 'B';
  const stats = useMemo(
    () => (moves ? summarizeReportMoves(moves, perspective) : null),
    [moves, perspective],
  );
  const points = useMemo(() => (moves ? winrateSeries(moves) : []), [moves]);

  const unanalyzed = t('review:cell_unanalyzed', '未分析');
  const cells: readonly StatusCell[] = [
    {
      label: t('review:accuracy', '准确率'),
      value: stats?.accuracy == null ? unanalyzed : `${Math.round(stats.accuracy)}%`,
      tone: 'good',
    },
    {
      label: t('review:mistakes', '失误'),
      value: stats == null ? unanalyzed : `${stats.mistakes} ${t('report:moves_unit', '手')}`,
      tone: 'warn',
    },
    {
      label: t('review:brilliants', '妙手'),
      value: stats == null ? unanalyzed : `${stats.brilliants} ${t('report:moves_unit', '手')}`,
      tone: 'good',
    },
  ];

  const railSync = (() => {
    if (!selectedSummary) return { left: t('review:rail_none', '还没有选中的对局'), right: '' };
    const title = rowTitle(selectedSummary, mine, t);
    const left = mine
      ? title
      : `${title} · ${interpolate(t('review:perspective', '{color}方视角'), {
        color: perspective === 'B' ? t('review:black', '黑') : t('review:white', '白'),
      })}`;
    const ts = savedAt(selectedSummary);
    return { left, right: ts == null ? '' : whenLabel(ts, t) };
  })();

  const plotEmpty = (() => {
    if (!selectedSummary) return t('review:plot_pick', '从下面挑一局');
    if (movesError) return movesError;
    if (movesLoading) return t('review:plot_loading', '正在读这一局的报告');
    if (completedTaskId == null) {
      return t('review:plot_unanalyzed', '这一局还没分析 —— 在下面「生成报告」里挑一档');
    }
    if (points.length < 2) return t('review:plot_thin', '报告里还没有算出来的手');
    return '';
  })();

  // ── 干活 ────────────────────────────────────────────────────────────────
  const createForGame = useCallback((game: UserGameSummary, reportType: ReportType) => (
    createReport({ userGameId: game.id, reportType, totalMoves: game.move_count })
  ), [createReport]);

  const updateLocation = useCallback((nextQuery: string, nextPage: number) => {
    const params: Record<string, string> = {};
    if (nextQuery) params.q = nextQuery;
    if (nextPage > 1) params.page = String(nextPage);
    setSearchParams(params);
  }, [setSearchParams]);

  const focusImportedGame = useCallback(async (game: UserGameDetail) => {
    setSelectedGameId(game.id);
    setSearchInput('');
    if (page !== 1 || query) setSearchParams({});
    else await loadGames();
  }, [loadGames, page, query, setSearchParams]);

  const handleLocalImport = useCallback(async (payload: LocalImportPayload, reportType?: ReportType) => {
    if (!token) return;
    setLocalImporting(reportType ?? 'save');
    setLocalImportError(null);
    try {
      const created = await UserGamesAPI.create(token, toLocalUserGameParams(payload));
      await focusImportedGame(created);
      if (reportType) await createForGame(created, reportType);
      setLocalImportOpen(false);
      setLocalImportError(null);
      await refreshTasks();
    } catch (error) {
      setLocalImportError(messageOf(error, translationRef.current('report:import_failed', '导入失败，请重试。')));
    } finally {
      setLocalImporting(null);
    }
  }, [createForGame, focusImportedGame, refreshTasks, token]);

  const handleLibraryImport = useCallback(async (album: KifuAlbumSummary, reportType?: ReportType) => {
    if (!token) return;
    setLibraryImporting(reportType ?? 'save');
    setLibraryImportError(null);
    try {
      const albumDetail = await KifuAPI.getAlbum(album.id);
      const created = await UserGamesAPI.create(token, toLibraryUserGameParams(album, albumDetail.sgf_content));
      await focusImportedGame(created);
      if (reportType) await createForGame(created, reportType);
      setLibraryImportOpen(false);
      setLibraryImportError(null);
      await refreshTasks();
    } catch (error) {
      setLibraryImportError(messageOf(error, translationRef.current('report:library_import_failed', '从棋谱库导入失败，请重试。')));
    } finally {
      setLibraryImporting(null);
    }
  }, [createForGame, focusImportedGame, refreshTasks, token]);

  const confirmDelete = useCallback(async () => {
    if (!token || !deleteTarget) return;
    const deletedId = deleteTarget;
    setDeleteLoading(true);
    setActionError(null);
    try {
      await UserGamesAPI.delete(token, deletedId);
      if (selectedGameId === deletedId) {
        setSelectedGameId(null);
        setSelectedGame(null);
        setBoard(null);
      }
      const next = await loadGames();
      await refreshTasks();
      if (next && next.items.length === 0 && page > 1 && next.total > 0) updateLocation(query, page - 1);
      setDeleteTarget(null);
    } catch (error) {
      setActionError(messageOf(error, translationRef.current('report:delete_failed', '删除失败，请重试。')));
    } finally {
      setDeleteLoading(false);
    }
  }, [deleteTarget, loadGames, page, query, refreshTasks, selectedGameId, token, updateLocation]);

  if (!isAuthenticated) {
    return (
      <div className="kiosk-side" data-testid="review-page">
        <div className="empty">
          <h4>{t('report:login_required', '请先登录后查看复盘。')}</h4>
        </div>
      </div>
    );
  }

  const totalPages = Math.max(1, Math.ceil(totalGames / PAGE_SIZE));
  const countLabel = query
    ? interpolate(t('review:matched_games', '搜到 {n} 局'), { n: totalGames })
    : interpolate(t('review:local_games', '本机 {n} 局'), { n: totalGames });

  return (
    <>
      <div className="kiosk-layout-l1" data-testid="review-page">
        <KioskConsoleRail
          title={t('review:rail_title', '选中这一局')}
          sub="Selected"
          board={(
            <GoBoardSvg
              size={selectedGame?.board_size || 19}
              black={board?.black ?? []}
              white={board?.white ?? []}
              last={board?.last}
              muted={board == null}
              label={t('review:rail_board', '选中那一局的终局盘')}
            />
          )}
          syncLeft={detailError ?? railSync.left}
          syncRight={railSync.right}
          statuses={cells}
        />

        <div className="kiosk-side">
          <div className="kiosk-side__fixed">
            <section className="kiosk-section">
              <KioskSecLabel zh={t('review:sec_winrate', '这一局的胜率')} en="Win rate" />
              <ReviewWinratePlot
                points={points}
                empty={plotEmpty}
                axisTop={`${t('review:black', '黑')} 100`}
                axisMid="50"
                axisBottom={`${t('review:white', '白')} 100`}
                label={t('review:plot_label', '逐手胜率，上方黑优、下方白优')}
              />
            </section>

            <KioskScrollZone
              grow
              className={searchOpen ? 'has-search' : undefined}
              resetKey={`${query}|${page}`}
              head={(
                <>
                  <KioskSecLabel
                    zh={t('review:sec_games', '历史对局')}
                    en="Games"
                    value={countLabel}
                    action={(
                      <button
                        type="button"
                        className="kiosk-seclabel__act"
                        aria-expanded={searchOpen}
                        aria-label={t('review:search_toggle', '搜历史对局')}
                        onClick={() => {
                          const next = !searchOpen;
                          setSearchOpen(next);
                          if (!next && query) updateLocation('', 1);
                        }}
                      >
                        <Icon name="magnifying-glass" />
                      </button>
                    )}
                  />
                  {searchOpen && (
                    <input
                      className="ksearch__box rvsearch"
                      data-testid="review-search"
                      type="search"
                      value={searchInput}
                      placeholder={t('report:search_placeholder', '按棋手、标题或赛事搜索')}
                      aria-label={t('review:search_toggle', '搜历史对局')}
                      onChange={(event) => setSearchInput(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter') updateLocation(searchInput.trim(), 1);
                      }}
                    />
                  )}
                </>
              )}
            >
              {gamesError ? (
                <div className="empty">
                  <h4>{t('review:list_failed', '对局列表读不到')}</h4>
                  <p>{gamesError}</p>
                  <button type="button" className="kiosk-btn kiosk-btn--pill pill" onClick={() => void loadGames()}>
                    {t('kifu:retry', '重试')}
                  </button>
                </div>
              ) : gamesLoading && games.length === 0 ? (
                <div className="empty"><h4>{t('review:list_loading', '正在读你的对局')}</h4></div>
              ) : games.length === 0 ? (
                <div className="empty">
                  <h4>{query ? t('review:no_match', '没有对得上的对局') : t('review:no_games', '还没有下过的棋')}</h4>
                  <p>
                    {query
                      ? t('review:no_match_hint', '换棋手名或赛事名再试。')
                      : t('review:no_games_hint', '下完一局会自动记在这里；也可以从下面导入一份 SGF。')}
                  </p>
                </div>
              ) : (
                <div className="kiosk-rows" data-testid="review-rows">
                  {games.map((game) => (
                    <ReviewRow
                      key={game.id}
                      game={game}
                      state={rowState(game, reportStatesByGame[game.id] || {})}
                      selected={game.id === selectedGameId}
                      username={user?.username}
                      t={t}
                      onSelect={() => setSelectedGameId(game.id)}
                      onOpenReport={(taskId) => navigate(`/kiosk/report/${taskId}`)}
                      onResume={(taskId) => { void retryReport(taskId).catch(() => undefined); }}
                      onDelete={() => setDeleteTarget(game.id)}
                    />
                  ))}
                </div>
              )}
              {totalPages > 1 && (
                <div className="kpager" data-testid="review-pager">
                  <button
                    type="button" className="kiosk-btn kiosk-btn--pill"
                    disabled={page <= 1} onClick={() => updateLocation(query, page - 1)}
                  >
                    {t('kifu:prev_page', '上一页')}
                  </button>
                  <span>{page} / {totalPages}</span>
                  <button
                    type="button" className="kiosk-btn kiosk-btn--pill"
                    disabled={page >= totalPages} onClick={() => updateLocation(query, page + 1)}
                  >
                    {t('kifu:next_page', '下一页')}
                  </button>
                </div>
              )}
            </KioskScrollZone>

            <section className="kiosk-section">
              <KioskSecLabel
                zh={t('review:sec_report', '生成报告')}
                en="Report"
                value={t('review:two_tiers', '两档：500 / 2000 次计算')}
              />
              {(actionError || tasksError) && (
                <p className="rverr" role="status">
                  {actionError || tasksError}
                  <button
                    type="button" className="kiosk-btn kiosk-btn--pill"
                    onClick={() => { setActionError(null); clearTasksError(); void refreshTasks(); }}
                  >
                    {t('kifu:retry', '重试')}
                  </button>
                </p>
              )}
              <div className="kiosk-cards" data-testid="review-cards">
                <KioskCard
                  title={t('review:tier_standard', '标准')}
                  sub={t('review:tier_standard_sub', '每手算 500 次')}
                  icon="lightbulb"
                  disabled={!selectedSummary}
                  onClick={() => {
                    if (!selectedSummary) return;
                    setActionError(null);
                    void createForGame(selectedSummary, 'normal').catch(() => undefined);
                  }}
                />
                <KioskCard
                  title={t('review:tier_deep', '精读')}
                  sub={t('review:tier_deep_sub', '每手算 2000 次 · 慢四倍')}
                  icon="magnifying-glass"
                  disabled={!selectedSummary}
                  onClick={() => {
                    if (!selectedSummary) return;
                    setActionError(null);
                    void createForGame(selectedSummary, 'deep').catch(() => undefined);
                  }}
                />
                <ReportImportMenu
                  onImportLocal={() => { setLocalImportError(null); setLocalImportOpen(true); }}
                  onImportLibrary={() => { setLibraryImportError(null); setLibraryImportOpen(true); }}
                />
              </div>
            </section>
          </div>
        </div>
      </div>

      <ReportLocalImportDialog
        open={localImportOpen}
        loading={localImporting !== null}
        error={localImportError}
        onClose={() => { setLocalImportError(null); setLocalImportOpen(false); }}
        onSubmit={handleLocalImport}
      />
      <ReportLibraryImportDialog
        open={libraryImportOpen}
        loading={libraryImporting !== null}
        error={libraryImportError}
        onClose={() => { setLibraryImportError(null); setLibraryImportOpen(false); }}
        onImport={handleLibraryImport}
      />
      {deleteTarget !== null && (
        <div className="rvconfirm" role="dialog" aria-modal="true" aria-label={t('report:delete_confirm_title', '确认删除棋谱')}>
          <div className="empty">
            <h4>{t('report:delete_confirm_title', '确认删除棋谱')}</h4>
            <p>{t('report:delete_confirm_body', '删除后将无法恢复，关联复盘数据也会一并删除。')}</p>
            <div className="rvconfirm__row">
              <button
                type="button" className="kiosk-btn kiosk-btn--pill"
                disabled={deleteLoading} onClick={() => setDeleteTarget(null)}
              >
                {t('common:cancel', '取消')}
              </button>
              <button
                type="button" className="kiosk-btn kiosk-btn--pill rvdanger"
                disabled={deleteLoading} onClick={() => void confirmDelete()}
              >
                {t('report:confirm_delete', '确认删除')}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

/**
 * 一行 = 一局。**左半整块是「选中」的靶,行尾是这一行自己的动作** ——
 * 「跳转和干活分在两个手势上」(Fan 2026-07-28)。
 * 整行做不成一个 `<button>`:按钮里套按钮是非法 DOM。
 */
function ReviewRow({ game, state, selected, username, t, onSelect, onOpenReport, onResume, onDelete }: {
  game: UserGameSummary;
  state: RowState;
  selected: boolean;
  username?: string | null;
  t: (key: string, fallback?: string) => string;
  onSelect: () => void;
  onOpenReport: (taskId: number) => void;
  onResume: (taskId: number) => void;
  onDelete: () => void;
}) {
  const mine = yourColor(game, username);
  const ts = savedAt(game);
  // 没下完的那句话自己就带着手数(「下到第 22 手就退出了」),再挂一段「22 手」是同一个数说两遍。
  const sub = [
    outcomeLine(game, mine, t),
    game.result ? `${game.move_count} ${t('report:moves_unit', '手')}` : null,
    ts == null ? null : whenLabel(ts, t),
  ].filter(Boolean).join(' · ');

  return (
    <div className="kiosk-row" data-testid="review-row" data-selected={selected ? 'true' : 'false'} data-state={state.kind}>
      <button type="button" className="rvpick" onClick={onSelect} aria-pressed={selected}>
        <span className={`disc ${rowDisc(mine)}`} aria-hidden="true" />
        <span className="kiosk-row__t">
          <b>{rowTitle(game, mine, t)}</b>
          <em>{sub}</em>
        </span>
      </button>
      <span className="kiosk-row__end">
        {state.kind === 'analyzed' && (
          <>
            <span className="kiosk-tag kiosk-tag--win">{t('review:tag_analyzed', '已分析')}</span>
            <button type="button" className="kiosk-btn kiosk-btn--pill" onClick={() => onOpenReport(state.taskId)}>
              {t('review:open_report', '查看报告')}
            </button>
          </>
        )}
        {state.kind === 'running' && (
          <>
            <span className="kiosk-tag">
              {interpolate(t('review:tag_running', '正在分析 {a}/{b}'), { a: state.analyzed, b: state.total })}
            </span>
            <span className="rvprog" aria-hidden="true">
              <i style={{ width: `${state.total > 0 ? Math.min(100, (state.analyzed / state.total) * 100) : 0}%` }} />
            </span>
          </>
        )}
        {state.kind === 'partial' && (
          <>
            <span className="kiosk-tag kiosk-tag--warn">
              {interpolate(t('review:tag_partial', '只算到 {a}/{b}'), { a: state.analyzed, b: state.total })}
            </span>
            <button type="button" className="kiosk-btn kiosk-btn--pill" onClick={() => onResume(state.taskId)}>
              {t('review:resume_analysis', '继续分析')}
            </button>
          </>
        )}
        {state.kind === 'failed' && (
          <>
            <span className="kiosk-tag kiosk-tag--bad">{t('review:tag_failed', '分析失败')}</span>
            <button type="button" className="kiosk-btn kiosk-btn--pill" onClick={() => onResume(state.taskId)}>
              {t('kifu:retry', '重试')}
            </button>
          </>
        )}
        {state.kind === 'unanalyzed' && (
          <span className="kiosk-tag">{t('review:tag_unanalyzed', '未分析')}</span>
        )}
        {state.kind === 'unfinished' && (
          <span className="kiosk-tag">{t('review:tag_unfinished', '未终局')}</span>
        )}
        {/* 删除只挂在**选中**的那一行上。稿子的行尾只有一个状态标,而删除是一条不可逆的操作 ——
            五十二高的行上并排三个可点的东西,误触的是最不能误触的那个。
            (`kiosk-shell/icons/` 里没有 trash:那 41 对图标由 MANIFEST 钉着,
             为一个按钮往共享资产包里塞一份新二进制不划算,所以这里用文字。) */}
        {selected && (
          <button type="button" className="kiosk-btn kiosk-btn--pill rvdanger" onClick={onDelete}>
            {t('review:delete_game', '删除')}
          </button>
        )}
      </span>
    </div>
  );
}
