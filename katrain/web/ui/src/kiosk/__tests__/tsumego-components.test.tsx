import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';

// ProblemCard reads its own progress entry from the unified source — mock it with a
// configurable map so border-state / last-time branches are deterministic.
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

import ProgressDots from '../components/tsumego/ProgressDots';
import ProblemCard from '../components/tsumego/ProblemCard';
import SuccessOverlay from '../components/tsumego/SuccessOverlay';

const FILLED = 'rgb(88, 181, 122)'; // #58b57a — the "filled dot" color
const GREEN = 'rgb(88, 181, 122)'; // #58b57a — completed border
const AMBER = 'rgb(224, 162, 74)'; // #e0a24a — attempted border

const renderDots = (completed: number, total: number) =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <ProgressDots completed={completed} total={total} />
    </ThemeProvider>
  );

// Count dots whose computed background is the "filled" jade-glow color.
// MUI applies `bgcolor` via an emotion class, so read the resolved computed style.
const countFilled = (container: HTMLElement): number => {
  const flex = container.firstElementChild as HTMLElement;
  let filled = 0;
  Array.from(flex.children).forEach((d) => {
    if (getComputedStyle(d as HTMLElement).backgroundColor === FILLED) filled += 1;
  });
  return filled;
};

describe('ProgressDots thresholds', () => {
  beforeEach(() => {
    for (const k of Object.keys(mockProgress)) delete mockProgress[k];
  });

  it('renders exactly 5 dots', () => {
    const { container } = renderDots(0, 10);
    // 5 dot boxes inside the flex container.
    const flex = container.firstElementChild as HTMLElement;
    expect(flex.children.length).toBe(5);
  });

  it('0% → 0 filled dots', () => {
    const { container } = renderDots(0, 10);
    expect(countFilled(container)).toBe(0);
  });

  it('≤20% → 1 filled dot', () => {
    const { container } = renderDots(2, 10); // 20%
    expect(countFilled(container)).toBe(1);
  });

  it('≤40% → 2 filled dots', () => {
    const { container } = renderDots(4, 10); // 40%
    expect(countFilled(container)).toBe(2);
  });

  it('≤60% → 3 filled dots', () => {
    const { container } = renderDots(6, 10); // 60%
    expect(countFilled(container)).toBe(3);
  });

  it('≤80% → 4 filled dots', () => {
    const { container } = renderDots(8, 10); // 80%
    expect(countFilled(container)).toBe(4);
  });

  it('>80% → 5 filled dots', () => {
    const { container } = renderDots(9, 10); // 90%
    expect(countFilled(container)).toBe(5);
  });

  it('100% → 5 filled dots', () => {
    const { container } = renderDots(10, 10);
    expect(countFilled(container)).toBe(5);
  });

  it('just over a boundary (21%) bumps to the next band (2 dots)', () => {
    const { container } = renderDots(21, 100); // 21% > 20%
    expect(countFilled(container)).toBe(2);
  });

  it('handles total=0 without filling any dots', () => {
    const { container } = renderDots(0, 0);
    expect(countFilled(container)).toBe(0);
  });
});

const renderCard = (problemId: string, index = 0) =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <ProblemCard
        problemId={problemId}
        index={index}
        initialBlack={['pd']}
        initialWhite={['dp']}
        onClick={() => {}}
      />
    </ThemeProvider>
  );

describe('ProblemCard border-state & last-time', () => {
  beforeEach(() => {
    for (const k of Object.keys(mockProgress)) delete mockProgress[k];
  });

  it('untouched problem → gray border (neither green nor amber)', () => {
    const { container } = renderCard('x1');
    const card = container.querySelector('.MuiCard-root') as HTMLElement;
    expect(card).not.toHaveStyle(`border-color: ${GREEN}`);
    expect(card).not.toHaveStyle(`border-color: ${AMBER}`);
  });

  it('completed problem → green border', () => {
    mockProgress['x1'] = { completed: true, attempts: 3 };
    const { container } = renderCard('x1');
    const card = container.querySelector('.MuiCard-root') as HTMLElement;
    expect(card).toHaveStyle(`border-color: ${GREEN}`);
  });

  it('attempted-not-completed problem → amber border', () => {
    mockProgress['x1'] = { completed: false, attempts: 2 };
    const { container } = renderCard('x1');
    const card = container.querySelector('.MuiCard-root') as HTMLElement;
    expect(card).toHaveStyle(`border-color: ${AMBER}`);
  });

  it('shows the problem number (index + 1)', () => {
    renderCard('x1', 4);
    expect(screen.getAllByText((_, el) => el?.textContent === '第 5 题').length).toBeGreaterThan(0);
  });

  it('shows "上次用时" with formatted duration when completed with lastDuration', () => {
    mockProgress['x1'] = { completed: true, attempts: 1, lastDuration: 95 }; // 1m35s
    renderCard('x1');
    expect(screen.getByText((_, el) => el?.textContent === '上次用时 1m35s')).toBeInTheDocument();
  });

  it('formats sub-minute durations as seconds', () => {
    mockProgress['x1'] = { completed: true, attempts: 1, lastDuration: 42 };
    renderCard('x1');
    expect(screen.getByText((_, el) => el?.textContent === '上次用时 42s')).toBeInTheDocument();
  });

  it('shows the attempt count badge (xN) when attempts > 0', () => {
    mockProgress['x1'] = { completed: false, attempts: 4 };
    renderCard('x1');
    expect(screen.getByText('x4')).toBeInTheDocument();
  });

  it('does NOT show last-time for an untouched problem', () => {
    renderCard('x1');
    expect(screen.queryByText(/上次用时/)).not.toBeInTheDocument();
  });
});

// Built from a code point (not a literal glyph) so this source file itself stays free of the
// tofu-rendering character — the whole point of the T9 fix (Gate E scans src/kiosk for these).
const PARTY_POPPER_EMOJI = String.fromCodePoint(0x1f389); // U+1F389 — legacy "party popper" glyph

describe('SuccessOverlay tofu fix (T9)', () => {
  it('renders the EmojiEvents trophy SVG instead of the legacy party-popper emoji', () => {
    const { container } = render(
      <ThemeProvider theme={kioskTheme}>
        <SuccessOverlay show message="恭喜答对！" />
      </ThemeProvider>
    );
    expect(container.querySelector('[data-testid="EmojiEventsIcon"]')).toBeInTheDocument();
    expect(container.textContent).not.toContain(PARTY_POPPER_EMOJI);
  });
});
