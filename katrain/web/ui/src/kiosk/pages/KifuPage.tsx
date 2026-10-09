import { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { backToState } from '../hooks/useBackTo';
import { useTranslation } from '../../hooks/useTranslation';
import { ApiError } from '../../api';
import { KifuAPI } from '../../api/kifuApi';
import {
  cacheSgf, getCachedSgf, getProgress, listRecent,
  type BaipuProgress, type BaipuRecentEntry,
} from '../../api/baipuApi';
import { translateResult } from '../../utils/resultTranslation';
import { formatRank } from '../../utils/rank';
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

  const [recent, setRecent] = useState<RecentItem[]>(readRecent);
  const [showRecent, setShowRecent] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);

  // ── 名局棋谱:一进来就是第一页 ──
  const [searchInput, setSearchInput] = useState('');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [albums, setAlbums] = useState<KifuAlbumSummary[] | null>(null);
  const [albumsLang, setAlbumsLang] = useState<string | null>(null);
  const [total, setTotal] = useState<number | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  /** 列表失败是不是「连不上云端」(503)。棋谱库只在云端,这一种要说「要联网」,别的照原样报。 */
  const [listOffline, setListOffline] = useState(false);
  const [reload, setReload] = useState(0);

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
          setListOffline(err instanceof ApiError && err.status === 503);
          setAlbums(null);
        }
      });
    return () => { cancelled = true; };
  }, [query, page, reload, lang]);

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
    <div className="kiosk-side kifu-library">
      <div className="kiosk-greet">
        <b>{t('kifu:greet_a', '看别人的')}<i>{t('kifu:greet_b', '棋')}</i></b>
        <span>{t('kifu:greet_sub', '名局，以及把谱摆到实体盘上')}</span>
      </div>
      <KioskSecLabel
        zh={t('kifu:famous_records', '名局棋谱')}
        en="Records"
        value={total != null ? `${t('kifu:total_prefix', '共')} ${total.toLocaleString()} ${t('kifu:games_unit', '局')}` : undefined}
      />
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
              <h4>{listOffline ? t('kifu:list_offline', '棋谱库要联网才能搜') : t('kifu:list_failed', '棋谱库读不到')}</h4>
              <p>{listOffline
                ? t('kifu:list_offline_hint', '这台盒子现在连不上云端。摆过的谱和导入的 SGF 不受影响。')
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
                const event = a.display_event ?? a.event;
                const round = a.display_round_name ?? a.round_name;
                const winner = /^[Bb黑]/.test(a.result || '') ? 'black'
                  : /^[Ww白]/.test(a.result || '') ? 'white' : null;
                return (
                  <button
                    type="button"
                    className="kifu-record"
                    key={a.id}
                    onClick={() => navigate(`/kiosk/kifu/${a.id}${a.has_analysis ? '' : '/replay'}`)}
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
                    <span className="kifu-record__match">
                      <span className={`kifu-record__player${winner === 'black' ? ' is-winner' : ''}`}>
                        <span className="kifu-record__stone kifu-record__stone--black" aria-hidden="true" />
                        <span className="kifu-record__name">{(a.display_player_black ?? a.player_black) || t('game:black_side', '黑方')}</span>
                        {(a.display_black_rank ?? a.black_rank) && <small>{formatRank(a.display_black_rank ?? a.black_rank, t)}</small>}
                      </span>
                      <span className={`kifu-record__result${winner ? ` kifu-record__result--${winner}` : ''}`}>
                        {translateResult(a.result, t, a.rules)}
                      </span>
                      <span className={`kifu-record__player kifu-record__player--white${winner === 'white' ? ' is-winner' : ''}`}>
                        <span className="kifu-record__stone kifu-record__stone--white" aria-hidden="true" />
                        {(a.display_white_rank ?? a.white_rank) && <small>{formatRank(a.display_white_rank ?? a.white_rank, t)}</small>}
                        <span className="kifu-record__name">{(a.display_player_white ?? a.player_white) || t('game:white_side', '白方')}</span>
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </KioskScrollZone>

      <div className="kifu-library__footer">
        <button
          type="button"
          className="kiosk-btn kifu-library__recent-toggle"
          aria-pressed={showRecent}
          aria-controls="kifu-library-list"
          onClick={() => setShowRecent((value) => !value)}
        >
          <Icon name="books" />
          {t('kifu:recent', '最近摆过')}
        </button>
        <CompactPagination
          key={`${query}:${lang}`} page={page} totalPages={totalPages}
          disabled={total == null || listError != null}
          onPageChange={(next) => { setShowRecent(false); setPage(next); }}
        />
      </div>
    </div>
  );
};

export default KifuPage;
