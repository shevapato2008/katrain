import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ThemeProvider } from '@mui/material';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { TutorialCategory } from '../../types/tutorial';
import { kioskTheme } from '../theme';
import TutorialCategoriesPage from './TutorialCategoriesPage';

/**
 * 屏 23 课程 `/kiosk/tutorial`。
 *
 * 这一屏最容易犯的错是**把三种「没有」混成一种**:还没查、查了拿不到、查到了是空。
 * 屏上分别是「正在跟云端对课」/「加载失败」/「暂无教程」—— 每一条都在这儿钉住。
 *
 * ⚠️ 几何不在这儿断言:左栏 296、右栏 680、整栏滚,判据在
 * `tests/kiosk-shell-geometry.spec.ts` 和 `kiosk-shell-scroll.spec.ts`(真浏览器量)。
 */

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => ({
  ...(await importOriginal<typeof import('react-router-dom')>()),
  useNavigate: () => mockNavigate,
}));

const { getCategories } = vi.hoisted(() => ({ getCategories: vi.fn() }));
vi.mock('../../api/tutorialApi', () => ({ TutorialReadAPI: { getCategories } }));

const cat = (over: Partial<TutorialCategory>): TutorialCategory => ({
  slug: 'basics', title: '入门', summary: '规则与吃子', order: 1, book_count: 4, ...over,
});

const renderPage = () => render(
  <ThemeProvider theme={kioskTheme}>
    <MemoryRouter><TutorialCategoriesPage /></MemoryRouter>
  </ThemeProvider>,
);

const ringOf = (title: string) =>
  screen.getByRole('button', { name: new RegExp(title) }).querySelector('.kiosk-card__tile b')?.textContent;

beforeEach(() => {
  vi.clearAllMocks();
  getCategories.mockResolvedValue([
    cat({}),
    cat({ slug: 'shape', title: '基本功', summary: '死活 · 手筋', order: 2, book_count: 7 }),
    cat({ slug: 'fuseki', title: '布局与定式', summary: '开局怎么走', order: 3, book_count: 2 }),
  ]);
});

describe('屏 23 · 三种「没有」各有各的说法', () => {
  it('还没查到的时候说的是「正在跟云端对课」', () => {
    getCategories.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByTestId('tutorial-loading')).toBeInTheDocument();
    expect(screen.queryByTestId('tutorial-empty')).toBeNull();
  });

  it('拿不到就报错,重试真的会再问一次', async () => {
    getCategories.mockRejectedValueOnce(new Error('云端连不上'));
    renderPage();
    expect(await screen.findByTestId('tutorial-error')).toBeInTheDocument();
    expect(screen.getByText('云端连不上')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    await waitFor(() => expect(getCategories).toHaveBeenCalledTimes(2));
    await screen.findByTestId('tutorial-categories');
  });

  // **接口答了、答的是空** —— 这时候「暂无教程」是结论,不是「还没查」。
  it('接口返回空就是空态一句话,不摆一排点不开的卡', async () => {
    getCategories.mockResolvedValue([]);
    renderPage();
    expect(await screen.findByTestId('tutorial-empty')).toBeInTheDocument();
    expect(screen.queryByTestId('tutorial-categories')).toBeNull();
  });
});

describe('屏 23 · 分类', () => {
  it('分类名和本数全从接口来,一个字都不写死', async () => {
    getCategories.mockResolvedValue([cat({ title: '云端新分类', summary: '接口说了算', book_count: 9 })]);
    renderPage();
    const cards = await screen.findByTestId('tutorial-categories');
    expect(cards.textContent).toContain('云端新分类');
    expect(cards.textContent).toContain('接口说了算');
    expect(cards.textContent).toContain('9 本');
    // 稿子上那三个名字是**形状不是清单**
    expect(cards.textContent).not.toContain('基本功');
  });

  it('按 order 排,不按接口给的顺序', async () => {
    getCategories.mockResolvedValue([
      cat({ slug: 'c', title: '第三', order: 3 }),
      cat({ slug: 'a', title: '第一', order: 1 }),
      cat({ slug: 'b', title: '第二', order: 2 }),
    ]);
    renderPage();
    const cards = await screen.findByTestId('tutorial-categories');
    expect([...cards.querySelectorAll('.kiosk-card__t b')].map((b) => b.textContent))
      .toEqual(['第一', '第二', '第三']);
  });

  // ⚠️ 环渲染的是**进度百分比**,而接口只给本数。拿本数去画进度环会画出一条谁也读不懂的弧。
  it('环里恒是「—」——每类看到哪儿了接口不给,本数写在副标上', async () => {
    renderPage();
    await screen.findByTestId('tutorial-categories');
    expect(ringOf('入门')).toBe('—');
    expect(ringOf('基本功')).toBe('—');
    expect(screen.getByRole('button', { name: /入门/ }).textContent).toContain('4 本');
  });

  // 稿子这一格写「每类几本，由接口返回」——那是说给读稿人听的;规范里这一格放的是数据。
  it('组标题右端写的是真数,不是一句关于数据从哪来的话', async () => {
    renderPage();
    await screen.findByTestId('tutorial-categories');
    expect(screen.getByText('3 类 · 共 13 本')).toBeInTheDocument();
    expect(screen.queryByText(/由接口返回/)).toBeNull();
  });

  it('点一张卡进那一类的书目', async () => {
    renderPage();
    await screen.findByTestId('tutorial-categories');
    fireEvent.click(screen.getByRole('button', { name: /基本功/ }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tutorial/shape');
  });
});

describe('屏 23 · 另外两块', () => {
  it('「一课长什么样」四层都在,最里那层标着带音频', async () => {
    renderPage();
    await screen.findByTestId('tutorial-categories');
    const rows = screen.getByTestId('tutorial-anatomy');
    expect(rows.querySelectorAll('.kiosk-row')).toHaveLength(4);
    expect(rows.textContent).toContain('节才是「一课」');
    expect(rows.querySelector('.kiosk-tag--win')?.textContent).toBe('带音频');
  });

  // 有课的时候它就成了一排永远在的杂物 —— 只在没课的时候把人送到有内容的地方去。
  it('「现在能练的」只在一类都没有的时候出现', async () => {
    renderPage();
    await screen.findByTestId('tutorial-categories');
    expect(screen.queryByTestId('tutorial-instead')).toBeNull();

    getCategories.mockResolvedValue([]);
    renderPage();
    const instead = await screen.findAllByTestId('tutorial-instead');
    expect(instead).toHaveLength(1);
    expect(instead[0].textContent).toContain('去训练营');
    expect(instead[0].textContent).toContain('去摆谱');
  });

  it('那两张卡各去各的地方', async () => {
    getCategories.mockResolvedValue([]);
    renderPage();
    await screen.findByTestId('tutorial-instead');
    fireEvent.click(screen.getByRole('button', { name: /去训练营/ }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego');
    fireEvent.click(screen.getByRole('button', { name: /去摆谱/ }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/baipu');
  });
});
