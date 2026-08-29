import { render, screen } from '@testing-library/react';
import { describe, expect, test } from 'vitest';
import { KioskStatusCells } from './KioskStatusCells';
import { GO_HARDWARE_CELLS } from './goHardware';

describe('围棋的硬件三格', () => {
  // 规范 §5:统一的是**格数、几何和灯色语义,不是器件名**。
  // 国象/象棋盘上根本没有摄像头,五子棋盘上没有 LED —— 说明书上没有的东西,界面上不能有。
  test('围棋是 摄像头 · 标定 · LED —— 摄像头识子,盘上另有一层 LED 指下一手', () => {
    expect(GO_HARDWARE_CELLS.map((c) => c.label)).toEqual(['摄像头', '标定', 'LED']);
  });

  test('渲染出三格,每格上行是名称+灯、下行是状态值', () => {
    render(<KioskStatusCells cells={[
      { label: '摄像头', value: '已连接', tone: 'good' },
      { label: '标定', value: '需重标', tone: 'warn' },
      { label: 'LED', value: '就绪', tone: 'good' },
    ]} />);
    expect(document.querySelectorAll('.kiosk-status__cell')).toHaveLength(3);
    expect(screen.getByText('需重标')).toBeInTheDocument();
  });

  test('两格变体只给成长用 —— 三格是硬件状态的形状,不许拿来装两个数', () => {
    const { container } = render(<KioskStatusCells cells={[
      { label: '本月', value: '—' }, { label: '最高', value: '—' },
    ]} />);
    expect(container.querySelector('.kiosk-status--2')).not.toBeNull();
  });

  test('三格**不带** --2 修饰类 —— 「只给成长用」那句话的另一半(§17.1 的下界)', () => {
    const { container } = render(<KioskStatusCells cells={GO_HARDWARE_CELLS} />);
    expect(container.querySelector('.kiosk-status--2')).toBeNull();
    expect(container.querySelector('.kiosk-status')).not.toBeNull();
  });

  test('没有 tone 就不画灯 —— 灯是状态,不是装饰', () => {
    const { container } = render(<KioskStatusCells cells={[
      { label: '准确率', value: '78%' }, { label: '失误', value: '4 手' }, { label: '漏着', value: '1 手' },
    ]} />);
    expect(container.querySelectorAll('.kiosk-status__k i')).toHaveLength(0);
  });

  test('灯色走 var(--good|warn|bad),不是自己调的十六进制', () => {
    const { container } = render(<KioskStatusCells cells={[
      { label: '摄像头', value: '未连接', tone: 'bad' },
    ]} />);
    const lamp = container.querySelector('.kiosk-status__k i') as HTMLElement;
    expect(lamp.style.color).toBe('var(--bad)');
  });

  test('GO_HARDWARE_CELLS 的默认值是「—」不是编出来的状态 —— 读不到就说读不到(G8)', () => {
    expect(GO_HARDWARE_CELLS.map((c) => c.value)).toEqual(['—', '—', '—']);
    expect(GO_HARDWARE_CELLS.every((c) => c.tone === undefined)).toBe(true);
  });
});
