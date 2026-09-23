import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import EngineWarmupBanner from './EngineWarmupBanner';

const { useEngineReadinessMock } = vi.hoisted(() => ({ useEngineReadinessMock: vi.fn() }));
vi.mock('../../context/EngineReadinessContext', () => ({
  useEngineReadiness: useEngineReadinessMock,
}));
vi.mock('../../../hooks/useTranslation', () => ({
  useTranslation: () => ({ t: (_key: string, fallback?: string) => fallback ?? '' }),
}));

describe('EngineWarmupBanner', () => {
  beforeEach(() => useEngineReadinessMock.mockReset());

  it('renders the warming and unavailable status copy, but nothing when ready', () => {
    useEngineReadinessMock.mockReturnValue('warming');
    const view = render(<EngineWarmupBanner />);
    expect(screen.getByRole('status')).toHaveTextContent('AI 引擎准备中，可先使用棋谱、课程等功能');
    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite');

    useEngineReadinessMock.mockReturnValue('unavailable');
    view.rerender(<EngineWarmupBanner />);
    expect(screen.getByRole('status')).toHaveTextContent('AI 引擎暂未就绪，可稍后重试');

    useEngineReadinessMock.mockReturnValue('ready');
    view.rerender(<EngineWarmupBanner />);
    expect(screen.queryByRole('status')).toBeNull();
  });
});
