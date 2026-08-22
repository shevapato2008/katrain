import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../../hooks/useTranslation';
import { KifuAPI } from '../../api/kifuApi';
import {
  cacheSgf, getCachedSgf, getProgress, listRecent,
  type BaipuProgress, type BaipuRecentEntry,
} from '../../api/baipuApi';
import { useLiveMatches } from '../../hooks/live/useLiveMatches';
import { translateResult } from '../../utils/resultTranslation';
import { KioskScrollZone } from '../shell/KioskScrollZone';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import { KioskCard } from '../shell/KioskCard';
import type { KifuAlbumSummary } from '../../types/kifu';
import type { MatchSource } from '../../types/live';
import { whenLabel } from '../utils/whenLabel';

const DEBOUNCE_MS = 350;
/** 一页 6 条:这是**滚栏里的一段**,不是整屏的列表。20 条会把下面两组挤到看不见。 */
const PAGE_SIZE = 6;

/**
 * 直播源的中文名。`components/live/MatchCard.tsx` 和 `MatchInfo.tsx` 里已经各有一份
 * 同样的表(两份并行,早于本轮),这是第三处 —— **没有合并是有意的**:那两份带着颜色,
 * 是 galaxy 那套卡片的样子;这里只要名字。合并要动 galaxy 的两屏,已登记为债。
 */
const SOURCE_LABEL: Record<MatchSource, string> = {
  xingzhen: '星阵',
  yike: '弈客',
  pandanet: 'PandaNet',
};

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
 * 「棋谱 / 摆谱 / 直播」三项收在这儿。**摆谱和直播的入口就在这一屏** ——
 * Task 4 把那两项下了 Dock,在本屏接上之前它们只能靠输 URL 到达,那笔账在这里销。
 *
 * 结构对着稿子 `data-screen="kifu"`:
 * 问候 → 继续摆谱 → 名局棋谱 → 最近摆过 → 职业直播。
 *
 * ## 三处和稿子不一样的地方
 *
 * ① **稿子第五块「棋谱详情 · 后端已有 · 界面未接」没搬。** 那一整块(连同里面的
 *    `PlaceholderPage`、`galaxy/pages/KifuLibraryPage.tsx` 两个文件名)是**说给读稿人听的**
 *    进度说明,不是给下棋的人用的东西 —— 和那三处 `.note` 同类(G5)。
 *    而且它说的事本轮已经不成立:详情屏(屏 16)接上了,就在这张列表点下去的地方。
 *
 * ② **搜索没有被三张卡换掉。** 稿子把「搜棋谱」画成一张卡,而现状这一页本来就是一个
 *    能用的棋谱库(搜索 + 分页 + 预览)。**把能用的功能换成一个入口是净损失**,
 *    所以「搜棋谱」这张卡是个开关:按下去搜索框和结果行就在这一组里展开,
 *    收起时这一组和稿子逐像素一样。结果行点进屏 16。
 *
 * ③ **组标题右端那个值换成了真数据。** 稿子写的是「按棋手 / 赛事 / 日期搜」——
 *    那是一句解释;规范说 `.secval` 的位置放的是数据(G5),所以写「共 N 局」。
 *    直播那组同理:稿子写死「来源:星阵 · 弈客」,实现里按**这一批真的来自哪几家**算。
 *
 * ## `kifu:famous_records` 是另起的 key
 *
 * `kifu:records` 在 cn PO 里是**「条记录」**(galaxy 拿它当「1234 条记录」的量词用)。
 * 复用它,这一组的标题会变成「条记录」——**PO 赢默认值**,闸四(`kiosk-shell-contract`)
 * 抓的就是这个。
 *
 * ## 直播那一块断网时整块不渲染
 *
 * 稿子的原话:「断网时这一块**整块不渲染**,不摆一排『加载中』骗人在等」。照办。
 * ⚠️ 代价要说清楚:**「没有直播」和「拉不到」在屏上长得一样**。这是稿子选的口径
 * (7″ 屏上一块常驻的报错块比它值钱的地方少),已登记。
 */
const KifuPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [recent, setRecent] = useState<RecentItem[]>(readRecent);
  const [importError, setImportError] = useState<string | null>(null);

  // ── 名局棋谱:默认收起,按「搜棋谱」展开 ──
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchInput, setSearchInput] = useState('');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [albums, setAlbums] = useState<KifuAlbumSummary[] | null>(null);
  const [total, setTotal] = useState<number | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  const { matches, error: liveError } = useLiveMatches({ limit: 8 });

  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(searchInput);
      setPage(1);
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [searchInput]);

  // 收起时**只探一个数**:组标题右端那句「共 N 局」是稿子给这个位置留的值,
  // 而规范说这个位置放的是数据。`page_size: 1` 只为拿 `total`,**不取列表也不渲染行** ——
  // 一屏常路是「继续摆谱 / 接着摆」,不该为它拉一页六条回来。
  useEffect(() => {
    if (searchOpen) return;
    let cancelled = false;
    KifuAPI.getAlbums({ page: 1, page_size: 1 })
      .then((resp) => { if (!cancelled) setTotal(resp.total); })
      .catch(() => { /* 离线就没有这个数 —— 位置空着,不编一个 */ });
    return () => { cancelled = true; };
  }, [searchOpen]);

  useEffect(() => {
    if (!searchOpen) return;
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
        if (!cancelled) { setListError(err.message); setAlbums(null); }
      });
    return () => { cancelled = true; };
  }, [searchOpen, query, page, reload]);

  const startSession = useCallback((id: string, name: string, sgf: string) => {
    cacheSgf(id, name, sgf);
    navigate(`/kiosk/baipu/session/${encodeURIComponent(id)}`, { state: { sgf, name } });
  }, [navigate]);

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

  const liveSources = [...new Set(matches.map((m) => m.source))]
    .map((s) => SOURCE_LABEL[s] ?? s)
    .join(' · ');

  return (
    <KioskScrollZone>
      <div className="kiosk-greet">
        <b>{t('kifu:greet_a', '看别人的')}<i>{t('kifu:greet_b', '棋')}</i></b>
        <span>{t('kifu:greet_sub', '名局、职业直播，以及把谱摆到实体盘上')}</span>
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
        <div className="kiosk-cards">
          <KioskCard
            title={t('kifu:search_records', '搜棋谱')}
            sub={t('kifu:search_sub', '一个搜索框，模糊匹配')}
            icon="magnifying-glass"
            current={searchOpen}
            ariaLabel={`${t('kifu:search_records', '搜棋谱')}，${searchOpen ? t('kifu:expanded', '已展开') : t('kifu:collapsed', '收起')}`}
            onClick={() => setSearchOpen((v) => !v)}
          />
          <KioskCard
            title={t('kifu:place_on_board', '摆到实体盘')}
            sub={t('kifu:place_sub', '灯一手一手指着摆')}
            icon="grid-nine"
            onClick={() => navigate('/kiosk/baipu')}
          />
          <KioskCard
            title={t('kifu:import_sgf', '导入 SGF')}
            sub={t('kifu:import_sub', '本地文件，离线也能摆')}
            icon="upload-simple"
            onClick={() => fileInputRef.current?.click()}
          />
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".sgf"
          hidden
          data-testid="kifu-sgf-input"
          onChange={onImport}
        />

        {searchOpen && (
          <div className="ksearch" data-testid="kifu-search">
            <input
              type="search"
              className="ksearch__box"
              placeholder={t('kifu:search_placeholder_cn', '棋手、赛事、年份都能搜')}
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
            />
            {listError ? (
              <div className="empty">
                <h4>{t('kifu:list_failed', '棋谱库读不到')}</h4>
                <p>{listError}</p>
                <button
                  type="button"
                  className="kiosk-btn kiosk-btn--pill pill"
                  onClick={() => { setListError(null); setReload((v) => v + 1); }}
                >
                  {t('kifu:retry', '重试')}
                </button>
              </div>
            ) : albums == null ? (
              <div className="empty"><h4>{t('kifu:searching', '正在找')}</h4></div>
            ) : albums.length === 0 ? (
              <div className="empty">
                <h4>{t('kifu:no_results_cn', '没有对得上的谱')}</h4>
                <p>{t('kifu:no_results_hint', '换棋手名、赛事名或者年份再试。')}</p>
              </div>
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
        )}
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

      {/* 断网 / 还没取到 ⇒ 整块不渲染。见文件头那段。 */}
      {!liveError && matches.length > 0 && (
        <section className="kiosk-section" data-testid="kifu-live">
          <KioskSecLabel
            zh={t('kifu:pro_live', '职业直播')}
            en="Live"
            value={liveSources ? `${t('kifu:source_prefix', '来源：')}${liveSources}` : undefined}
          />
          <div className="kiosk-rows">
            {matches.slice(0, 4).map((m) => (
              <button
                type="button"
                className="kiosk-row"
                key={m.id}
                onClick={() => navigate(`/kiosk/live/${m.id}`)}
              >
                <span className="kiosk-row__lead">
                  {m.status === 'live' ? t('kifu:live_now', '直播中') : whenLabel(new Date(m.date).getTime(), t)}
                </span>
                <span className="kiosk-row__t">
                  <b>{[m.tournament, m.round_name].filter(Boolean).join(' · ')}</b>
                  <em>
                    {SOURCE_LABEL[m.source] ?? m.source}
                    {' · '}
                    {m.status === 'live'
                      ? `${t('kifu:move_ordinal', '第')} ${m.move_count} ${t('kifu:moves_unit', '手')}`
                      : `${m.player_black} ${t('kifu:versus', '对')} ${m.player_white}`}
                  </em>
                </span>
                <span className="kiosk-row__end">
                  {m.status === 'live' ? (
                    <span className="kiosk-tag kiosk-tag--live">{t('kifu:live_now', '直播中')}</span>
                  ) : m.status === 'finished' ? (
                    <span className="kiosk-tag">{t('kifu:ended', '已结束')}</span>
                  ) : (
                    <span className="kiosk-tag">{t('kifu:not_started', '未开始')}</span>
                  )}
                </span>
              </button>
            ))}
          </div>
        </section>
      )}
    </KioskScrollZone>
  );
};

export default KifuPage;
