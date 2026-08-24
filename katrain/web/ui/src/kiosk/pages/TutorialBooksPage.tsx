import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';

import { TutorialReadAPI } from '../../api/tutorialApi';
import { useTranslation } from '../../hooks/useTranslation';
import type { TutorialBook, TutorialBookDetail, TutorialSection } from '../../types/tutorial';
import { Icon } from '../shell/icons';
import { KioskCard } from '../shell/KioskCard';
import { KioskPagebar } from '../shell/KioskPagebar';
import { KioskScrollZone } from '../shell/KioskScrollZone';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import type { SectionNavState } from '../types/tutorialNav';
import { interpolate } from '../utils/interpolate';

/**
 * 屏 24 · 课程 · 书目与章节 `/kiosk/tutorial/:category?book=<id>` —— L2 布局 B(通栏,整栏滚)。
 *
 * ## 两屏合一(2026-08-24 裁定)
 *
 * 这一屏吃掉了原来的 `tutorial/book/:bookId` + `TutorialBookDetailPage.tsx`,**那条路由和那个
 * 页面一起删了**。判据是稿子自己写的:选完书之后**下面那半屏才有内容**,分成两屏的话第一屏
 * 只有三张卡、剩下 350px 全空 —— 上下两块是同一条路上的两步,不是两个地方。
 * 没留重定向:kiosk 是全屏 chromium,没有地址栏也没有书签,一条没人走的重定向
 * 就是「抄一条挡不住任何东西的规则比没有更坏」的另一种写法。
 *
 * ## 选中的书**进 URL**(`?book=`),不是页内 state
 *
 * 这是为了保住**现有行为**:屏 25 按「← 目录」今天回得到章节树。页内 state 会让它回到
 * 「一本都没选」的空半屏 —— 那不是重画,那是把一条走通的路走断。
 * 没有 `?book=` 时自动选第一本并 `replace` 回写(不进历史,返回键不会卡在半路)。
 *
 * ## 进度那一层一处不上
 *
 * 环恒 `null`(屏上「—」)、副标只写 `{chapter_count} 章`,**不写稿子那句「已看到第 3 章」**;
 * 章行行尾的三态(已看完 / 接着看 / 开始)整个不做。理由是**盒上没有可信的「谁看过什么」**:
 * `UserTutorialProgress`(`models_db.py:522`)第一行注释就写着 DEPRECATED,主键是 V1 的字符串
 * `example_id`/`topic_id`,和 V2 的整数 id 之间**没有任何映射**,全仓零个端点读写它。
 * 拿 localStorage 顶替更坏 —— 这台盒子有账号,按机器存会把甲的进度显示成乙的:
 * 那是关于一个人的假话,比不显示更坏。
 *
 * ⚠️ 上一版这里的三态是**假的**:`CircularProgress` + `height:'50vh'` 当加载态(而画布是
 * 固定 1024×600,`50vh` 在这里没有意义),空态和读不到共用一句「该分类暂无书籍」。
 * 换成屏 23 定下的 `.empty` 三态,且**空态和读不到必须两句话** —— 「一本都没有」是结论,
 * 「没读到」是还没查。
 *
 * ## 章行本身就是展开控件
 *
 * 节那一层留在这一屏、章行行内展开(Fan 8-22 收进注释的是那句**解释**,不是那个行为)。
 * 用 `.kiosk-row` 的按钮变体(52 高 ≥44),**不用 `KioskFold`** —— 它的 `__head` 是 30 高
 * 11px 字,那是面板标题不是列表行,拿它当章行既破 44 又把章名压成 11px。
 */

/** 一本书的章节树:书本体 + 每章的节。**两者一起到**,免得屏上出现「有章无节」的中间态。 */
interface BookTree {
  detail: TutorialBookDetail;
  sections: Record<number, TutorialSection[]>;
}

/** 失败**带着它属于哪一本** —— 换一本书时旧的错误自然失效,不必在 effect 里清状态。 */
interface Failure {
  id: number | string;
  message: string;
}

const TutorialBooksPage = () => {
  const { category = '' } = useParams<{ category: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { t } = useTranslation();

  const [books, setBooks] = useState<TutorialBook[] | null>(null);
  const [booksError, setBooksError] = useState<Failure | null>(null);
  const [booksReload, setBooksReload] = useState(0);

  const [tree, setTree] = useState<BookTree | null>(null);
  const [treeError, setTreeError] = useState<Failure | null>(null);
  const [treeReload, setTreeReload] = useState(0);

  const bookParam = searchParams.get('book');
  const bookId = bookParam && /^\d+$/.test(bookParam) ? Number(bookParam) : null;
  // 摊开的是哪一章**也在 URL 里**,理由和书一样:屏 25 按「← 目录」要回到你离开时那一屏。
  // 上一版(`TutorialBookDetailPage`)是 `<Accordion defaultExpanded>` —— 回来时**每一章都是开的**,
  // 所以「回来时全收起」不是「换个默认值」,是把一条走通的路走断。
  const chapterParam = searchParams.get('ch');
  const openChapter = chapterParam && /^\d+$/.test(chapterParam) ? Number(chapterParam) : null;

  // ── 书目 ──
  useEffect(() => {
    let cancelled = false;
    // ⚠️ 清空只能在异步回调里(`react-hooks/set-state-in-effect`);重试那一下靠计数器再进一次。
    TutorialReadAPI.getBooks(category)
      .then((data) => {
        if (cancelled) return;
        setBooks(data);
        setBooksError(null);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setBooks(null);
        setBooksError({ id: category, message: err instanceof Error ? err.message : String(err) });
      });
    return () => { cancelled = true; };
  }, [category, booksReload]);

  // 没有 `?book=`(或指着一本这一类里没有的书)⇒ 自动选第一本,`replace` 回写。
  useEffect(() => {
    if (!books || books.length === 0) return;
    if (bookParam && books.some((b) => String(b.id) === bookParam)) return;
    setSearchParams({ book: String(books[0].id) }, { replace: true });
  }, [books, bookParam, setSearchParams]);

  // ── 选中那本书的章节树 ──
  useEffect(() => {
    if (bookId == null) return;
    let cancelled = false;
    TutorialReadAPI.getBook(bookId)
      .then(async (detail) => {
        // 每一章的节**并行**拉,不许串行 —— 一本 8 章的书串起来就是 8 个来回。
        const lists = await Promise.all(detail.chapters.map((ch) => TutorialReadAPI.getSections(ch.id)));
        return { detail, lists };
      })
      .then(({ detail, lists }) => {
        if (cancelled) return;
        const sections: Record<number, TutorialSection[]> = {};
        detail.chapters.forEach((ch, i) => { sections[ch.id] = lists[i]; });
        setTree({ detail, sections });
        setTreeError(null);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setTreeError({ id: bookId, message: err instanceof Error ? err.message : String(err) });
      });
    return () => { cancelled = true; };
  }, [bookId, treeReload]);

  // 换书是一次**导航**(进历史);展开哪一章是一个**视图偏好**(`replace`,不进历史) ——
  // 否则摊开三章之后,历史里就多出三条一模一样的地址。
  const openBook = useCallback((id: number) => {
    setSearchParams({ book: String(id) });
  }, [setSearchParams]);
  const toggleChapter = useCallback((id: number, open: boolean) => {
    const next: Record<string, string> = { book: String(bookId ?? '') };
    if (!open) next.ch = String(id);
    setSearchParams(next, { replace: true });
  }, [bookId, setSearchParams]);

  // 这本书当下是不是已经在手上 —— 拿它当加载态,就不必在 effect 里先清空一遍。
  const treeReady = tree != null && tree.detail.id === bookId;
  const treeFailed = treeError != null && treeError.id === bookId;

  const chapterStats = useMemo(() => {
    if (!treeReady) return null;
    const chapters = tree.detail.chapters;
    const sections = chapters.reduce((n, ch) => n + (tree.sections[ch.id]?.length ?? 0), 0);
    return { chapters: chapters.length, sections };
  }, [tree, treeReady]);

  const currentBook = books?.find((b) => b.id === bookId) ?? null;

  return (
    <div className="kiosk-layout-b" data-testid="tutorial-books-page">
      <KioskPagebar
        testId="tutorial-books-pagebar"
        backLabel={t('tutorial:title_cn', '课程')}
        onBack={() => navigate('/kiosk/tutorial')}
        // 分类的 slug **就是它的中文名**(`db_queries.py:22` 那四条写死的:入门 / 布局 / 中盘 / 官子),
        // 所以标题直接用地址里那一段 —— 不为一个已经在手上的字符串再发一次 `/categories`。
        title={decodeURIComponent(category)}
        sub={books
          ? interpolate(t('tutorial:books_synced', '{n} 本 · 内容随云端同步'), { n: books.length })
          : t('tutorial:synced', '随云端同步')}
      />

      <KioskScrollZone resetKey={`${category}/${bookId ?? ''}`}>
        {/* ── 选一本 ── */}
        <section className="kiosk-section">
          {/* 稿子这一格写「书目由云端下发」——那是说给读稿人听的,而那一格按规范放**数据**。
              本数已经在页控条副标上了,一个数不摆两处 ⇒ 这一格留空。 */}
          <KioskSecLabel zh={t('tutorial:pick_book', '选一本')} en="Books" />
          {booksError ? (
            <div className="empty" data-testid="tutorial-books-error">
              <h4>{t('tutorial:books_failed', '没读到这一类的书目')}</h4>
              <p>{booksError.message}</p>
              <button
                type="button"
                className="kiosk-btn kiosk-btn--pill pill"
                onClick={() => { setBooksError(null); setBooksReload((v) => v + 1); }}
              >
                {t('kifu:retry', '重试')}
              </button>
            </div>
          ) : books == null ? (
            <div className="empty" data-testid="tutorial-books-loading">
              <h4>{t('tutorial:books_loading', '正在读这一类的书目')}</h4>
            </div>
          ) : books.length === 0 ? (
            // 接口答了、答的是空 —— 这时候「一本都没有」是**结论**,和上面那句「没读到」不是一件事。
            <div className="empty" data-testid="tutorial-books-empty">
              <h4>{t('tutorial:books_empty', '这一类下面一本书都没有')}</h4>
              <p>{t('tutorial:books_empty_hint', '云端还没有把这一类同步下来；别的分类可能已经有了。')}</p>
            </div>
          ) : (
            <div className="kiosk-cards" data-testid="tutorial-book-cards">
              {books.map((b) => (
                <KioskCard
                  key={b.id}
                  title={b.title}
                  // 环恒是「—」:接口只给章数不给进度。副标写真数,**不写「已看到第 3 章」**。
                  sub={[b.author, interpolate(t('tutorial:chapters_n', '{n} 章'), { n: b.chapter_count })]
                    .filter(Boolean).join(' · ')}
                  ring={null}
                  current={b.id === bookId}
                  onClick={() => openBook(b.id)}
                />
              ))}
            </div>
          )}
        </section>

        {/* ── 目录 ── 选了书才有 */}
        {currentBook && (
          <section className="kiosk-section" data-testid="tutorial-chapters">
            <KioskSecLabel
              zh={interpolate(t('tutorial:toc_of', '{title} · 目录'), { title: currentBook.title })}
              en="Chapters"
              // 稿子这一格写「点到『节』才有讲解」—— 同上,换成真数。
              value={chapterStats
                ? interpolate(t('tutorial:toc_count', '{c} 章 · {s} 节'),
                  { c: chapterStats.chapters, s: chapterStats.sections })
                : undefined}
            />
            {treeFailed ? (
              <div className="empty" data-testid="tutorial-toc-error">
                <h4>{t('tutorial:toc_failed', '没读到这本书的目录')}</h4>
                <p>{treeError.message}</p>
                <button
                  type="button"
                  className="kiosk-btn kiosk-btn--pill pill"
                  onClick={() => { setTreeError(null); setTreeReload((v) => v + 1); }}
                >
                  {t('kifu:retry', '重试')}
                </button>
              </div>
            ) : !treeReady ? (
              <div className="empty" data-testid="tutorial-toc-loading">
                <h4>{t('tutorial:toc_loading', '正在读这本书的目录')}</h4>
              </div>
            ) : tree.detail.chapters.length === 0 ? (
              <div className="empty" data-testid="tutorial-toc-empty">
                <h4>{t('tutorial:toc_empty', '这本书还没有章节')}</h4>
                <p>{t('tutorial:toc_empty_hint', '书目同步下来了，正文还没有；这不是你这台盒子的问题。')}</p>
              </div>
            ) : (
              <div className="kiosk-rows" data-testid="tutorial-chapter-rows">
                {tree.detail.chapters.map((ch) => {
                  const sections = tree.sections[ch.id] ?? [];
                  const figures = sections.reduce((n, s) => n + (s.figure_count || 0), 0);
                  const open = openChapter === ch.id;
                  return (
                    <div key={ch.id}>
                      {/* 行本身就是展开控件 —— 行尾那颗 caret 说的是**这一行现在是开是合**,
                          不是「你看过没有」。前者屏上为真,后者盒上问不出来。 */}
                      <button
                        type="button"
                        className="kiosk-row chrow"
                        aria-expanded={open}
                        data-testid="tutorial-chapter-row"
                        onClick={() => toggleChapter(ch.id, open)}
                      >
                        <span className="kiosk-row__lead">{ch.chapter_number}</span>
                        <span className="kiosk-row__t">
                          <b>{ch.title}</b>
                          <em>
                            {interpolate(t('tutorial:sections_n', '{n} 节'), { n: sections.length })}
                            {' · '}
                            {interpolate(t('tutorial:figures_n', '{n} 图'), { n: figures })}
                          </em>
                        </span>
                        <span className="kiosk-row__end">
                          <span className="chcaret" aria-hidden="true"><Icon name="caret-down" /></span>
                        </span>
                      </button>
                      {open && (
                        <div className="secrows" data-testid="tutorial-section-rows">
                          {sections.length === 0 ? (
                            <p className="lobbyempty">{t('tutorial:no_sections', '这一章还没有节')}</p>
                          ) : sections.map((s) => {
                            const state: SectionNavState = {
                              bookId: tree.detail.id,
                              bookTitle: tree.detail.title,
                              bookSlug: tree.detail.slug,
                              chapterId: ch.id,
                              chapterTitle: ch.title,
                              sectionTitle: s.title,
                              category,
                              // ⚠️ `has_video` **只有 `getSections` 这条路可信**:详情端点
                              // `getSection(id)` 从不设这个字段,走 Pydantic 默认 `False`
                              // (`tutorials/models.py:52`)—— 一个恒假的字段。
                              hasVideo: s.has_video,
                            };
                            return (
                              <button
                                key={s.id}
                                type="button"
                                className="kiosk-row secrow"
                                data-testid="tutorial-section-row"
                                onClick={() => navigate(`/kiosk/tutorial/section/${s.id}`, { state })}
                              >
                                <span className="kiosk-row__lead">{s.section_number}</span>
                                <span className="kiosk-row__t"><b>{s.title}</b></span>
                                <span className="kiosk-row__end">
                                  <span className="secfig">
                                    {interpolate(t('tutorial:figures_n', '{n} 图'), { n: s.figure_count })}
                                  </span>
                                  {s.has_video && (
                                    <span className="kiosk-tag kiosk-tag--win">
                                      {t('tutorial:has_video', '有视频')}
                                    </span>
                                  )}
                                  <Icon name="caret-right" />
                                </span>
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        )}
      </KioskScrollZone>
    </div>
  );
};

export default TutorialBooksPage;
