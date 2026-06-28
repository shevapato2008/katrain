import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import type { TutorialSectionDetail } from '../../types/tutorial';

// Mock the shared API (getSection) and the asset URL builder. tutorialAssets.ts
// imports the same module, so its assetUrl resolves through this mock too.
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
  bbox: null, page_image_path: 'tutorial_assets/test-book/page/page_1.jpg',
  board_payload: { size: 19, stones: { B: [[3, 3]], W: [[15, 15]] }, labels: { '3,3': '1', '15,15': '2' }, viewport: { col: 0, row: 0, cols: 8, rows: 8 } },
  recognition_debug: null, narration: null, audio_asset: null, video_asset: null,
  video_duration_ms: null, video_size_bytes: null, order: 0, updated_at: null, ...over,
});

// has_video is INTENTIONALLY false — the page must not use it to gate video.
const SECTION: TutorialSectionDetail = {
  id: 10, chapter_id: 11, section_number: '1', title: '第一节', order: 0,
  figure_count: 1, has_video: false, figures: [figure({})],
} as unknown as TutorialSectionDetail;

const SECTION_NO_SLUG: TutorialSectionDetail = {
  id: 20, chapter_id: 11, section_number: '2', title: '无视频节', order: 1,
  figure_count: 1, has_video: false,
  figures: [figure({ id: 201, section_id: 20, figure_label: '图A', page_image_path: null })],
} as unknown as TutorialSectionDetail;

const VIDEO_URL = '/api/v1/tutorials/assets/tutorial_assets/test-book/video/section_10.mp4';

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

  it('attempts the section video from a figure-derived slug even when has_video is false (P0-1)', async () => {
    getSection.mockResolvedValue(SECTION);
    const { container } = renderSection('/kiosk/tutorial/section/10');

    await waitFor(() => expect(container.querySelector('video')).toBeTruthy());
    expect(container.querySelector('video')?.getAttribute('src')).toBe(VIDEO_URL);
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
      state: { bookId: 1, bookTitle: '测试教程书', bookSlug: 'test-book', chapterTitle: '基础', sectionTitle: '第一节', hasVideo: true },
    });

    expect(await screen.findByText('测试教程书 ▸ 基础 ▸ 1. 第一节')).toBeInTheDocument();
  });

  it('degrades to "本节暂无视频" and still renders board diagrams when no slug resolves', async () => {
    getSection.mockResolvedValue(SECTION_NO_SLUG);
    const { container } = renderSection('/kiosk/tutorial/section/20');

    expect(await screen.findByText('本节暂无视频')).toBeInTheDocument();
    expect(screen.getByText('图A')).toBeInTheDocument(); // board diagram thumbnail caption
    expect(container.querySelector('video')).toBeNull();
  });

  it('opens the enlarge dialog with a move slider when a thumbnail is clicked', async () => {
    getSection.mockResolvedValue(SECTION);
    renderSection('/kiosk/tutorial/section/10');

    const caption = await screen.findByText('图1'); // thumbnail caption
    fireEvent.click(caption);

    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    // labels present (maxStep = 2 > 0) → replay slider rendered
    expect(document.querySelector('.MuiSlider-root')).toBeTruthy();
  });
});
