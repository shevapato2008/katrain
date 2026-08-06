import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import AiLadderSettlementPanel from './AiLadderSettlementPanel';

describe('AiLadderSettlementPanel', () => {
  it('keeps the authoritative result and the two next journeys together', () => {
    const onPlayAgain = vi.fn();
    const onReturn = vi.fn();
    render(
      <AiLadderSettlementPanel
        feedback={{ kind: 'promotion', message: '升级：5段' }}
        onPlayAgain={onPlayAgain}
        onReturn={onReturn}
      />,
    );

    expect(screen.getByRole('heading', { name: '本局已结算' })).toBeInTheDocument();
    expect(screen.getByText('升级：5段')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '再来一局' }));
    fireEvent.click(screen.getByRole('button', { name: '返回对局' }));
    expect(onPlayAgain).toHaveBeenCalledOnce();
    expect(onReturn).toHaveBeenCalledOnce();
  });

  it('shows an explicit pending state and exposes only retry while authority is pending', () => {
    const retry = vi.fn();
    render(
      <AiLadderSettlementPanel
        feedback={{ kind: 'pending', message: '升降级结算仍在处理中', retry }}
        onPlayAgain={vi.fn()}
        onReturn={vi.fn()}
      />,
    );

    expect(screen.getByRole('heading', { name: '正在确认结算' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '再来一局' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(retry).toHaveBeenCalledOnce();
  });
});
