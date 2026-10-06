import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { KifuAlbumDetail, VerifiedAnalysisParameters } from '../../types/kifu';
import type { MoveAnalysis } from '../../types/live';
import KifuReportDetailPage from './KifuReportDetailPage';

const mocks = vi.hoisted(() => ({ getAlbum: vi.fn(), navigate: vi.fn(), board: {} as Record<string, unknown> }));
vi.mock('react-router-dom', async (original) => ({ ...(await original<typeof import('react-router-dom')>()), useNavigate: () => mocks.navigate }));
vi.mock('../../api/kifuApi', () => ({ KifuAPI: { getAlbum: mocks.getAlbum } }));
const candidate = { move: 'Q10', visits: 800, winrate: 0.64, score_lead: 4.1, prior: 0.5, pv: ['Q10', 'D10'], psv: 1 };
const analysis: MoveAnalysis = {
  match_id: '7', move_number: 0, move: null, player: null, winrate: 0.6, score_lead: 3,
  top_moves: Array.from({ length: 10 }, (_, i) => ({ ...candidate, move: `A${i + 1}` })), ownership: null,
  is_brilliant: false, is_mistake: false, is_questionable: false, delta_score: 0, delta_winrate: 0,
};
let analysisFailed = false;
let analysisParameters: VerifiedAnalysisParameters | null = null;
vi.mock('../../features/kifu/useKifuAnalysis', () => ({ useKifuAnalysis: () => ({
  detail: { status: 'running', analyzed_moves: 0, total_moves: 2, requested_visits: 1500, moves: [],
    analysis_parameters: analysisParameters, parameters_verified: analysisParameters !== null },
  analysisByMove: { 0: analysis }, error: analysisFailed,
}) }));
vi.mock('../../components/live/LiveBoard', () => ({ default: (props: Record<string, unknown>) => {
  mocks.board = props;
  return <button onClick={() => (props.onTryMove as (move: string) => void)?.('D4')}>place try</button>;
} }));
const album: KifuAlbumDetail = {
  id: 7, player_black: '黑棋手', player_white: '白棋手', black_rank: '9p', white_rank: '8p',
  event: '赛事甲', round_name: '决赛', result: 'W+R', date_played: '2026-10-01', rules: 'japanese',
  komi: 6.5, handicap: 2, board_size: 19, move_count: 2, place: '上海', source: 'archive',
  sources: ['archive', 'source-b'], sgf_content: '(;SZ[19]HA[2]AB[dd][pp];W[dp];B[pd])',
};
function renderPage() {
  return render(<MemoryRouter initialEntries={['/kiosk/kifu/7']}><Routes>
    <Route path="/kiosk/kifu/:kifuId" element={<KifuReportDetailPage />} />
  </Routes></MemoryRouter>);
}
async function loaded() { await screen.findByTestId('kifu-report-ai'); }

describe('职业报告固定右栏', () => {
  beforeEach(() => { vi.clearAllMocks(); mocks.getAlbum.mockResolvedValue(album); analysisFailed = false; analysisParameters = null; });

  it('让子局按SGF白方视角显示五行，PSV分母包含全部十条候选', async () => {
    renderPage(); await loaded();
    const rows = screen.getAllByTestId('ai-recommend-row');
    expect(rows).toHaveLength(6);
    expect(rows[5]).toHaveTextContent('实战 · D4');
    expect(rows[0]).toHaveTextContent('10%');
    expect(rows[0]).toHaveTextContent('−4.1');
    expect(rows[0]).toHaveTextContent('36.0%');
    expect(mocks.board.currentMove).toBe(2);
    expect(screen.getByTestId('kifu-report-head')).toHaveTextContent('1500 visits');
  });

  it('候选变化可预览及清空，试下可落子和清空，翻手清掉试下', async () => {
    renderPage(); await loaded();
    fireEvent.click(screen.getAllByTestId('ai-recommend-row')[0]);
    expect(mocks.board.pvMoves).toEqual(['Q10', 'D10']);
    fireEvent.click(screen.getByRole('button', { name: '清除变化' }));
    expect(mocks.board.pvMoves).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '试下' }));
    fireEvent.click(screen.getByRole('button', { name: 'place try' }));
    fireEvent.click(screen.getByRole('button', { name: '清空' }));
    expect(mocks.board.tryMoves).toEqual([]);
    fireEvent.click(screen.getByRole('button', { name: 'place try' }));
    fireEvent.click(screen.getByRole('button', { name: '下一手' }));
    expect(mocks.board.tryMoves).toEqual([]);
    expect(mocks.board.currentMove).toBe(3);
  });

  it('坐标切换保留四条刻度带及棋盘几何参数', async () => {
    renderPage(); await loaded();
    fireEvent.click(screen.getByRole('button', { name: '坐标' }));
    expect(screen.getByTestId('kifu-report-detail-board')).toHaveAttribute('data-coordinates', 'false');
    expect(document.querySelectorAll('.kiosk-board__ruler')).toHaveLength(4);
    expect(mocks.board.showCoordinates).toBe(false);
  });

  it('分析弹层保留五页签、七档及筛选，能够关闭', async () => {
    renderPage(); await loaded();
    fireEvent.click(screen.getByRole('button', { name: '着手评价 · 七档' }));
    const dialog = screen.getByRole('dialog');
    for (const tab of ['走势', '妙手', '失误', '发挥水准', 'AI吻合度']) expect(within(dialog).getByRole('button', { name: tab })).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole('button', { name: '妙手' }));
    expect(within(dialog).getByRole('button', { name: '全盘' })).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole('button', { name: '关闭' }));
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('详情保留赛事日期结果段位规则贴目状态来源，查看棋谱仍跳转原页', async () => {
    renderPage(); await loaded();
    fireEvent.click(screen.getByRole('button', { name: '对局详情' }));
    const dialog = screen.getByRole('dialog');
    for (const value of ['赛事甲', '2026-10-01', 'W+R', '9p', '8p', 'japanese', '6.5', '分析中', 'archive', 'source-b']) expect(dialog).toHaveTextContent(value);
    fireEvent.click(screen.getByRole('button', { name: '查看棋谱' }));
    expect(mocks.navigate).toHaveBeenCalledWith('/kiosk/kifu/7/replay');
  });

  it('读取棋谱失败提供重试，分析读取失败也提供重试', async () => {
    mocks.getAlbum.mockRejectedValueOnce(new Error('offline'));
    analysisFailed = true;
    renderPage();
    await screen.findByText('职业棋局暂时无法读取');
    fireEvent.click(screen.getByRole('button', { name: '重试加载' }));
    await loaded();
    await waitFor(() => expect(mocks.getAlbum).toHaveBeenCalledTimes(2));
    expect(screen.getByTestId('kifu-report-detail-shell').querySelector('.report-analysis-rail__notices [role="status"]')).toHaveTextContent('分析状态暂时无法读取');
    expect(screen.getByTestId('kifu-report-detail-shell').querySelector('.report-playback button[aria-label="播放"]')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '重试加载' }));
    expect(mocks.navigate).toHaveBeenCalledWith(0);
  });

  it('version 2 已审纠正参数覆盖原始规则，详情分别保留 SGF 值和零贴目', async () => {
    analysisParameters = { version: 2, verified: true, rules: 'japanese', komi: 0,
      sgf_sha256: 'sgf', parameter_sha256: 'parameters', provenance: {} };
    mocks.getAlbum.mockResolvedValue({ ...album, rules: 'chinese' });
    renderPage(); await loaded();
    expect(screen.getByTestId('kifu-report-metadata')).toHaveTextContent('日本规则 · 分析贴目 0');
    expect(screen.queryByRole('button', { name: '查看棋谱' })).toBeNull();
    expect([...screen.getByTestId('kifu-report-actions').querySelectorAll('button')].map(button => button.textContent)).toEqual(['试下', '领地', '支招', '分析']);
    expect([...screen.getByTestId('kifu-report-toggles').querySelectorAll('button')].map(button => button.textContent)).toEqual(['手数', '坐标', '清空', '详情']);
    fireEvent.click(screen.getByRole('button', { name: '对局详情' }));
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveTextContent('日本规则');
    expect(within(dialog).getByText('SGF 规则').parentElement).toHaveTextContent('chinese');
    expect(within(dialog).getByText('SGF 贴目').parentElement).toHaveTextContent('6.5');
    expect(within(dialog).getByText('分析贴目（已核验）').parentElement).toHaveTextContent('0');
  });
});
