import { useCallback, useEffect, useRef, useState } from 'react';
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
import { KioskScrollZone } from '../shell/KioskScrollZone';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import { Icon } from '../shell/icons';
import type { KifuAlbumSummary } from '../../types/kifu';
import { whenLabel } from '../utils/whenLabel';

const DEBOUNCE_MS = 350;
/** 一页 6 条:这是**滚栏里的一段**,不是整屏的列表。20 条会把下面两组挤到看不见。 */
const PAGE_SIZE = 6;

interface RecentItem extends BaipuRecentEntry {
  progress: BaipuProgress | null;
}

const readRecent = (): RecentItem[] =>
  listRecent().map((e) => ({ ...e, progress: getProgress(e.id) }));

/** 摆完了没有 —— **只有两个数都在的时候才敢答**,见 `BaipuProgress.total` 那段注释。 */
const isDone = (p: BaipuProgress | null): boolean =>
  p != null && p.total != null && p.k >= p.total;

/**
 * 屏 15 · 棋谱 `/kiosk/kifu` —— L1 布局 A(镜像栏 296 + 16 + 右栏 680)。
 *
 * 规范 §3 只许围棋加**一个**棋种专属 Dock 项,这一项就是它:原来的
 * 「棋谱 / 摆谱 / 直播」三项收在这儿。**摆谱的入口就在这一屏** ——
 * Task 4 把它下了 Dock,在本屏接上之前它只能靠输 URL 到达,那笔账在这里销。
 *
 * 结构对着稿子 `data-screen="kifu"`(2026-09-23 版):
 * 问候 → 继续摆谱 → 名局棋谱(搜索框 + 导入 SGF / 一页六局 / 翻页)→ 最近摆过。
 *
 * ## 名局列表一进来就摊开(Fan 2026-09-23)
 *
 * 上一版照 8 月的稿子画成三张卡(搜棋谱 / 摆到实体盘 / 导入 SGF),列表收在「搜棋谱」开关后面,
 * 首屏能看见的一排行是直播 —— 盒上看起来就是「直播的列表挪进了棋谱库」。Fan 改判:这一屏的
 * 正文就是棋谱库那一页谱。三张卡拆掉:搜索框常驻在列表头上,「导入 SGF」贴在它右边;
 * 「摆到实体盘」不另开入口 —— 挑一局点进屏 16 再摆,和从这张表挑谱是同一个动作。
 *
 * ## 没有直播(Fan 2026-09-22)
 *
 * kiosk 端整个直播模块删掉,只在 galaxy 保留 —— 这一屏没有直播那一组,问候副标里的「职业直播」
 * 也一起去掉,盒上的 `/api/v1/board/live/*` 代理同样删了。**别再把直播加回这一屏。**
 *
 * ## 组标题右端是真数据
 *
 * 规范说 `.secval` 的位置放的是数据(G5),所以写「共 N 局」,取自列表那一发的 `total`。
 *
 * ## `kifu:famous_records` 是另起的 key
 *
 * `kifu:records` 在 cn PO 里是**「条记录」**(galaxy 拿它当「1234 条记录」的量词用)。
 * 复用它,这一组的标题会变成「条记录」——**PO 赢默认值**,闸四(`kiosk-shell-contract`)
 * 抓的就是这个。
 */
const KifuPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [recent, setRecent] = useState<RecentItem[]>(readRecent);
  const [importError, setImportError] = useState<string | null>(null);

  // ── 名局棋谱:一进来就是第一页 ──
  const [searchInput, setSearchInput] = useState('');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [albums, setAlbums] = useState<KifuAlbumSummary[] | null>(null);
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
    KifuAPI.getAlbums({ q: query || undefined, page, page_size: PAGE_SIZE })
      .then((resp) => {
        if (cancelled) return;
        setListError(null);
        setAlbums(resp.items);
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
  }, [query, page, reload]);

  const startSession = useCallback((id: string, name: string, sgf: string) => {
    cacheSgf(id, name, sgf);
    navigate(`/kiosk/baipu/session/${encodeURIComponent(id)}`, { state: { ...backToState(location), sgf, name } });
  }, [navigate, location]);

  const resume = useCallback((entry: RecentItem) => {
    const cached = getCachedSgf(entry.id);
    if (!cached) {
      // 谱是**整份缓存在本地**的,缓存没了就没法离线接着摆 —— 如实说,不假装还能点。
      setImportError(t('kifu:cache_gone', '这份谱的本地缓存没了,得重新选一次'));
      setRecent(readRecent());
      return;
    }
    startSession(cached.id, cached.name, cached.sgf);
  }, [startSession, t]);

  const onImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const text = String(reader.result || '');
      if (!text.includes('(;')) {
        setImportError(t('kifu:bad_sgf', '不是有效的 SGF 文件'));
        return;
      }
      startSession(`local_${Date.now()}`, file.name.replace(/\.sgf$/i, ''), text);
    };
    reader.onerror = () => setImportError(t('kifu:read_failed', '读取文件失败'));
    reader.readAsText(file);
    e.target.value = '';   // 同一个文件要能再导一次
  };

  // 「继续摆谱」认的是**最近摆过、又还没摆完**的那一份。
  const resumable = recent.find((e) => (e.progress?.k ?? 0) > 0 && !isDone(e.progress)) ?? null;
  const totalPages = total == null ? 1 : Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <KioskScrollZone>
      <div className="kiosk-greet">
        <b>{t('kifu:greet_a', '看别人的')}<i>{t('kifu:greet_b', '棋')}</i></b>
        <span>{t('kifu:greet_sub', '名局，以及把谱摆到实体盘上')}</span>
      </div>

      {resumable && (
        <div className="kiosk-resume" data-testid="resume-baipu-bar">
          <span className="bar" />
          <div>
            <h4>{t('kifu:resume_baipu', '继续摆谱')}</h4>
            <p>
              {t('kifu:resume_at', '上次摆到第')} {resumable.progress?.k} {t('kifu:moves_unit', '手')}
              {' · '}
              {t('kifu:resume_hint', '灯会指下一手落在哪')}
            </p>
          </div>
          <button
            type="button"
            className="kiosk-btn kiosk-btn--pill pill"
            onClick={() => resume(resumable)}
          >
            {t('kifu:resume', '继续')}
          </button>
        </div>
      )}

      {importError && (
        <div className="empty" data-testid="kifu-action-error">
          <h4>{t('kifu:cannot_start', '这一份摆不了')}</h4>
          <p>{importError}</p>
        </div>
      )}

      <section className="kiosk-section">
        <KioskSecLabel
          zh={t('kifu:famous_records', '名局棋谱')}
          en="Records"
          value={total != null ? `${t('kifu:total_prefix', '共')} ${total.toLocaleString()} ${t('kifu:games_unit', '局')}` : undefined}
        />
        <input
          ref={fileInputRef}
          type="file"
          accept=".sgf"
          hidden
          data-testid="kifu-sgf-input"
          onChange={onImport}
        />

        <div className="ksearch" data-testid="kifu-search">
          <div className="ksearch__bar">
            <label className="ksearch__field">
              <Icon name="magnifying-glass" />
              <input
                type="search"
                className="ksearch__box"
                placeholder={t('kifu:search_placeholder_cn', '棋手、赛事、年份都能搜')}
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
              />
            </label>
            <button
              type="button"
              className="kiosk-btn kiosk-btn--pill ksearch__import"
              onClick={() => fileInputRef.current?.click()}
            >
              <Icon name="upload-simple" />
              {t('kifu:import_sgf', '导入 SGF')}
            </button>
          </div>
          {listError ? (
            <div className="empty">
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
          ) : albums == null ? (
            <div className="empty">
              <h4>{query ? t('kifu:searching', '正在找') : t('kifu:loading', '加载中...')}</h4>
            </div>
          ) : albums.length === 0 ? (
            // 没搜任何东西时是空库,不是「没对上」—— 别叫人去换一个根本没输过的词。
            query ? (
              <div className="empty">
                <h4>{t('kifu:no_results_cn', '没有对得上的谱')}</h4>
                <p>{t('kifu:no_results_hint', '换棋手名、赛事名或者年份再试。')}</p>
              </div>
            ) : (
              <div className="empty"><h4>{t('kifu:no_results', '未找到棋谱')}</h4></div>
            )
          ) : (
            <>
              <div className="kiosk-rows">
                {albums.map((a) => (
                  <button
                    type="button"
                    className="kiosk-row"
                    key={a.id}
                    onClick={() => navigate(`/kiosk/kifu/${a.id}`)}
                  >
                    <span className="kiosk-row__lead">{a.move_count} {t('kifu:moves_unit', '手')}</span>
                    <span className="kiosk-row__t">
                      <b>{a.player_black} {t('kifu:versus', '对')} {a.player_white}</b>
                      <em>{[a.event, a.round_name, a.date_played].filter(Boolean).join(' · ')}</em>
                    </span>
                    <span className="kiosk-row__end">
                      <span className="kiosk-tag">{translateResult(a.result, t, a.rules)}</span>
                    </span>
                  </button>
                ))}
              </div>
              {totalPages > 1 && (
                <div className="kpager">
                  <button
                    type="button"
                    className="kiosk-btn kiosk-btn--pill"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                  >
                    {t('kifu:prev_page', '上一页')}
                  </button>
                  <span>{page} / {totalPages}</span>
                  <button
                    type="button"
                    className="kiosk-btn kiosk-btn--pill"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  >
                    {t('kifu:next_page', '下一页')}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </section>

      <section className="kiosk-section">
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
                    {done
                      ? t('kifu:whole_game', '全谱')
                      : `${e.progress?.k ?? 0} ${t('kifu:moves_unit', '手')}`}
                  </span>
                  <span className="kiosk-row__t">
                    <b>{e.name}</b>
                    <em>
                      {done
                        ? t('kifu:placed_all', '摆完')
                        // 行里写「摆到第 N 手」,横幅上才写「上次」—— 横幅说的是「你上一次在做什么」,
                        // 行说的是「这一份摆到哪儿了」。稿子这两处也是分开的两句。
                        : `${t('kifu:placed_at', '摆到第')} ${e.progress?.k ?? 0} ${t('kifu:moves_unit', '手')}`}
                      {' · '}
                      {whenLabel(e.savedAt, t)}
                    </em>
                  </span>
                  <span className="kiosk-row__end">
                    {done ? (
                      <span className="kiosk-tag kiosk-tag--win">{t('kifu:done_tag', '已摆完')}</span>
                    ) : (
                      <button
                        type="button"
                        className="kiosk-btn kiosk-btn--pill"
                        onClick={() => resume(e)}
                      >
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
    </KioskScrollZone>
  );
};

export default KifuPage;
