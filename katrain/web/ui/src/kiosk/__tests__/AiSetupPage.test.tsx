import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import AiSetupPage from '../pages/AiSetupPage';
import { openPick, pick } from './helpers/setupPick';

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
    await pick(user, 'setup-handicap', '2');
    expect(board).toHaveAttribute('data-handicap', '2');
    // **点名是哪两个点**,不是数个数:数个数的话摆错位置照样绿。
    // Q16 / D4 照后端 `core/sgf_parser.py:374 place_handicap_stones` 那一份算出来。
    expect(stones()).toEqual(['Q16', 'D4']);
    expect(board.querySelectorAll('[data-stone="w"]')).toHaveLength(0);
  });

  it('路数三档', async () => {
    renderPage();
    const pop = await openPick(userEvent.setup(), 'setup-size');
    expect([...pop.querySelectorAll('[data-k]')].map((e) => e.getAttribute('data-k')))
      .toEqual(['19', '13', '9']);
  });

  it('规则四项:韩国撤掉,AI 赛顶上', async () => {
    renderPage();
    const pop = await openPick(userEvent.setup(), 'setup-rules');
    // 韩国规则在 KataGo 里和日本规则是同一个 if 分支、逐字相同(cpp/game/rules.cpp:276),
    // 留着等于四选一里有一项是纯装饰。
    expect([...pop.querySelectorAll('[data-k]')].map((e) => e.getAttribute('data-k')))
      .toEqual(['chinese', 'japanese', 'aga', 'button']);
    expect(pop.querySelector('[data-k="chinese"]')).toHaveAttribute('aria-selected', 'true');
  });

  it('我执三项:黑 / 白 / 猜先', async () => {
    renderPage();
    const pop = await openPick(userEvent.setup(), 'setup-color');
    expect([...pop.querySelectorAll('[data-k]')].map((e) => e.getAttribute('data-k')))
      .toEqual(['black', 'white', 'guess']);
  });

  it('让子局关掉「猜先」,并说得出为什么', async () => {
    renderPage('free');
    const user = userEvent.setup();
    await pick(user, 'setup-handicap', '4');
    const pop = await openPick(user, 'setup-color');
    const guess = pop.querySelector('[data-k="guess"]') as HTMLButtonElement;
    // 让子局黑方先摆子 —— 让哪一方是这一局的前提,不能再抽签。
    expect(guess).toBeDisabled();
    expect(guess).toHaveTextContent('让子局黑方先摆子');
  });

  it('renders start button', () => {
    renderPage();
    expect(screen.getByRole('button', { name: /开始对局/i })).toBeInTheDocument();
  });

  it('AI 策略那一组已经撤掉 —— 对手钉死拟人', () => {
    renderPage('free');
    // 撤它不是为了省一行:改版前选了 KataGo/实地/厚势/策略就连棋力档都不给选,
    // 而后端仍照写 `ai/{strategy}/kyu_rank`。一根只对五分之一选项成立的档位轴,
    // 不该用一个平行的五选一去否定它。
    expect(screen.queryByTestId('setup-strategy')).not.toBeInTheDocument();
    expect(screen.getByTestId('setup-strength')).toBeInTheDocument();
  });

  it('棋力读数带上等级 —— 改版前那半截从来没接上过', () => {
    renderPage('free');
    // 那句 msgid 的缺省值结尾就是「第 {n} 档 · 」,屏上是个吊着的点号。
    expect(screen.getByTestId('setup-strength-value')).toHaveTextContent(/第 15 档 · \S/);
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

  it('让子默认分先;十一档从倒贴排到让 9 子', async () => {
    renderPage();
    expect(screen.getByTestId('setup-handicap-value')).toHaveTextContent('分先');
    const pop = await openPick(userEvent.setup(), 'setup-handicap');
    expect([...pop.querySelectorAll('[data-k]')].map((e) => e.getAttribute('data-k')))
      .toEqual(['rev', 'even', 'sen', '2', '3', '4', '5', '6', '7', '8', '9', 'free']);
  });

  it('贴目是推导出来的读数,平时点不动', () => {
    renderPage('free');
    const komi = screen.getByTestId('setup-komi');
    expect(komi).toBeDisabled();
    expect(screen.getByTestId('setup-komi-value')).toHaveTextContent('黑贴 3¾ 子 · 7.5 目');
  });

  it('换规则,贴目跟着换 —— 而且单位跟着规则走', async () => {
    renderPage('free');
    const user = userEvent.setup();
    await pick(user, 'setup-rules', 'japanese');
    // 数目的规则只写目,不写子
    expect(screen.getByTestId('setup-komi-value')).toHaveTextContent('黑贴 6.5 目');
    await pick(user, 'setup-rules', 'button');
    // 面积 + button 的 KataGo 默认是 7.0(docs/Analysis_Engine.md:82)
    expect(screen.getByTestId('setup-komi-value')).toHaveTextContent('黑贴 3½ 子 · 7 目');
  });

  it('让子局不贴目 —— 补偿是 KataGo 按规则自动加的', async () => {
    renderPage('free');
    await pick(userEvent.setup(), 'setup-handicap', '2');
    expect(screen.getByTestId('setup-komi-value')).toHaveTextContent('不贴目 · 黑先摆 2 子');
  });

  it('「自定贴目」那一档,贴目条才变回控件', async () => {
    renderPage('free');
    const user = userEvent.setup();
    expect(screen.getByTestId('setup-komi')).toBeDisabled();
    await pick(user, 'setup-handicap', 'free');
    expect(screen.getByTestId('setup-komi')).toBeEnabled();
    await pick(user, 'setup-komi', '3.5');
    expect(screen.getByTestId('setup-komi-value')).toHaveTextContent('黑贴 1¾ 子 · 3.5 目');
  });

  it('shows time control selector', () => {
    renderPage();
    expect(screen.getByTestId('setup-clock')).toBeInTheDocument();
  });

  it('time selector defaults to untimed in free mode', () => {
    renderPage('free');
    expect(screen.getByTestId('setup-clock-value')).toHaveTextContent('不限时');
  });

  it('offers timed presets that map onto the existing main-time/byoyomi state', async () => {
    renderPage('free');
    await pick(userEvent.setup(), 'setup-clock', '60');
    expect(screen.getByTestId('setup-clock-value')).toHaveTextContent('60分+3×30秒');
  });

  it('time selector excludes the untimed preset for ranked mode (time is forced on)', async () => {
    renderPage('ranked');
    // 计分局只有 6 档 —— 「不限时」整个不在清单上,不是灰掉。
    const pop = await openPick(userEvent.setup(), 'setup-clock');
    expect(pop.querySelectorAll('[data-k]')).toHaveLength(6);
    expect(pop.querySelector('[data-k="untimed"]')).toBeNull();
  });

  it('ranked mode defaults to a byoyomi-only preset (30s x3), same as prior slider defaults', () => {
    renderPage('ranked');
    expect(screen.getByTestId('setup-clock-value')).toHaveTextContent(/仅读秒.*30秒.*3/);
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
