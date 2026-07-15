import { ThemeProvider } from '@mui/material/styles';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { ReportTaskSummary } from '../../../api/reportApi';
import type { UserGameDetail } from '../../../api/userGamesApi';
import type { MoveAnalysis } from '../../../types/live';
import { kioskTheme } from '../../theme';
import ReportMetaPanel from './ReportMetaPanel';

vi.mock('../../../hooks/useTranslation', () => ({
  useTranslation: () => ({
    lang: 'zh-CN',
    t: (key: string, fallback?: string) => ({
      'result:black_win': '黑胜',
      'result:white_win': '白胜',
      'result:resign': '中盘',
    }[key] ?? fallback ?? key),
  }),
}));

const game = (overrides: Partial<UserGameDetail> = {}): UserGameDetail => ({
  id: 'game-1',
  user_id: 8,
  title: '银河挑战赛决赛',
  player_black: '王小明',
  player_white: '李青',
  black_rank: '2D',
  white_rank: '9P',
  result: 'B+R',
  board_size: 19,
  rules: 'chinese',
  komi: 7.5,
  move_count: 218,
  source: 'kifu_library',
  category: 'game',
  game_type: null,
  event: null,
  round_name: '第3轮',
  game_date: '2026-07-12',
  created_at: '2026-07-13T08:30:00Z',
  updated_at: null,
  sgf_content: '(;GM[1]SZ[19])',
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

const analysis = (overrides: Partial<MoveAnalysis> = {}): MoveAnalysis => ({
  id: 87,
  game_id: 'game-1',
  move_number: 87,
  status: 'completed',
  winrate: 0.642,
  score_lead: 4.1,
  visits: 500,
  top_moves: [],
  ownership: null,
  move: 'Q10',
  actual_player: 'B',
  delta_score: 0.2,
  delta_winrate: 0.01,
  is_brilliant: false,
  is_mistake: false,
  is_questionable: false,
  ...overrides,
});

function renderPanel(overrides: {
  game?: UserGameDetail | null;
  task?: ReportTaskSummary | null;
  currentMove?: number;
  currentAnalysis?: MoveAnalysis | null;
} = {}) {
  render(
    <ThemeProvider theme={kioskTheme}>
      <ReportMetaPanel
        game={overrides.game === undefined ? game() : overrides.game}
        task={overrides.task === undefined ? task() : overrides.task}
        currentMove={overrides.currentMove ?? 87}
        currentAnalysis={overrides.currentAnalysis === undefined ? analysis() : overrides.currentAnalysis}
      />
    </ThemeProvider>,
  );
}

describe('ReportMetaPanel status and type', () => {
  it.each([
    ['pending', '排队中'],
    ['running', '生成中'],
    ['completed', '已完成'],
    ['failed', '失败'],
  ] as const)('renders the %s report status in Chinese', (status, label) => {
    renderPanel({ task: task({ status }) });
    expect(screen.getByTestId('report-meta-status')).toHaveTextContent(label);
  });

  it.each([
    ['normal', '普通复盘'],
    ['deep', '深度复盘'],
  ] as const)('renders the %s report type in Chinese', (reportType, label) => {
    renderPanel({ task: task({ report_type: reportType }) });
    expect(screen.getByTestId('report-meta-type')).toHaveTextContent(label);
  });
});

describe('ReportMetaPanel game and analysis metadata', () => {
  it('shows title, players, ranks, result, source, rules, komi, analysis and report progress', () => {
    renderPanel();

    expect(screen.getByTestId('report-meta-title')).toHaveTextContent('银河挑战赛决赛 · 第3轮');
    expect(screen.getByText('王小明')).toBeInTheDocument();
    expect(screen.getByText('2D')).toBeInTheDocument();
    expect(screen.getByText('李青')).toBeInTheDocument();
    expect(screen.getByText('9P')).toBeInTheDocument();
    expect(screen.getByText('黑胜中盘')).toBeInTheDocument();
    expect(screen.getByText('棋谱库')).toBeInTheDocument();
    expect(screen.getByText('中国规则')).toBeInTheDocument();
    expect(screen.getByText('贴目 7.5')).toBeInTheDocument();
    expect(screen.getByText('黑 64.2%')).toBeInTheDocument();
    expect(screen.getByText('白 35.8%')).toBeInTheDocument();
    expect(screen.getByText('黑领先 4.1 目')).toBeInTheDocument();
    expect(screen.getByText('已分析 218 / 218 手')).toBeInTheDocument();
  });

  it.each([
    ['import', '本地导入'],
    ['play_ai', 'AI 对弈'],
    ['play_human', '人人对弈'],
    ['kifu_library', '棋谱库'],
    ['mystery', '其他来源'],
  ])('translates source %s with a Chinese fallback', (source, label) => {
    renderPanel({ game: game({ source }) });
    expect(screen.getByTestId('report-meta-source')).toHaveTextContent(label);
  });

  it.each([
    ['chinese', '中国规则'],
    ['japanese', '日本规则'],
    ['korean', '韩国规则'],
    ['aga', 'AGA 规则'],
  ])('translates rules %s with a Chinese fallback', (rules, label) => {
    renderPanel({ game: game({ rules }) });
    expect(screen.getByTestId('report-meta-rules')).toHaveTextContent(label);
  });

  it('shows a white score lead without losing the signed value', () => {
    renderPanel({ currentAnalysis: analysis({ winrate: 0.37, score_lead: -2.5 }) });
    expect(screen.getByText('黑 37.0%')).toBeInTheDocument();
    expect(screen.getByText('白 63.0%')).toBeInTheDocument();
    expect(screen.getByText('白领先 2.5 目')).toBeInTheDocument();
  });

  it('shows the current move and a clear placeholder when analysis is missing', () => {
    renderPanel({ currentMove: 42, currentAnalysis: null, task: task({ status: 'running', analyzed_moves: 41 }) });

    expect(screen.getByText('第 42 手')).toBeInTheDocument();
    expect(screen.getByText('当前手暂无分析')).toBeInTheDocument();
    expect(screen.getByText('已分析 41 / 218 手')).toBeInTheDocument();
    expect(screen.queryByText(/黑 \d+\.\d%/)).not.toBeInTheDocument();
  });

  it('keeps unknown totals explicit instead of showing an invalid ratio', () => {
    renderPanel({ task: task({ analyzed_moves: 0, total_moves: 0 }), game: game({ move_count: 0 }) });
    expect(screen.getByText('已分析 0 / ? 手')).toBeInTheDocument();
  });

  it('normalizes and clamps non-finite or out-of-range numeric API values', () => {
    renderPanel({
      currentMove: Number.NaN,
      currentAnalysis: analysis({ winrate: 4.2, score_lead: Number.POSITIVE_INFINITY }),
      task: task({ analyzed_moves: 999.8, total_moves: 218.9 }),
      game: game({ komi: Number.NaN }),
    });

    expect(screen.getByText('第 0 手')).toBeInTheDocument();
    expect(screen.getByText('黑 100.0%')).toBeInTheDocument();
    expect(screen.getByText('白 0.0%')).toBeInTheDocument();
    expect(screen.queryByText(/领先/)).not.toBeInTheDocument();
    expect(screen.getByText('已分析 218 / 218 手')).toBeInTheDocument();
    expect(screen.getByText('贴目 -')).toBeInTheDocument();
    expect(screen.queryByText(/NaN|Infinity/)).not.toBeInTheDocument();
    expect(screen.getByRole('progressbar', { name: '复盘分析进度' })).toHaveAttribute('aria-valuenow', '100');
  });

  it('normalizes negative and non-finite progress counts without invalid progress output', () => {
    renderPanel({
      task: task({ status: 'completed', analyzed_moves: Number.NEGATIVE_INFINITY, total_moves: 12.9 }),
    });

    expect(screen.getByText('已分析 0 / 12 手')).toBeInTheDocument();
    expect(screen.getByRole('progressbar', { name: '复盘分析进度' })).toHaveAttribute('aria-valuenow', '0');
    expect(screen.queryByText(/NaN|Infinity/)).not.toBeInTheDocument();
  });

  it.each(['pending', 'running'] as const)(
    'uses indeterminate progress for an active %s task with no valid total',
    (status) => {
      renderPanel({
        task: task({ status, analyzed_moves: 7.8, total_moves: Number.NaN }),
        game: game({ move_count: Number.POSITIVE_INFINITY }),
      });

      expect(screen.getByText('已分析 7 / ? 手')).toBeInTheDocument();
      const progress = screen.getByRole('progressbar', { name: '复盘分析进度' });
      expect(progress).not.toHaveAttribute('aria-valuenow');
      expect(progress.className).toContain('MuiLinearProgress-indeterminate');
    },
  );

  it.each(['completed', 'failed'] as const)(
    'does not animate unknown progress for a terminal %s task',
    (status) => {
      renderPanel({
        task: task({ status, analyzed_moves: 7, total_moves: Number.NaN }),
        game: game({ move_count: Number.POSITIVE_INFINITY }),
      });

      expect(screen.getByText('已分析 7 / ? 手')).toBeInTheDocument();
      expect(screen.queryByRole('progressbar', { name: '复盘分析进度' })).not.toBeInTheDocument();
    },
  );

  it('does not invent a normal report or source when null props are still loading', () => {
    renderPanel({ game: null, task: null, currentMove: Number.POSITIVE_INFINITY, currentAnalysis: null });

    expect(screen.queryByTestId('report-meta-status')).not.toBeInTheDocument();
    expect(screen.queryByTestId('report-meta-type')).not.toBeInTheDocument();
    expect(screen.queryByTestId('report-meta-source')).not.toBeInTheDocument();
    expect(screen.queryByText('普通复盘')).not.toBeInTheDocument();
    expect(screen.queryByText('其他来源')).not.toBeInTheDocument();
    expect(screen.queryByText(/Infinity|NaN/)).not.toBeInTheDocument();
  });
});

describe('ReportMetaPanel kiosk layout', () => {
  it('ellipsizes a long title inside a compact min-width-zero panel', () => {
    const longTitle = '一段必须在七英寸屏幕内省略且不能挤压右侧分析控件的超长赛事标题';
    renderPanel({ game: game({ title: longTitle, round_name: null }) });

    const panel = screen.getByTestId('report-meta-panel');
    const title = screen.getByTestId('report-meta-title');
    expect(panel).toHaveStyle({ minWidth: '0' });
    expect(title).toHaveAttribute('title', longTitle);
    expect(title).toHaveStyle({ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' });
  });

  it('keeps compact information rows at least 48px tall for the touch layout rhythm', () => {
    renderPanel();
    expect(screen.getByTestId('report-meta-identity-row')).toHaveStyle({ minHeight: '48px' });
    expect(screen.getByTestId('report-meta-analysis-row')).toHaveStyle({ minHeight: '48px' });
  });
});
