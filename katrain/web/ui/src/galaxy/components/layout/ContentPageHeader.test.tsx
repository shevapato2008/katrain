import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import ContentPageHeader from './ContentPageHeader';

const requestNavigation = vi.fn();
vi.mock('../../context/GameNavigationContext', () => ({
  useGameNavigation: () => ({ requestNavigation }),
}));

describe('ContentPageHeader', () => {
  it('places the title left and the parent return action right', async () => {
    render(<ContentPageHeader title="升降级对弈" parentLabel="对局" parentTo="/galaxy/play" />);

    expect(screen.getByRole('heading', { name: '升降级对弈' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '返回对局' }));
    expect(requestNavigation).toHaveBeenCalledWith('/galaxy/play');
  });
});
