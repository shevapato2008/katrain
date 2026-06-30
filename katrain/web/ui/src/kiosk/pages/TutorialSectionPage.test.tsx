import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import type { TutorialSectionDetail } from '../../types/tutorial';

// Mock the shared API (getSection + assetUrl).
const { getSection } = vi.hoisted(() => ({ getSection: vi.fn() }));
vi.mock('../../api/tutorialApi', () => ({
  TutorialReadAPI: {
    getSection: (...args: unknown[]) => getSection(...args),
    assetUrl: (p: string) => `/api/v1/tutorials/assets/${p}`,
  },
}));

// Kiosk is fixed-landscape.
vi.mock('../context/OrientationContext', () => ({
  useOrientation: () => ({ rotation: 0, isPortrait: false, setRotation: vi.fn() }),
}));

import TutorialSectionPage from './TutorialSectionPage';

const figure = (over: Record<string, unknown>) => ({
  id: 101, section_id: 10, page: 1, figure_label: '图1', book_text: null, page_context_text: null,
  bbox: null, page_image_path: 'tutorial_assets/test-book/pages/page_1.jpg',
  board_payload: { size: 19, stones: { B: [[3, 3]], W: [[15, 15]] }, labels: { '3,3': '1', '15,15': '2' }, viewport: { col: 0, row: 0, cols: 8, rows: 8 } },
  recognition_debug: null, narration: null, audio_asset: null, video_asset: null,
  video_duration_ms: null, video_size_bytes: null, order: 0, updated_at: null, ...over,
});

// A figure WITH its own video (the per-figure video_asset model).
const FIG_WITH_VIDEO = figure({
  id: 101, figure_label: '图1',
  video_asset: 'tutorial_assets/test-book/video/fig_1.mp4',
  narration: '黑1是三三点。',
  audio_asset: 'tutorial_assets/test-book/audio/fig_1.mp3',
});
// A figure WITHOUT a video.
const FIG_NO_VIDEO = figure({ id: 102, figure_label: '图2', video_asset: null });

// has_video is INTENTIONALLY false — the page must not use it; per-figure video_asset drives playback.
const SECTION: TutorialSectionDetail = {
  id: 10, chapter_id: 11, section_number: '1', title: '第一节', order: 0,
  figure_count: 2, has_video: false, figures: [FIG_WITH_VIDEO, FIG_NO_VIDEO],
} as unknown as TutorialSectionDetail;

const VIDEO_URL = '/api/v1/tutorials/assets/tutorial_assets/test-book/video/fig_1.mp4';
const POSTER_URL = '/api/v1/tutorials/assets/tutorial_assets/test-book/video/fig_1.jpg';

const renderSection = (entry: string | { pathname: string; state: unknown }) =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/kiosk/tutorial/section/:sectionId" element={<TutorialSectionPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  );

describe('TutorialSectionPage', () => {
  beforeEach(() => getSection.mockReset());

  it('plays the per-figure video (figure.video_asset) with its poster', async () => {
    getSection.mockResolvedValue(SECTION);
    const { container } = renderSection('/kiosk/tutorial/section/10');

    await waitFor(() => expect(container.querySelector('video')).toBeTruthy());
    const video = container.querySelector('video')!;
    expect(video.getAttribute('src')).toBe(VIDEO_URL);
    expect(video.getAttribute('poster')).toBe(POSTER_URL);
    // Note: the Referer is stripped document-wide via a kiosk-only
    // <meta name="referrer" content="no-referrer"> (vite.config.ts), not a
    // per-element attribute (which <video> does not honor).
  });

  it('renders the board with a 手数 replay slider', async () => {
    getSection.mockResolvedValue(SECTION);
    renderSection('/kiosk/tutorial/section/10');

    expect(await screen.findByText(/手数/)).toBeInTheDocument();
    expect(document.querySelector('.MuiSlider-root')).toBeTruthy();
  });

  it('renders a clean breadcrumb on deep-link with no router state (no "undefined")', async () => {
    getSection.mockResolvedValue(SECTION);
    renderSection('/kiosk/tutorial/section/10');

    expect(await screen.findByText('教程 ▸ 1. 第一节')).toBeInTheDocument();
    expect(screen.queryByText(/undefined/)).toBeNull();
  });

  it('uses the full breadcrumb from router state on the normal click path', async () => {
    getSection.mockResolvedValue(SECTION);
    renderSection({
      pathname: '/kiosk/tutorial/section/10',
      state: { bookId: 7, bookTitle: '测试教程书', chapterTitle: '基础' },
    });

    expect(await screen.findByText('测试教程书 ▸ 基础 ▸ 1. 第一节')).toBeInTheDocument();
  });

  it('steps to the next figure (图2) which shows "本图暂无视频" and no <video>', async () => {
    getSection.mockResolvedValue(SECTION);
    const { container } = renderSection('/kiosk/tutorial/section/10');

    expect(await screen.findByText('图1 (1 / 2)')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('下一图'));

    expect(await screen.findByText('图2 (2 / 2)')).toBeInTheDocument();
    expect(screen.getByText('本图暂无视频')).toBeInTheDocument();
    expect(container.querySelector('video')).toBeNull();
  });
});
