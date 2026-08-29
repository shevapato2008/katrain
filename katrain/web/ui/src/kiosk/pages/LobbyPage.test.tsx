import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import LobbyPage from './LobbyPage';

/**
 * 屏 06 在线大厅的**行为**那一半。版式归 `kiosk-screen-06-lobby.fourup.spec.ts`(眼睛)
 * 和 `kiosk-shell-scroll.spec.ts`(机器量),这里一条几何都不断言 —— jsdom 没有布局引擎。
 *
 * 这里断言的是四件**和布局无关**的事,每一件挂了都是一个产品缺陷:
 *   ① 「空闲 / 对局中」是**算**出来的 —— 后端没有这个状态位,它靠比对两份列表得出。
 *      算错了,屏上会请人去邀请一个正在下棋的人。
 *   ② 名单**按能不能邀请排序**。排错了,能点的那几个埋在十几行灰按钮下面。
 *   ③ 没定级时排位那一段**灰掉且说明原因**;定过级就放开。
 *      灰而不说原因是这套稿子在别处专门骂过的事。
 *   ④ 「邀请」发出去的是 `{type:'invite', target_id}` —— 发错了对面收不到。
 *
 * **变异记录**(2026-08-24,两条都真跑过):
 *   · 去掉 `roster` 那个 `sort` ⇒ 排序那条红,实到
 *     `['小满','云在青天','柳三石','我','大熊']`(正在下棋的两个人排在最前)。
 *   · 把「访客早退」挪回 `/ws/lobby` 那个 `useEffect` **前面** ⇒ 最后两条红,
 *     报的正是 React 的 `Rendered more hooks than during the previous render`。
 */

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: auth.token, user: auth.user }),
}));
const { getAiLadderStatus } = vi.hoisted(() => ({ getAiLadderStatus: vi.fn() }));
vi.mock('../../features/aiLadder/api', () => ({ getAiLadderStatus }));

const auth = { token: 'tok' as string | null, user: { id: 1, username: '我' } };

const GAMES = [
  { session_id: 'aaaa1111', player_b: '小满', player_w: '云在青天', spectator_count: 3, move_count: 87 },
  { session_id: 'bbbb2222', player_b: '不系舟', player_w: '半日闲', spectator_count: 0, move_count: 12 },
];
const USERS = [
  // 故意让**在下棋的人排在前面** —— 排序那一条要是没写,这个顺序会原样上屏。
  { id: 5, username: '小满' }, { id: 6, username: '云在青天' },
  { id: 2, username: '柳三石' }, { id: 1, username: '我' }, { id: 3, username: '大熊' },
];

/** 假 WebSocket:记下发出去的每一条,并留一个口子把服务端的推送打进来。 */
const sent: string[] = [];
let push: (m: unknown) => void = () => {};
class FakeWS {
  static readonly OPEN = 1;
  readyState = 1;
  onmessage: ((e: { data: string }) => void) | null = null;
  close() { this.readyState = 3; }
  send(s: string) { sent.push(s); }
  constructor() { push = (m) => this.onmessage?.({ data: JSON.stringify(m) }); }
}

const renderPage = () =>
  render(<ThemeProvider theme={kioskTheme}><MemoryRouter><LobbyPage /></MemoryRouter></ThemeProvider>);

const rowOf = (name: string) =>
  screen.getAllByTestId('lobby-player').find((r) => within(r).queryByText(name))!;

beforeEach(() => {
  vi.clearAllMocks();
  sent.length = 0;
  auth.token = 'tok';
  auth.user = { id: 1, username: '我' };
  vi.stubGlobal('WebSocket', FakeWS);
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    const body = url.includes('/users/online') ? USERS
      : url.includes('/games/active/multiplayer') ? GAMES
        : [];
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response);
  }));
  getAiLadderStatus.mockResolvedValue({
    view_state: 'ready',
    placement_state: { phase: 'placement', completed_games: 2, total_games: 5 },
    current_opponent: null, recent_ranked_results: [], net_score: 0, pending_settlement: false,
  });
});

afterEach(() => { vi.unstubAllGlobals(); });

describe('屏 06 在线大厅', () => {
  it('「对局中」是比对出来的:名字出现在进行中的对局里 ⇒ 灰、邀请键点不动', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('lobby-player')).toHaveLength(5));

    const busy = rowOf('小满');
    expect(within(busy).getByText('对局中')).toBeInTheDocument();
    expect(within(busy).getByRole('button', { name: '邀请' })).toBeDisabled();

    const free = rowOf('柳三石');
    expect(within(free).getByText('空闲')).toBeInTheDocument();
    expect(within(free).getByRole('button', { name: '邀请' })).toBeEnabled();
  });

  it('名单按能不能邀请排序:我 → 空闲 → 对局中(接口给的顺序正好相反)', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('lobby-player')).toHaveLength(5));
    const names = screen.getAllByTestId('lobby-player').map((r) => r.querySelector('h4')!.textContent);
    expect(names).toEqual(['我', '柳三石', '大熊', '小满', '云在青天']);
  });

  it('自己那一行不给邀请键,给「这是你」', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('lobby-player')).toHaveLength(5));
    const me = rowOf('我');
    expect(within(me).getByText('这是你')).toBeInTheDocument();
    expect(within(me).queryByRole('button', { name: '邀请' })).not.toBeInTheDocument();
  });

  it('「邀请」发的是 {type:"invite", target_id}', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('lobby-player')).toHaveLength(5));
    await userEvent.click(within(rowOf('柳三石')).getByRole('button', { name: '邀请' }));
    expect(JSON.parse(sent.at(-1)!)).toEqual({ type: 'invite', target_id: 2 });
  });

  it('没定级:排位那一段灰着,并说清还差几局', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByRole('radio', { name: '排位赛' })).toBeDisabled());
    expect(screen.getByTestId('lobby-rated-why')).toHaveTextContent('你还差 3 局');
    expect(screen.getByRole('radio', { name: '自由对局' })).toBeEnabled();
  });

  it('读不到定级进度:仍然挡住排位,但**不报一个编出来的局数**', async () => {
    getAiLadderStatus.mockRejectedValue(new Error('boom'));
    renderPage();
    await waitFor(() => expect(screen.getByRole('radio', { name: '排位赛' })).toBeDisabled());
    expect(screen.getByTestId('lobby-rated-why')).not.toHaveTextContent('还差');
  });

  it('定过级:排位放开,那行解释整条不见', async () => {
    getAiLadderStatus.mockResolvedValue({
      view_state: 'ready',
      placement_state: { phase: 'placed', rung: { rung: 12, rank_name: '业余 2 段' } },
      current_opponent: null, recent_ranked_results: [], net_score: 0, pending_settlement: false,
    });
    renderPage();
    await waitFor(() => expect(screen.getByRole('radio', { name: '排位赛' })).toBeEnabled());
    expect(screen.queryByTestId('lobby-rated-why')).not.toBeInTheDocument();
  });

  it('开始匹配发的是当下选中的那一档', async () => {
    getAiLadderStatus.mockResolvedValue({
      view_state: 'ready',
      placement_state: { phase: 'placed', rung: { rung: 12, rank_name: '业余 2 段' } },
      current_opponent: null, recent_ranked_results: [], net_score: 0, pending_settlement: false,
    });
    renderPage();
    await waitFor(() => expect(screen.getByRole('radio', { name: '排位赛' })).toBeEnabled());
    await userEvent.click(screen.getByRole('radio', { name: '排位赛' }));
    await userEvent.click(screen.getByTestId('lobby-start-match'));
    expect(JSON.parse(sent.at(-1)!)).toEqual({ type: 'start_matchmaking', game_type: 'rated' });
  });

  it('收到邀请:弹窗给的是邀请人的名字,接受发 accept_invite,拒绝只关窗', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('lobby-player')).toHaveLength(5));

    push({ type: 'invitation', from_id: 2, from_name: '柳三石', mode: 'free' });
    await waitFor(() => expect(screen.getByTestId('lobby-invitation')).toBeInTheDocument());
    expect(screen.getByText('柳三石邀你下一局')).toBeInTheDocument();

    // 「拒绝」今天只关掉本地这个窗 —— 后端没有 decline,**一条消息都不该发出去**。
    const beforeDecline = sent.length;
    await userEvent.click(screen.getByRole('button', { name: '拒绝' }));
    await waitFor(() => expect(screen.queryByTestId('lobby-invitation')).not.toBeInTheDocument());
    expect(sent).toHaveLength(beforeDecline);

    push({ type: 'invitation', from_id: 2, from_name: '柳三石', mode: 'free' });
    await waitFor(() => expect(screen.getByTestId('lobby-invitation')).toBeInTheDocument());
    await userEvent.click(screen.getByRole('button', { name: '接受并开局' }));
    expect(JSON.parse(sent.at(-1)!)).toEqual({ type: 'accept_invite', target_id: 2 });
  });

  /**
   * 「点进去可以观战」**撤掉了**(2026-08-25,S1)。观战这条路今天不存在:
   * `/api/session/{id}/*` 一律过 `guard_session_reader`,陌生人进去必 403 ——
   * 原来那句话是在邀请用户去按一颗必然失败的按钮。
   *
   * 两条一起看才有意义:**没有正对照,「点了没反应」和「这一列整个渲染坏了」分不开。**
   */
  it('别人的对局卡不是按钮,点了什么都不会发生', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('lobby-game')).toHaveLength(2));
    const card = screen.getAllByTestId('lobby-game')[0];
    // 夹具里两局都不是「我」的(小满/云在青天、不系舟/半日闲)。
    expect(card.tagName).not.toBe('BUTTON');
    expect(card).toHaveAttribute('data-mine', '0');
    await userEvent.click(card);
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('自己在里面的那一局点得回去 —— 判别位是用户名(端点只回名字,没有 id)', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      const body = url.includes('/users/online') ? USERS
        : url.includes('/games/active/multiplayer') ? [{ ...GAMES[0], player_w: '我' }]
          : [];
      return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response);
    }));
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('lobby-game')).toHaveLength(1));
    const card = screen.getByTestId('lobby-game');
    expect(card.tagName).toBe('BUTTON');
    await userEvent.click(card);
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/pvp/room/aaaa1111');
  });

  /**
   * `await res.json()` 回来的是 `unknown`,`as ActiveGame[]` 只是让类型检查闭嘴。
   * 少一个 `session_id`,`.slice(0,4)` 当场抛,而这一屏上面没有 error boundary ⇒ 整个 app 白屏。
   * 2026-08-24 `navigation.integration.test.tsx` 真的这么炸过(它那个兜底 fetch
   * 对所有 URL 回同一份分类数组)。
   */
  it('接口回了认不出的行:整行丢掉,不白屏', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      const body = url.includes('/users/online') ? USERS
        : url.includes('/games/active/multiplayer')
          ? [{ level: '15k', categories: { tesuji: 139 }, total: 1000 }, GAMES[0]]
          : [];
      return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response);
    }));
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('lobby-game')).toHaveLength(1));
    expect(within(screen.getByTestId('lobby-game')).getByText('小满')).toBeInTheDocument();
  });

  it('配上了就直接进对局 —— 不再多问一次', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('lobby-player')).toHaveLength(5));
    push({ type: 'match_found', session_id: 'sess-9' });
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/pvp/room/sess-9'));
  });

  it('没登录:走那道门,一份灰名单都不摆', async () => {
    auth.token = null;
    renderPage();
    expect(await screen.findByTestId('lobby-guest')).toBeInTheDocument();
    expect(screen.getByText('登录后进在线大厅')).toBeInTheDocument();
    expect(screen.queryAllByTestId('lobby-player')).toHaveLength(0);
    await userEvent.click(screen.getByRole('button', { name: '前往登录' }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/login');
  });

  /**
   * 旧版把「没登录就早退」写在一部分 hooks 中间(`/ws/lobby` 那个 `useEffect` 在它后面),
   * 于是访客那一帧比登录那一帧**少注册一个 hook** —— 同一个组件实例上登录一次就当场抛
   * 「Rendered more hooks than during the previous render」。
   * 这条用同一个实例走一遍「访客 → 登录」,把它钉住。
   */
  it('访客态和登录态是同一条 hook 序列 —— 同一个实例上登录不许炸', async () => {
    auth.token = null;
    const view = renderPage();
    expect(await screen.findByTestId('lobby-guest')).toBeInTheDocument();

    auth.token = 'tok';
    view.rerender(
      <ThemeProvider theme={kioskTheme}><MemoryRouter><LobbyPage /></MemoryRouter></ThemeProvider>,
    );
    await waitFor(() => expect(screen.getAllByTestId('lobby-player')).toHaveLength(5));
  });
});
