import { fireEvent, render, screen } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import { describe, expect, it, vi } from 'vitest';
import { zenTheme } from '../../theme';
import AiLadderStatusCard from './AiLadderStatusCard';
import type { AiLadderCatalogEntry, AiLadderReadyStatus, AiLadderStatus } from './types';

const availableOpponent: AiLadderCatalogEntry = {
  rung: 17,
  rank_name: '4级',
  certification_status: 'certified',
  availability: 'available',
  route: 'server',
};

const readyPlacement: AiLadderReadyStatus = {
  view_state: 'ready',
  placement_state: {
    phase: 'placement',
    completed_games: 3,
    total_games: 5,
  },
  current_opponent: availableOpponent,
  recent_ranked_results: ['win', 'loss', 'win', 'win', 'loss'],
  net_score: 0,
  pending_settlement: false,
};

const renderCard = (
  status: AiLadderStatus = readyPlacement,
  handlers: { onPrimaryAction?: () => void; onRetry?: () => void } = {},
) =>
  render(
    <ThemeProvider theme={zenTheme}>
      <AiLadderStatusCard status={status} {...handlers} />
    </ThemeProvider>,
  );

describe('AiLadderStatusCard', () => {
  it('shows placement 3/5, the current opponent, its route, and labelled progress', () => {
    renderCard();

    expect(screen.getByRole('heading', { name: 'AI升降级对弈' })).toBeInTheDocument();
    expect(screen.getByText('定级进度 3/5')).toBeInTheDocument();
    expect(screen.getByText('当前对手：4级')).toBeInTheDocument();
    expect(screen.getByText('服务器对弈')).toBeInTheDocument();
    expect(screen.getByRole('progressbar', { name: '定级进度：已完成3盘，共5盘' })).toHaveAttribute(
      'aria-valuenow',
      '3',
    );
  });

  it('shows a placed rung, certification, local route, and ranked CTA', () => {
    // `current_opponent` mirrors `placement_state.rung` here because the server builds both
    // from one value (`ai_ladder.py _status_payload`: `opponent = catalog_entry(...)` is
    // assigned to both), and never sends null -- POST /start asserts it is a dict. The
    // fixture used to say null, which no server can produce.
    const placedRung: AiLadderCatalogEntry = {
      rung: 32,
      rank_name: '6段',
      certification_status: 'certified',
      availability: 'available',
      route: 'local',
    };
    renderCard(
      {
        ...readyPlacement,
        placement_state: { phase: 'placed', rung: placedRung },
        current_opponent: placedRung,
      },
      { onPrimaryAction: vi.fn() },
    );

    expect(screen.getByText('当前段位：6段')).toBeInTheDocument();
    expect(screen.queryByText('第32档')).not.toBeInTheDocument();
    expect(screen.getByText('已认证')).toBeInTheDocument();
    expect(screen.getByText('本机对弈')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '开始升降级对弈' })).toBeEnabled();
  });

  it.each([-2, -1, 0, 1, 2] as const)(
    'renders cumulative net score %s on a signed, accessible promotion/demotion bar',
    (netScore) => {
    renderCard({ ...readyPlacement, net_score: netScore });

    const displayedScore = netScore > 0 ? `+${netScore}` : `${netScore}`;
      expect(screen.getByText(`累计净胜分：${displayedScore}`)).toBeInTheDocument();

      const meter = screen.getByRole('meter', {
        name: '累计净胜分，负值朝降段方向，正值朝升段方向',
      });
      expect(meter).toHaveAttribute('aria-valuemin', '-3');
      expect(meter).toHaveAttribute('aria-valuemax', '3');
      expect(meter).toHaveAttribute('aria-valuenow', `${netScore}`);
      expect(screen.getByText('降段 -3')).toBeInTheDocument();
      expect(screen.getByText('升段 +3')).toBeInTheDocument();
    },
  );

  it('separates recent-five display from cumulative score and names the actual promotion trigger', () => {
    renderCard();

    expect(screen.getByText('最近5盘')).toBeInTheDocument();
    expect(screen.getByText('累计净胜分：0')).toBeInTheDocument();
    expect(screen.getByText('最近5盘仅供展示，升降段只看累计净胜分')).toBeInTheDocument();
  });

  it('renders five ranked outcomes as distinct text-labelled win and loss markers', () => {
    renderCard();

    expect(screen.getByRole('list', { name: '最近5盘升降级AI对局结果' })).toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(5);
    expect(screen.getByRole('listitem', { name: '第1盘：胜' })).toHaveTextContent('胜');
    expect(screen.getByRole('listitem', { name: '第2盘：负' })).toHaveTextContent('负');
    expect(screen.getByRole('listitem', { name: '第5盘：负' })).toHaveTextContent('负');
  });

  it('announces pending settlement and disables another ranked action', () => {
    renderCard({ ...readyPlacement, pending_settlement: true });

    expect(screen.getByRole('status')).toHaveTextContent('本盘成绩结算中');
    expect(screen.getByRole('button', { name: '成绩结算中' })).toBeDisabled();
  });

  it('shows an accessible loading state without an action', () => {
    renderCard({ view_state: 'loading' });

    expect(screen.getByRole('status')).toHaveTextContent('正在加载升降级对弈状态…');
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('fails closed for an unavailable opponent with text accompanying its state', () => {
    renderCard({
      ...readyPlacement,
      current_opponent: {
        ...availableOpponent,
        certification_status: 'provisional',
        availability: 'unavailable',
        route: 'local',
      },
    });

    expect(screen.getByText('暂定')).toBeInTheDocument();
    expect(screen.getByText('该档位暂不可挑战')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '暂不可挑战' })).toBeDisabled();
  });

  it('fails closed for a provisional opponent even if availability says available', () => {
    renderCard({
      ...readyPlacement,
      current_opponent: {
        ...availableOpponent,
        certification_status: 'provisional',
        availability: 'available',
      },
    });

    expect(screen.getByText('该档位暂不可挑战')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '暂不可挑战' })).toBeDisabled();
  });

  it('lets an uncertified rung be started on a node that allows provisional play', () => {
    // The two tests above are a node WITHOUT the switch, where failing closed is right.
    // With the switch on, the server accepts the start (POST /start seats the rung), so a
    // card that still refuses is disagreeing with the very server it is displaying. The
    // rung's own certification_status is identical in both cases -- only the node differs
    // -- which is why this has to be read from the payload and cannot be inferred.
    const onPrimaryAction = vi.fn();
    renderCard(
      {
        ...readyPlacement,
        current_opponent: {
          ...availableOpponent,
          certification_status: 'provisional',
          availability: 'unavailable',
        },
        provisional_play_allowed: true,
      },
      { onPrimaryAction },
    );

    expect(screen.queryByText('该档位暂不可挑战')).not.toBeInTheDocument();
    expect(screen.getByText('该档位尚未标定，可以试下，但本局不计入升降级')).toBeInTheDocument();

    const cta = screen.getByRole('button', { name: '继续定级' });
    expect(cta).toBeEnabled();
    fireEvent.click(cta);
    expect(onPrimaryAction).toHaveBeenCalledTimes(1);
  });

  it('offers an accessible retry action in the error state', () => {
    const onRetry = vi.fn();
    renderCard({ view_state: 'error' }, { onRetry });

    expect(screen.getByRole('alert')).toHaveTextContent('升降级对弈状态加载失败');
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it('keeps the retry control visible but disabled when no retry callback is provided', () => {
    renderCard({ view_state: 'error' });

    expect(screen.getByRole('button', { name: '重试' })).toBeDisabled();
  });

  it('uses the placement CTA label, calls its handler, and keeps it at least 44px high', () => {
    const onPrimaryAction = vi.fn();
    renderCard(readyPlacement, { onPrimaryAction });

    const action = screen.getByRole('button', { name: '继续定级' });
    expect(getComputedStyle(action).minHeight).toBe('44px');
    fireEvent.click(action);
    expect(onPrimaryAction).toHaveBeenCalledOnce();
  });

  it('keeps the primary control visible but disabled when no action callback is provided', () => {
    renderCard();

    expect(screen.getByRole('button', { name: '继续定级' })).toBeDisabled();
  });

  it('does not expose forbidden provider or engine internals', () => {
    const { container } = renderCard();

    expect(container).not.toHaveTextContent(/星阵|model|模型文件|temperature|温度|visits|访问次数|recipe|配方/i);
  });
});
