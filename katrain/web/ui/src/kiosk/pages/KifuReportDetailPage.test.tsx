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
let analysisByMove: Record<number, MoveAnalysis> = { 0: analysis };
let analysisFailed = false;
let analysisParameters: VerifiedAnalysisParameters | null = null;
let parametersValid: boolean | undefined;
let analysisCompleted = false;
vi.mock('../../features/kifu/useKifuAnalysis', () => ({ useKifuAnalysis: () => ({
  detail: { status: analysisCompleted ? 'completed' : 'running', analyzed_moves: 0, total_moves: 2, requested_visits: 1500, moves: analysisCompleted ? [analysis] : [],
    analysis_parameters: analysisParameters, parameters_valid: parametersValid, parameters_verified: analysisParameters?.verified === true },
  analysisByMove, error: analysisFailed,
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
function pickTab(name: string) {
  fireEvent.click(screen.getByRole('button', { name, exact: true }));
}

describe('职业报告固定右栏', () => {
  beforeEach(() => { vi.clearAllMocks(); mocks.getAlbum.mockResolvedValue(album); analysisByMove = { 0: analysis }; analysisFailed = false; analysisParameters = null; parametersValid = undefined; analysisCompleted = false; });

  it('让子局按SGF白方视角显示前五和第六行实战，PSV分母包含全部十条候选', async () => {
    renderPage(); await loaded();
    const rows = screen.getAllByTestId('ai-recommend-row');
    expect(rows).toHaveLength(6);
    expect(rows[5]).toHaveTextContent('D4实战');
    expect(rows[0]).toHaveTextContent('10%');
    expect(rows[0]).toHaveTextContent('−4.1');
    expect(rows[0]).toHaveTextContent('36.0%');
    expect(mocks.board.currentMove).toBe(2);
    expect(screen.getByTestId('kifu-report-head')).toHaveTextContent('1500 visits');
    expect(screen.getByTestId('kifu-report-head')).toHaveTextContent('分析中');
  });

  it('当前局面无分析时显示真实状态，不创建候选占位，详情不重复状态', async () => {
    analysisByMove = {};
    renderPage(); await loaded();
    expect(screen.queryAllByTestId('ai-recommend-row')).toHaveLength(0);
    expect(screen.queryAllByTestId('ai-recommend-empty-row')).toHaveLength(0);
    expect(within(screen.getByTestId('kifu-report-ai')).getByText('当前局面暂无分析数据')).toBeVisible();
    expect(screen.getByTestId('kifu-report-head')).toHaveTextContent('分析中');
    expect(screen.getByTestId('kifu-report-scores')).toHaveTextContent('—');
    expect(screen.getByTestId('kifu-report-scores')).not.toHaveTextContent('0.0%');
    expect(screen.getByRole('button', { name: '领地' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '对局详情' }));
    expect(screen.getAllByTestId('kifu-report-head')).toHaveLength(1);
    expect(within(screen.getByRole('dialog', { name: '对局详情' })).getByTestId('kifu-report-head')).toHaveTextContent('分析中');
    fireEvent.click(screen.getByRole('button', { name: '关闭' }));
    expect(screen.getByTestId('kifu-report-head')).toHaveTextContent('分析中');
  });

  it('候选变化可预览及清空，试下可落子和清空，翻手清掉试下', async () => {
    renderPage(); await loaded();
    fireEvent.click(screen.getAllByTestId('ai-recommend-row')[0]);
    expect(mocks.board.pvMoves).toEqual(['Q10', 'D10']);
    fireEvent.click(screen.getByRole('button', { name: '清除变化' }));
    expect(mocks.board.pvMoves).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '试下' }));
    fireEvent.click(screen.getByRole('button', { name: 'place try' }));
    fireEvent.click(screen.getByRole('button', { name: '试下' }));
    expect(mocks.board.tryMoves).toBeUndefined();
    fireEvent.click(screen.getByRole('button', { name: '试下' }));
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

  it('六页签内联显示，放大和收起保留图表页签、阶段及棋手筛选', async () => {
    renderPage(); await loaded();
    expect(screen.queryByRole('dialog')).toBeNull();
    const tabs = within(screen.getByRole('group', { name: '着手评价' }));
    for (const name of ['推荐', '走势', '妙手', '失误', '发挥水准', 'AI吻合度']) {
      expect(tabs.getByRole('button', { name, exact: true })).toHaveAttribute('aria-pressed', String(name === '推荐'));
    }
    expect(screen.queryByRole('button', { name: '分析', exact: true })).toBeNull();
    pickTab('妙手');
    fireEvent.click(screen.getByRole('button', { name: '布局', exact: true }));
    fireEvent.click(screen.getByRole('button', { name: '白方', exact: true }));
    const panel = screen.getByTestId('grade-panel');
    fireEvent.click(screen.getByRole('button', { name: '放大当前分析图表或推荐列表' }));
    const dialog = screen.getByRole('dialog', { name: '妙手', exact: true });
    expect(within(dialog).getByTestId('grade-panel')).toBe(panel);
    expect(screen.getAllByTestId('grade-panel')).toHaveLength(1);
    for (const name of ['妙手', '布局', '白方']) {
      expect(within(dialog).getByRole('button', { name, exact: true })).toHaveAttribute('aria-pressed', 'true');
    }
    fireEvent.click(within(dialog).getByRole('button', { name: '收起分析工作区' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(screen.getByTestId('grade-panel')).toBe(panel);
    for (const name of ['妙手', '布局', '白方']) {
      expect(screen.getByRole('button', { name, exact: true })).toHaveAttribute('aria-pressed', 'true');
    }
    pickTab('推荐');
    expect(screen.getAllByTestId('ai-recommend-row')).toHaveLength(6);
  });

  it('详情保留赛事日期结果段位规则贴目状态来源，查看棋谱仍跳转原页', async () => {
    renderPage(); await loaded();
    fireEvent.click(screen.getByRole('button', { name: '对局详情' }));
    const dialog = screen.getByRole('dialog', { name: '对局详情' });
    for (const value of ['赛事甲', '2026-10-01', 'W+R', '9p', '8p', 'japanese', '6.5', '分析中', 'archive', 'source-b']) expect(dialog).toHaveTextContent(value);
    expect(dialog).not.toHaveTextContent('已核验');
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
    const metadata = screen.getByTestId('kifu-report-metadata');
    expect(metadata.querySelectorAll('span')).toHaveLength(3);
    expect(within(metadata).getByText('日本规则', { exact: true })).toBeInTheDocument();
    expect(within(metadata).getByText('贴目 0', { exact: true })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '查看棋谱' })).toBeNull();
    const actions = within(screen.getByTestId('kifu-report-actions')).getAllByRole('button');
    expect(actions).toHaveLength(4);
    ['试下', '领地', '支招', '实体棋盘'].forEach((name, index) => expect(actions[index]).toHaveAccessibleName(name));
    const toggles = within(screen.getByTestId('kifu-report-toggles')).getAllByRole('button');
    expect(toggles).toHaveLength(2);
    ['手数', '坐标'].forEach((name, index) => expect(toggles[index]).toHaveAccessibleName(name));
    expect(screen.getByRole('button', { name: '领地' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '对局详情' }));
    const dialog = screen.getByRole('dialog', { name: '对局详情' });
    expect(dialog).toHaveTextContent('日本规则');
    expect(within(dialog).getByText('SGF 规则').parentElement).toHaveTextContent('chinese');
    expect(within(dialog).getByText('SGF 贴目').parentElement).toHaveTextContent('6.5');
    expect(within(dialog).getByText('贴目').parentElement).toHaveTextContent('0');
  });

  it.each([['japanese', 6.5, '日本规则'], ['chinese', 7.5, '中国规则']] as const)('valid default %s reports show completion and explain the source in details', async (rules, komi, label) => {
    analysisParameters = { version: 3, verified: false, rules, komi,
      sgf_sha256: 'sgf', parameter_sha256: 'parameters',
      provenance: { source: 'komi_default', raw_rules: null, raw_komi: String(komi), policy: 'komi-default-v1' } };
    parametersValid = true;
    analysisCompleted = true;
    mocks.getAlbum.mockResolvedValue({ ...album, rules: 'japanese', komi });
    renderPage(); await loaded();
    const metadata = screen.getByTestId('kifu-report-metadata');
    expect(metadata.querySelectorAll('span')).toHaveLength(3);
    expect(within(metadata).getByText(label, { exact: true })).toBeInTheDocument();
    expect(within(metadata).getByText(`贴目 ${komi}`, { exact: true })).toBeInTheDocument();
    expect(screen.queryByTestId('kifu-report-head')).toBeNull();
    expect(screen.getAllByTestId('ai-recommend-row')).toHaveLength(6);
    fireEvent.click(screen.getByRole('button', { name: '对局详情' }));
    const dialog = screen.getByRole('dialog', { name: '对局详情' });
    expect(dialog).toHaveTextContent('分析已完成');
    expect(within(dialog).getByText('SGF 规则').parentElement).toHaveTextContent('—');
    expect(within(dialog).getByText('SGF 贴目').parentElement).toHaveTextContent(String(komi));
    expect(within(dialog).getByText('分析规则', { exact: true }).parentElement).toHaveTextContent(`${label}`);
    expect(within(dialog).getByText('贴目', { exact: true }).parentElement).toHaveTextContent(String(komi));
    expect(within(dialog).getByText('规则来源').parentElement).toHaveTextContent(`SGF 未记录规则；按贴目 ${komi} 默认采用${label}，未核验赛事实际规则。`);
    expect(dialog).not.toHaveTextContent('已核验');
  });
});


it('报告的实体棋盘入口携带原始 SGF 和报告返回地址', async () => {
  renderPage(); await loaded();
  expect(screen.queryByRole('button', { name: '清空' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '实体棋盘' }));
  expect(mocks.navigate).toHaveBeenCalledWith('/kiosk/baipu/session/kifu_7', {
    state: expect.objectContaining({ sgf: album.sgf_content, backTo: '/kiosk/kifu/7', backLabel: '报告' }),
  });
});

it('非19路报告不能进入实体棋盘摆谱', async () => {
  mocks.getAlbum.mockResolvedValue({ ...album, board_size: 9, sgf_content: '(;SZ[9];B[dd])' });
  renderPage(); await loaded();
  expect(screen.getByRole('button', { name: '实体棋盘' })).toBeDisabled();
});
