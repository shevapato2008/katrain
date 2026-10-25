import { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { backToState } from '../hooks/useBackTo';
import { useTranslation } from '../../hooks/useTranslation';
import { ApiError } from '../../api';
import { BaipuAPI } from '../../api/baipuApi';
import { GoBoardSvg } from '../shell/GoBoardSvg';
import { replayBaipuSteps, type BoardState } from '../../utils/baipuReplay';
import { KifuAPI } from '../../api/kifuApi';
import {
  cacheSgf, getCachedSgf, getProgress, listRecent,
  type BaipuProgress, type BaipuRecentEntry,
} from '../../api/baipuApi';
import RecordMatchLine from '../components/records/RecordMatchLine';
import { getListRank, listResult } from '../utils/listRecordPresentation';
import { KioskScrollZone } from '../shell/KioskScrollZone';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import { Icon } from '../shell/icons';
import type { KifuAlbumSummary } from '../../types/kifu';
import { whenLabel } from '../utils/whenLabel';
import CompactPagination from '../../components/CompactPagination';
import './kifuLibrary.css';

const DEBOUNCE_MS = 350;
/** Fetch only the current 20 records; the existing list owns its scroll area. */
const PAGE_SIZE = 20;
const SEARCH_SESSION_KEY = 'katrain_kiosk_kifu_search';

const readSearchSession = (): { query: string; page: number } => {
  try {
    const saved = JSON.parse(sessionStorage.getItem(SEARCH_SESSION_KEY) ?? 'null');
    if (typeof saved?.query === 'string' && Number.isInteger(saved.page) && saved.page >= 1) return saved;
  } catch { /* Session storage may be unavailable. */ }
  return { query: '', page: 1 };
};

interface RecentItem extends BaipuRecentEntry {
  progress: BaipuProgress | null;
}

const readRecent = (): RecentItem[] =>
  listRecent().map((e) => ({ ...e, progress: getProgress(e.id) }));

/** 摆完了没有 —— **只有两个数都在的时候才敢答**,见 `BaipuProgress.total` 那段注释。 */
const isDone = (p: BaipuProgress | null): boolean =>
  p != null && p.total != null && p.k >= p.total;

/** L1 library: keep the shell geometry; only the current page/local history scrolls. */
const KifuPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { t, lang } = useTranslation();

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [preview, setPreview] = useState<{ id: number; board: BoardState; size: number } | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [recent, setRecent] = useState<RecentItem[]>(readRecent);
  const [showRecent, setShowRecent] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);

  // Preserve the current search and page when returning from Settings.
  const [initialSearch] = useState(readSearchSession);
  const [searchInput, setSearchInput] = useState(initialSearch.query);
  const [query, setQuery] = useState(initialSearch.query);
  const [page, setPage] = useState(initialSearch.page);
  const [albums, setAlbums] = useState<KifuAlbumSummary[] | null>(null);
  const [albumsLang, setAlbumsLang] = useState<string | null>(null);
  const [total, setTotal] = useState<number | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [listFailure, setListFailure] = useState<'unreachable' | 'service' | 'other'>('other');
  const [reload, setReload] = useState(0);

  useEffect(() => {
    try {
      sessionStorage.setItem(SEARCH_SESSION_KEY, JSON.stringify({ query, page }));
    } catch { /* Keep searching even if session storage is unavailable. */ }
  }, [query, page]);

  // 只在输入**真变了**时才起表。挂载时 `'' === ''` 也起表的话,350ms 后那一下 `setPage(1)`
  // 会把进屏就翻的页弹回第 1 页 —— 列表藏在开关后面时没人碰得到,默认摊开后就碰得到了。
  useEffect(() => {
    if (searchInput === query) return;
    const timer = setTimeout(() => {
      setQuery(searchInput);
      setPage(1);
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [searchInput, query]);

  useEffect(() => {
    let cancelled = false;
    // ⚠️ 清空只能在异步回调里(`react-hooks/set-state-in-effect`)。重试那一下靠 `reload`
    // 计数器 —— `setPage(p => p)` 是同一个值,React 会跳过重渲染,效应根本不会再跑。
    KifuAPI.getAlbums({ q: query || undefined, page, page_size: PAGE_SIZE, lang })
      .then((resp) => {
        if (cancelled) return;
        setListError(null);
        setAlbums(resp.items);
        setAlbumsLang(lang);
        setTotal(resp.total);
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setListError(err.message);
          const detail = err instanceof ApiError ? err.detail : null;
          const unreachable = err instanceof ApiError && err.status === 503
            && typeof detail === 'object' && detail !== null
            && 'code' in detail && detail.code === 'kifu_cloud_unreachable';
          setListFailure(unreachable ? 'unreachable' : err instanceof ApiError && err.status >= 500 ? 'service' : 'other');
          setAlbums(null);
        }
      });
    return () => { cancelled = true; };
  }, [query, page, reload, lang]);

  useEffect(() => {
    setSelectedId(albums?.[0]?.id ?? null);
  }, [albums]);

  useEffect(() => {
    let cancelled = false;
    setPreview(null);
    setPreviewError(null);
    if (selectedId == null) return;
    KifuAPI.getAlbum(selectedId, lang).then(async (album) => {
      if (!album.sgf_content) throw new Error('没有可用棋谱');
      const loaded = await BaipuAPI.load({ sgf: album.sgf_content });
      if (!cancelled) setPreview({ id: selectedId, size: loaded.board_size || album.board_size || 19,
        board: replayBaipuSteps(loaded.steps, loaded.steps.length, loaded.board_size || album.board_size || 19) });
    }).catch(() => { if (!cancelled) setPreviewError(t('kifu:preview_failed', '棋谱预览加载失败')); });
    return () => { cancelled = true; };
  }, [selectedId, lang]);

  useEffect(() => {
    setSelectedId(null);
    setPreview(null);
  }, [query, page, lang]);

  const startSession = useCallback((id: string, name: string, sgf: string) => {
    cacheSgf(id, name, sgf);
    navigate(`/kiosk/baipu/session/${encodeURIComponent(id)}`, { state: { ...backToState(location), sgf, name } });
  }, [navigate, location]);

  const resume = useCallback((entry: RecentItem) => {
    const cached = getCachedSgf(entry.id);
    if (!cached) {
      // 谱是**整份缓存在本地**的,缓存没了就没法离线接着摆 —— 如实说,不假装还能点。
      setSessionError(t('kifu:cache_gone', '这份谱的本地缓存没了,得重新选一次'));
      setRecent(readRecent());
      return;
    }
    startSession(cached.id, cached.name, cached.sgf);
  }, [startSession, t]);

  // 「继续摆谱」认的是**最近摆过、又还没摆完**的那一份。
  const resumable = recent.find((e) => (e.progress?.k ?? 0) > 0 && !isDone(e.progress)) ?? null;
  const totalPages = total == null ? 1 : Math.max(1, Math.ceil(total / PAGE_SIZE));
  const visibleAlbums = albumsLang === lang ? albums : null;

  return (
    <div className="kiosk-layout-l1 archive-reviewed">
      <aside className="archive-preview">
        <h2>{t('kifu:selected_game', '选中这一局')}</h2>
        <div className="archive-preview__board"><GoBoardSvg size={preview?.size ?? 19}
          black={preview?.board.black ?? []} white={preview?.board.white ?? []}
          last={preview?.board.last} muted={!preview} label={t('kifu:final_board', '选中棋谱的终局盘')} /></div>
        <p role="status">{previewError ?? (selectedId == null ? t('kifu:select_game', '请选择棋谱') : !preview ? t('kifu:preview_loading', '正在加载棋谱') : t('kifu:final_position', '终局棋谱'))}</p>
        <div className="archive-preview__actions">
          <button type="button" className="kiosk-btn" disabled={!preview || preview.id !== selectedId} onClick={() => navigate(`/kiosk/kifu/${selectedId}/replay`)}>{t('kifu:open_replay', '查看棋谱')}</button>
          <button type="button" className="kiosk-btn" disabled={!preview || preview.id !== selectedId || !albums?.find(a => a.id === selectedId)?.has_analysis}
            onClick={() => navigate(`/kiosk/kifu/${selectedId}`)}>{t('kifu:open_analysis', '查看分析')}</button>
        </div>
      </aside>
    <div className="kiosk-side kifu-library">
      <div className="kiosk-greet archive-library-heading">
        <b>{t('kifu:professional_library', '职业棋谱')}</b>
        <span>{total != null ? `${t('kifu:total_prefix', '共')} ${total.toLocaleString()} ${t('kifu:games_unit', '局')}` : ''}</span>
      </div>
      <div className="archive-library-tabs" role="group" aria-label={t('kifu:library_views', '棋谱分类')}>
        <button type="button" className="kiosk-btn" aria-pressed={!showRecent} onClick={() => setShowRecent(false)}>{t('kifu:famous_records', '名局棋谱')}</button>
        <button type="button" className="kiosk-btn" aria-pressed={showRecent} onClick={() => setShowRecent(true)}>{t('kifu:recent', '最近摆过')}</button>
      </div>
      <div className="ksearch" data-testid="kifu-search">
        <div className="ksearch__bar">
          <label className="ksearch__field">
            <Icon name="magnifying-glass" />
            <input
              type="search"
              className="ksearch__box"
              aria-label={t('kifu:search_placeholder_cn', '棋手、赛事、年份都能搜')}
              placeholder={t('kifu:search_placeholder_cn', '棋手、赛事、年份都能搜')}
              value={searchInput}
              onChange={(e) => { setSearchInput(e.target.value); setShowRecent(false); }}
            />
          </label>
        </div>
      </div>

      <KioskScrollZone grow className="kifu-library__list" resetKey={`${query}:${page}:${lang}:${showRecent}`}>
        <div id="kifu-library-list">
          {sessionError && (
            <div className="empty" role="alert" data-testid="kifu-action-error">
              <h4>{t('kifu:cannot_start', '这一份摆不了')}</h4>
              <p>{sessionError}</p>
            </div>
          )}
          {resumable && (
            <div className="kiosk-resume" data-testid="resume-baipu-bar">
              <span className="bar" />
              <div>
                <h4>{t('kifu:resume_baipu', '继续摆谱')}</h4>
                <p>
                  {t('kifu:resume_at', '上次摆到第')} {resumable.progress?.k} {t('kifu:moves_unit', '手')}
                  {' · '}{t('kifu:resume_hint', '灯会指下一手落在哪')}
                </p>
              </div>
              <button type="button" className="kiosk-btn kiosk-btn--pill pill" onClick={() => resume(resumable)}>
                {t('kifu:resume', '继续')}
              </button>
            </div>
          )}
          {showRecent ? (
            <section className="kifu-library__recent">
              <KioskSecLabel
                zh={t('kifu:recent', '最近摆过')}
                en="Recent"
                value={t('kifu:on_this_box', '存在这台盒子上')}
              />
              {recent.length === 0 ? (
                <div className="empty" data-testid="kifu-recent-empty">
                  <h4>{t('kifu:no_recent', '这台盒子上还没摆过谱')}</h4>
                  <p>{t('kifu:no_recent_hint', '从上面挑一份,或者导入一个 SGF —— 选过的谱整份存在本地,断网也摆得完。')}</p>
                </div>
              ) : (
                <div className="kiosk-rows" data-testid="kifu-recent-rows">
                  {recent.slice(0, 6).map((e) => {
                    const done = isDone(e.progress);
                    return (
                      <div className="kiosk-row" key={e.id}>
                        <span className="kiosk-row__lead">
                          {done ? t('kifu:whole_game', '全谱') : `${e.progress?.k ?? 0} ${t('kifu:moves_unit', '手')}`}
                        </span>
                        <span className="kiosk-row__t">
                          <b>{e.name}</b>
                          <em>
                            {done ? t('kifu:placed_all', '摆完')
                              : `${t('kifu:placed_at', '摆到第')} ${e.progress?.k ?? 0} ${t('kifu:moves_unit', '手')}`}
                            {' · '}{whenLabel(e.savedAt, t)}
                          </em>
                        </span>
                        <span className="kiosk-row__end">
                          {done ? (
                            <span className="kiosk-tag kiosk-tag--win">{t('kifu:done_tag', '已摆完')}</span>
                          ) : (
                            <button type="button" className="kiosk-btn kiosk-btn--pill" onClick={() => resume(e)}>
                              {t('kifu:keep_placing', '接着摆')}
                            </button>
                          )}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          ) : listError ? (
            <div className="empty" role="alert">
              <h4>{listFailure === 'unreachable'
                ? t('kifu:list_offline', '无法连接棋谱库')
                : listFailure === 'service'
                  ? t('kifu:service_unavailable', '棋谱库暂时不可用')
                  : t('kifu:list_failed', '棋谱库读不到')}</h4>
              <p>{listFailure === 'unreachable'
                ? t('kifu:list_offline_hint', '请检查网络连接或稍后重试。')
                : listFailure === 'service'
                  ? t('kifu:service_unavailable_hint', '云端服务暂时出了问题，请稍后重试。')
                  : listError}</p>
              <button
                type="button"
                className="kiosk-btn kiosk-btn--pill pill"
                onClick={() => { setListError(null); setReload((v) => v + 1); }}
              >
                {t('kifu:retry', '重试')}
              </button>
            </div>
          ) : visibleAlbums == null ? (
            <div className="empty" role="status">
              <h4>{query ? t('kifu:searching', '正在找') : t('kifu:loading', '加载中...')}</h4>
            </div>
          ) : visibleAlbums.length === 0 ? (
            <div className="empty">
              <h4>{query ? t('kifu:no_results_cn', '没有对得上的谱') : t('kifu:no_results', '未找到棋谱')}</h4>
              {query && <p>{t('kifu:no_results_hint', '换棋手名、赛事名或者年份再试。')}</p>}
            </div>
          ) : (
            <div className="kifu-records" data-testid="kifu-records">
              {visibleAlbums.map((a) => {
                const event = a.display_event ?? '';
                const round = a.display_round_name ?? '';
                const result = listResult(a.result, t, a.rules, lang);
                return (
                  <button
                    type="button"
                    className={`kifu-record${selectedId === a.id ? ' is-selected' : ''}`}
                    aria-pressed={selectedId === a.id}
                    key={a.id}
                    onClick={() => setSelectedId(a.id)}
                  >
                    <span className="kifu-record__head">
                      <span className="kifu-record__entry" role="img"
                        aria-label={a.has_analysis ? t('kifu:view_analysis_report', '查看分析报告') : t('kifu:view_kifu', '查看棋谱')}
                        title={a.has_analysis ? t('kifu:view_analysis_report', '查看分析报告') : t('kifu:view_kifu', '查看棋谱')}>
                        <Icon name={a.has_analysis ? 'trend-up' : 'books'} />
                      </span>
                      <span className="kifu-record__event" title={[event, round].filter(Boolean).join(' · ')}>
                        {event || ''}
                        {round && <span className="kifu-record__round"> · {round}</span>}
                      </span>
                      <span className="kifu-record__meta">
                        {a.date_played && <span>{a.date_played}</span>}
                        <span>{a.move_count} {t('kifu:moves_unit', '手')}</span>
                      </span>
                    </span>
                    <RecordMatchLine variant="kifu"
                      black={{ name: a.display_player_black ?? t('game:black_side', '黑方'), rank: getListRank(a.display_black_rank, a.black_rank, t) }}
                      white={{ name: a.display_player_white ?? t('game:white_side', '白方'), rank: getListRank(a.display_white_rank, a.white_rank, t) }}
                      result={result.label} winner={result.winner}
                      unknownRankLabel={t('review:rank_not_recorded', '等级未记录')} />
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </KioskScrollZone>

      <div className="kifu-library__footer">
        <CompactPagination showEdgeButtons
          key={`${query}:${lang}`} page={page} totalPages={totalPages}
          disabled={total == null || listError != null}
          onPageChange={(next) => { setShowRecent(false); setPage(next); }}
        />
      </div>
    </div>
    </div>
  );
};

export default KifuPage;
