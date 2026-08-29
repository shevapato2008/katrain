import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import { AUTO_ADVANCE_KEY, sequenceKey } from '../pages/tsumegoUnits';
import type { PhysicalTsumegoState } from '../hooks/usePhysicalTsumego';

// ---- Hoisted spies referenced by the mock factories below ----
const { mockNavigate, mockFlush, mockReadPhysicalMode } = vi.hoisted(() => ({
  mockNavigate: vi.fn(),
  mockFlush: vi.fn(),
  mockReadPhysicalMode: vi.fn(() => false),
}));

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

// Only `readPhysicalMode` is mocked (D1.3) — every other export (sequenceKey,
// AUTO_ADVANCE_KEY, PHYSICAL_MODE_KEY, readAutoAdvance, levelChinese, ...) passes through
// unmocked so the rest of the test file's existing behavior is unaffected.
vi.mock('../pages/tsumegoUnits', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../pages/tsumegoUnits')>();
  return { ...actual, readPhysicalMode: () => mockReadPhysicalMode() };
});

vi.mock('../context/OrientationContext', () => ({
  useOrientation: () => ({ rotation: 0, setRotation: vi.fn() }),
}));

// 视觉默认关掉(BoardSetupGuide / API.visionSetupMode 那条分支保持不动)。
// ⚠️ **可切换**:实体模式真正的开关是 `physicalEnabled = 用户开关 && 视觉就绪 && 19 路`,
// 光把 `readPhysicalMode` 打开**进不了**那条分支。上一版测试断言「开关一开就挂出状态板」,
// 那是把 `physicalMode` 当成了 `physicalEnabled` —— 而生产里那种组合下 phase 恒为 'off',
// 状态板自己就返回 null。**断言建在一个到不了的状态上。**
const { mockVision } = vi.hoisted(() => ({
  mockVision: { enabled: false, recognitionReady: false },
}));
vi.mock('../context/VisionContext', () => ({
  useVision: () => ({
    visionStatus: {
      enabled: mockVision.enabled,
      cameraConnected: mockVision.enabled,
      poseLocked: mockVision.enabled,
      syncState: 'idle',
      boundSessionId: null,
      recognitionReady: mockVision.recognitionReady,
    },
    isVisionEnabled: mockVision.enabled,
    refreshStatus: vi.fn(),
  }),
}));

vi.mock('../hooks/useVisionSync', () => ({
  useVisionSync: () => ({
    syncEvents: [],
    latestEvent: null,
    setupProgress: null,
    isSetupComplete: false,
  }),
}));

vi.mock('../../hooks/useSound', () => ({
  useSound: () => ({ play: vi.fn() }),
}));

// Progress source — `progress` map drives the "上次用时" (last-time) display.
const { mockProgress } = vi.hoisted(() => ({ mockProgress: {} as Record<string, any> }));
vi.mock('../../context/TsumegoProgressContext', () => ({
  useTsumegoProgress: () => ({
    progress: mockProgress,
    markProgress: vi.fn(),
    isCompleted: () => false,
    unitProgress: () => ({ completed: 0, total: 0 }),
    categoryProgress: () => ({ completed: 0, total: 0 }),
    refresh: vi.fn(),
  }),
}));

const mockUndo = vi.fn();
const mockReset = vi.fn();
const mockToggleHint = vi.fn();
const mockEnterTryMode = vi.fn();
const mockExitTryMode = vi.fn();
const mockPlaceStone = vi.fn();
const mockSaveProgress = vi.fn();

const defaultHookReturn = {
  problem: { id: 'p1', level: '15k', category: '手筋', hint: '找到要点', boardSize: 9, initialBlack: [], initialWhite: [], sgfContent: '' },
  loading: false,
  error: null,
  boardSize: 9,
  stones: [{ player: 'B' as const, coords: [2, 3] as [number, number] }],
  lastMove: [2, 3] as [number, number],
  currentNode: null,
  nextPlayer: 'W' as const,
  moveHistory: [],
  isSolved: false,
  isFailed: false,
  isTryMode: false,
  startTime: Date.now(),
  elapsedTime: 42,
  attempts: 1,
  showHint: false,
  hintCoords: [4, 4] as [number, number],
  placeStone: mockPlaceStone,
  undo: mockUndo,
  reset: mockReset,
  toggleHint: mockToggleHint,
  enterTryMode: mockEnterTryMode,
  exitTryMode: mockExitTryMode,
  saveProgress: mockSaveProgress,
  // Phase 4: the page calls flushProgress before every navigation away from a problem.
  flushProgress: mockFlush,
};

let hookReturn = { ...defaultHookReturn };

vi.mock('../../hooks/useTsumegoProblem', () => ({
  useTsumegoProblem: () => hookReturn,
}));

// usePhysicalTsumego is the REAL IO hook (its own 38-test suite covers the phase machine +
// vision/LED/voice effects). Here it's mocked to a controllable state so the D1.3 page-wiring
// tests assert the panel mount/hide + prop passthrough in isolation — without driving vision IO,
// and without depending on the real hook's clearing→setup lifecycle (which needs a live vision WS).
// stonesToVisionBoard passes through (the page imports it for screen-click passthrough).
const defaultPhysicalReturn: PhysicalTsumegoState = {
  phase: 'off',
  stage: 'black',
  missing: [],
  extra: [],
  stageMatched: 0,
  stageTotal: 0,
  ledOk: true,
  onScreenMove: vi.fn(),
};
let physicalReturn: PhysicalTsumegoState = { ...defaultPhysicalReturn };

vi.mock('../hooks/usePhysicalTsumego', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../hooks/usePhysicalTsumego')>();
  return { ...actual, usePhysicalTsumego: () => physicalReturn };
});

import TsumegoProblemPage from '../pages/TsumegoProblemPage';

// The category sequence used for prev/next. The mocked problem id is 'p1'.
const SEQUENCE = ['p0', 'p1', 'p2'];

const renderPage = (problemId = 'p1') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[`/kiosk/tsumego/problem/${problemId}`]}>
        <Routes>
          <Route path="/kiosk/tsumego/problem/:problemId" element={<TsumegoProblemPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

beforeEach(() => {
  vi.clearAllMocks();
  hookReturn = { ...defaultHookReturn };
  physicalReturn = { ...defaultPhysicalReturn };
  for (const k of Object.keys(mockProgress)) delete mockProgress[k];
  sessionStorage.clear();
  localStorage.clear();
  // vi.clearAllMocks() clears call history but not a prior mockReturnValue override —
  // reset explicitly so physical mode defaults OFF for every test unless a case opts in.
  mockReadPhysicalMode.mockReturnValue(false);
  mockVision.enabled = false;
  mockVision.recognitionReady = false;
  // Seed the prev/next sequence the units page would have written.
  sessionStorage.setItem(sequenceKey('15k', '手筋'), JSON.stringify(SEQUENCE));
});

describe('TsumegoProblemPage · 屏 14 做题屏', () => {
  /**
   * **2026-08-22 按稿子整屏换过**,所以和上一版对不上是预期的:
   * 上一版是「MUI 按钮 + Alert + 一排药丸」,稿子上是 L2 布局 A ——
   * 盘 516 + 右栏五块(页控条 / 这一题 / 你的走法 / 第 N 单元 / 动作区)。
   *
   * 留下来的是**契约**,不是文案:上/下一题算得对、走之前先落盘、做对之后自动翻页、
   * 实体模式那条分支的门槛,以及**题面不许编**。
   */

  const enablePhysical = () => {
    mockReadPhysicalMode.mockReturnValue(true);
    mockVision.enabled = true;
    mockVision.recognitionReady = true;
    // 实体盘固定 19 路 —— 非 19 路的题这条分支根本不开。
    hookReturn = { ...defaultHookReturn, boardSize: 19 };
  };

  const action = (name: string) => screen.getByRole('button', { name });

  it('页控条:标题是第几题,副标是档位和分类,返回键回这一题所在的单元', () => {
    renderPage('p1');
    expect(screen.getByText('第 2 题')).toBeInTheDocument();
    expect(screen.getByText('15 级 · 手筋')).toBeInTheDocument();
  });

  /* ── 这一屏最容易犯的错:**题库里没有题面** ──────────────────────────────
   * `TsumegoProblem` 的列只有 id / level / category / hint(16 字) / board_size /
   * initial_black / initial_white / sgf_content。稿子上那段「黑先。白有两颗子……」
   * 和页控条上的「一手叫吃两边」都是**画稿时手写的**。搬过来 = 生产代码里的假业务数据。 */
  it('题面只说得出 hint 那一句 + 这一屏自己的规则,不编题面', () => {
    renderPage();
    const q = screen.getByTestId('puzzle-statement');
    expect(q).toHaveTextContent('找到要点');
    expect(q).toHaveTextContent('落子即判');
    // 稿子上那段手写题面一个字都不许出现。
    expect(q.textContent).not.toMatch(/白有两颗子|不连在一起/);
  });

  it('两个标签是分类和档位;稿子第三个「示意题面」不搬 —— 真题来自题库,挂着就是撒谎', () => {
    renderPage();
    const tags = Array.from(document.querySelectorAll('.kiosk-tag')).map((n) => n.textContent);
    expect(tags).toEqual(['手筋', '15 级']);
  });

  it('盘画出来了', () => {
    renderPage();
    expect(screen.getByTestId('tsumego-board')).toBeInTheDocument();
  });

  it('计数条:用时 + 试了几次(和屏 13 同一个口径:做对的那一次要算进去)', () => {
    renderPage();
    expect(screen.getByTestId('puzzle-counters')).toHaveTextContent('用时 0:42');
    expect(screen.getByTestId('puzzle-counters')).toHaveTextContent('1 次');
  });

  it('做对之后「试了几次」+1 —— attempts 数的是失败的那几次', () => {
    hookReturn = { ...defaultHookReturn, isSolved: true, attempts: 1 };
    renderPage();
    expect(screen.getByTestId('puzzle-counters')).toHaveTextContent('2 次');
  });

  it('动作区五个键一排:提示 / 退一手 / 重摆 / 上一题 / 下一题', () => {
    renderPage();
    const labels = Array.from(
      document.querySelectorAll('[data-testid="puzzle-actions"] button'),
    ).map((b) => b.textContent);
    expect(labels).toEqual(['提示', '退一手', '重摆', '上一题', '下一题']);
  });

  it('退一手 / 重摆 / 提示 各自接对了', () => {
    renderPage();
    fireEvent.click(action('退一手'));
    expect(mockUndo).toHaveBeenCalled();
    fireEvent.click(action('重摆'));
    expect(mockReset).toHaveBeenCalled();
    fireEvent.click(action('提示'));
    expect(mockToggleHint).toHaveBeenCalled();
  });

  it('提示开着时键上写「收提示」,而且是按下的状态', () => {
    hookReturn = { ...defaultHookReturn, showHint: true };
    renderPage();
    expect(action('收提示')).toHaveAttribute('aria-pressed', 'true');
  });

  /* 「试下」原来是两个轮流出现的按钮(试下 / 退出试下)—— 那本来就是**一个开关的两半**。 */
  it('「试下」是开关不是动作键:开一次进、再按一次出', () => {
    renderPage();
    const toggle = screen.getByTestId('try-mode-toggle');
    expect(toggle).toHaveAttribute('role', 'switch');
    expect(toggle).toHaveAttribute('aria-checked', 'false');
    fireEvent.click(toggle);
    expect(mockEnterTryMode).toHaveBeenCalled();

    hookReturn = { ...defaultHookReturn, isTryMode: true };
    renderPage();
    const on = screen.getAllByTestId('try-mode-toggle').pop()!;
    expect(on).toHaveAttribute('aria-checked', 'true');
    fireEvent.click(on);
    expect(mockExitTryMode).toHaveBeenCalled();
  });

  it('实体棋盘开关:条件不够时按不动,而且右边写出为什么', () => {
    renderPage();
    expect(screen.getByTestId('physical-mode-toggle')).toBeDisabled();
    // 9 路题 ⇒ 这条分支根本不该开。
    expect(screen.getByTestId('puzzle-toggle-hint')).toHaveTextContent('19 路');
  });

  it('做对了显示成功提示', () => {
    hookReturn = { ...defaultHookReturn, isSolved: true };
    renderPage();
    expect(screen.getByText('正确！')).toBeInTheDocument();
  });

  // ---- 你的走法 ----
  describe('你的走法', () => {
    it('一手没落时写「还没落子」,不是一片空白', () => {
      renderPage();
      expect(screen.getByTestId('puzzle-moves')).toHaveTextContent('还没落子');
    });

    it('落了子就逐手列出来,判定只写在最后一手上', () => {
      hookReturn = {
        ...defaultHookReturn,
        moveHistory: [
          { player: 'B' as const, coords: [2, 3] as [number, number] },
          { player: 'W' as const, coords: [8, 15] as [number, number] },
        ],
        isFailed: true,
      };
      renderPage();
      const rows = screen.getByTestId('puzzle-moves');
      // x=2 → 'C'(GO_COLS 跳过 I),y=3 → 4;x=8 → 'J',y=15 → 16。
      expect(rows).toHaveTextContent('黑 C4');
      expect(rows).toHaveTextContent('白 J16');
      expect(rows).toHaveTextContent('走错了');
      // 前面那几手既没对也没错 —— 只有一个判定。
      expect(rows.textContent!.match(/走错了/g)).toHaveLength(1);
    });

    it('做对了写「对了」,试下模式下写「试下」而不是「走错了」', () => {
      const moveHistory = [{ player: 'B' as const, coords: [2, 3] as [number, number] }];
      hookReturn = { ...defaultHookReturn, moveHistory, isSolved: true };
      renderPage();
      expect(screen.getByTestId('puzzle-moves')).toHaveTextContent('对了');

      hookReturn = { ...defaultHookReturn, moveHistory, isTryMode: true, isFailed: true };
      renderPage();
      expect(screen.getAllByTestId('puzzle-moves').pop()).toHaveTextContent('试下');
    });
  });

  // ---- 第 N 单元 · 点阵 ----
  describe('单元点阵', () => {
    it('一个点一道题,做对的绿、当前这道是强调色', () => {
      mockProgress['p0'] = { completed: true, attempts: 1 };
      renderPage('p1');
      const dots = Array.from(screen.getByTestId('puzzle-dots').children).map((n) => n.className);
      expect(dots).toEqual(['ok', 'now', '']);
      expect(screen.getByTestId('puzzle-unit')).toHaveTextContent('第 1 单元 · 3 题');
    });

    it('顺序表读不到时不画一排空格子冒充「都没做」,写出原因,上/下一题跟着灰', () => {
      sessionStorage.clear();
      // 深链 + 取不到 ⇒ 页面自己那次 fetch 也失败。
      global.fetch = vi.fn().mockRejectedValue(new Error('offline')) as any;
      renderPage('p1');
      expect(screen.queryByTestId('puzzle-dots')).toBeNull();
      expect(screen.getByTestId('puzzle-no-sequence')).toBeInTheDocument();
      expect(action('上一题')).toBeDisabled();
      expect(action('下一题')).toBeDisabled();
    });
  });

  // ---- 上/下一题 ----
  describe('上/下一题', () => {
    it('第一题时「上一题」是灰的,第二题时不是', () => {
      renderPage('p0');
      expect(action('上一题')).toBeDisabled();
      renderPage('p1');
      expect(screen.getAllByRole('button', { name: '上一题' }).pop()).not.toBeDisabled();
    });

    it('走之前先落盘,再导航 —— 顺序反了这一题的记录就丢了', () => {
      renderPage('p1');
      fireEvent.click(action('上一题'));
      expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/problem/p0');
      expect(mockFlush.mock.invocationCallOrder[0]).toBeLessThan(
        mockNavigate.mock.invocationCallOrder[0],
      );
    });

    it('下一题同理', () => {
      renderPage('p1');
      fireEvent.click(action('下一题'));
      expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/problem/p2');
      expect(mockFlush.mock.invocationCallOrder[0]).toBeLessThan(
        mockNavigate.mock.invocationCallOrder[0],
      );
    });

    /* ⚠️ 回的是**屏 13 题目列表**(这道题所在的那一单元),不是屏 12 类目页 ——
     * 稿子上写的是「← 吃子」,那是 2026-08-21 补出屏 13 之前的画法;
     * 从一道题退出来,该落在它旁边那 20 道题上。 */
    it('最后一题时「下一题」变成「返回单元」,回的是这一单元的题目列表', () => {
      renderPage('p2');
      const back = action('返回单元');
      fireEvent.click(back);
      expect(mockFlush).toHaveBeenCalled();
      expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/15k/手筋/1');
    });

    it('页控条的返回键同一个去处,而且也先落盘', () => {
      renderPage('p1');
      fireEvent.click(screen.getByText('第 1 单元'));
      expect(mockFlush).toHaveBeenCalled();
      expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/15k/手筋/1');
    });
  });

  // ---- 上次用时 ----
  describe('上次用时', () => {
    it('没有记录就不写', () => {
      renderPage('p1');
      expect(screen.getByTestId('puzzle-counters').textContent).not.toMatch(/上次/);
    });

    it('有记录就写在计数条里', () => {
      mockProgress['p1'] = { completed: true, attempts: 2, lastDuration: 65 };
      renderPage('p1');
      expect(screen.getByTestId('puzzle-counters')).toHaveTextContent('上次 1:05');
    });
  });

  // ---- 三态 ----
  describe('读题的三态', () => {
    it('加载中说的是加载中', () => {
      hookReturn = { ...defaultHookReturn, loading: true };
      renderPage();
      expect(screen.getByTestId('puzzle-loading')).toBeInTheDocument();
      expect(screen.queryByTestId('tsumego-board')).toBeNull();
    });

    it('读不到时写出原因', () => {
      hookReturn = { ...defaultHookReturn, error: 'Problem not found' };
      renderPage();
      expect(screen.getByTestId('puzzle-error')).toHaveTextContent('Problem not found');
    });
  });

  // ---- SuccessOverlay + 自动下一题 ----
  describe('success overlay & auto-advance', () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });
    afterEach(() => {
      vi.runOnlyPendingTimers();
      vi.useRealTimers();
    });

    it('做对约 1.5 秒后自动翻到下一题(默认开)', () => {
      hookReturn = { ...defaultHookReturn, isSolved: true };
      renderPage('p1');
      expect(mockNavigate).not.toHaveBeenCalled();
      act(() => {
        vi.advanceTimersByTime(1500);
      });
      expect(mockFlush).toHaveBeenCalled();
      expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/problem/p2');
    });

    it('设置里关了就不自动翻', () => {
      localStorage.setItem(AUTO_ADVANCE_KEY, 'false');
      hookReturn = { ...defaultHookReturn, isSolved: true };
      renderPage('p1');
      act(() => {
        vi.advanceTimersByTime(3000);
      });
      expect(mockNavigate).not.toHaveBeenCalled();
    });

    it('最后一题没有下一题,不翻', () => {
      localStorage.setItem(AUTO_ADVANCE_KEY, 'true');
      hookReturn = { ...defaultHookReturn, isSolved: true };
      renderPage('p2');
      act(() => {
        vi.advanceTimersByTime(3000);
      });
      expect(mockNavigate).not.toHaveBeenCalled();
    });

    it('没做对不翻', () => {
      localStorage.setItem(AUTO_ADVANCE_KEY, 'true');
      hookReturn = { ...defaultHookReturn, isSolved: false };
      renderPage('p1');
      act(() => {
        vi.advanceTimersByTime(3000);
      });
      expect(mockNavigate).not.toHaveBeenCalled();
    });
  });

  // ---- 实体棋盘 ----
  describe('实体棋盘那条分支', () => {
    it('开关打开 + 视觉就绪 + 19 路,才真的进这条分支', () => {
      enablePhysical();
      physicalReturn = { ...defaultPhysicalReturn, phase: 'setup', stageMatched: 2, stageTotal: 5 };
      renderPage('p1');
      const panel = screen.getByTestId('physical-state-panel');
      expect(panel).toHaveAttribute('data-phase', 'setup');
      // 摆盘阶段这一块**换掉**着法表,不是加一块 —— 加一块会把动作区顶出右栏。
      expect(screen.queryByTestId('puzzle-moves')).toBeNull();
      expect(screen.getByTestId('puzzle-physical-guide')).toBeInTheDocument();
    });

    it('只开开关、视觉没就绪时进不去 —— 状态板不挂,着法表还在', () => {
      mockReadPhysicalMode.mockReturnValue(true);
      physicalReturn = { ...defaultPhysicalReturn, phase: 'setup' };
      renderPage('p1');
      expect(screen.queryByTestId('physical-state-panel')).toBeNull();
      expect(screen.getByTestId('puzzle-moves')).toBeInTheDocument();
    });

    it('摆完盘那一刻要说「轮到你了」和落哪一色 —— 人这时是低头看盘的', () => {
      enablePhysical();
      physicalReturn = { ...defaultPhysicalReturn, phase: 'ready' };
      renderPage('p1');
      const cue = screen.getByTestId('puzzle-physical-ready');
      expect(cue).toHaveTextContent('轮到你了');
      // defaultHookReturn 的 nextPlayer 是 'W'。
      expect(cue).toHaveTextContent('白棋');
      // ready 阶段人还是在盘上落子 ⇒ 着法表回来。
      expect(screen.getByTestId('puzzle-moves')).toBeInTheDocument();
    });

    it('实体模式下「退一手」按不动,而且说得出为什么', () => {
      enablePhysical();
      physicalReturn = { ...defaultPhysicalReturn, phase: 'ready' };
      renderPage('p1');
      const undoBtn = action('退一手');
      expect(undoBtn).toBeDisabled();
      expect(undoBtn).toHaveAttribute('title', expect.stringContaining('拿掉'));
    });

    it('LED 没连上要说出来 —— 不然人只会觉得灯坏了', () => {
      enablePhysical();
      physicalReturn = { ...defaultPhysicalReturn, phase: 'replying', ledOk: false };
      renderPage('p1');
      expect(screen.getByTestId('puzzle-led-down')).toBeInTheDocument();
    });
  });
});
