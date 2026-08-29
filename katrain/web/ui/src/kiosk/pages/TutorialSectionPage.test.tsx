import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import type { TutorialSectionDetail } from '../../types/tutorial';
import TutorialSectionPage from './TutorialSectionPage';

/**
 * 屏 25 课程 · 小节讲解的**行为**那一半。版式归
 * `tests/kiosk-screen-25-section.fourup.spec.ts`(眼睛)和
 * `tests/kiosk-shell-geometry.spec.ts`(机器量刻度带对不对得上线),这里一条几何都不断言 ——
 * jsdom 没有布局引擎,对「字和线对不对齐」无权作证。
 *
 * 下面每一条挂了都是一个产品缺陷:
 *   ① **有没有视频看 `figure.video_asset`,不看 `section.has_video`** —— 后者从详情端点
 *      出来时恒是 `False`(`tutorials/models.py:52` 的 Pydantic 默认),那是个恒假的字段。
 *   ② **视频不是一进来就放**:进来先看棋图,按了「看视频讲解」它才占那块 516。
 *   ③ **「讲解」是三级阶梯**,四个词一个都不共用;两头都没有时灰掉**并说明原因**。
 *   ④ **手数把子藏起来**:编号大于当前手数的子整颗不画。没编号的图整块控件不渲染。
 *   ⑤ **没有 viewport 时「局部 / 全盘」整个不画** —— 上一版那个二选一在这种图上按了没反应。
 *   ⑥ **刻度带写的是这个窗口里的坐标**,不是恒 19 个字。
 *   ⑦ **「← 目录」回得到你离开时那一屏**(书 + 摊开的章)。
 */

const { getSection } = vi.hoisted(() => ({ getSection: vi.fn() }));
vi.mock('../../api/tutorialApi', () => ({
  TutorialReadAPI: {
    getSection: (...a: unknown[]) => getSection(...a),
    assetUrl: (p: string) => `/api/v1/tutorials/assets/${p}`,
  },
}));
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

// jsdom 的 <audio> 没有真的解码器 —— 这两个是**脚手架**(让组件跑起来),不是被测的结论。
beforeEach(() => {
  vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined);
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {});
});

const figure = (over: Record<string, unknown>) => ({
  id: 101, section_id: 10, page: 12, figure_label: '图1',
  book_text: null, page_context_text: null, bbox: null,
  page_image_path: null,
  board_payload: {
    size: 19,
    stones: { B: [[2, 16], [3, 15]], W: [[4, 15]] },
    labels: { '3,15': '1', '4,15': '2' },
    letters: { '5,14': 'A' },
    shapes: { '2,14': 'triangle' },
    highlights: [[2, 16]],
    viewport: { col: 0, row: 9, size: 10 },
  },
  recognition_debug: null, narration: null, audio_asset: null, video_asset: null,
  video_duration_ms: null, video_size_bytes: null, order: 0, updated_at: null,
  ...over,
});

const FIG_VIDEO = figure({
  id: 101, figure_label: '图4',
  video_asset: 'tutorial_assets/b/video/fig_1.mp4',
  video_duration_ms: 24000,
  narration: '白 C5 是禁入点。',
  audio_asset: 'tutorial_assets/b/audio/fig_1.mp3',
});
const FIG_AUDIO = figure({
  id: 102, figure_label: '图5', audio_asset: 'tutorial_assets/b/audio/fig_2.mp3',
  narration: '能提子就不是禁入点。',
});
const FIG_TEXT = figure({ id: 103, figure_label: '图6', narration: '这一段书上有字，没录音。' });
const FIG_NONE = figure({ id: 104, figure_label: '图7', narration: null, book_text: null });

// `has_video` 故意留 false —— 这一屏一个字都不许读它。
const SECTION = {
  id: 10, chapter_id: 11, section_number: '2', title: '禁入点', order: 0,
  figure_count: 4, has_video: false, figures: [FIG_VIDEO, FIG_AUDIO, FIG_TEXT, FIG_NONE],
} as unknown as TutorialSectionDetail;

const NAV = {
  bookId: 7, bookTitle: '围棋入门一本通', category: '入门',
  chapterId: 71, chapterNumber: '第 3 章', chapterTitle: '禁入点与打劫',
};

const renderPage = (entry: string | { pathname: string; state: unknown } = '/kiosk/tutorial/section/10') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/kiosk/tutorial/section/:sectionId" element={<TutorialSectionPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  );

const ready = () => waitFor(() => expect(screen.getAllByTestId('tutorial-figure-row').length).toBeGreaterThan(0));
const stones = (color: 'b' | 'w') => document.querySelectorAll(`[data-stone="${color}"]`);
const topRuler = () => [...document.querySelectorAll('.kiosk-board__ruler--top span')].map((e) => e.textContent);
const leftRuler = () => [...document.querySelectorAll('.kiosk-board__ruler--left span')].map((e) => e.textContent);

beforeEach(() => {
  vi.clearAllMocks();
  getSection.mockResolvedValue(SECTION);
});

describe('屏 25 课程 · 小节讲解', () => {
  it('进来看到的是**棋图**,不是视频 —— 视频要按了才占那块 516', async () => {
    renderPage();
    await ready();
    expect(screen.getByTestId('tutorial-figure-board')).toBeInTheDocument();
    expect(document.querySelector('video'), '一进来就自动放视频').toBeNull();
  });

  it('按「看视频讲解」视频占了盘位,再按回到棋图;src 和 poster 都从 figure 来', async () => {
    renderPage();
    await ready();
    await userEvent.click(screen.getByRole('button', { name: '看视频讲解' }));
    const video = document.querySelector('video')!;
    expect(video.getAttribute('src')).toBe('/api/v1/tutorials/assets/tutorial_assets/b/video/fig_1.mp4');
    expect(video.getAttribute('poster')).toBe('/api/v1/tutorials/assets/tutorial_assets/b/video/fig_1.jpg');
    expect(screen.queryByTestId('tutorial-figure-board'), '视频和棋图同时占着左边那一格').toBeNull();

    await userEvent.click(screen.getByRole('button', { name: '回到棋图' }));
    expect(screen.getByTestId('tutorial-figure-board')).toBeInTheDocument();
    expect(document.querySelector('video')).toBeNull();
  });

  it('三级阶梯:视频 / 语音 / 文字 / 暂无,四个词一个都不共用', async () => {
    renderPage();
    await ready();
    const rows = screen.getAllByTestId('tutorial-figure-row');
    expect(rows[0]).toHaveTextContent('视频讲解');
    expect(rows[1]).toHaveTextContent('语音讲解');
    expect(rows[2]).toHaveTextContent('文字讲解');
    expect(rows[3]).toHaveTextContent('暂无讲解');
    // 稿子那对作废了:它把「有没有旁白」和「有没有视频」当成一根轴。
    expect(screen.queryByText('有讲解')).toBeNull();
    expect(screen.queryByText('本图暂无视频')).toBeNull();
  });

  it('秒数只在有视频时长时出 —— 语音那张不编一个时长', async () => {
    renderPage();
    await ready();
    const rows = screen.getAllByTestId('tutorial-figure-row');
    expect(rows[0]).toHaveTextContent('24 秒');
    expect(rows[1]).not.toHaveTextContent('秒');
  });

  it('只有语音的那张:动作键变成播放,盘位仍然是棋图', async () => {
    renderPage();
    await ready();
    await userEvent.click(screen.getAllByTestId('tutorial-figure-row')[1]);
    const play = screen.getByRole('button', { name: '播放语音讲解' });
    expect(play).toBeEnabled();
    await userEvent.click(play);
    expect(screen.getByTestId('tutorial-figure-audio')).toHaveAttribute(
      'src', '/api/v1/tutorials/assets/tutorial_assets/b/audio/fig_2.mp3',
    );
    expect(document.querySelector('video')).toBeNull();
    expect(screen.getByRole('button', { name: '停下' })).toBeInTheDocument();
  });

  it('两头都没有时灰掉**并说出原因** —— 灰而不说原因是这套稿子专门骂过的事', async () => {
    renderPage();
    await ready();
    await userEvent.click(screen.getAllByTestId('tutorial-figure-row')[3]);
    const none = screen.getByRole('button', { name: '暂无讲解' });
    expect(none).toBeDisabled();
    // 屏上那句由讲解块自己说(「书上没有配文字,也还没有录讲解」);读屏那一侧走 title。
    expect(screen.getByTestId('tutorial-figure-explain')).toHaveTextContent(/还没有录讲解/);
    expect(none).toHaveAttribute('title', expect.stringContaining('还没有录讲解'));
    expect(screen.queryByText(/云端同步下来才会有/), '同一句话占了两处').toBeNull();

    await userEvent.click(screen.getAllByTestId('tutorial-figure-row')[2]);
    expect(screen.getByRole('button', { name: '只有文字讲解' })).toBeDisabled();
    // 这一档屏上那段是**书上的字**,不是「为什么灰」——所以那句话要另有落点。
    expect(screen.getByText(/已经写在上面了/)).toBeInTheDocument();
  });

  it('手数:退到第 1 手时第 2 手那颗子整颗不画,读数跟着走', async () => {
    renderPage();
    await ready();
    expect(stones('b')).toHaveLength(2);
    expect(stones('w')).toHaveLength(1);

    await userEvent.click(screen.getByRole('button', { name: '退一手' }));
    expect(screen.getByTestId('tutorial-step-track').parentElement).toHaveTextContent('走到第 1 手');
    expect(stones('w'), '第 2 手是白子,退到第 1 手它还在盘上').toHaveLength(0);
    expect(stones('b'), '没编号的底子和第 1 手都该在').toHaveLength(2);

    await userEvent.click(screen.getByRole('button', { name: '退一手' }));
    expect(screen.getByTestId('tutorial-step-track').parentElement).toHaveTextContent('只摆底子');
    expect(stones('b')).toHaveLength(1);
  });

  it('没编号的图:手数那一块整个不渲染,不摆一个 0/0 的控件', async () => {
    getSection.mockResolvedValue({
      ...SECTION,
      figures: [figure({ id: 201, board_payload: { size: 19, stones: { B: [[3, 3]], W: [] }, viewport: null } })],
    });
    renderPage();
    await ready();
    expect(screen.queryByTestId('tutorial-step-group')).toBeNull();
  });

  it('没有 viewport 时「局部 / 全盘」整个不画 —— 那一屏没有第二种画法', async () => {
    getSection.mockResolvedValue({
      ...SECTION,
      figures: [figure({ id: 202, board_payload: { size: 19, stones: { B: [[3, 3]], W: [] }, viewport: null } })],
    });
    renderPage();
    await ready();
    expect(screen.queryByRole('radio', { name: '局部' })).toBeNull();
    expect(topRuler(), '全盘时刻度带是 19 个字').toHaveLength(19);
  });

  it('默认落在「局部」;刻度带写的是这个窗口里的坐标,切到全盘才变 19 个', async () => {
    renderPage();
    await ready();
    expect(screen.getByRole('radio', { name: '局部' })).toHaveAttribute('aria-checked', 'true');
    // viewport {col:0,row:9,size:10} = 左下角:列 A–K(跳 I)、行 10…1
    expect(topRuler()).toEqual(['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K']);
    expect(leftRuler()).toEqual(['10', '9', '8', '7', '6', '5', '4', '3', '2', '1']);

    await userEvent.click(screen.getByRole('radio', { name: '全盘' }));
    expect(topRuler()).toHaveLength(19);
    expect(leftRuler()[0]).toBe('19');
  });

  it('翻图:换一张之后手数、局部/全盘、视频全部回到这一张自己的默认', async () => {
    renderPage();
    await ready();
    await userEvent.click(screen.getByRole('button', { name: '看视频讲解' }));
    expect(document.querySelector('video')).toBeTruthy();

    await userEvent.click(screen.getByRole('button', { name: '下一图' }));
    expect(document.querySelector('video'), '换了图,上一张的视频还占着盘位').toBeNull();
    expect(screen.getByTestId('tutorial-section-pagebar')).toHaveTextContent('第 2 / 4 图');
  });

  it('页控条按稿子写「第 3 章 · 第 2 节 禁入点」;没有 state 时不出现 undefined', async () => {
    renderPage({ pathname: '/kiosk/tutorial/section/10', state: NAV });
    await ready();
    expect(screen.getByTestId('tutorial-section-pagebar')).toHaveTextContent('第 3 章 · 第 2 节 禁入点');

    mockNavigate.mockClear();
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('tutorial-section-pagebar')).toHaveLength(2));
    expect(screen.queryByText(/undefined/)).toBeNull();
  });

  it('「← 目录」回得到你离开时那一屏:书 + 摊开的那一章', async () => {
    renderPage({ pathname: '/kiosk/tutorial/section/10', state: NAV });
    await ready();
    await userEvent.click(screen.getByRole('button', { name: /目录/ }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tutorial/%E5%85%A5%E9%97%A8?book=7&ch=71');
  });

  it('没有 state(深链)时「← 目录」退回课程首页 —— 不猜一个分类', async () => {
    renderPage();
    await ready();
    await userEvent.click(screen.getByRole('button', { name: /目录/ }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tutorial');
  });

  it('读不到这一节:说出来 + 重试,重试真的再请求一次', async () => {
    getSection.mockRejectedValueOnce(new Error('这一节 500'));
    renderPage();
    await screen.findByTestId('tutorial-section-error');
    expect(screen.getByTestId('tutorial-section-error')).toHaveTextContent('这一节 500');
    await userEvent.click(screen.getByRole('button', { name: '重试' }));
    await ready();
    expect(getSection).toHaveBeenCalledTimes(2);
  });

  it('目录里有这一节、正文还没同步:另一句话', async () => {
    getSection.mockResolvedValue({ ...SECTION, figures: [] });
    renderPage();
    await screen.findByTestId('tutorial-section-empty');
    expect(screen.getByTestId('tutorial-section-empty')).toHaveTextContent('这一节还没有棋图');
  });

  it('字母和记号画在空点上,并且带着坐标把手 —— 掉了就是掉书正文里的宾语', async () => {
    renderPage();
    await ready();
    expect(document.querySelector('.gob .letter[data-at="F5"]')?.textContent).toBe('A');
    expect(document.querySelector('.gob .shape[data-at]')).toBeNull();  // 记号是 polygon,没有 data-at
    expect(document.querySelectorAll('.gob .shape')).toHaveLength(1);
    expect(document.querySelectorAll('.gob .hl')).toHaveLength(1);
  });
});
