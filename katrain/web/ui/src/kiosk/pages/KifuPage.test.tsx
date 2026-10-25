import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import KifuPage from './KifuPage';
import KifuDetailPage from './KifuDetailPage';
vi.mock('../../hooks/useReplayStoneSound', () => ({ useReplayStoneSound: () => undefined }));

const api = vi.hoisted(() => ({ list: vi.fn(), get: vi.fn(), load: vi.fn() }));
vi.mock('../../hooks/useTranslation', () => ({ useTranslation: () => ({ lang: 'cn', t: (_key: string, fallback: string) => fallback }) }));
vi.mock('../../api/kifuApi', () => ({ KifuAPI: { getAlbums: api.list, getAlbum: api.get } }));
vi.mock('../../api/baipuApi', async importOriginal => ({ ...await importOriginal<object>(), BaipuAPI: { load: api.load }, listRecent: () => [] }));
function Location() { return <output data-testid="location">{useLocation().pathname}</output>; }
const albums = [1, 2].map(id => ({ id, display_event: `赛事 ${id}`, display_player_black: '黑棋手', display_player_white: '白棋手',
  date_played: '2026-10-19', move_count: 2, result: 'B+R', has_analysis: id === 2, board_size: 19 }));
beforeEach(() => {
  vi.clearAllMocks(); sessionStorage.clear();
  api.list.mockResolvedValue({ items: albums, total: 40 });
  api.get.mockResolvedValue({ sgf_content: '(;SZ[19];B[dd])', board_size: 19 });
  api.load.mockResolvedValue({ board_size: 19, steps: [{ kind: 'move', row: 3, col: 3, color: 'B', removed: [] }] });
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
  expect(players[0]).toHaveTextContent(`${black}职业九段`);
  expect(players[1]).toHaveTextContent(`业余9段${white}`);
  expect(within(card).getByText(black)).toHaveAttribute('title', black);
  expect(within(card).getByText(white)).toHaveAttribute('title', white);
  await waitFor(() => expect(api.get).toHaveBeenCalledTimes(1));
});

it('shows absent historical ranks honestly and highlights black when white resigns', async () => {
  api.list.mockResolvedValue({ items: [{ ...albums[0], result: '白认输' }, { ...albums[1], result: '白棋结果待核实', display_white_rank: '6k' }], total: 2 });
  render(<MemoryRouter><KifuPage /></MemoryRouter>);
  const card = await screen.findByRole('button', { name: /赛事 1/ });
  expect(within(card).getAllByLabelText('等级未记录')).toHaveLength(2);
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
