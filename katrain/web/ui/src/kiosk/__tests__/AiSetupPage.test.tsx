import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import AiSetupPage from '../pages/AiSetupPage';

/**
 * 屏 02 / 03 的**控件与开局载荷**那一半。（版式、赌注口径、挡局面板在
 * `pages/AiSetupPage.test.tsx`，那一份是这一屏的主测试。两份并存是历史遗留，
 * 不是分工——合并要动 700 行，登记，不在这一轮。）
 *
 * 2026-08-23 按稿子重画之后，这里原来那 20 条**全部钉在 MUI 下拉上**：
 * `getByRole('combobox', { name: '规则' })` 之类。控件换成分段 / 档位轨之后
 * 它们不是「碰巧红了」，而是**守的那个东西整个换了形状**。
 * 判别方式改成「这一组在不在、当前读数是什么」——那才是它们本来要守的。
 */

vi.mock('../../api', () => ({
  API: {
    createSession: vi.fn().mockResolvedValue({ session_id: 'new-session-123', state: {} }),
    gameSetup: vi.fn().mockResolvedValue({ session_id: 'new-session-123', state: {} }),
  },
}));

vi.mock('../../features/aiLadder/api', () => ({ startAiLadderGame: vi.fn().mockResolvedValue({ session_id: 'ranked-s1', game_id: 'g1' }) }));
vi.mock('../../features/aiLadder/useAiLadderStatus', () => ({ useAiLadderStatus: () => ({ status: { view_state: 'ready', placement_state: { phase: 'placement', completed_games: 2, total_games: 5 }, current_opponent: { rung: 12, rank_name: '9级', certification_status: 'certified', availability: 'available', route: 'server' }, recent_ranked_results: [], net_score: 0, pending_settlement: false }, retry: vi.fn() }) }));

/* 登录态要能在用例之间变 —— 游客那三条断言全靠它。
   ⚠️ **`token` 不是登录态**:strict box kiosk 上鉴权走 HttpOnly 的 `sb_go_token` cookie,
   `token` 恒为 null 而人是登录着的。所以下面两者分开设,别用一个字段代替另一个。 */
const authState = {
  token: 'test-token' as string | null,
  user: { id: 1, username: 'test' } as { id: number; username: string } | null,
  isAuthenticated: true,
  isLoading: false,
};
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => authState,
}));

// 「怎么落子」读的是设备能力,不是设置项 —— 这一屏因此要 VisionProvider 的桩。
vi.mock('../context/VisionContext', () => ({
  useVision: () => ({
    visionStatus: { enabled: false },
    isVisionEnabled: false,
    refreshStatus: vi.fn(),
  }),
}));

const renderPage = (mode = 'free') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[`/kiosk/play/ai/setup/${mode}`]}>
        <Routes>
          <Route path="/kiosk/play/ai/setup/:mode" element={<AiSetupPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

/** 档位轨的 ＋ 键。轨本身不可点(29 个点摊在 330px 上手指点不准),只有两头的键能按。 */
const step = (testId: string, dir: '＋' | '−') => {
  const track = screen.getByTestId(testId);
  return within(track).getByRole('button', { name: dir === '＋' ? /多|提高|增加/ : /少|降低|减少/ });
};

describe('AiSetupPage', () => {
  // 原来钉的是 `document.querySelector('canvas')` —— 那是 `LiveBoard` 的实现细节。
  // 改布局 A 之后左栏换成了自己画的 SVG 盘(`KioskSetupBoard`,规范 `:512`),canvas 没了。
  // **规则过期,陷阱没有**:它守的是「这一屏左边必须有一块真盘」,那条一直成立。
  it('renders the opening-position board on the left', () => {
    renderPage();
    expect(screen.getByTestId('kiosk-setup-board')).toBeInTheDocument();
    expect(document.querySelectorAll('.kiosk-board__ruler--top span')).toHaveLength(19);
  });

  // 规范 §11:左边那块盘画的是**按下按钮后真会出现的那个局面**。让子局的起始局面
  // 带着几颗黑子 —— 2026-08-23 之前这里恒画空盘,是四图一比才露出来的。
  it('让子调上去,左边那块盘跟着摆出让子', async () => {
    renderPage('free');
    const board = screen.getByTestId('kiosk-setup-board');
    const stones = () => [...board.querySelectorAll('[data-stone]')].map((g) => g.getAttribute('data-at'));
    expect(board).toHaveAttribute('data-handicap', '0');
    expect(stones()).toEqual([]);

    const user = userEvent.setup();
    await user.click(step('setup-handicap', '＋'));
    await user.click(step('setup-handicap', '＋'));
    expect(board).toHaveAttribute('data-handicap', '2');
    // **点名是哪两个点**,不是数个数:数个数的话摆错位置照样绿。
    // Q16 / D4 照后端 `core/sgf_parser.py:374 place_handicap_stones` 那一份算出来,
    // 也正是稿子 02 屏那一帧盘上的两颗。
    expect(stones()).toEqual(['Q16', 'D4']);
    expect(board.querySelectorAll('[data-stone="w"]')).toHaveLength(0);
  });

  it('renders board size options', () => {
    renderPage();
    const size = screen.getByTestId('setup-size');
    expect(size).toHaveTextContent('19 路');
    expect(size).toHaveTextContent('13 路');
    expect(size).toHaveTextContent('9 路');
  });

  it('renders ruleset selector', () => {
    renderPage();
    const rules = screen.getByTestId('setup-rules');
    for (const label of ['中国', '日本', '韩国', 'AGA']) expect(rules).toHaveTextContent(label);
    // 四段并排 ⇒ 四个选项**同时可见**,不再藏在下拉后面(规范 §11 项数上限 6)。
    expect(within(rules).getAllByRole('button')).toHaveLength(4);
    expect(within(rules).getByRole('button', { name: '中国' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('renders color selection', () => {
    renderPage();
    const color = screen.getByTestId('setup-color');
    expect(color).toHaveTextContent('执黑');
    expect(color).toHaveTextContent('执白');
    // 稿子第三项「随机」是搬象棋骨架带来的,围棋 kiosk 和 galaxy 两处都只给黑白。
    expect(within(color).getAllByRole('button')).toHaveLength(2);
  });

  it('renders start button', () => {
    renderPage();
    expect(screen.getByRole('button', { name: /开始对局/i })).toBeInTheDocument();
  });

  it('shows AI strategy selector for free mode', () => {
    renderPage('free');
    const strategy = screen.getByTestId('setup-strategy');
    for (const label of ['拟人', 'KataGo', '实地', '厚势', '策略']) {
      expect(strategy).toHaveTextContent(label);
    }
    expect(within(strategy).getByRole('button', { name: '拟人' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('shows AI strength selector in free mode when human strategy selected', () => {
    renderPage('free');
    // 默认策略是 ai:human,棋力那条轨因此在。
    expect(screen.getByTestId('setup-strength')).toBeInTheDocument();
  });

  it('hides AI strength selector in free mode for non-human strategy', async () => {
    renderPage('free');
    const user = userEvent.setup();
    await user.click(within(screen.getByTestId('setup-strategy')).getByRole('button', { name: 'KataGo' }));
    expect(screen.queryByTestId('setup-strength')).not.toBeInTheDocument();
  });

  it('hides AI strategy selector for ranked mode', () => {
    renderPage('ranked');
    expect(screen.queryByTestId('setup-strategy')).not.toBeInTheDocument();
  });

  it('shows the authoritative ladder opponent for ranked mode', () => {
    renderPage('ranked');
    expect(screen.getByText('定级对手：9级')).toBeInTheDocument();
    expect(screen.queryByTestId('setup-strength')).not.toBeInTheDocument();
  });

  it('renders handicap selector defaulting to none', () => {
    renderPage();
    expect(screen.getByTestId('setup-handicap')).toBeInTheDocument();
    expect(screen.getByText('不让子')).toBeInTheDocument();
  });

  it('shows komi selector in free mode with no handicap', () => {
    renderPage('free');
    expect(screen.getByTestId('setup-komi')).toBeInTheDocument();
    expect(screen.queryByTestId('setup-komi-explain')).not.toBeInTheDocument();
  });

  it('hides komi selector when handicap is set', async () => {
    renderPage('free');
    const user = userEvent.setup();
    await user.click(step('setup-handicap', '＋'));
    await user.click(step('setup-handicap', '＋'));
    expect(screen.queryByTestId('setup-komi')).not.toBeInTheDocument();
    // **不是把控件灰掉** —— 换成一段说明:这一局根本没有贴目这回事。
    expect(screen.getByTestId('setup-komi-explain')).toHaveTextContent('已经让了 2 子');
  });

  it('shows time control selector', () => {
    renderPage();
    expect(screen.getByTestId('setup-clock')).toBeInTheDocument();
  });

  it('time selector defaults to untimed in free mode', () => {
    renderPage('free');
    expect(screen.getByText('不限时')).toBeInTheDocument();
  });

  // 轨上按时长从短到长排:仅读秒 → 5 → 10 → 20 → 30 → 60 → 不限时。
  // 自由对弈默认停在最右端(不限时),所以往回按一格是 60 分。
  it('offers timed presets that map onto the existing main-time/byoyomi state', async () => {
    renderPage('free');
    const user = userEvent.setup();
    await user.click(step('setup-clock', '−'));
    expect(screen.getByTestId('setup-clock').parentElement).toHaveTextContent('60分+3×30秒');
    await user.click(step('setup-clock', '−'));
    expect(screen.getByTestId('setup-clock').parentElement).toHaveTextContent('30分+3×30秒');
  });

  it('time selector excludes the untimed preset for ranked mode (time is forced on)', () => {
    renderPage('ranked');
    // 计分局那条轨只有 6 档 —— 「不限时」整个不在轨上,不是灰掉。
    expect(screen.getByTestId('setup-clock').parentElement).toHaveTextContent('6 档');
    expect(screen.queryByText('不限时')).not.toBeInTheDocument();
  });

  it('ranked mode defaults to a byoyomi-only preset (30s x3), same as prior slider defaults', () => {
    renderPage('ranked');
    // 读数那一行(`.catmeta b`)才是「现在停在哪一档」;同样的字也出现在右边的范围里
    // (「6 档 · 仅读秒 30秒×3 → 60分+3×30秒」),所以要挑左半,不能 getByText。
    const meta = screen.getByTestId('setup-clock').parentElement!.querySelector('.catmeta b');
    expect(meta).toHaveTextContent(/仅读秒.*30秒.*3/);
  });

  it('calls API.createSession and gameSetup on start', async () => {
    renderPage('free');
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /开始对局/i }));
    const { API } = await import('../../api');
    await waitFor(() => {
      expect(API.createSession).toHaveBeenCalled();
      expect(API.gameSetup).toHaveBeenCalledWith('new-session-123', 'free', expect.objectContaining({
        board_size: 19,
        rules: 'chinese',
        color: 'black',
      }));
    });
  });

  it('shows error alert when API call fails', async () => {
    const { API } = await import('../../api');
    (API.createSession as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error('Network error'));
    renderPage('free');
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /开始对局/i }));
    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  /* --- 游客(develop 的 feature/guest-free-play 放开了无人认领的会话) ---------------
     后端那半是共享的,kiosk 自动吃到;这三条守的是 kiosk 前端那半 —— 在这之前
     kiosk 一处都没跟上(改动全落在 `galaxy/`)。 */
  describe('游客', () => {
    afterEach(() => {
      authState.isAuthenticated = true;
      authState.isLoading = false;
      authState.token = 'test-token';
      authState.user = { id: 1, username: 'test' };
    });

    it('未登录时在自由对弈屏上说清这一局不会保存', async () => {
      authState.isAuthenticated = false;
      authState.user = null;
      renderPage('free');
      expect(await screen.findByTestId('setup-guest-notice')).toHaveTextContent('游客身份');
    });

    it('已登录时不说 —— 判据是 isAuthenticated,不是 token', async () => {
      // 盒上 strict kiosk 的真实形态:cookie 鉴权,`token` 恒为 null 而人是登录着的。
      // 拿 `!token` 当判据的话,这一条会红 —— 它会对每一个盒上用户说「你是游客」。
      authState.isAuthenticated = true;
      authState.token = null;
      renderPage('free');
      await screen.findByTestId('ai-setup-page');
      expect(screen.queryByTestId('setup-guest-notice')).toBeNull();
    });

    it('`/me` 还没回来时不抢先说 —— 否则已登录用户每次进来都要闪一下', async () => {
      authState.isAuthenticated = false;
      authState.isLoading = true;
      renderPage('free');
      await screen.findByTestId('ai-setup-page');
      expect(screen.queryByTestId('setup-guest-notice')).toBeNull();
    });

    it('开局被 401 拒时给的是「去登录」,不是一句英文报文', async () => {
      const { API } = await import('../../api');
      const err = Object.assign(new Error('Request failed 401: {"detail":"Not authenticated"}'), { status: 401 });
      (API.createSession as ReturnType<typeof vi.fn>).mockRejectedValueOnce(err);
      renderPage('free');
      const user = userEvent.setup();
      await user.click(screen.getByRole('button', { name: /开始对局/i }));
      const prompt = await screen.findByTestId('setup-auth-prompt');
      expect(prompt).toHaveTextContent('需要登录');
      expect(within(prompt).getByRole('button', { name: /去登录/ })).toBeInTheDocument();
      // 原始英文报文不许再出现在屏上
      expect(screen.queryByText(/Not authenticated/)).toBeNull();
    });

    it('🔴 已登录时的 403 **不是**「去登录」—— 那是对登录着的人说假话', async () => {
      // 这一格是这组里最容易写错的:403 在这条链上最常见的是
      // `guard_user_has_no_pending_ranked_game` 的「你有一局升降级还没结算」,
      // 把它也翻成「需要登录」,用户照着做也解决不了。
      const { API } = await import('../../api');
      const err = Object.assign(new Error('You already have a pending ranked AI game'), { status: 403 });
      (API.createSession as ReturnType<typeof vi.fn>).mockRejectedValueOnce(err);
      authState.isAuthenticated = true;
      renderPage('free');
      const user = userEvent.setup();
      await user.click(screen.getByRole('button', { name: /开始对局/i }));
      await waitFor(() => {
        expect(screen.getByText(/pending ranked AI game/)).toBeInTheDocument();
      });
      expect(screen.queryByTestId('setup-auth-prompt')).toBeNull();
    });

    it('🔴 升降级那一屏对游客说的是「需要登录」,而且给两条出路', async () => {
      // 路由摘掉守卫之后 `:mode` 也匹配 ranked ⇒ 游客真的能走到这一屏。
      // 段位记在账号上,没有账号就无处可记 —— 说原因,不是报故障。
      authState.isAuthenticated = false;
      authState.user = null;
      renderPage('ranked');
      const panel = await screen.findByTestId('ranked-login-required');
      expect(panel).toHaveTextContent('需要登录');
      expect(within(panel).getByRole('button', { name: /去登录/ })).toBeInTheDocument();
      // 只说「去登录」等于把人堵在这儿 —— 他现在就能下的那一种也要给。
      expect(within(panel).getByRole('button', { name: /先去自由对弈/ })).toBeInTheDocument();
    });

    it('已登录时升降级屏照常渲染设置,不弹登录', async () => {
      authState.isAuthenticated = true;
      renderPage('ranked');
      await screen.findByTestId('ai-setup-page');
      expect(screen.queryByTestId('ranked-login-required')).toBeNull();
    });

    it('未登录时的 403 仍归登录引导', async () => {
      const { API } = await import('../../api');
      const err = Object.assign(new Error('Forbidden'), { status: 403 });
      (API.createSession as ReturnType<typeof vi.fn>).mockRejectedValueOnce(err);
      authState.isAuthenticated = false;
      authState.user = null;
      renderPage('free');
      const user = userEvent.setup();
      await user.click(screen.getByRole('button', { name: /开始对局/i }));
      expect(await screen.findByTestId('setup-auth-prompt')).toHaveTextContent('需要登录');
    });
  });
});
