import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import CompactPagination from '../../components/CompactPagination';
import './personalGamesReviewed.css';
import { BaipuAPI } from '../../api/baipuApi';
import { KifuAPI } from '../../api/kifuApi';
import { ReportsAPI, type ReportTaskMove, type ReportType } from '../../api/reportApi';
import {
  UserGamesAPI, type DataAuthority, type UserGameDetail, type UserGameSummary,
} from '../../api/userGamesApi';
import { useAuth } from '../../context/AuthContext';
import { toLibraryUserGameParams } from '../../features/report/reportModel';
import { summarizeReportMoves } from '../../features/report/reportStats';
import { useReportTasks } from '../../features/report/useReportTasks';
import { useTranslation } from '../../hooks/useTranslation';
import type { KifuAlbumSummary } from '../../types/kifu';
import { replayBaipuSteps, type BoardState } from '../../utils/baipuReplay';
import { cacheBackedReadFailureKind, requestFailureKind, type RequestFailureKind } from '../../utils/requestFailure';
import ReportImportMenu from '../components/report/ReportImportMenu';
import ReportLibraryImportDialog from '../components/report/ReportLibraryImportDialog';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import {
  failureLine, failureReason, historyCardTitle, historyResult, isPlaySource, outcomeLine, rowState, rowTitle, yourColor, type RowState,
} from '../components/report/reviewPresentation';
import { GoBoardSvg } from '../shell/GoBoardSvg';
import { Icon } from '../shell/icons';
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
 * 每手 500 或 2000 次计算,跟盒子算力无关;判级在服务端(`katrain/core/move_grade.yaml` 七档)。
 * ⇒ 照稿子写「妙手」。2026-09-14 起两格与屏 20 走同一条判级管线,见 `features/report/reportStats.ts`。
 *
 * ## 和稿子不一样的地方(每条都有理由,四图上会红)
 *
 * ① **行尾多了动作键。** 稿子的行尾只有一个状态标,而规范 §11 要求四种状态各有各的样子、
 *    且「开始 / 继续分析」要**就地干活不跳页**(Fan 2026-07-28)。国象稿子同一处画的就是
 *    「状态标 + 药丸键」。稿子这一屏是漏画,不是简化。
 * ② **历史搜索默认可见。** 标题右端的放大镜仍可收起它,收起时清掉搜索条件。
 * ③ **第三张卡是能用的,不是「即将上线」。** 见 `ReportImportMenu` 头上那段。
 * ④ **选中的那一行有选中的样子。** 稿子没画,可稿子左栏写的是「选中这一局」——
 *    没有选中态,那三个字就没有出处。
 */

const PAGE_SIZE = 20;

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
  // Keep the existing history search visible on entry. The header icon remains a compact collapse control.
  const [searchOpen, setSearchOpen] = useState(true);
  const [searchInput, setSearchInput] = useState(query);

  const [games, setGames] = useState<UserGameSummary[]>([]);
  const [totalGames, setTotalGames] = useState(0);
  /**
   * **这个 `total` 是谁数的。** 盒子在线时列表和总数来自云端(跨设备),
   * 离线时才是本机那一份 —— 两者在屏上长得一模一样。
   * 老服务端不带这一格 ⇒ `null` = 不知道,而**不知道要退到最保守的那句话**。
   */
  const [authority, setAuthority] = useState<DataAuthority | null>(null);
  // 初值判 `isAuthenticated` 不判 `token`:盒上 token 恒为 null,判 token 时首帧 gamesLoading=false、
  // games=[],列表回来之前会先闪一帧「还没有下过的棋」(2026-09-14 调研 N7)。
  // 不配单测:jsdom 的 render 包在 act 里,effect 在断言前已经跑完,「effect 之前那一帧」测不到。
  const [gamesLoading, setGamesLoading] = useState(isAuthenticated);
  /** 列表读不到的**原因类别**。存类别不存原文:原文在盒上断网时是 `Request failed 503: {…}`。 */
  const [gamesFailure, setGamesFailure] = useState<RequestFailureKind | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const listRequestGenerationRef = useRef(0);

  const [selectedGameId, setSelectedGameId] = useState<string | null>(null);
  const [selectedGame, setSelectedGame] = useState<UserGameDetail | null>(null);
  const [board, setBoard] = useState<(BoardState & { gameId: string }) | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const detailRequestRef = useRef(0);

  const [moves, setMoves] = useState<ReportTaskMove[] | null>(null);
  const movesRequestRef = useRef(0);

  const [libraryImportOpen, setLibraryImportOpen] = useState(false);
  const [libraryImporting, setLibraryImporting] = useState<ImportAction>(null);
  const [libraryImportError, setLibraryImportError] = useState<string | null>(null);
  const [reportMenuOpen, setReportMenuOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const {
    reportStatesByGame, error: tasksError, errorKind: tasksErrorKind, clearError: clearTasksError,
    refresh: refreshTasks, createReport, retryReport,
  } = useReportTasks(token, isAuthenticated);

  // 屏上只说分出来的类别,原文不印 —— 但排障时总得有个地方能看见它。
  useEffect(() => {
    if (tasksError != null) console.warn('[review] report tasks', tasksError);
  }, [tasksError]);

  // ── 列表 ────────────────────────────────────────────────────────────────
  const loadGames = useCallback(async () => {
    const requestGeneration = ++listRequestGenerationRef.current;
    if (!isAuthenticated) {
      if (requestGeneration === listRequestGenerationRef.current) setGamesLoading(false);
      return null;
    }
    setGamesLoading(true);
    setGamesFailure(null);
    try {
      const response = await UserGamesAPI.list(token, {
        page, page_size: PAGE_SIZE, q: query || undefined, sort: 'created_at_desc',
      });
      // 迟到的成功不许覆盖新结果 —— 搜索输入快过网络时,旧那批会盖掉刚回来的。
      if (requestGeneration !== listRequestGenerationRef.current) return null;
      setGames(response.items);
      setTotalGames(response.total);
      setAuthority(response.authority ?? null);
      return response;
    } catch (error) {
      if (requestGeneration !== listRequestGenerationRef.current) return null;
      // 屏上只说分出来的类别,原文不上屏 —— 但排障时总得有个地方能看见它。
      console.warn('[review] list', error);
      setGamesFailure(requestFailureKind(error));
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
    if (!isAuthenticated || !selectedGameId) return;
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
          setBoard({ ...replayBaipuSteps(loaded.steps, loaded.steps.length, loaded.board_size || size), gameId: game.id });
        } catch {
          // 谱读不出来时**画空盘并说明**,不要摆一盘不是这一局的子当装饰(D11)。
          if (request !== detailRequestRef.current) return;
          setBoard(null);
          setDetailError(translationRef.current('review:board_failed', '这一局的谱读不出来'));
        }
      })
      .catch((error: Error) => {
        if (request !== detailRequestRef.current) return;
        console.warn('[review] preview', error);
        setSelectedGame(null);
        setBoard(null);
        // 预览读的是 GET /user-games/{id}:盒上云端失败会退本机缓存,缓存没有也回 404 ⇒ 404 不能说成「已经不在了」。
        setDetailError(failureLine(translationRef.current('report:preview_failed', '棋谱预览加载失败'), cacheBackedReadFailureKind(error), translationRef.current));
      });
    return () => { detailRequestRef.current += 1; };
  }, [isAuthenticated, selectedGameId, token]);

  // ── 选中那一局的报告逐手 ────────────────────────────────────────────────
  const selectedState: RowState | null = useMemo(() => {
    const game = games.find((g) => g.id === selectedGameId);
    if (!game) return null;
    return rowState(game, reportStatesByGame[game.id] || {});
  }, [games, reportStatesByGame, selectedGameId]);
  const completedTaskId = selectedState?.kind === 'analyzed' ? selectedState.taskId : null;

  useEffect(() => {
    if (!isAuthenticated || completedTaskId == null) {
      setMoves(null);
      return;
    }
    const request = ++movesRequestRef.current;
    ReportsAPI.getMoves(token, completedTaskId)
      .then((rows) => {
        if (request !== movesRequestRef.current) return;
        setMoves(rows);
      })
      .catch((error: Error) => {
        if (request !== movesRequestRef.current) return;
        console.warn('[review] moves', error);
        setMoves(null);
      });
    return () => { movesRequestRef.current += 1; };
  }, [completedTaskId, isAuthenticated, token]);

  // ── 左栏三格 ────────────────────────────────────────────────────────────
  const selectedBoard = board?.gameId === selectedGameId ? board : null;
  const selectedSummary = games.find((g) => g.id === selectedGameId) ?? null;
  const mine = selectedSummary ? yourColor(selectedSummary, user?.username) : null;
  // 判不出「你」的时候按**黑方**算,并且把视角写进同步行 —— 不写的话
  // 「准确率 78%」说的是谁就成了一句谁也验证不了的话。
  const perspective: 'B' | 'W' = mine ?? 'B';
  const stats = useMemo(
    () => (moves ? summarizeReportMoves(moves, perspective) : null),
    [moves, perspective],
  );

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

  const handleLibraryImport = useCallback(async (album: KifuAlbumSummary, reportType?: ReportType) => {
    if (!isAuthenticated) return;
    setLibraryImporting(reportType ?? 'save');
    setLibraryImportError(null);
    // `created` 记住的是「对局存上了没有」;报告失败不能让用户重复导入已保存的对局。
    let created: UserGameDetail | null = null;
    try {
      const albumDetail = await KifuAPI.getAlbum(album.id);
      created = await UserGamesAPI.create(token, toLibraryUserGameParams(album, albumDetail.sgf_content));
      await focusImportedGame(created);
      if (reportType) await createForGame(created, reportType);
      setLibraryImportOpen(false);
      setLibraryImportError(null);
      await refreshTasks();
    } catch (error) {
      console.warn('[review] import-library', error);
      if (created) {
        // 导入本身成功了 —— 建报告那一步失败已经由 `useReportTasks.createReport` 落到
        // 「生成报告」告警行,这里不重复说一遍。
        setLibraryImportOpen(false);
        setLibraryImportError(null);
      } else {
        // 这个 catch 前面还有 `KifuAPI.getAlbum`:今天它抛的错不带 status ⇒ 那一步失败落 other、只说前半句。
        // kifu 赛道 T6 改抛 ApiError(status) 后自动分得出;本赛道不改 kifuApi.ts(归 kifu 赛道,改了必冲突)。
        setLibraryImportError(failureLine(translationRef.current('report:library_import_failed', '从棋谱库导入失败'), requestFailureKind(error), translationRef.current));
      }
    } finally {
      setLibraryImporting(null);
    }
  }, [createForGame, focusImportedGame, isAuthenticated, refreshTasks, token]);

  const confirmDelete = useCallback(async () => {
    if (!isAuthenticated || !deleteTarget) return;
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
      console.warn('[review] delete', error);
      setActionError(failureLine(translationRef.current('report:delete_failed', '删除对局失败'), requestFailureKind(error), translationRef.current));
    } finally {
      setDeleteLoading(false);
    }
  }, [deleteTarget, isAuthenticated, loadGames, page, query, refreshTasks, selectedGameId, token, updateLocation]);

  if (!isAuthenticated) {
    return (
      <div className="kiosk-side" data-testid="review-page">
        <div className="empty">
          <h4>{t('report:login_required', '请先登录后查看和生成复盘报告。')}</h4>
        </div>
      </div>
    );
  }

  const totalPages = Math.max(1, Math.ceil(totalGames / PAGE_SIZE));
  // 列表读不到时的原因。**一整张列表不会「已经不在了」** —— `not_found` 只在单局取谱时才成立
  // (那局被删了),对列表本身没有意义,这里不说。
  const gamesFailureReason = gamesFailure && gamesFailure !== 'not_found' ? failureReason(gamesFailure, t) : '';
  /**
   * **没下完的局不给生成报告。** 半局的报告本身没意义;而且离线 KataGo 把残局算完再回去
   * 接着下,那是一条真作弊通道。
   * ⚠️ 判别位是「**这局结束了没有**」——**不是「算不算分」**。用 `isRated` 去管它,
   * 就又变成一个 prop 兼管两件事、逼调用方撒谎(计分局下完了照样该有报告,
   * 国象稿子明写两者进的是同一条复盘线)。
   * 「未终局」只由 `rowState` 给**对弈局**(`isPlaySource`)—— 导入的谱、棋谱库、研究存档
   * 没写结果不算没下完,没有「回去接着下」这回事,照样能分析(P14)。这里不另写一份判定。
   */
  const canAnalyzeSelected = Boolean(selectedSummary) && selectedState?.kind !== 'unfinished';
  /**
   * ⚠️ **「本机 N 局」以前是句假话。** 盒子在线时 `user_games_list` 走的是云端
   * (`RepositoryDispatcher.user_games_list`),这个 `total` 是**跨设备**的总数,
   * 而标签写死着「本机」—— 只有断网那一档它才碰巧是真的,
   * 而用户没有任何办法分辨自己看的是哪一档。
   *
   * 现在跟着 `authority` 走,**只有确知来自云端时才敢说「共」**:
   * `null`(老服务端不带这一格)退回「本机」—— 不知道就说小的那个。
   * 搜索/筛选那两句本来就不声称完整,不动。
   */
  const countLabel = query
    ? interpolate(t('review:matched_games', '搜到 {n} 局'), { n: totalGames })
    : authority === 'cloud'
        ? interpolate(t('review:all_games', '共 {n} 局'), { n: totalGames })
        : interpolate(t('review:local_games', '本机 {n} 局'), { n: totalGames });

  return (
    <>
      <div className="kiosk-layout-l1 personal-games-reviewed" data-testid="review-page">
        <div className="personal-games-preview">
        <KioskConsoleRail
          title={t('review:rail_title', '选中这一局')}
          sub="Selected"
          board={(
            <GoBoardSvg
              size={selectedGame?.board_size || 19}
              black={selectedBoard?.black ?? []}
              white={selectedBoard?.white ?? []}
              last={selectedBoard?.last}
              muted={selectedBoard == null}
              label={t('review:rail_board', '选中那一局的终局盘')}
            />
          )}
          syncLeft={detailError ?? railSync.left}
          syncRight={railSync.right}
          statuses={cells}
        />
        <div className="personal-games-preview__actions">
          <button type="button" className="kiosk-btn" disabled={!selectedGame || selectedGame.id !== selectedGameId || !selectedBoard}
            onClick={() => navigate(`/kiosk/research?user_game_id=${encodeURIComponent(selectedGameId!)}`)}>{t('review:open_replay', '查看棋谱')}</button>
          <button type="button" className="kiosk-btn personal-games-report-trigger" aria-haspopup="menu" aria-expanded={reportMenuOpen} disabled={!selectedSummary}
            onClick={() => setReportMenuOpen(value => !value)}>{t('review:analysis_report', '分析报告')} <Icon name="caret-down" /></button>
          {reportMenuOpen && <div className="personal-games-tier-menu" role="group" aria-label="分析报告档位">
            {(['normal', 'deep'] as const).map(tier => {
              const status = selectedGameId ? reportStatesByGame[selectedGameId] : undefined;
              const completed = tier === 'normal' ? status?.completedNormal : status?.completedDeep;
              const active = tier === 'normal' ? status?.activeNormal : status?.activeDeep;
              const failed = tier === 'normal' ? status?.failedNormal : status?.failedDeep;
              return <button key={tier} type="button" className="kiosk-btn" disabled={(!completed && Boolean(active)) || !canAnalyzeSelected}
                onClick={() => {
                  if (completed) navigate(`/kiosk/report/${completed.id}`);
                  else if (failed) void retryReport(failed.id).catch(() => undefined);
                  else if (selectedSummary) void createForGame(selectedSummary, tier).catch(() => undefined);
                  setReportMenuOpen(false);
                }}><strong>{completed ? t('review:tier_view', '查看') : active ? t('review:tier_working', '分析中') : failed ? t('kifu:retry', '重试') : t('review:tier_generate', '生成')}{tier === 'normal' ? t('report:normal', '普通报告') : t('report:deep', '深度报告')}</strong><span>每手 {tier === 'normal' ? 500 : 2000} 次</span></button>;
            })}
          </div>}
        </div>
        </div>

        <div className="kiosk-side">
          <div className="kiosk-side__fixed">
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
                        aria-label={t('review:history_search_toggle', '显示或收起历史搜索')}
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
                    <div className="rvfind">
                      <input
                        className="ksearch__box rvsearch"
                        data-testid="review-search"
                        type="search"
                        value={searchInput}
                        placeholder={t('report:search_placeholder', '按棋手、标题或赛事搜索')}
                        aria-label={t('report:search_placeholder', '按棋手、标题或赛事搜索')}
                        onChange={(event) => setSearchInput(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter') updateLocation(searchInput.trim(), 1);
                        }}
                      />
                    </div>
                  )}
                </>
              )}
            >
              {gamesFailure ? (
                <div className="empty">
                  <h4>{t('review:list_failed', '对局列表读不到')}</h4>
                  {gamesFailureReason && <p>{gamesFailureReason}</p>}
                  <button type="button" className="kiosk-btn kiosk-btn--pill pill" onClick={() => void loadGames()}>
                    {t('kifu:retry', '重试')}
                  </button>
                </div>
              ) : gamesLoading && games.length === 0 ? (
                <div className="empty"><h4>{t('review:list_loading', '正在读你的对局')}</h4></div>
              ) : games.length === 0 ? (
                <div className="empty">
                  {/* 三种「没有」是三句话:搜不到 / 这一类还没有 / 一局都没下过。
                      筛在「面对面」上而结果为空时说「还没有下过的棋」,是把筛选的后果
                      栽到用户头上 —— 他可能下过一百局人机。 */}
                  <h4>
                    {query
                      ? t('review:no_match', '没有对得上的对局')
                      : t('review:no_games', '还没有下过的棋')}
                  </h4>
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
                      onDelete={() => setDeleteTarget(game.id)}
                    />
                  ))}
                </div>
              )}
            </KioskScrollZone>
            <div className="personal-games-pagination"><CompactPagination showEdgeButtons page={page} totalPages={totalPages} disabled={gamesLoading || Boolean(gamesFailure)}
              onPageChange={next => updateLocation(query, next)} /></div>

            <section className="kiosk-section">
              <KioskSecLabel
                zh={t('review:sec_report', '生成报告')}
                en="Report"
                value={t('review:two_tiers', '两档：500 / 2000 次计算')}
              />
              {(actionError || tasksError) && (
                <p className="rverr" role="status">
                  {/* 报告任务那条错可能来自列表、创建或重试,前半句说不准是哪件 ⇒ 前半句固定说
                      「报告任务出错了」,后半句按类别接原因;分不出原因时只说前半句,不能只剩
                      一句「已经不在了」没有主语。不印原文(盒上断网时是 Request failed 503: {…})。 */}
                  {actionError || failureLine(t('review:tasks_failed', '报告任务出错了'), tasksErrorKind ?? 'other', t)}
                  <button
                    type="button" className="kiosk-btn kiosk-btn--pill"
                    onClick={() => { setActionError(null); clearTasksError(); void refreshTasks(); }}
                  >
                    {t('kifu:retry', '重试')}
                  </button>
                </p>
              )}
              <div className="kiosk-cards" data-testid="review-cards">
                <ReportImportMenu
                  onImportLibrary={() => { setLibraryImportError(null); setLibraryImportOpen(true); }}
                />
              </div>
            </section>
          </div>
        </div>
      </div>

      <ReportLibraryImportDialog
        open={libraryImportOpen}
        loading={libraryImporting !== null}
        error={libraryImportError}
        onClose={() => { setLibraryImportError(null); setLibraryImportOpen(false); }}
        onImport={handleLibraryImport}
      />
      {/* 删除确认框:标题 / 正文 / 危险键三条**与 galaxy 同一组 key**
          (`galaxy/pages/report/ReportsPage.tsx:599-611`)—— 同一个对话框、同一个动作,
          两处说的话必须是同一句。
          危险键原来是 kiosk 自铸的 `report:confirm_delete`,fallback「确认删除」,
          而标题的 PO 也是「确认删除」⇒ 标题和按钮会是同四个字。当时的躲法是把标题写长成
          「确认删除棋谱」,那又让屏上冒出一个稿子从没用过的词。改用 galaxy 已有的
          `report:delete_game` 之后碰撞自然消失,自铸那颗键也就没有使用者了。 */}
      {deleteTarget !== null && (
        <div className="rvconfirm" role="dialog" aria-modal="true" aria-label={t('report:delete_confirm_title', '确认删除')}>
          <div className="empty">
            <h4>{t('report:delete_confirm_title', '确认删除')}</h4>
            <p>{t('report:delete_confirm_body', '删除后对局及所有关联分析数据将不可恢复，确认删除？')}</p>
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
                {t('report:delete_game', '删除对局')}
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
function ReviewRow({ game, state, selected, username, t, onSelect, onDelete }: {
  game: UserGameSummary;
  state: RowState;
  selected: boolean;
  username?: string | null;
  t: (key: string, fallback?: string) => string;
  onSelect: () => void;
  onDelete: () => void;
}) {
  const mine = yourColor(game, username);
  const ts = savedAt(game);
  // 没下完的那句话自己就带着手数(「下到第 22 手就退出了」),再挂一段「22 手」是同一个数说两遍。
  // 只有对弈局会念那一句;导入的谱没写结果时念「谱里没写结果」,手数照常挂在后面。
  const sub = [
    outcomeLine(game, mine, t),
    game.result || !isPlaySource(game.source) ? `${game.move_count} ${t('report:moves_unit', '手')}` : null,
    ts == null ? null : whenLabel(ts, t),
  ].filter(Boolean).join(' · ');

  return (
    <div className="personal-game-row" data-testid="review-row" data-selected={selected ? 'true' : 'false'} data-state={state.kind}>
      <button type="button" className="kiosk-row rvpick personal-game-card" onClick={onSelect} aria-pressed={selected} aria-label={rowTitle(game, mine, t)} title={sub}>
        <span className="personal-game-description">{sub}</span>
        <span className="personal-game-head">
          <Icon name="books" /><b>{historyCardTitle(game, mine, t)}</b>
          <span className="personal-game-state">{state.kind === 'analyzed' ? t('review:tag_analyzed', '已分析')
            : state.kind === 'running' ? interpolate(t('review:tag_running', '正在分析 {a}/{b}'), { a: state.analyzed, b: state.total })
            : state.kind === 'partial' ? interpolate(t('review:tag_partial', '只算到 {a}/{b}'), { a: state.analyzed, b: state.total })
            : state.kind === 'failed' ? t('review:tag_failed', '分析失败')
            : state.kind === 'unfinished' ? t('review:tag_unfinished', '未终局') : t('review:tag_unanalyzed', '未分析')}</span>
          <small>{game.game_date || (ts == null ? '—' : whenLabel(ts, t))} · {game.move_count} {t('report:moves_unit', '手')}</small>
        </span>
        <span className="personal-game-match">
          <span><i className="personal-game-stone" />{game.player_black || t('game:black_side', '黑方')}</span>
          <em>{historyResult(game, t)}</em>
          <span>{game.player_white || t('game:white_side', '白方')}<i className="personal-game-stone is-white" /></span>
        </span>
      </button>
      {selected && game.source !== 'kifu_library' && (
        <button type="button" className="personal-game-delete" aria-label={t('review:delete_game', '删除对局')} title={t('review:delete_game', '删除对局')} onClick={onDelete}>
          <DeleteOutlineIcon aria-hidden="true" />
        </button>
      )}
    </div>
  );
}
