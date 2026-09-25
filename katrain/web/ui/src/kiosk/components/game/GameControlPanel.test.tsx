import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, test, expect, vi } from 'vitest';
import GameControlPanel from './GameControlPanel';
import type { GameState } from '../../../api';

const mockGameState: GameState = {
  game_id: 'test-game',
  board_size: [19, 19],
  komi: 6.5,
  handicap: 0,
  ruleset: '日本',
  current_node_id: 0,
  current_node_index: 0,
  history: [{ node_id: 0, score: 0, winrate: 0.5 }],
  player_to_move: 'B',
  stones: [],
  last_move: null,
  prisoner_count: { B: 0, W: 0 },
  analysis: null,
  commentary: '',
  is_root: true,
  is_pass: false,
  end_result: null,
  children: [],
  ghost_stones: [],
  players_info: {
    B: { player_type: 'human', player_subtype: '', name: '张三', calculated_rank: '2D', periods_used: 0, main_time_used: 0 },
    W: { player_type: 'ai', player_subtype: 'katago', name: 'KataGo', calculated_rank: '5D', periods_used: 0, main_time_used: 0 },
  },
  note: '',
  ui_state: {
    show_children: false, show_dots: false, show_hints: false, show_policy: false,
    show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false,
  },
} as GameState;

describe('GameControlPanel', () => {
  test('ranked territory uses the shared action icon and shows quota and result without analysis scores', () => {
    const onRequest = vi.fn();
    const { rerender } = render(<GameControlPanel gameState={{ ...mockGameState, game_type: 'ai_ladder_ranked' }}
      onAction={() => {}} onNavigate={() => {}} analysisToggles={{ coords: true }} onToggleAnalysis={() => {}}
      isRanked territory={{ remaining: 3, phase: 'loading', disabled: true, retrySameRequest: false, onRequest }} />);
    expect(screen.getByRole('button', { name: /领地 3/ })).toBeDisabled();
    expect(screen.getByText('正在请求云端判断…')).toBeInTheDocument();
    expect(screen.queryByText(/胜率/)).toBeNull();
    rerender(<GameControlPanel gameState={{ ...mockGameState, game_type: 'ai_ladder_ranked' }}
      onAction={() => {}} onNavigate={() => {}} analysisToggles={{ coords: true }} onToggleAnalysis={() => {}}
      isRanked territory={{ remaining: 2, phase: 'result', blackArea: 78, whiteArea: 66, disabled: false, retrySameRequest: false, onRequest }} />);
    fireEvent.click(screen.getByRole('button', { name: /领地 2/ }));
    expect(onRequest).toHaveBeenCalledOnce();
    expect(screen.getByText('约 78')).toBeInTheDocument();
    expect(screen.getByText('约 66')).toBeInTheDocument();
    expect(screen.getByText('领地判断：本局剩余 2 次')).toBeInTheDocument();
  });
  // The 3D board was removed from the kiosk on 2026-07-13 (freed ~321MB Mali GPU contending
  // with KataGo's OpenCL). Guard against reintroducing the toggle; core controls must remain.
  test('renders core controls and NO 3D toggle', () => {
    render(
      <GameControlPanel
        gameState={mockGameState}
        onAction={() => {}}
        onNavigate={() => {}}
        analysisToggles={{}}
        onToggleAnalysis={() => {}}
        isGameOver={false}
      />
    );
    expect(screen.queryByText('3D')).toBeNull();
    expect(screen.getByText('领地')).toBeInTheDocument();
    expect(screen.getByText('数子')).toBeInTheDocument();
  });

  test('胜率图只在终局后允许跳转棋谱位置', () => {
    const history = [
      { node_id: 10, score: 0, winrate: 0.5 },
      { node_id: 11, score: 1, winrate: 0.55 },
    ];
    const onNavigate = vi.fn();
    const active = panel({ game_type: 'free', history }, { analysisToggles: { score: true }, onNavigate });
    const activeGraph = active.container.querySelector('svg[data-eval]')!;
    Object.defineProperty(activeGraph, 'getBoundingClientRect', { value: () => ({ left: 0, width: 382 }) });
    fireEvent.click(activeGraph, { clientX: 29 });
    expect(onNavigate).not.toHaveBeenCalled();
    active.unmount();

    const terminal = panel({ game_type: 'free', history }, {
      analysisToggles: { score: true }, onNavigate, isGameOver: true,
    });
    const terminalGraph = terminal.container.querySelector('svg[data-eval]')!;
    Object.defineProperty(terminalGraph, 'getBoundingClientRect', { value: () => ({ left: 0, width: 382 }) });
    fireEvent.click(terminalGraph, { clientX: 29 });
    expect(onNavigate).toHaveBeenCalledWith(11);
  });

  // ── 悔棋按对弈方式判 ────────────────────────────────────────────────────────
  // 只有本地人机自由对弈允许悔棋。星阵机器人页按平台原界面保留灰色按钮，
  // 其余不支持悔棋的对局仍不显示。
  //
  // 五种对弈方式**逐个都要出现在这张表里** —— 少一行就等于那一种没被裁过。
  // 判据落在**屏上有没有这颗键**,不落在 `undoAllowed` 那个变量上:
  // 变量对「渲染那一支忘了引它」免疫,而那正是上一版的病(engineMode 和 playActions
  // 是两支各写一遍的代码,改一支漏一支不会有人红)。
  //
  // 这条留在 jsdom 里是对的:「按钮在不在 DOM 里」是**结构**不是布局,
  // 不经过浏览器的布局引擎;同一批里「三颗键还贴不贴右栏底」那种数在
  // `tests/kiosk-screen-05-game.spec.ts` 里用真浏览器量。
  //
  // **变异记录**(2026-08-25,五处逐个改坏、逐个跑过,不是推演):
  //   M1 `playActions` 无条件出悔棋      → 升降级×2 / 本地 / 大厅 / 灰键那条,红 5
  //   M2 engineMode 那一支把悔棋加回去    → 星阵那行,红 1
  //   M3 `undoAllowed = false`           → 自由对弈那行,红 1
  //   M4 `rankedGame` 只认 prop 不读 game_type → 「漏传 isRanked」那行,红 1
  //   M5 改成留一颗 `disabled` 的悔棋(稿子那个写法) → 红 5(同 M1)
  // 每一行都被至少一处变异单独点过名 —— 没有哪一行是靠别人红顺带绿的。
  const panel = (over: Partial<GameState>, props: Record<string, unknown> = {}) =>
    render(
      <GameControlPanel
        gameState={{ ...mockGameState, ...over }}
        onAction={() => {}}
        onNavigate={() => {}}
        analysisToggles={{}}
        onToggleAnalysis={() => {}}
        isGameOver={false}
        {...props}
      />
    );

  test('an untimed platform game never presents inherited cumulative time as a clock', () => {
    panel({
      game_type: 'free',
      players_info: {
        B: { ...mockGameState.players_info.B, main_time_used: 123 },
        W: { ...mockGameState.players_info.W, main_time_used: 98 },
      },
      timer: { configured: false, paused: false, current_node_time_used: 12, main_time_used: 123, next_player_periods_used: 0,
        settings: { main_time: 20, byo_length: 30, byo_periods: 5, minimal_use: 0, sound: true } },
    }, { engineMode: true });
    expect(screen.queryByText('2:03')).toBeNull();
    expect(screen.queryByText('1:38')).toBeNull();
    expect(screen.getByText('不限时')).toBeInTheDocument();
  });

  test('physical placement status replaces login/count hints without fault styling', () => {
    const { container } = panel(
      { game_type: 'free', analysis_delivered: false, history: [] },
      { analysisRequiresLogin: true, physicalStatus: 'AI 已落子 D4 · 请摆放白子' },
    );
    const hint = container.querySelector('.gtoggles .ghint');
    expect(hint).toHaveTextContent('D4');
    expect(hint).not.toHaveTextContent('登录后可用');
    expect(hint).not.toHaveTextContent('数子要下满');
    expect(hint).not.toHaveAttribute('data-fault');
  });

  test('hardware fault has priority over physical placement status and alone owns data-fault', () => {
    const { container } = panel(
      { game_type: 'free', history: [] },
      { physicalStatus: 'AI 已落子 D4', hardwareFault: 'LED 未连接' },
    );
    const hint = container.querySelector('.gtoggles .ghint');
    expect(hint).toHaveTextContent('LED 未连接');
    expect(hint).not.toHaveTextContent('D4');
    expect(hint).toHaveAttribute('data-fault', 'true');
  });

  test('login then count hints resume when physical placement status is absent', () => {
    const login = panel(
      { game_type: 'free', analysis_delivered: false, history: [] },
      { analysisRequiresLogin: true },
    );
    expect(login.container.querySelector('.gtoggles .ghint')).toHaveTextContent('登录后可用');
    login.unmount();

    const count = panel({ game_type: 'free', history: [] });
    expect(count.container.querySelector('.gtoggles .ghint')).toHaveTextContent('数子要下满 100 手');
  });

  test.each([
    ['人机 · 自由对弈', { game_type: 'free' }, {}, true],
    ['人机 · 升降级对弈', { game_type: 'ai_ladder_ranked' }, { isRanked: true }, false],
    // `isRanked` **没传**:闸自己从 `game_type` 也读得出来。少传一次 prop 不该把闸打开。
    ['人机 · 升降级对弈(调用方漏传 isRanked)', { game_type: 'ai_ladder_ranked' }, {}, false],
    ['人人 · 本地对局', { game_type: 'pvp_local' }, {}, false],
    ['人人 · 对战大厅', { game_type: 'pvp_online' }, {}, false],
    ['跨平台 · 星阵人机（保留灰色平台按钮）', { game_type: 'free' }, { engineMode: true }, true],
  ] as const)('悔棋:%s → %s', (_name, over, props, expected) => {
    panel(over as Partial<GameState>, props as Record<string, unknown>);
    const undo = screen.queryByText('悔棋');
    expect(undo === null, '悔棋这颗键在不在').toBe(!expected);
    // 「认输」在五种里都在 —— 用它证这一排本身渲染了,
    // 否则整块没渲染时上面那句对「不该有」的四行会**全绿**。
    expect(screen.getByText('认输')).toBeInTheDocument();
  });

  test('星阵人机局固定显示四颗动作键；悔棋禁用，数子接到免费形势判断', () => {
    const history = Array.from({ length: 120 }, (_, i) => ({ node_id: i, score: 0, winrate: 0.5 }));
    const onAction = vi.fn();
    const onEngineAnalysis = vi.fn();
    const { container } = panel(
      { game_type: 'free', history },
      { engineMode: true, onAction, onEngineAnalysis },
    );
    expect(screen.getByRole('button', { name: '悔棋' })).toBeDisabled();
    screen.getByRole('button', { name: '停一手' }).click();
    screen.getByRole('button', { name: '数子' }).click();
    expect(screen.getByText('认输')).toBeInTheDocument();
    expect(onAction).toHaveBeenCalledWith('pass');
    expect(onEngineAnalysis).toHaveBeenCalledWith('judge');
    expect(container.querySelector('.gtoggles .ghint')).toHaveTextContent('数子只查看当前形势，不结束对局');
  });

  // ── 棋谱折叠块(星阵屏)────────────────────────────────────────────────────
  // 稿子 `:1833`。数据来自后端 2026-08-25 在主线循环里加的 `history[].move/player`。
  // 这里守的是**怎么叠行**(纯 DOM 结构,jsdom 有权作证);
  // 「装不下时它自己能不能滚 / 一手没下时会不会塌」在
  // `tests/kiosk-screen-05-game.spec.ts` 里用真浏览器量 —— 那些数 jsdom 一条都给不出。
  //
  // **变异记录**(2026-08-25):
  //   M4 按手数奇偶判黑白(不认 `player`) → 只红「让子局」那行
  //   M5 棋谱闸写反(`!engineMode` 才画)  → 红 6 行(这一组全部)
  //   M6 虚手不翻译直接印 `pass`          → 只红「虚手」那行
  //   M7 守卫只挡 `move` 不挡 `player`     → **全绿,没红** ⚠️
  //
  // M7 是我预测会红而没红的:「老后端」那行的 fixture **两个键都没给**,所以 `!h.move`
  // 一条就把它挡住了。想让 `!h.player` 那半边有覆盖,得造一个「给了 move 却没给 player」
  // 的后端 —— 而那种后端不存在(两个键是同一次提交、同一个循环里一起写的)。
  // ⇒ `|| !h.player` 是**防身的,不是闸**。写在这儿是为了下一个人别把它当成有测试守着。
  const hist = (moves: [string, 'B' | 'W'][]) => [
    { node_id: 0, score: null, winrate: null, move: null, player: null },
    ...moves.map(([move, player], i) => ({ node_id: i + 1, score: null, winrate: null, move, player })),
  ] as GameState['history'];

  const rowsOf = () => {
    const body = document.querySelector('[data-testid="game-moves-fold"] .kiosk-fold__body')!;
    const cells = Array.from(body.querySelectorAll('span')).map((n) => n.textContent);
    const out: string[][] = [];
    for (let i = 0; i < cells.length; i += 3) out.push(cells.slice(i, i + 3) as string[]);
    return out;
  };

  // A11(kiosk-go-play-ai,2026-09-14)推翻了「棋谱只在星阵屏」:scope §27 那条概念债说的就是
  // 「没有哪种对局原则上拿不到自己下过的手」。现在胜率块不在的局中段都是棋谱;只有胜率块开着时那块地方归胜率图。
  test('胜率块开着时棋谱不出现 —— 屏 05 那块地方归胜率图', () => {
    panel({ history: hist([['Q16', 'B'], ['D4', 'W']]) }, { analysisToggles: { score: true } });
    expect(screen.queryByTestId('game-moves-fold')).toBeNull();
  });

  test('棋谱按黑白叠行,当前那一手高亮且只有一处', () => {
    panel({ history: hist([['Q16', 'B'], ['D4', 'W'], ['Q4', 'B']]), current_node_index: 3 },
      { engineMode: true });
    expect(rowsOf()).toEqual([['1', 'Q16', 'D4'], ['2', 'Q4', '']]);
    const now = document.querySelectorAll('[data-testid="game-moves-fold"] .mv.now');
    expect(now.length).toBe(1);
    expect(now[0].textContent).toBe('Q4');
  });

  // ⚠️ **不许按手数奇偶判黑白。** 让子局第一手就是白,而让子那几手是连着的黑 ——
  // 按奇偶叠出来会把黑子塞进白列。判据只认后端给的 `player`。
  test('让子局:连着三手黑各占一行的黑格,白格空着', () => {
    panel({ history: hist([['Q16', 'B'], ['D4', 'B'], ['Q4', 'B'], ['D16', 'W']]), current_node_index: 4 },
      { engineMode: true });
    expect(rowsOf()).toEqual([['1', 'Q16', ''], ['2', 'D4', ''], ['3', 'Q4', 'D16']]);
  });

  test('虚手写「虚手」,不写 pass', () => {
    panel({ history: hist([['Q16', 'B'], ['pass', 'W']]), current_node_index: 2 }, { engineMode: true });
    expect(rowsOf()).toEqual([['1', 'Q16', '虚手']]);
  });

  // 一手没下、以及**后端还是老的那一版**(没有 move/player 两个键)——
  // 两种都不许白板一块,也不许崩。后者是真会发生的:盒子上的服务比前端旧几天是常态。
  test.each([
    ['一手没下', hist([])],
    ['老后端没给 move/player', [{ node_id: 0, score: null, winrate: null },
                               { node_id: 1, score: null, winrate: null }] as GameState['history']],
  ])('棋谱空态会说话:%s', (_name, history) => {
    panel({ history, current_node_index: 0 }, { engineMode: true });
    expect(screen.getByText('这一局还没有着法')).toBeInTheDocument();
  });

  // 撤掉不是灰着:这四种里悔棋是**开局就定死的没有**,不是过一会儿会回来的状态。
  // 判据「永久不可用 → 撤掉;暂时不可用 → 灰着」 —— 所以不许留一颗 `disabled` 的悔棋。
  test('不该有悔棋的局里,也不许留一颗灰着的悔棋', () => {
    panel({ game_type: 'pvp_online' });
    expect(screen.queryByRole('button', { name: /悔棋/ })).toBeNull();
  });

  // ── 本地对局右栏(v2 D1)────────────────────────────────────────────────
  // 「领地」「AI 支招」**撤掉不是灰着**:这一局开局就定死不接引擎辅助,永久不可用 → 不渲染。
  // 结构断言(在不在 DOM),不是布局断言;右栏高度与滚动在 kiosk-screen-05-game.spec.ts 里量。
  const actionLabels = () =>
    within(screen.getByTestId('game-actions')).getAllByRole('button').map((b) => b.textContent?.trim());

  test('本地对局:右栏只有 数子 · 停一手 · 认输', () => {
    panel({ game_type: 'pvp_local', history: hist([]) });
    expect(actionLabels()).toEqual(['数子', '停一手', '认输']);
    expect(screen.queryByText('领地')).toBeNull();
    expect(screen.queryByText('AI支招')).toBeNull();
    expect(screen.getByRole('switch', { name: '坐标' })).toBeInTheDocument();
    expect(screen.getByRole('switch', { name: '手数' })).toBeInTheDocument();
  });

  test('自由对弈右栏不受影响:领地仍在', () => {
    panel({ game_type: 'free' });
    expect(screen.getByText('领地')).toBeInTheDocument();
  });

  test('「数子要下满 N 手」的 N 读服务端下发的 count_min_moves(9 路 22)', () => {
    panel({ game_type: 'pvp_local', board_size: [9, 9], count_min_moves: 22, history: hist([['E5', 'B']]) });
    expect(screen.getByText('数子要下满 22 手')).toBeInTheDocument();
    expect(screen.getByText('数子').closest('button')).toBeDisabled();
  });

  test('本地对局登录态之外也不说「领地 / 支招 / 图表 登录后可用」—— 那三颗键这一局根本没有', () => {
    panel({ game_type: 'pvp_local', count_min_moves: 22, history: hist([['E5', 'B']]) }, { analysisRequiresLogin: true });
    expect(screen.queryByText('领地 / 支招 / 图表 登录后可用')).toBeNull();
    expect(screen.getByText('数子要下满 22 手')).toBeInTheDocument();
  });

  test('升降级手动数子数的是实际 100 手，不把根节点算作一手', () => {
    panel({ game_type: 'ai_ladder_ranked', count_min_moves: 100,
      history: Array(100).fill(mockGameState.history[0]) });
    expect(screen.getByText('数子').closest('button')).toBeDisabled();
  });

  test('双 pass 后后端在等数子(awaiting_count)⇒ 手数不够也亮,右端不再说门槛', () => {
    panel({
      // end_result 照后端真实形状写(F1):双 pass 后一定非空,判据是 awaiting_count 不是它。
      game_type: 'pvp_local', count_min_moves: 100, awaiting_count: true, end_result: '终局',
      history: hist([['Q16', 'B'], ['pass', 'W'], ['pass', 'B']]),
      players_info: {
        ...mockGameState.players_info,
        B: { ...mockGameState.players_info.B, player_type: 'player:human' },
        W: { ...mockGameState.players_info.W, player_type: 'player:human' },
      },
    });
    expect(screen.getByText('数子').closest('button')).not.toBeDisabled();
    expect(screen.queryByText(/数子要下满/)).toBeNull();
  });
});
