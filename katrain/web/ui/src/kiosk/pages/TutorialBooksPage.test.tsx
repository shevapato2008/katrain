import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import TutorialBooksPage from './TutorialBooksPage';

/**
 * 屏 24 课程 · 书目与章节的**行为**那一半。版式归
 * `tests/kiosk-screen-24-books.fourup.spec.ts`(眼睛)和 `tests/kiosk-shell-scroll.spec.ts`
 * (机器量),这里一条几何都不断言。
 *
 * 这一屏是**两屏合一**:原来的 `tutorial/book/:bookId` + `TutorialBookDetailPage.tsx`
 * 一起删了。下面每一条挂了都是一个产品缺陷:
 *   ① 选中的书**在 URL 里** —— 页内 state 会让屏 25 的「← 目录」回到一本都没选的空半屏。
 *   ② 进度一处不上:环恒「—」、副标不写「已看到第 3 章」、章行行尾三态整个没有 ——
 *      盒上没有可信的「谁看过什么」,画出来就是关于一个人的假话。
 *   ③ 章数 / 节数 / 图数**全是真数**,一个字面量都不许写死。
 *   ④ 空态和读不到是**两句话**:前者是结论,后者是还没查。
 *   ⑤ 点到节要把 `category` 和 `hasVideo` 一起带过去 —— 前者是屏 25 返回的唯一去向,
 *      后者是**唯一可信的那一份**(详情端点的 `has_video` 恒假)。
 */

const { getBooks, getBook, getSections } = vi.hoisted(() => ({
  getBooks: vi.fn(), getBook: vi.fn(), getSections: vi.fn(),
}));
vi.mock('../../api/tutorialApi', () => ({
  TutorialReadAPI: { getBooks, getBook, getSections },
}));

const BOOKS = [
  { id: 7, category: '入门', subcategory: '', title: '围棋入门一本通', author: '吴老师', translator: null, slug: 'rumen', chapter_count: 2 },
  { id: 8, category: '入门', subcategory: '', title: '吃子技巧图解', author: null, translator: null, slug: 'chizi', chapter_count: 1 },
];

const CH = (id: number, n: string, title: string, count: number) =>
  ({ id, book_id: 7, chapter_number: n, title, order: id, section_count: count });

const BOOK7 = { ...BOOKS[0], chapters: [CH(71, '第 1 章', '棋盘与棋子', 2), CH(72, '第 2 章', '气与提子', 1)] };
const BOOK8 = { ...BOOKS[1], chapters: [CH(81, '第 1 章', '门吃', 1)] };

const SEC = (id: number, chapter: number, n: string, title: string, figs: number, video: boolean) =>
  ({ id, chapter_id: chapter, section_number: n, title, order: id, figure_count: figs, has_video: video });

const SECTIONS: Record<number, ReturnType<typeof SEC>[]> = {
  71: [SEC(711, 71, '1', '十九路', 4, true), SEC(712, 71, '2', '黑先白后', 3, false)],
  72: [SEC(721, 72, '1', '数气', 5, false)],
  81: [SEC(811, 81, '1', '门吃', 2, false)],
};

let lastPath = '';
const Spy = () => { const l = useLocation(); lastPath = `${l.pathname}${l.search}`; return null; };
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const renderPage = (entry = '/kiosk/tutorial/%E5%85%A5%E9%97%A8') => render(
  <ThemeProvider theme={kioskTheme}>
    <MemoryRouter initialEntries={[entry]}>
      <Spy />
      <Routes>
        <Route path="/kiosk/tutorial/:category" element={<TutorialBooksPage />} />
      </Routes>
    </MemoryRouter>
  </ThemeProvider>,
);

/** 目录读回来了 = 这一屏的控件全部就绪。 */
const tocReady = () => waitFor(() => expect(screen.getByTestId('tutorial-chapter-rows')).toBeInTheDocument());

beforeEach(() => {
  vi.clearAllMocks();
  lastPath = '';
  getBooks.mockResolvedValue(BOOKS);
  getBook.mockImplementation((id: number) => Promise.resolve(id === 8 ? BOOK8 : BOOK7));
  getSections.mockImplementation((id: number) => Promise.resolve(SECTIONS[id] ?? []));
});

describe('屏 24 课程 · 书目与章节', () => {
  it('没有 ?book= 时自动选第一本,并且**写进 URL**(replace)', async () => {
    renderPage();
    await tocReady();
    expect(lastPath, '选中的书没进 URL —— 屏 25 的「← 目录」会回到一本都没选的空半屏')
      .toContain('book=7');
  });

  it('地址里指名哪一本就读哪一本 —— 不是恒读第一本', async () => {
    renderPage('/kiosk/tutorial/%E5%85%A5%E9%97%A8?book=8');
    await tocReady();
    expect(getBook).toHaveBeenCalledWith(8);
    expect(screen.getByText('吃子技巧图解 · 目录')).toBeInTheDocument();
  });

  it('环恒是「—」,副标只写真章数,**不写「已看到第 N 章」**', async () => {
    renderPage();
    await tocReady();
    const cards = screen.getByTestId('tutorial-book-cards');
    expect(within(cards).getAllByText('—')).toHaveLength(2);
    expect(within(cards).queryByText(/%/), '环里出现了百分数 —— 那个进度盒上问不出来').toBeNull();
    expect(within(cards).getByText('吴老师 · 2 章')).toBeInTheDocument();
    expect(within(cards).queryByText(/已看到/)).toBeNull();
  });

  it('章数 / 节数 / 图数全是真数 —— 换一份下发就跟着变', async () => {
    renderPage();
    await tocReady();
    // 组标题右端:2 章 · 3 节(71 有两节、72 有一节)
    expect(screen.getByText('2 章 · 3 节')).toBeInTheDocument();
    const rows = screen.getAllByTestId('tutorial-chapter-row');
    // 第 1 章:2 节 · 7 图(4 + 3)
    expect(rows[0]).toHaveTextContent('2 节 · 7 图');
    expect(rows[1]).toHaveTextContent('1 节 · 5 图');
  });

  it('章行行尾**没有**「已看完 / 接着看 / 开始」那三态', async () => {
    renderPage();
    await tocReady();
    const rows = screen.getAllByTestId('tutorial-chapter-row');
    rows.forEach((r) => {
      expect(r).not.toHaveTextContent('已看完');
      expect(r).not.toHaveTextContent('接着看');
      expect(r).not.toHaveTextContent('开始');
    });
  });

  it('默认全收起;摊开一章、再按收起、按另一章换过去', async () => {
    renderPage();
    await tocReady();
    const rows = screen.getAllByTestId('tutorial-chapter-row');
    expect(rows[0]).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryAllByTestId('tutorial-section-row')).toHaveLength(0);

    await userEvent.click(rows[0]);
    expect(rows[0]).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getAllByTestId('tutorial-section-row')).toHaveLength(2);

    await userEvent.click(rows[1]);
    expect(rows[0]).toHaveAttribute('aria-expanded', 'false');
    expect(screen.getAllByTestId('tutorial-section-row')).toHaveLength(1);
    expect(screen.getByTestId('tutorial-section-row')).toHaveTextContent('数气');

    await userEvent.click(rows[1]);
    expect(screen.queryAllByTestId('tutorial-section-row')).toHaveLength(0);
  });

  /**
   * 上一版(`TutorialBookDetailPage`)是 `<Accordion defaultExpanded>` —— **每一章都摊开**。
   * 所以「摊开哪一章」不能只活在页内 state:屏 25 按「← 目录」回来时全收起,
   * 等于让人重新找一遍自己在哪。这一条挂了就是那条回归。
   */
  it('摊开哪一章进 URL(?ch=),带着 ?ch= 进来就是摊开的', async () => {
    renderPage();
    await tocReady();
    await userEvent.click(screen.getAllByTestId('tutorial-chapter-row')[1]);
    expect(lastPath).toContain('ch=72');

    lastPath = '';
    renderPage('/kiosk/tutorial/%E5%85%A5%E9%97%A8?book=7&ch=72');
    await waitFor(() => expect(screen.getAllByTestId('tutorial-chapter-rows')).toHaveLength(2));
    const second = screen.getAllByTestId('tutorial-chapter-rows')[1];
    const rows = within(second).getAllByTestId('tutorial-chapter-row');
    expect(rows[0]).toHaveAttribute('aria-expanded', 'false');
    expect(rows[1]).toHaveAttribute('aria-expanded', 'true');
    expect(within(second).getByTestId('tutorial-section-row')).toHaveTextContent('数气');
  });

  it('点节:去屏 25,并把 category / chapterId / hasVideo 一起带过去', async () => {
    renderPage();
    await tocReady();
    await userEvent.click(screen.getAllByTestId('tutorial-chapter-row')[0]);
    await userEvent.click(screen.getAllByTestId('tutorial-section-row')[0]);
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tutorial/section/711', {
      state: {
        bookId: 7, bookTitle: '围棋入门一本通', bookSlug: 'rumen',
        chapterId: 71, chapterTitle: '棋盘与棋子', sectionTitle: '十九路',
        category: '入门',
        hasVideo: true,
      },
    });
  });

  it('换一本书:目录跟着换,URL 也跟着换', async () => {
    renderPage();
    await tocReady();
    await userEvent.click(screen.getByRole('button', { name: /吃子技巧图解/ }));
    await waitFor(() => expect(screen.getByText('吃子技巧图解 · 目录')).toBeInTheDocument());
    expect(lastPath).toContain('book=8');
    expect(screen.getByTestId('tutorial-chapter-rows')).toHaveTextContent('门吃');
  });

  it('这一类一本书都没有:说的是**结论**,和「没读到」不是同一句', async () => {
    getBooks.mockResolvedValue([]);
    renderPage();
    await screen.findByTestId('tutorial-books-empty');
    expect(screen.getByTestId('tutorial-books-empty')).toHaveTextContent('这一类下面一本书都没有');
    // 一本都没有 ⇒ 下半屏整个不画,不摆一个空目录
    expect(screen.queryByTestId('tutorial-chapters')).toBeNull();
  });

  it('书目读不到:另一句话 + 重试,重试真的再请求一次', async () => {
    getBooks.mockRejectedValueOnce(new Error('云端没回话'));
    renderPage();
    await screen.findByTestId('tutorial-books-error');
    expect(screen.getByTestId('tutorial-books-error')).toHaveTextContent('没读到这一类的书目');
    expect(screen.getByTestId('tutorial-books-error')).toHaveTextContent('云端没回话');
    await userEvent.click(screen.getByRole('button', { name: '重试' }));
    await tocReady();
    expect(getBooks).toHaveBeenCalledTimes(2);
  });

  it('目录读不到:上半屏的书还在,下半屏说明为什么空', async () => {
    getBook.mockRejectedValue(new Error('目录 500'));
    renderPage();
    await screen.findByTestId('tutorial-toc-error');
    expect(screen.getByTestId('tutorial-toc-error')).toHaveTextContent('没读到这本书的目录');
    expect(screen.getByTestId('tutorial-book-cards')).toBeInTheDocument();
  });

  it('书在、正文还没同步下来:又是另一句话', async () => {
    getBook.mockResolvedValue({ ...BOOK7, chapters: [] });
    renderPage();
    await screen.findByTestId('tutorial-toc-empty');
    expect(screen.getByTestId('tutorial-toc-empty')).toHaveTextContent('这本书还没有章节');
  });

  it('返回键回课程首页', async () => {
    renderPage();
    await tocReady();
    await userEvent.click(screen.getByRole('button', { name: /课程/ }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tutorial');
  });
});
