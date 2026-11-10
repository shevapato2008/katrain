import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import TerritoryDialog from './TerritoryDialog';

describe('territory dialog', () => {
  const props = { source: 'ranked' as const, open: true, phase: 'result' as const,
    quotaNote: '升降级本局剩余 0 次 · 同局面可免费复看', onClose: vi.fn() };

  it.each([
    [4.5, '预计黑领先 4.5 目'], [-2.2, '预计白领先 2.2 目'], [0, '接近均势'],
    [undefined, '暂未取得领先判断'], [null, '暂未取得领先判断'], [NaN, '暂未取得领先判断'], [Infinity, '暂未取得领先判断'],
  ])('uses only a finite black-perspective lead (%s)', (lead, expected) => {
    render(<TerritoryDialog {...props} lead={lead} blackArea={78} whiteArea={66} />);
    const dialog = screen.getByRole('dialog', { name: '领地判断' });
    expect(within(dialog).getByText(expected)).toBeInTheDocument();
    expect(dialog).toHaveTextContent('黑方较确定区域 78 点');
    expect(dialog).toHaveTextContent('白方较确定区域 66 点');
    expect(dialog).not.toHaveTextContent('12.0 目');
    expect(dialog).not.toHaveTextContent('NaN');
    expect(dialog).toHaveTextContent('局中参考，正式胜负以终局数子为准');
  });

  it('shows actual Star winrate and quota without inventing absolute scores', () => {
    render(<TerritoryDialog {...props} source="star" lead={0} winrate={0.375} quotaNote="星阵账号领地道具剩余 9 次" />);
    expect(screen.getByText('黑棋胜率 37.5%')).toBeInTheDocument();
    expect(screen.getByText('星阵账号领地道具剩余 9 次')).toBeInTheDocument();
    expect(screen.queryByText(/较确定区域/)).toBeNull();
  });

  it.each(['loading', 'error', 'result'] as const)('can close %s with the shared callback', (phase) => {
    const onClose = vi.fn();
    render(<TerritoryDialog {...props} phase={phase} onClose={onClose} />);
    fireEvent.click(screen.getByRole('button', { name: '关闭领地，继续下棋' }));
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape', code: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it('routes a backdrop click through the same close callback', () => {
    const onClose = vi.fn();
    const { baseElement } = render(<TerritoryDialog {...props} onClose={onClose} />);
    const backdrop = baseElement.querySelector('.MuiDialog-container')!;
    fireEvent.mouseDown(backdrop);
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
