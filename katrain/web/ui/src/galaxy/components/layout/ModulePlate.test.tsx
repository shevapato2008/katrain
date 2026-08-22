import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useGameNavigation } from '../../context/GameNavigationContext';
import ModulePlate from './ModulePlate';

vi.mock('../../context/GameNavigationContext', () => ({ useGameNavigation: vi.fn() }));
vi.mock('../../../hooks/useTranslation', () => ({ useTranslation: () => ({ t: (_key: string, fallback: string) => fallback }) }));

describe('ModulePlate', () => {
  it('renders its pure content and navigates back through the guarded flow', () => {
    const requestNavigation = vi.fn();
    vi.mocked(useGameNavigation).mockReturnValue({ requestNavigation } as never);

    render(<ModulePlate title="Live match" subtitle="Round 3" status={<span>LIVE</span>} backTo="/galaxy/live" />);

    expect(screen.getByText('Live match')).toBeInTheDocument();
    expect(screen.getByText('Round 3')).toBeInTheDocument();
    expect(screen.getByText('LIVE')).toBeInTheDocument();
    const back = screen.getByRole('button', { name: '返回' });
    expect(back).toHaveStyle({ width: '40px', height: '40px' });
    fireEvent.click(back);
    expect(requestNavigation).toHaveBeenCalledWith('/galaxy/live');
  });

  it('renders no back control when showBack is false', () => {
    vi.mocked(useGameNavigation).mockReturnValue({ requestNavigation: vi.fn() } as never);
    render(<ModulePlate title="Research" backTo="/galaxy/research" showBack={false} />);
    expect(screen.queryByRole('button', { name: '返回' })).not.toBeInTheDocument();
  });

  // Fan 2026-08-22 裁定：返回键一律在右栏左上角，上一级简称不上屏、只进无障碍名。
  // 规范 §2.4 已按此改写。这条断言守的就是那个裁定 —— 位置在标题**之前**，
  // 且简称不出现在可见文本里。
  it('keeps the back control at the top-left of the rail and folds the parent name into its accessible name', () => {
    const requestNavigation = vi.fn();
    vi.mocked(useGameNavigation).mockReturnValue({ requestNavigation } as never);

    render(<ModulePlate title="升降级对弈" backLabel="升降级" backTo="/galaxy/play/ai?mode=rated" />);

    const plate = screen.getByTestId('module-plate');
    const heading = screen.getByRole('heading', { name: '升降级对弈' });
    const back = screen.getByRole('button', { name: '返回升降级' });

    // 返回键在标题之前（DOM 顺序即视觉顺序，这一行是 flex-start 的单行）
    expect(back.compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(plate).toHaveStyle({ justifyContent: 'flex-start' });
    // 简称只在无障碍名里，不上屏
    expect(within(plate).queryByText('升降级')).not.toBeInTheDocument();

    fireEvent.click(back);
    expect(requestNavigation).toHaveBeenCalledWith('/galaxy/play/ai?mode=rated');
  });
});
