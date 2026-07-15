import { ThemeProvider } from '@mui/material/styles';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import type { ReportTaskSummary } from '../../../api/reportApi';
import type { UserGameSummary } from '../../../api/userGamesApi';
import type { ReportGameStatus } from '../../../features/report/reportModel';
import { kioskTheme } from '../../theme';
import ReportGameCard from './ReportGameCard';

vi.mock('../../../hooks/useTranslation', () => ({
  useTranslation: () => ({
    lang: 'zh-CN',
    t: (key: string, fallback?: string) => (
      key === 'report:select_game' ? '选择棋局' : (fallback ?? key)
    ),
  }),
}));

const game = (overrides: Partial<UserGameSummary> = {}): UserGameSummary => ({
  id: 'game-1',
  user_id: 8,
  title: '星河挑战赛决赛',
  player_black: '王小明',
  player_white: '李青',
  black_rank: '2D',
  white_rank: '9P',
  result: 'B+R',
  board_size: 19,
  rules: 'chinese',
  komi: 7.5,
  move_count: 218,
  source: 'import',
  category: 'game',
  game_type: null,
  event: '智星杯第三轮',
  round_name: '第3轮',
  game_date: '2026-07-12',
  created_at: '2026-07-13T08:30:00Z',
  updated_at: null,
  ...overrides,
});

const task = (overrides: Partial<ReportTaskSummary> = {}): ReportTaskSummary => ({
  id: 11,
  user_game_id: 'game-1',
  status: 'completed',
  report_type: 'normal',
  total_moves: 218,
  analyzed_moves: 218,
  requested_visits: 500,
  ...overrides,
});

const callbacks = () => ({
  onSelect: vi.fn(),
  onCreateReport: vi.fn(),
  onOpenReport: vi.fn(),
  onRetry: vi.fn(),
  onDelete: vi.fn(),
});

function renderCard(
  options: {
    game?: UserGameSummary;
    reportState?: ReportGameStatus;
    selected?: boolean;
    handlers?: ReturnType<typeof callbacks>;
  } = {},
) {
  const handlers = options.handlers ?? callbacks();
  render(
    <ThemeProvider theme={kioskTheme}>
      <ReportGameCard
        game={options.game ?? game()}
        reportState={options.reportState ?? {}}
        selected={options.selected}
        {...handlers}
      />
    </ThemeProvider>,
  );
  return handlers;
}

describe('ReportGameCard metadata and selection', () => {
  it('matches kiosk game-card metadata and result conventions', () => {
    renderCard();

    expect(screen.getByText('智星杯第三轮')).toBeInTheDocument();
    expect(screen.getByText('第3轮')).toBeInTheDocument();
    expect(screen.getByText('2026-07-12')).toBeInTheDocument();
    expect(screen.getByText('218 手')).toBeInTheDocument();
    expect(screen.getByText('王小明')).toBeInTheDocument();
    expect(screen.getByText('2D')).toBeInTheDocument();
    expect(screen.getByText('李青')).toBeInTheDocument();
    expect(screen.getByText('9P')).toBeInTheDocument();
    expect(screen.getByTestId('result-badge')).toHaveTextContent('B+R');
  });

  it.each([
    [{ event: '春兰杯', title: '自定义标题', source: 'import' }, '春兰杯'],
    [{ event: null, title: '自定义标题', source: 'import' }, '自定义标题'],
    [{ event: null, title: null, source: 'play_ai', game_type: 'ranked' }, 'AI 排位对局'],
    [{ event: null, title: null, source: 'play_ai', game_type: 'free' }, 'AI 自由对局'],
    [{ event: null, title: null, source: 'play_human' }, '人人对局'],
    [{ event: null, title: null, source: 'import' }, '本地导入棋谱'],
    [{ event: null, title: null, source: 'kifu_library' }, '棋谱库导入'],
    [{ event: null, title: null, source: 'unknown' }, '未命名棋局'],
  ])('uses event, title, then translated source as the heading', (overrides, heading) => {
    renderCard({ game: game(overrides) });
    expect(screen.getByTestId('report-card-title')).toHaveTextContent(heading);
  });

  it('falls back to the creation date and translated player/result labels', () => {
    renderCard({
      game: game({
        game_date: null,
        event: null,
        title: null,
        created_at: '2026-06-05T10:00:00Z',
        player_black: null,
        player_white: null,
        black_rank: null,
        white_rank: null,
        result: null,
      }),
    });

    expect(screen.getByText('2026-06-05')).toBeInTheDocument();
    expect(screen.getByText('黑方')).toBeInTheDocument();
    expect(screen.getByText('白方')).toBeInTheDocument();
    expect(screen.getByText('暂无结果')).toBeInTheDocument();
  });

  it('marks the selected card and truncates long headings and player names', () => {
    const longText = '一段必须在七英寸屏幕内被省略而不能挤压操作区域的特别长文本';
    renderCard({
      selected: true,
      game: game({ event: longText, player_black: longText, player_white: longText }),
    });

    const selectedCard = screen.getByTestId('report-game-card');
    expect(selectedCard).toHaveAttribute('data-selected', 'true');
    expect(getComputedStyle(selectedCard).backgroundImage).toContain('linear-gradient');
    for (const element of [
      screen.getByTestId('report-card-title'),
      screen.getByTestId('report-card-black'),
      screen.getByTestId('report-card-white'),
    ]) {
      expect(element).toHaveStyle({ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' });
    }
  });

  it('keeps the heading in its accessible name when the static prefix has a loaded translation', async () => {
    const user = userEvent.setup();
    const handlers = renderCard();
    const selector = screen.getByRole('button', { name: '选择棋局：智星杯第三轮' });

    await user.click(selector);
    selector.focus();
    await user.keyboard('{Enter}');
    await user.keyboard(' ');

    expect(handlers.onSelect).toHaveBeenCalledTimes(3);
  });
});

describe('ReportGameCard report actions and status precedence', () => {
  it('offers translated normal/deep generation and deletion from a touch menu', async () => {
    const user = userEvent.setup();
    const handlers = renderCard();

    await user.click(screen.getByRole('button', { name: '更多复盘操作' }));
    const menu = screen.getByRole('menu', { name: '复盘操作' });
    expect(within(menu).getByRole('menuitem', { name: '生成普通复盘' })).toBeInTheDocument();
    expect(within(menu).getByRole('menuitem', { name: '生成深度复盘' })).toBeInTheDocument();
    expect(within(menu).getByRole('menuitem', { name: '删除棋谱' })).toBeInTheDocument();

    await user.click(within(menu).getByRole('menuitem', { name: '生成普通复盘' }));
    expect(handlers.onCreateReport).toHaveBeenCalledWith('normal');

    await user.click(screen.getByRole('button', { name: '更多复盘操作' }));
    await user.click(screen.getByRole('menuitem', { name: '生成深度复盘' }));
    expect(handlers.onCreateReport).toHaveBeenCalledWith('deep');

    await user.click(screen.getByRole('button', { name: '更多复盘操作' }));
    await user.click(screen.getByRole('menuitem', { name: '删除棋谱' }));
    expect(handlers.onDelete).toHaveBeenCalledOnce();
    expect(handlers.onSelect).not.toHaveBeenCalled();
  });

  it.each([
    {
      name: 'completed normal and active deep',
      state: {
        completedNormal: task({ id: 21 }),
        activeDeep: task({ id: 22, report_type: 'deep', status: 'running', analyzed_moves: 63 }),
      },
      visible: ['打开普通复盘', '深度复盘 · 生成中', '63 / 218 手'],
      hidden: ['打开深度复盘', '重试普通复盘'],
    },
    {
      name: 'active normal and completed deep',
      state: {
        activeNormal: task({ id: 31, status: 'pending', analyzed_moves: 0 }),
        completedDeep: task({ id: 32, report_type: 'deep' }),
      },
      visible: ['普通复盘 · 排队中', '0 / 218 手', '打开深度复盘'],
      hidden: ['打开普通复盘', '重试深度复盘'],
    },
    {
      name: 'failed normal and completed deep',
      state: {
        failedNormal: task({ id: 41, status: 'failed' }),
        completedDeep: task({ id: 42, report_type: 'deep' }),
      },
      visible: ['普通复盘 · 失败', '重试普通复盘', '打开深度复盘'],
      hidden: ['打开普通复盘', '重试深度复盘'],
    },
    {
      name: 'active normal supersedes old normal states without hiding deep',
      state: {
        activeNormal: task({ id: 51, status: 'running', analyzed_moves: 99 }),
        completedNormal: task({ id: 49 }),
        failedNormal: task({ id: 48, status: 'failed' }),
        completedDeep: task({ id: 52, report_type: 'deep' }),
      },
      visible: ['普通复盘 · 生成中', '99 / 218 手', '打开深度复盘'],
      hidden: ['打开普通复盘', '重试普通复盘'],
    },
    {
      name: 'active deep supersedes old deep states without hiding normal',
      state: {
        completedNormal: task({ id: 61 }),
        activeDeep: task({ id: 62, report_type: 'deep', status: 'pending', analyzed_moves: 7 }),
        completedDeep: task({ id: 60, report_type: 'deep' }),
        failedDeep: task({ id: 59, report_type: 'deep', status: 'failed' }),
      },
      visible: ['打开普通复盘', '深度复盘 · 排队中', '7 / 218 手'],
      hidden: ['打开深度复盘', '重试深度复盘'],
    },
  ])('renders $name', ({ state, visible, hidden }) => {
    renderCard({ reportState: state });
    visible.forEach((label) => expect(screen.getByText(label)).toBeInTheDocument());
    hidden.forEach((label) => expect(screen.queryByText(label)).not.toBeInTheDocument());
  });

  it('opens completed reports and retries failures without selecting the card', async () => {
    const user = userEvent.setup();
    const handlers = renderCard({
      reportState: {
        completedNormal: task({ id: 71 }),
        failedDeep: task({ id: 72, report_type: 'deep', status: 'failed' }),
      },
    });

    await user.click(screen.getByRole('button', { name: '打开普通复盘' }));
    await user.click(screen.getByRole('button', { name: '重试深度复盘' }));

    expect(handlers.onOpenReport).toHaveBeenCalledWith(71);
    expect(handlers.onRetry).toHaveBeenCalledWith(72);
    expect(handlers.onSelect).not.toHaveBeenCalled();
  });

  it('keeps both simultaneously active report types and clamps their progress', () => {
    renderCard({
      reportState: {
        activeNormal: task({ status: 'running', analyzed_moves: 300 }),
        activeDeep: task({ report_type: 'deep', status: 'running', total_moves: 0, analyzed_moves: 3 }),
      },
    });

    expect(screen.getByText('普通复盘 · 生成中')).toBeInTheDocument();
    expect(screen.getByText('深度复盘 · 生成中')).toBeInTheDocument();
    expect(screen.getByText('300 / 218 手')).toBeInTheDocument();
    expect(screen.getByText('3 / 218 手')).toBeInTheDocument();
    expect(screen.getByTestId('normal-report-progress')).toHaveAttribute('aria-valuenow', '100');
    expect(screen.getByTestId('deep-report-progress')).toHaveAttribute('aria-valuenow', '1');
  });

  it('gives every action and menu item a minimum 48px touch target', async () => {
    const user = userEvent.setup();
    renderCard({
      reportState: {
        completedNormal: task(),
        failedDeep: task({ report_type: 'deep', status: 'failed' }),
      },
    });

    const buttons = [
      screen.getByRole('button', { name: '选择棋局：智星杯第三轮' }),
      screen.getByRole('button', { name: '打开普通复盘' }),
      screen.getByRole('button', { name: '重试深度复盘' }),
      screen.getByRole('button', { name: '更多复盘操作' }),
    ];
    buttons.forEach((button) => expect(button).toHaveStyle({ minHeight: '48px', minWidth: '48px' }));

    await user.click(screen.getByRole('button', { name: '更多复盘操作' }));
    for (const menuItem of screen.getAllByRole('menuitem')) {
      expect(menuItem).toHaveStyle({ minHeight: '48px', minWidth: '48px' });
    }
  });
});
