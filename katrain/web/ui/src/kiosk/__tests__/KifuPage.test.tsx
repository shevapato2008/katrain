import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import KifuPage from '../pages/KifuPage';
import type { KifuAlbumSummary } from '../../types/kifu';
import { ApiError } from '../../api';
import {
  __resetKioskActivityStorageForTests,
  setKioskIdentity,
} from '../storage/kioskActivityStorage';

/**
 * 屏 15 · 棋谱 `/kiosk/kifu`。
 *
 * 这份文件是**整份重写**的:上一版断言的是 MUI 的两栏「列表 + 预览」(`variant="h4"` 标题、
 * `CardActionArea`、`Pagination`、右栏那块 `LiveBoard` 预览)。那套界面本轮整个换掉了 ——
 * 预览和「在研究中打开」搬进了屏 16(`KifuDetailPage`)。
 *
 * 几条**判据落在哪儿**值得写明:
 *  · 列表默认摊开(2026-09-23 Fan)—— 断言落在 `getAlbums` 的调用次数与参数形状上:
 *    进来只有一发,就是第一页六局。
 *  · 「已摆完」那三条(有 total / 没 total / k < total)是**同一条口径的三个方向**:
 *    旧进度里没有 `total`,读到 `undefined` 的正确反应是不下结论。
 */

const mockNavigate = vi.fn();
const TEST_UUID = 'kifu-page-test-user';
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const { getAlbums } = vi.hoisted(() => ({ getAlbums: vi.fn() }));
vi.mock('../../api/kifuApi', () => ({ KifuAPI: { getAlbums } }));

const album = (id: number, over: Partial<KifuAlbumSummary> = {}): KifuAlbumSummary => ({
  id,
  player_black: '柯洁', player_white: '申真谞',
  black_rank: '九段', white_rank: '九段',
  event: '第 29 届三星杯', result: 'B+R', move_count: 241,
  date_played: '2026-06-30', board_size: 19, handicap: 0,
  komi: 7.5, rules: 'chinese', round_name: '半决赛',
  ...over,
});

const renderPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={['/kiosk/kifu']}>
        <KifuPage />
      </MemoryRouter>
    </ThemeProvider>,
  );

/** 往当前用户的 localStorage 命名空间里造一条「最近摆过」。 */
const seedRecent = (
  entries: { id: string; name: string; savedAt: number }[],
  progress: Record<string, { k: number; frames: number; updatedAt: number; total?: number }> = {},
  sgfFor: string[] = [],
) => {
  localStorage.setItem(`baipu:recent:${TEST_UUID}`, JSON.stringify(entries));
  for (const [id, p] of Object.entries(progress)) {
    localStorage.setItem(`baipu:progress:${id}:${TEST_UUID}`, JSON.stringify(p));
  }
  for (const id of sgfFor) {
    localStorage.setItem(`baipu:sgf:${id}:${TEST_UUID}`, JSON.stringify({
      id, name: id, sgf: '(;FF[4]GM[1]SZ[19];B[pd])', savedAt: 1,
    }));
  }
};

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  __resetKioskActivityStorageForTests();
  setKioskIdentity(TEST_UUID, false);
  getAlbums.mockResolvedValue({ items: [album(1), album(2)], total: 2, page: 1, page_size: 6 });
});

describe('屏 15 棋谱 · 问候与列表头', () => {
  // 副标去掉了稿子里的「职业直播」:Fan 2026-09-22 裁定 kiosk 端不做直播,屏上不许许诺没有的东西。
  it('问候行照稿子写「看别人的棋」,副标不提直播', () => {
    renderPage();
    expect(screen.getByText('看别人的')).toBeInTheDocument();
    expect(screen.getByText('棋')).toBeInTheDocument();
    expect(screen.getByText('名局，以及把谱摆到实体盘上')).toBeInTheDocument();
  });

  // 2026-09-23 Fan:列表要一进来就在。三张卡(搜棋谱 / 摆到实体盘 / 导入 SGF)拆了,
  // 「导入 SGF」挪到搜索框右边 —— 屏上一张卡都不剩,也就没有要先按的开关。
  it('没有卡片,搜索框和「导入 SGF」一进来就在同一行', () => {
    renderPage();
    expect(document.querySelectorAll('.kiosk-card')).toHaveLength(0);
    const bar = document.querySelector('[data-testid="kifu-search"] .ksearch__bar')!;
    expect(within(bar as HTMLElement).getByPlaceholderText('棋手、赛事、年份都能搜')).toBeInTheDocument();
    expect(within(bar as HTMLElement).getByRole('button', { name: /导入 SGF/ })).toBeInTheDocument();
  });

  it('「导入 SGF」按下去开的是本地文件选择框', () => {
    renderPage();
    const input = screen.getByTestId('kifu-sgf-input') as HTMLInputElement;
    const clicked = vi.spyOn(input, 'click');
    fireEvent.click(screen.getByRole('button', { name: /导入 SGF/ }));
    expect(clicked).toHaveBeenCalled();
  });
});

describe('屏 15 棋谱 · 名局列表默认摊开', () => {
  it('进来就拉第一页六局并铺出行 —— 不先探一个数、不等谁按开关', async () => {
    renderPage();
    const rows = await screen.findAllByText('柯洁 对 申真谞');
    expect(rows).toHaveLength(2);
    // 判据落在请求形状上:只有一发,就是列表本身。旧写法挂载时先发一发 page_size: 1 探总数。
    expect(getAlbums).toHaveBeenCalledTimes(1);
    expect(getAlbums).toHaveBeenCalledWith({ q: undefined, page: 1, page_size: 6 });
  });

  it('组标题右端写的是真数据「共 N 局」', async () => {
    getAlbums.mockResolvedValue({ items: [album(1)], total: 1234, page: 1, page_size: 6 });
    renderPage();
    expect(await screen.findByText('共 1,234 局')).toBeInTheDocument();
    expect(screen.queryByText('按棋手 / 赛事 / 日期搜')).not.toBeInTheDocument();
  });

  it('点一行进屏 16 的详情', async () => {
    renderPage();
    const rows = await screen.findAllByText('柯洁 对 申真谞');
    fireEvent.click(rows[0].closest('button')!);
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/kifu/1');
  });

  it('没搜的时候库是空的:说「未找到棋谱」,不说「换棋手名再试」', async () => {
    getAlbums.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 6 });
    renderPage();
    expect(await screen.findByText('未找到棋谱')).toBeInTheDocument();
    expect(screen.queryByText('没有对得上的谱')).toBeNull();
    expect(screen.queryByText('换棋手名、赛事名或者年份再试。')).toBeNull();
  });

  it('搜了对不上:说「没有对得上的谱」并给换词的提示', async () => {
    renderPage();
    await screen.findAllByText('柯洁 对 申真谞');
    getAlbums.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 6 });
    fireEvent.change(screen.getByPlaceholderText('棋手、赛事、年份都能搜'), { target: { value: '不存在' } });
    expect(await screen.findByText('没有对得上的谱')).toBeInTheDocument();
    expect(screen.getByText('换棋手名、赛事名或者年份再试。')).toBeInTheDocument();
    expect(getAlbums).toHaveBeenLastCalledWith({ q: '不存在', page: 1, page_size: 6 });
  });

  it('翻页:第 1 页「上一页」是灰的;「下一页」发第 2 页', async () => {
    getAlbums.mockResolvedValue({ items: [album(1)], total: 20, page: 1, page_size: 6 });
    renderPage();
    await screen.findByText('1 / 4');
    expect(screen.getByRole('button', { name: '上一页' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '下一页' }));
    await waitFor(() => expect(getAlbums).toHaveBeenLastCalledWith({ q: undefined, page: 2, page_size: 6 }));
  });

  // 搜索防抖原先挂载时也跑一次:350ms 后 setQuery('') + setPage(1)。列表藏在开关后面时没人能在
  // 350ms 内翻页;默认摊开后,进屏就点「下一页」会被它弹回第 1 页。
  it('进来马上翻页,不会被搜索防抖弹回第 1 页', async () => {
    // 全假时钟:点击一定落在挂载后 350ms 以内(`findBy*` 会让真时间流过去,点击可能晚于那一下)。
    vi.useFakeTimers();
    try {
      getAlbums.mockResolvedValue({ items: [album(1)], total: 20, page: 1, page_size: 6 });
      renderPage();
      await act(async () => { await vi.advanceTimersByTimeAsync(0); });
      expect(screen.getByText('1 / 4')).toBeInTheDocument();
      fireEvent.click(screen.getByRole('button', { name: '下一页' }));
      await act(async () => { await vi.advanceTimersByTimeAsync(0); });
      expect(screen.getByText('2 / 4')).toBeInTheDocument();
      await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
      expect(screen.getByText('2 / 4')).toBeInTheDocument();
      expect(getAlbums).toHaveBeenLastCalledWith({ q: undefined, page: 2, page_size: 6 });
    } finally {
      vi.useRealTimers();
    }
  });

  it('在第 3 页改搜索词,结果回第 1 页', async () => {
    getAlbums.mockResolvedValue({ items: [album(1)], total: 30, page: 1, page_size: 6 });
    renderPage();
    await screen.findByText('1 / 5');
    fireEvent.click(screen.getByRole('button', { name: '下一页' }));
    await screen.findByText('2 / 5');
    fireEvent.click(screen.getByRole('button', { name: '下一页' }));
    await screen.findByText('3 / 5');
    fireEvent.change(screen.getByPlaceholderText('棋手、赛事、年份都能搜'), { target: { value: '柯洁' } });
    await waitFor(() => expect(getAlbums).toHaveBeenLastCalledWith({ q: '柯洁', page: 1, page_size: 6 }));
  });

  it('库读不到时如实报错并给重试 —— 重试真的会再发一次请求', async () => {
    getAlbums.mockRejectedValue(new Error('boom'));
    renderPage();
    expect(await screen.findByText('棋谱库读不到')).toBeInTheDocument();
    expect(screen.getByText('boom')).toBeInTheDocument();
    const before = getAlbums.mock.calls.length;
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    await waitFor(() => expect(getAlbums.mock.calls.length).toBe(before + 1));
  });

  it('棋谱库连不上云端(503)时说「要联网」,不印原文,也不说「没搜到」', async () => {
    getAlbums.mockRejectedValue(new ApiError(503, 'Request failed 503: {"detail":"Remote kifu service unavailable"}'));
    renderPage();
    expect(await screen.findByText('棋谱库要联网才能搜')).toBeInTheDocument();
    expect(screen.queryByText(/Request failed/)).toBeNull();
    expect(screen.queryByText('没有对得上的谱')).toBeNull();
    expect(screen.getByRole('button', { name: '重试' })).toBeInTheDocument();
    // 断网不连累另外两条路:导入 SGF 还在
    expect(screen.getByRole('button', { name: /导入 SGF/ })).toBeInTheDocument();
  });
});

describe('屏 15 棋谱 · 继续摆谱与最近摆过', () => {
  it('有没摆完的谱就出「继续摆谱」,写的是第几手', () => {
    seedRecent(
      [{ id: 'kifu_1', name: '第 29 届三星杯 · 半决赛', savedAt: Date.now() }],
      { kifu_1: { k: 47, frames: 0, updatedAt: Date.now(), total: 241 } },
      ['kifu_1'],
    );
    renderPage();
    const bar = screen.getByTestId('resume-baipu-bar');
    expect(within(bar).getByText('继续摆谱')).toBeInTheDocument();
    expect(bar.textContent).toContain('上次摆到第 47 手');
  });

  it('摆完了的那份不会再被当成「继续摆谱」', () => {
    seedRecent(
      [{ id: 'kifu_1', name: '名人战 · 第七局', savedAt: Date.now() }],
      { kifu_1: { k: 241, frames: 0, updatedAt: Date.now(), total: 241 } },
      ['kifu_1'],
    );
    renderPage();
    expect(screen.queryByTestId('resume-baipu-bar')).not.toBeInTheDocument();
    expect(screen.getByText('已摆完')).toBeInTheDocument();
  });

  // ⚠️ 这一条守的是 `BaipuProgress.total` 那段注释:2026-08-22 之前存下的进度里**没有**
  // 这个字段。把 `undefined` 当成「没摆完」和当成「摆完了」都是在替用户下结论 ——
  // 这里要的是**不下结论**:不出「已摆完」的标,也不出「继续摆谱」那条横幅。
  it('旧进度没有 total 时,既不说「已摆完」也不当成能继续', () => {
    seedRecent(
      [{ id: 'kifu_9', name: '老进度', savedAt: Date.now() }],
      { kifu_9: { k: 12, frames: 0, updatedAt: Date.now() } },
      ['kifu_9'],
    );
    renderPage();
    expect(screen.queryByText('已摆完')).not.toBeInTheDocument();
    // k > 0 且不能证明摆完了 ⇒ 仍然可以接着摆(那是安全的一侧:再摆一遍不会丢东西)
    expect(screen.getByTestId('resume-baipu-bar').textContent).toContain('上次摆到第 12 手');
  });

  it('「接着摆」带着本地缓存的谱进摆谱屏', () => {
    seedRecent(
      [{ id: 'kifu_1', name: '三星杯', savedAt: Date.now() }],
      { kifu_1: { k: 47, frames: 0, updatedAt: Date.now(), total: 241 } },
      ['kifu_1'],
    );
    renderPage();
    fireEvent.click(within(screen.getByTestId('kifu-recent-rows')).getByRole('button', { name: '接着摆' }));
    expect(mockNavigate).toHaveBeenCalledWith(
      '/kiosk/baipu/session/kifu_1',
      expect.objectContaining({ state: expect.objectContaining({ name: 'kifu_1' }) }),
    );
  });

  it('缓存没了就说清楚,不假装还能摆', () => {
    seedRecent(
      [{ id: 'kifu_1', name: '三星杯', savedAt: Date.now() }],
      { kifu_1: { k: 47, frames: 0, updatedAt: Date.now(), total: 241 } },
      [],   // 谱的缓存被清掉了
    );
    renderPage();
    fireEvent.click(within(screen.getByTestId('kifu-recent-rows')).getByRole('button', { name: '接着摆' }));
    expect(mockNavigate).not.toHaveBeenCalled();
    expect(screen.getByTestId('kifu-action-error').textContent).toContain('本地缓存没了');
  });

  it('一次都没摆过时写的是空态,不是一排假行', () => {
    renderPage();
    expect(screen.getByTestId('kifu-recent-empty')).toBeInTheDocument();
    expect(screen.queryByTestId('kifu-recent-rows')).not.toBeInTheDocument();
  });
});
