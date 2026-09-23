import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { KioskStepTrack } from './KioskStepTrack';

/**
 * `KioskStepTrack` 是共享件（屏 02/09 的让子·棋力轨都靠它）。这里只测 `readout`
 * 开关本身——几何/触屏手感的断言在各屏自己的测试里。
 */
describe('KioskStepTrack', () => {
  it('readout 默认画（不传 = true）—— 屏 02 的既有调用点不受影响', () => {
    render(<KioskStepTrack
      count={39} index={0} onChange={() => {}}
      value="星猛虎 · 9 段" meta="第 1 / 39 档"
      decLabel="弱一档" incLabel="强一档" testId="trk"
    />);
    expect(screen.getByText('第 1 / 39 档')).toBeInTheDocument();
  });

  it('readout={false} 时不画读数行 —— 屏 09 把读数搬进了名牌', () => {
    render(<KioskStepTrack
      count={39} index={0} onChange={() => {}}
      value="星猛虎 · 9 段" meta="第 1 / 39 档"
      readout={false}
      decLabel="弱一档" incLabel="强一档" testId="trk"
    />);
    expect(screen.queryByText('第 1 / 39 档')).toBeNull();
  });

  it('两头禁用不回绕', () => {
    const onChange = vi.fn();
    render(<KioskStepTrack
      count={3} index={0} onChange={onChange}
      value="v" decLabel="弱一档" incLabel="强一档" testId="trk"
    />);
    expect(screen.getByRole('button', { name: '弱一档' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '强一档' })).toBeEnabled();
  });
});
