import { render, screen } from '@testing-library/react';
import { describe, expect, test } from 'vitest';
import { KioskCard } from './KioskCard';

const tile = (c: HTMLElement) => c.querySelector('.kiosk-card__tile') as HTMLElement;

describe('KioskCard —— 图标卡与环卡是**同一张卡**,只换衬里那一块', () => {
  test('不传 ring 就是图标卡:衬里是内联 svg 图标,没有 is-ring', () => {
    const { container } = render(<KioskCard title="自由对弈" sub="自己挑强度" icon="robot" />);
    expect(tile(container).className).not.toContain('is-ring');
    expect(tile(container).querySelector('.kiosk-icon')).not.toBeNull();
  });

  test('传了 ring 就是环卡,几何类名换成 is-ring —— 卡本身的类名一个不变', () => {
    const { container } = render(<KioskCard title="15 级" sub="最容易的一档" ring={0} />);
    expect(tile(container).className).toContain('is-ring');
    expect(container.querySelector('.kiosk-card')!.className).toBe('kiosk-card');
  });
});

describe('环:读不到值要说读不到', () => {
  // G8。0% 是一句事实断言(「你一道都没做」),而 ring=null 的意思是「我不知道」。
  // 拿 0 顶上去,界面就替后端编了一个它没给的数。
  test('ring=null 写「—」,不写 0%', () => {
    render(<KioskCard title="15 级" sub="x" ring={null} />);
    expect(screen.getByText('—')).toBeInTheDocument();
    expect(screen.queryByText('0%')).not.toBeInTheDocument();
  });

  test('ring=0 写 0%,而且**不画**那段进度弧', () => {
    const { container } = render(<KioskCard title="15 级" sub="x" ring={0} />);
    expect(screen.getByText('0%')).toBeInTheDocument();
    // 只剩底圈一个 circle。画一段圆头 0 长弧会显示成一个小圆点,看着像「有一点点进度」。
    expect(container.querySelectorAll('circle')).toHaveLength(1);
  });

  test('0 < pct < 100 画两圈,弧长按周长比例给', () => {
    const { container } = render(<KioskCard title="x" sub="y" ring={25} />);
    const circles = container.querySelectorAll('circle');
    expect(circles).toHaveLength(2);
    const C = 2 * Math.PI * 18;
    expect(circles[1].getAttribute('stroke-dasharray'))
      .toBe(`${(C * 0.25).toFixed(2)} ${C.toFixed(2)}`);
    expect(circles[1].getAttribute('stroke')).toBe('var(--accent)');
  });

  test('100% 走 --good 不走 --accent —— 「学完了」是状态,换棋种也得读得出', () => {
    const { container } = render(<KioskCard title="x" sub="y" ring={100} />);
    expect(container.querySelectorAll('circle')[1].getAttribute('stroke')).toBe('var(--good)');
  });

  test('越界的值夹回 0–100,不让弧转出圈', () => {
    const { container } = render(<KioskCard title="x" sub="y" ring={140} />);
    const C = 2 * Math.PI * 18;
    expect(container.querySelectorAll('circle')[1].getAttribute('stroke-dasharray'))
      .toBe(`${C.toFixed(2)} ${C.toFixed(2)}`);
    expect(screen.getByText('100%')).toBeInTheDocument();
  });
});

describe('「还不能用」的两种,点不动', () => {
  test('soon 的文案由调用方给,并且卡是 disabled 的', () => {
    render(<KioskCard title="野狐围棋" sub="接口还没通" icon="globe-hemisphere-west" soon="即将上线" />);
    expect(screen.getByText('即将上线')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^野狐围棋，/ })).toBeDisabled();
  });

  test('todo 压暗且点不动', () => {
    const { container } = render(<KioskCard title="第 3 课" sub="未录制" todo />);
    expect(container.querySelector('.kiosk-card')!.className).toContain('is-todo');
    expect(screen.getByRole('button', { name: /^第 3 课，/ })).toBeDisabled();
  });

  test('能用的卡不 disabled —— 「不超过 N」那一侧的下界(§17.1)', () => {
    render(<KioskCard title="在线大厅" sub="约战" icon="globe-hemisphere-west" dot />);
    expect(screen.getByRole('button', { name: /^在线大厅，/ })).toBeEnabled();
  });
});
