import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { vi, beforeEach, describe, expect, it, type Mock } from 'vitest';

import TutorialFigurePage from './TutorialFigurePage';
import { TutorialAPI } from '../../api/tutorialApi';
import { useAuth } from '../../../context/AuthContext';

vi.mock('../../api/tutorialApi', () => ({
  TutorialAPI: {
    getSection: vi.fn(),
    saveNarration: vi.fn(),
    generateFigureAudio: vi.fn(),
    assetUrl: vi.fn((path: string) => `/assets/${path}`),
    saveBoardPayload: vi.fn(),
    verifyFigure: vi.fn(),
  },
}));

vi.mock('../../../context/AuthContext', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../context/AuthContext')>();
  return {
    ...actual,
    useAuth: vi.fn(),
  };
});

vi.mock('../../components/tutorials/SGFBoard', () => ({
  default: () => <div data-testid="sgf-board" />,
}));

vi.mock('../../components/tutorials/BoardEditToolbar', () => ({
  default: () => <div data-testid="board-edit-toolbar" />,
}));

vi.mock('../../components/tutorials/RecognitionDebugPanel', () => ({
  default: () => <div data-testid="recognition-debug" />,
}));

vi.mock('../../components/tutorials/AudioPlayer', () => ({
  default: ({ src }: { src: string | null }) => <div data-testid="audio-player">{src ?? 'no-audio'}</div>,
}));

const sectionResponse = {
  id: 1,
  chapter_id: 1,
  section_number: '1',
  title: '外势和实地',
  order: 1,
  figure_count: 1,
  has_video: false,
  figures: [
    {
      id: 7,
      section_id: 1,
      page: 12,
      figure_label: '图1',
      book_text: '原书内容',
      page_context_text: null,
      bbox: null,
      page_image_path: null,
      board_payload: null,
      recognition_debug: null,
      narration: '旧讲解',
      audio_asset: 'tutorial_assets/test-buju/audio/fig_7-old.mp3',
      video_asset: null,
      video_duration_ms: null,
      video_size_bytes: null,
      order: 1,
      updated_at: '2026-04-10T00:00:00Z',
    },
  ],
};

describe('TutorialFigurePage', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    (useAuth as Mock).mockReturnValue({ token: 'fake-token' });
    (TutorialAPI.getSection as Mock).mockResolvedValue(sectionResponse);
    (TutorialAPI.saveNarration as Mock).mockResolvedValue({
      ...sectionResponse.figures[0],
      narration: '只更新文字',
      audio_asset: 'tutorial_assets/test-buju/audio/fig_7-old.mp3',
    });
    (TutorialAPI.generateFigureAudio as Mock).mockResolvedValue({
      ...sectionResponse.figures[0],
      narration: '新的讲解',
      audio_asset: 'tutorial_assets/test-buju/audio/fig_7.mp3',
    });
  });

  it('lets the user edit narration and regenerate audio', async () => {
    render(
      <MemoryRouter initialEntries={['/tutorials/sections/1']}>
        <Routes>
          <Route path="/tutorials/sections/:sectionId" element={<TutorialFigurePage />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText('旧讲解');

    fireEvent.click(screen.getByRole('button', { name: /编辑讲解/i }));

    const input = screen.getByRole('textbox', { name: /讲解文本/i });
    fireEvent.change(input, { target: { value: '新的讲解' } });
    fireEvent.click(screen.getByRole('button', { name: /生成语音并保存/i }));

    await waitFor(() => {
      expect(TutorialAPI.generateFigureAudio).toHaveBeenCalledWith(7, '新的讲解', 'fake-token');
    });

    expect(await screen.findByText('新的讲解')).toBeInTheDocument();
    expect(screen.getByTestId('audio-player')).toHaveTextContent('/assets/tutorial_assets/test-buju/audio/fig_7.mp3');
  });

  it('saves narration text without regenerating audio', async () => {
    render(
      <MemoryRouter initialEntries={['/tutorials/sections/1']}>
        <Routes>
          <Route path="/tutorials/sections/:sectionId" element={<TutorialFigurePage />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText('旧讲解');

    fireEvent.click(screen.getByRole('button', { name: /编辑讲解/i }));

    const input = screen.getByRole('textbox', { name: /讲解文本/i });
    fireEvent.change(input, { target: { value: '只更新文字' } });
    fireEvent.click(screen.getByRole('button', { name: /保存文字/i }));

    await waitFor(() => {
      expect(TutorialAPI.saveNarration).toHaveBeenCalledWith(7, '只更新文字', 'tutorial_assets/test-buju/audio/fig_7-old.mp3', 'fake-token');
    });

    expect(TutorialAPI.generateFigureAudio).not.toHaveBeenCalled();
    expect(await screen.findByText('只更新文字')).toBeInTheDocument();
    expect(screen.getByTestId('audio-player')).toHaveTextContent('/assets/tutorial_assets/test-buju/audio/fig_7-old.mp3');
  });
});
