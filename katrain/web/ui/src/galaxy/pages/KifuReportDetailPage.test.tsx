import { render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';

import type { KifuAlbumDetail } from '../../types/kifu';
import type { MoveAnalysis } from '../../types/live';
import KifuReportDetailPage from './KifuReportDetailPage';

const mocks = vi.hoisted(() => ({ getAlbum: vi.fn() }));
vi.mock('../../api/kifuApi', () => ({ KifuAPI: { getAlbum: mocks.getAlbum } }));
vi.mock('../../features/kifu/useKifuAnalysis', () => ({ useKifuAnalysis: () => ({
  detail: { status: 'completed', requested_visits: 2000, total_moves: 2, analyzed_moves: 2 },
  analysisByMove: { 2: analysis }, error: false,
}) }));
vi.mock('../../components/live/LiveBoard', () => ({ default: () => <div data-testid="board" /> }));
vi.mock('../../components/live/TrendChart', () => ({ default: () => <div data-testid="trend" /> }));

const analysis: MoveAnalysis = {
  match_id: '7', move_number: 2, move: 'D4', player: 'W', winrate: .55, score_lead: 1,
  top_moves: ['Q10', 'D10', 'C3', 'R6', 'K10'].map((move) => ({ move, visits: 400, winrate: .55, score_lead: 1, prior: .1, pv: [move] })),
  ownership: null, is_brilliant: false, is_mistake: false, is_questionable: false,
  delta_score: 0, delta_winrate: 0,
};
const album: KifuAlbumDetail = {
  id: 7, player_black: '黑棋手', player_white: '白棋手', black_rank: '9p', white_rank: '8p',
  event: '赛事甲', round_name: '决赛', result: 'W+R', date_played: '2026-10-01', rules: 'chinese',
  komi: 7.5, handicap: 0, board_size: 19, move_count: 2, place: '上海', source: 'archive',
  sources: ['archive'], sgf_content: '(;SZ[19]PB[黑棋手]PW[白棋手];B[pd];W[dp])',
};

beforeEach(() => { mocks.getAlbum.mockReset().mockResolvedValue(album); });

it('shows the professional report in the shared fixed rail without a duplicate kifu entry', async () => {
  render(<MemoryRouter initialEntries={['/galaxy/kifu/7/report']}><Routes>
    <Route path="/galaxy/kifu/:albumId/report" element={<KifuReportDetailPage />} />
  </Routes></MemoryRouter>);

  const rail = await screen.findByTestId('report-analysis-layout');
  expect(within(rail).getByTestId('report-meta-panel')).toHaveTextContent('赛事甲');
  expect(within(rail).getByTestId('report-candidate-list').children).toHaveLength(5);
  expect(within(rail).queryByRole('button', { name: '查看棋谱' })).not.toBeInTheDocument();
  expect(within(rail).getByRole('switch', { name: '手数' })).toBeInTheDocument();
  expect(within(rail).getByRole('switch', { name: 'Coordinates' })).toBeInTheDocument();
  expect(within(rail).getByRole('button', { name: '展开分析' })).toBeInTheDocument();
});
