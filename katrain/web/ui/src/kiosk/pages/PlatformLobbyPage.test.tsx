import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import PlatformLobbyPage from './PlatformLobbyPage';

/**
 * 屏 08 跨平台 · 大厅的**行为**那一半。版式归四图,一条几何都不断言。
 *
 * 断言四件事:
 *   ① **回车才搜**。旧实现是 400ms 防抖 —— 每敲一个字向**外部平台**发一次搜索,
 *      而屏上那行字写的是「输入之后回车」。两处必须说同一件事。
 *   ② **对局中的人不摆按钮**,摆状态标 —— 那个人现在收不到挑战,灰按钮会让人一直按。
 *   ③ **挑战前确认一次**,发出去的条件和屏上那行只读读数**同源**(19 路 / 中国规则 / 计分局)。
 *   ④ **自动匹配那一段按能力出现**:平台不支持就整段不渲染,不是灰一颗按钮。
 */

const { platformStatus, platformUsers, platformSendChallenge, platformStartAutomatch, platformCancelAutomatch } =
  vi.hoisted(() => ({
    platformStatus: vi.fn(),
    platformUsers: vi.fn(),
    platformSendChallenge: vi.fn(),
    platformStartAutomatch: vi.fn(),
    platformCancelAutomatch: vi.fn(),
  }));
vi.mock('../../api', () => ({
  API: { platformStatus, platformUsers, platformSendChallenge, platformStartAutomatch, platformCancelAutomatch },
}));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ token: 'tok', user: { id: 1, username: 'u' } }) }));
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const USERS = [
  { user_id: '1', username: 'stone_walker', rank: '4d', status: 'idle' },
  { user_id: '2', username: 'mokuhazushi', rank: '1k', status: 'seeking' },
  { user_id: '3', username: 'tenuki_now', rank: '2d', status: 'playing' },
];

const withAutomatch = (yes: boolean) => ({
  platforms: [{
    platform: 'ogs', connected: true, saved_username: 'me',
    supports_live_play: true, supports_automatch: yes,
    supports_rooms: false, supports_seek_graph: true, supports_engine_play: false,
  }],
});

const renderPage = (search = '?platform=ogs') => render(
  <ThemeProvider theme={kioskTheme}>
    <MemoryRouter initialEntries={[`/kiosk/play/cross-platform/lobby${search}`]}>
      <PlatformLobbyPage />
    </MemoryRouter>
  </ThemeProvider>,
);

const rowOf = (name: string) =>
  screen.getAllByTestId('platform-user').find((r) => within(r).queryByText(name))!;

beforeEach(() => {
  vi.clearAllMocks();
  platformStatus.mockResolvedValue(withAutomatch(true));
  platformUsers.mockResolvedValue({ users: USERS });
  platformSendChallenge.mockResolvedValue({});
  platformStartAutomatch.mockResolvedValue({});
  platformCancelAutomatch.mockResolvedValue({});
});

describe('屏 08 跨平台 · 大厅', () => {
  it('回车才搜:边打字不发请求', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('platform-user')).toHaveLength(3));
    const calls = platformUsers.mock.calls.length;

    await userEvent.type(screen.getByTestId('platform-search'), 'stone');
    expect(platformUsers.mock.calls.length, '边打字就发了请求 —— 屏上写的是「输入之后回车」')
      .toBe(calls);

    await userEvent.keyboard('{Enter}');
    await waitFor(() => expect(platformUsers).toHaveBeenLastCalledWith('ogs', 'tok', 'stone'));
  });

  it('对局中那一行不摆按钮,摆状态标', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('platform-user')).toHaveLength(3));
    const busy = rowOf('tenuki_now');
    expect(within(busy).queryByRole('button', { name: '挑战' })).not.toBeInTheDocument();
    expect(within(busy).getAllByText('对局中').length).toBeGreaterThan(0);
    expect(within(rowOf('stone_walker')).getByRole('button', { name: '挑战' })).toBeEnabled();
  });

  it('挑战先确认一次,发出去的条件和屏上那行读数同源', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('platform-user')).toHaveLength(3));
    await userEvent.click(within(rowOf('stone_walker')).getByRole('button', { name: '挑战' }));

    const dlg = await screen.findByTestId('platform-challenge-confirm');
    expect(within(dlg).getByText('向 stone_walker 发起挑战？')).toBeInTheDocument();
    expect(platformSendChallenge, '还没确认就发出去了').not.toHaveBeenCalled();

    await userEvent.click(within(dlg).getByRole('button', { name: '发出挑战' }));
    await waitFor(() => expect(platformSendChallenge).toHaveBeenCalledWith(
      'ogs', { user_id: '1', board_size: 19, rules: 'chinese', ranked: true }, 'tok',
    ));
  });

  it('确认框里按取消:一条都不发', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('platform-user')).toHaveLength(3));
    await userEvent.click(within(rowOf('stone_walker')).getByRole('button', { name: '挑战' }));
    const dlg = await screen.findByTestId('platform-challenge-confirm');
    await userEvent.click(within(dlg).getByRole('button', { name: '取消' }));
    await waitFor(() => expect(screen.queryByTestId('platform-challenge-confirm')).not.toBeInTheDocument());
    expect(platformSendChallenge).not.toHaveBeenCalled();
  });

  it('自动匹配那一段按能力出现:平台不支持就整段不渲染', async () => {
    platformStatus.mockResolvedValue(withAutomatch(false));
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('platform-user')).toHaveLength(3));
    expect(screen.queryByTestId('platform-automatch')).not.toBeInTheDocument();
  });

  it('开始匹配 → 再按变成取消匹配', async () => {
    renderPage();
    const action = await screen.findByTestId('platform-automatch-action');
    expect(action).toHaveTextContent('开始匹配');
    await userEvent.click(action);
    await waitFor(() => expect(platformStartAutomatch).toHaveBeenCalledWith('ogs', { board_size: 19 }, 'tok'));
    expect(action).toHaveTextContent('取消匹配');
    await userEvent.click(action);
    await waitFor(() => expect(platformCancelAutomatch).toHaveBeenCalledWith('ogs', 'tok'));
  });

  /**
   * 稿子把「自动匹配」画了两处(搜索行行尾一颗 + 底下一整段),两颗打同一个接口。
   * 这一屏不滚,两颗同屏可见 ⇒ 排队中会同时挂着「取消匹配」和「开始匹配」。
   * **一个状态摆两个地方,必有一个在撒谎。**
   */
  it('全屏只有一处能开匹配,按下之后「开始匹配」一个字都不许再出现', async () => {
    const { container } = renderPage();
    const action = await screen.findByTestId('platform-automatch-action');
    expect(screen.getAllByRole('button', { name: '开始匹配' })).toHaveLength(1);
    // 搜索那一行的行尾只剩输入框。
    const searchEnd = container.querySelector('.kiosk-row--search .kiosk-row__end')!;
    expect(searchEnd.querySelectorAll('button')).toHaveLength(0);

    await userEvent.click(action);
    // 键换成「取消匹配」—— 它说的是**按下去会发生什么**,而且不留着就撤不回已发出的排队。
    await waitFor(() => expect(screen.getByRole('button', { name: '取消匹配' })).toBeInTheDocument());
    expect(container.textContent).not.toContain('开始匹配');
  });

  /**
   * 「排队中」那枚标和「配上就自动进对局」那句话**都撤了**(2026-08-25,S1)。
   *
   * 后半句是**平的假话**:OGS 适配器收 `automatch/start` 后会
   * `_emit("automatch_found", …)`,但 `on_automatch_found` **全仓零订阅者**
   * ⇒ 平台真给你配上局了,这台盒子永远不会知道。前半句「排队中」也没人维护:
   * 纯前端本地状态,刷一下页面就没了,而 OGS 那边还排着。
   *
   * 这条守的是**两态都不许再出现那些词** —— 只查按下之前那一帧的话,
   * 撤了一半也是绿的。
   */
  it('不摆「排队中」这种没人维护的状态,也不承诺配上会自己回来', async () => {
    const { container } = renderPage();
    const action = await screen.findByTestId('platform-automatch-action');
    const box = screen.getByTestId('platform-automatch');

    for (const phase of ['按下之前', '按下之后']) {
      expect(box, phase).not.toHaveTextContent('排队中');
      expect(box, phase).not.toHaveTextContent('自动进对局');
      expect(container.querySelector('.kiosk-tag--warn'), phase).toBeNull();
      if (phase === '按下之前') await userEvent.click(action);
    }
    // 换上的那句话两态都在,而且把「配上之后要去哪」说清楚了。
    expect(box).toHaveTextContent('不会自动回到这台盒子');
  });

  it('名单取不回来:说出来,不摆一张空名单冒充「那边没人」', async () => {
    platformUsers.mockRejectedValue(new Error('boom'));
    renderPage();
    expect(await screen.findByText('没能从平台取回名单')).toBeInTheDocument();
    expect(screen.queryAllByTestId('platform-user')).toHaveLength(0);
  });

  it('搜了但那边没这个人,和「还没搜」是两句话', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('platform-user')).toHaveLength(3));
    platformUsers.mockResolvedValue({ users: [] });
    await userEvent.type(screen.getByTestId('platform-search'), 'nobody{Enter}');
    expect(await screen.findByText('那边没有这个人')).toBeInTheDocument();
  });
});
