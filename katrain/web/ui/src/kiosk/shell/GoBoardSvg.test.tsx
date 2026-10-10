import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { GoBoardSvg } from './GoBoardSvg';

describe('GoBoardSvg · 摆谱的两种圈', () => {
  it('remove 画蓝圈、hint 画白圈,各一颗一个', () => {
    const { container } = render(<GoBoardSvg black={['C6']} remove={['C6']} hint={['C7', 'R3']} />);
    expect(container.querySelectorAll('circle.remove')).toHaveLength(1);
    expect(container.querySelectorAll('circle.hint')).toHaveLength(2);
  });
  it('不传就一个都不画(既有消费者不受影响)', () => {
    const { container } = render(<GoBoardSvg black={['C6']} />);
    expect(container.querySelectorAll('circle.remove, circle.hint')).toHaveLength(0);
  });
});

describe('GoBoardSvg last stone', () => {
  it.each([['b', ['D4'], [], '#ffffff'], ['w', [], ['D4'], '#000000']] as const)('marks a %s stone with a contrast hollow ring', (_color, black, white, stroke) => {
    const { container } = render(<GoBoardSvg black={black} white={white} last="D4" />);
    const ring = container.querySelector('circle.mark');
    expect(ring).toHaveStyle({ stroke, fill: 'none' });
  });
  it('does not mark an empty point or pass', () => {
    const { container, rerender } = render(<GoBoardSvg black={['D4']} last="Q16" />);
    expect(container.querySelector('circle.mark')).toBeNull();
    rerender(<GoBoardSvg black={['D4']} last="pass" />);
    expect(container.querySelector('circle.mark')).toBeNull();
  });
});
