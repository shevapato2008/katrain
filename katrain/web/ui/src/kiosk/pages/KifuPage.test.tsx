import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import KifuPage from './KifuPage';
import KifuDetailPage from './KifuDetailPage';
import sgf140859 from '../../utils/__fixtures__/kifu-140859.sgf?raw';
import sgf124442 from '../../utils/__fixtures__/kifu-124442.sgf?raw';
import sgf118394 from '../../utils/__fixtures__/kifu-118394.sgf?raw';
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ isLoading: false, isGuest: true, identityKey: null, token: null, status: 'guest' }) }));
vi.mock('../../hooks/useReplayStoneSound', () => ({ useReplayStoneSound: () => undefined }));

const api = vi.hoisted(() => ({ list: vi.fn(), get: vi.fn(), load: vi.fn() }));
vi.mock('../../hooks/useTranslation', () => ({ useTranslation: () => ({ lang: 'cn', t: (_key: string, fallback: string) => fallback }) }));
vi.mock('../../api/kifuApi', () => ({ KifuAPI: { getAlbums: api.list, getAlbum: api.get } }));
vi.mock('../../api/baipuApi', async importOriginal => ({ ...await importOriginal<object>(), BaipuAPI: { load: api.load }, listRecent: () => [] }));
function Location() { return <output data-testid="location">{useLocation().pathname}</output>; }
function ChangeAlbum() {
  const navigate = useNavigate();
  return <button onClick={() => navigate('/kiosk/kifu/2/replay')}>另一局</button>;
}
function renderReplay() {
  return render(<MemoryRouter initialEntries={['/kiosk/kifu/1/replay']}>
    <ChangeAlbum /><Routes><Route path="/kiosk/kifu/:kifuId/replay" element={<KifuDetailPage />} /></Routes>
  </MemoryRouter>);
}
const stoneAt = (coord: string) => document.querySelector(`[data-stone][data-at="${coord}"]`);
const albums = [1, 2].map(id => ({ id, display_event: `赛事 ${id}`, display_player_black: '黑棋手', display_player_white: '白棋手',
  date_played: '2026-10-19', move_count: 2, result: 'B+R', has_analysis: id === 2, board_size: 19 }));
beforeEach(() => {
  vi.clearAllMocks(); sessionStorage.clear();
  api.list.mockResolvedValue({ items: albums, total: 40 });
  api.get.mockResolvedValue({ sgf_content: '(;SZ[19];B[dd])', board_size: 19 });
  api.load.mockRejectedValue(new Error('screen replay must not load physical steps'));
});
it('selects an archive card without navigating and enables only available actions', async () => {
  render(<MemoryRouter initialEntries={['/kiosk/kifu']}><KifuPage /><Location /></MemoryRouter>);
  await waitFor(() => expect(screen.getByRole('button', { name: '查看棋谱', exact: true })).toBeEnabled());
  expect(screen.getByRole('button', { name: '查看分析', exact: true })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: /赛事 2/ }));
  await waitFor(() => expect(screen.getByRole('button', { name: '查看分析', exact: true })).toBeEnabled());
  expect(screen.getByTestId('location')).toHaveTextContent('/kiosk/kifu');
  fireEvent.click(screen.getByRole('button', { name: '查看分析', exact: true }));
  expect(screen.getByTestId('location')).toHaveTextContent('/kiosk/kifu/2');
});

it('previews occupied-point SGF and enables replay even when physical placement would reject it', async () => {
  api.get.mockResolvedValue({ ...albums[0], sgf_content: '(;SZ[19];B[dd];W[dd])' });
  api.load.mockRejectedValue(new Error('Space occupied'));
  render(<MemoryRouter><KifuPage /></MemoryRouter>);
  await waitFor(() => expect(screen.getByRole('button', { name: '查看棋谱', exact: true })).toBeEnabled());
  expect(screen.getByRole('status')).toHaveTextContent('终局棋谱');
  expect(stoneAt('D16')).toHaveAttribute('data-stone', 'w');
  expect(document.querySelectorAll('[data-stone]')).toHaveLength(1);
  expect(api.load).not.toHaveBeenCalled();
});

it.each(['', '  ', 'not an SGF', '(;SZ[19])'])('reports unusable SGF as a preview failure: %j', async sgf => {
  api.get.mockResolvedValue({ ...albums[0], sgf_content: sgf });
  render(<MemoryRouter><KifuPage /></MemoryRouter>);
  expect(await screen.findByText('棋谱预览加载失败')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '查看棋谱', exact: true })).toBeDisabled();
});

it('keeps a detail API rejection visible in the preview', async () => {
  api.get.mockRejectedValue(new Error('offline'));
  render(<MemoryRouter><KifuPage /></MemoryRouter>);
  expect(await screen.findByText('棋谱预览加载失败')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '查看棋谱', exact: true })).toBeDisabled();
});

it('previews a setup-only SGF as a usable position', async () => {
  api.get.mockResolvedValue({ ...albums[0], sgf_content: '(;SZ[13]AB[dd]AW[jj])' });
  render(<MemoryRouter><KifuPage /></MemoryRouter>);
  await waitFor(() => expect(screen.getByRole('button', { name: '查看棋谱', exact: true })).toBeEnabled());
  expect(stoneAt('D10')).toHaveAttribute('data-stone', 'b');
  expect(stoneAt('K4')).toHaveAttribute('data-stone', 'w');
});
it('uses twenty-record server pagination and numeric page jump', async () => {
  render(<MemoryRouter><KifuPage /></MemoryRouter>);
  await screen.findByRole('button', { name: /赛事 1/ });
  fireEvent.change(screen.getByRole('textbox', { name: '跳转页码' }), { target: { value: '2' } });
  fireEvent.click(screen.getByRole('button', { name: '跳转', exact: true }));
  await waitFor(() => expect(api.list).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2, page_size: 20 })));
});

it('mirrors historical ranks around complete accessible names and uses this record raw rank as fallback', async () => {
  const black = '示例中文很长的棋手姓名';
  const white = 'Example Alexander Dinerchtein';
  api.list.mockResolvedValue({ items: [{ ...albums[0], display_player_black: black, display_player_white: white,
    display_black_rank: ' ', black_rank: '9p', display_white_rank: '9d', white_rank: '6k' }], total: 1 });
  render(<MemoryRouter><KifuPage /></MemoryRouter>);
  const card = await screen.findByRole('button', { name: /赛事 1/ });
  const players = card.querySelectorAll('.record-match__player');
  expect(players[0]).toHaveTextContent(`${black}九段`);
  expect(players[1]).toHaveTextContent(`业余9段${white}`);
  expect(within(card).getByText(black)).toHaveAttribute('title', black);
  expect(within(card).getByText(white)).toHaveAttribute('title', white);
  await waitFor(() => expect(api.get).toHaveBeenCalledTimes(1));
});

it('omits a raw invalid rank when the API display rank is explicitly empty', async () => {
  api.list.mockResolvedValue({ items: [{ ...albums[0],
    display_black_rank: '', black_rank: '前人',
    display_white_rank: '9p', white_rank: '9p',
  }], total: 1 });
  render(<MemoryRouter><KifuPage /></MemoryRouter>);
  const card = await screen.findByRole('button', { name: /赛事 1/ });
  expect(card).toHaveTextContent('黑棋手');
  expect(card).toHaveTextContent('白棋手');
  expect(card).not.toHaveTextContent('前人');
  expect(card.querySelectorAll('.record-match__rank')).toHaveLength(1);
  expect(within(card).getByText('九段')).toBeInTheDocument();
});

it('omits absent historical ranks and highlights black when white resigns', async () => {
  api.list.mockResolvedValue({ items: [{ ...albums[0], result: '白认输' }, { ...albums[1], result: '白棋结果待核实', display_white_rank: '6k' }], total: 2 });
  render(<MemoryRouter><KifuPage /></MemoryRouter>);
  const card = await screen.findByRole('button', { name: /赛事 1/ });
  expect(card.querySelectorAll('.record-match__rank')).toHaveLength(0);
  expect(card).not.toHaveTextContent('未记录');
  expect(within(card).getByText('黑中盘胜')).toBeInTheDocument();
  expect(card.querySelector('.record-match__player--black')).toHaveClass('is-winner');
  expect(card.querySelector('.record-match__player--white')).not.toHaveClass('is-winner');
  const unknown = screen.getByRole('button', { name: /赛事 2/ });
  expect(unknown.querySelector('.is-winner')).toBeNull();
  expect(within(unknown).getByText('6级')).toBeInTheDocument();
});

it('unanalysed professional replay shows honest status and real range/step controls', async () => {
  api.get.mockResolvedValue({ ...albums[0], has_analysis: false, sgf_content: '(;SZ[19];B[dd])' });
  render(<MemoryRouter initialEntries={['/kiosk/kifu/1/replay']}><Routes><Route path="/kiosk/kifu/:kifuId/replay" element={<KifuDetailPage />} /></Routes></MemoryRouter>);
  await screen.findByText('尚未分析');
  expect(screen.getByText('最近落子')).toBeInTheDocument();
  const range = screen.getByRole('slider', { name: '棋谱手数' });
  expect(range).toHaveValue('1');
  fireEvent.click(screen.getByRole('button', { name: '回到开局', exact: true }));
  expect(range).toHaveValue('0');
  expect(screen.getByRole('button', { name: '上一手', exact: true })).toBeDisabled();
  fireEvent.change(range, { target: { value: '1' } });
  expect(screen.getByRole('button', { name: '下一手', exact: true })).toBeDisabled();
  expect(screen.getByRole('button', { name: '实体盘', exact: true })).toBeEnabled();
});

it('replays before and after an occupied-point move while keeping handicap outside the move cursor', async () => {
  api.get.mockResolvedValue({ ...albums[0], sgf_content: '(;SZ[19]HA[2]AB[pd][dp];W[dd];B[dd])' });
  api.load.mockRejectedValue(new Error('Space occupied'));
  renderReplay();
  const range = await screen.findByRole('slider', { name: '棋谱手数' });
  expect(range).toHaveAttribute('max', '2');
  expect(range).toHaveValue('2');
  expect(stoneAt('D16')).toHaveAttribute('data-stone', 'b');
  fireEvent.click(screen.getByRole('button', { name: '上一手', exact: true }));
  expect(stoneAt('D16')).toHaveAttribute('data-stone', 'w');
  fireEvent.click(screen.getByRole('button', { name: '回到开局', exact: true }));
  expect(range).toHaveValue('0');
  expect(stoneAt('D16')).toBeNull();
  expect(stoneAt('Q16')).toHaveAttribute('data-stone', 'b');
  expect(stoneAt('D4')).toHaveAttribute('data-stone', 'b');
  fireEvent.click(screen.getByRole('button', { name: '下一手', exact: true }));
  expect(stoneAt('D16')).toHaveAttribute('data-stone', 'w');
  fireEvent.change(range, { target: { value: '2' } });
  expect(stoneAt('D16')).toHaveAttribute('data-stone', 'b');
  fireEvent.click(screen.getByRole('button', { name: '回到开局', exact: true }));
  fireEvent.click(screen.getByRole('button', { name: '跳到最后', exact: true }));
  expect(range).toHaveValue('2');
  expect(api.load).not.toHaveBeenCalled();
});

it.each(['', '  ', 'not an SGF', '(;SZ[19])'])('reports unusable SGF as a detail failure: %j', async sgf => {
  api.get.mockResolvedValue({ ...albums[0], sgf_content: sgf });
  renderReplay();
  expect(await screen.findByTestId('kifu-detail-error')).toBeInTheDocument();
  expect(screen.queryByRole('slider', { name: '棋谱手数' })).toBeNull();
});

it('keeps an actual detail fetch rejection visible', async () => {
  api.get.mockRejectedValue(new Error('offline'));
  renderReplay();
  expect(await screen.findByTestId('kifu-detail-error')).toHaveTextContent('offline');
});

it('shows setup-only detail at move zero', async () => {
  api.get.mockResolvedValue({ ...albums[0], sgf_content: '(;SZ[19]AB[dd]AW[pp])' });
  renderReplay();
  const range = await screen.findByRole('slider', { name: '棋谱手数' });
  expect(range).toHaveAttribute('max', '0');
  expect(range).toHaveValue('0');
  expect(stoneAt('D16')).toHaveAttribute('data-stone', 'b');
  expect(stoneAt('Q4')).toHaveAttribute('data-stone', 'w');
});

it('hides the previous album and board while another route loads', async () => {
  api.get.mockResolvedValueOnce({ ...albums[0], sgf_content: '(;SZ[19];B[dd])' });
  let resolve!: (value: unknown) => void;
  api.get.mockReturnValueOnce(new Promise(done => { resolve = done; }));
  renderReplay();
  await screen.findByTestId('kifu-detail-hero');
  fireEvent.click(screen.getByRole('button', { name: '另一局' }));
  expect(screen.queryByTestId('kifu-detail-hero')).toBeNull();
  expect(screen.getByTestId('kifu-detail-loading')).toBeInTheDocument();
  expect(document.querySelectorAll('[data-stone]')).toHaveLength(0);
  await act(async () => { resolve({ ...albums[1], sgf_content: '(;SZ[19];W[pp])' }); });
  expect(await screen.findByTestId('kifu-detail-hero')).toHaveTextContent('赛事 2');
  expect(stoneAt('Q4')).toHaveAttribute('data-stone', 'w');
});

it.each([
  { id: 140859, sgf: sgf140859, total: 345, overwrite: 224, coord: 'A5', color: 'b', setup: 2 },
  { id: 124442, sgf: sgf124442, total: 488, overwrite: 250, coord: 'T10', color: 'w', setup: 0 },
  { id: 118394, sgf: sgf118394, total: 304, overwrite: 191, coord: 'C9', color: 'b', setup: 0 },
])('opens actual record $id from its preview and replays its overwrite, start and end', async record => {
  const album = { ...albums[0], id: record.id, move_count: record.total, sgf_content: record.sgf };
  api.list.mockResolvedValue({ items: [album], total: 1 });
  api.get.mockResolvedValue(album);
  api.load.mockRejectedValue(new Error('Space occupied'));
  render(<MemoryRouter initialEntries={['/kiosk/kifu']}><Routes>
    <Route path="/kiosk/kifu" element={<KifuPage />} />
    <Route path="/kiosk/kifu/:kifuId/replay" element={<KifuDetailPage />} />
  </Routes></MemoryRouter>);
  const openReplay = screen.getByRole('button', { name: '查看棋谱', exact: true });
  await waitFor(() => expect(openReplay).toBeEnabled());
  expect(document.querySelectorAll('[data-stone]').length).toBeGreaterThan(0);
  fireEvent.click(openReplay);
  const range = await screen.findByRole('slider', { name: '棋谱手数' });
  expect(range).toHaveAttribute('max', String(record.total));
  expect(range).toHaveValue(String(record.total));
  fireEvent.change(range, { target: { value: String(record.overwrite - 1) } });
  expect(stoneAt(record.coord)).toHaveAttribute('data-stone', record.color === 'b' ? 'w' : 'b');
  fireEvent.click(screen.getByRole('button', { name: '下一手', exact: true }));
  expect(stoneAt(record.coord)).toHaveAttribute('data-stone', record.color);
  fireEvent.click(screen.getByRole('button', { name: '回到开局', exact: true }));
  expect(range).toHaveValue('0');
  expect(document.querySelectorAll('[data-stone]')).toHaveLength(record.setup);
  fireEvent.click(screen.getByRole('button', { name: '跳到最后', exact: true }));
  expect(range).toHaveValue(String(record.total));
  expect(api.load).not.toHaveBeenCalled();
});
