import { render, screen } from '@testing-library/react';
import { describe, expect, test, vi, beforeEach } from 'vitest';

const vision = vi.fn();
const geometry = vi.fn();
vi.mock('../../context/VisionContext', () => ({ useOptionalVision: () => vision() }));
vi.mock('../../context/GeometryContext', () => ({ useOptionalGeometry: () => geometry() }));

import { GoConsoleRail } from './GoConsoleRail';

const lampOf = (label: string) =>
  (screen.getByText(label).querySelector('i') as HTMLElement | null)?.style.color ?? null;

beforeEach(() => {
  vision.mockReturnValue(null);
  geometry.mockReturnValue(null);
});

describe('GoConsoleRail —— 状态格接真硬件', () => {
  test('两个 Context 都缺席时,三格是「—」且一颗灯都不点', () => {
    const { container } = render(<GoConsoleRail />);
    expect([...container.querySelectorAll('.kiosk-status__v')].map((e) => e.textContent))
      .toEqual(['—', '—', '—']);
    expect(container.querySelectorAll('.kiosk-status__k i')).toHaveLength(0);
  });

  test('读到了就照实画:摄像头断=红、标定 ready=绿、LED 连上=绿', () => {
    vision.mockReturnValue({ visionStatus: { cameraConnected: false, ledConnected: true } });
    geometry.mockReturnValue({ status: { phase: 'ready' } });
    render(<GoConsoleRail />);
    expect(lampOf('摄像头')).toBe('var(--bad)');
    expect(lampOf('标定')).toBe('var(--good)');
    expect(lampOf('LED')).toBe('var(--good)');
    expect(screen.getByText('未连接')).toBeInTheDocument();
    expect(screen.getByText('已标定')).toBeInTheDocument();
    expect(screen.getByText('就绪')).toBeInTheDocument();
  });

  // ⚠️ 这一条守的是旧 `SmartBoardConsole.tsx:83` 那个 `ledConnected ?? false`:
  // `boolean | null` 的 null 意思是**后端没说**,被 `?? false` 折成了「未连接」。
  // 「否定的答复不携带原因」—— 一条消息的缺席不能当判别位。
  test('LED 是 null(后端没说)⇒ 写「—」不点灯,不许画成「未连接」', () => {
    vision.mockReturnValue({ visionStatus: { cameraConnected: true, ledConnected: null } });
    geometry.mockReturnValue({ status: { phase: 'ready' } });
    render(<GoConsoleRail />);
    expect(screen.getByText('LED').parentElement?.querySelector('.kiosk-status__v')?.textContent).toBe('—');
    expect(lampOf('LED')).toBe(null);
    // 同一屏上另外两格照旧亮 —— 证明「—」是这一格的判断,不是整栏退化了
    expect(lampOf('摄像头')).toBe('var(--good)');
  });

  test('标定 degraded/failed 是红,其余未就绪是琥珀', () => {
    vision.mockReturnValue({ visionStatus: { cameraConnected: true, ledConnected: true } });
    geometry.mockReturnValue({ status: { phase: 'failed' } });
    const bad = render(<GoConsoleRail />);
    expect(lampOf('标定')).toBe('var(--bad)');
    bad.unmount();

    geometry.mockReturnValue({ status: { phase: 'required' } });
    render(<GoConsoleRail />);
    expect(lampOf('标定')).toBe('var(--warn)');
    expect(screen.getByText('需校准')).toBeInTheDocument();
  });

  test('镜像框现在是空的,而同步行把这件事说出来 —— 不画假子', () => {
    const { container } = render(<GoConsoleRail />);
    expect(container.querySelector('.kiosk-mini-board')?.innerHTML).toBe('');
    expect(screen.getByText('识别的盘面还没接进来')).toBeInTheDocument();
    expect(screen.getByText('暂不可用')).toBeInTheDocument();
  });

  // ⚠️ 旧 `SmartBoardConsole` 的三格是 `<ButtonBase>`,点任意一格跳 `/kiosk/vision/setup`。
  // 规范 §5 说得很直白:镜像栏**是状态显示,不是入口**。稿子里 `.kiosk-status__cell` 就是
  // 一个 `<div>`。所以这里把那个入口**有意去掉**了 —— 不是漏了。
  // 标定入口还在,在设置屏的「实体棋盘」那一组(`SettingsPage.tsx:131`),
  // 而设置自 Task 4 起就在 Dock 上;做题屏出错时也还有一条直达按钮
  // (`TsumegoProblemPage.tsx:478`)。**没有欠账。**
  test('状态格不是按钮 —— 镜像栏是状态显示不是入口(§5)', () => {
    vision.mockReturnValue({ visionStatus: { cameraConnected: true, ledConnected: true } });
    geometry.mockReturnValue({ status: { phase: 'ready' } });
    const { container } = render(<GoConsoleRail />);
    expect(container.querySelectorAll('button')).toHaveLength(0);
    expect(container.querySelectorAll('.kiosk-status__cell')).toHaveLength(3);
  });

  test('标题逐字取自稿子:实体棋盘 / Camera board', () => {
    render(<GoConsoleRail />);
    expect(screen.getByText('实体棋盘')).toBeInTheDocument();
    expect(screen.getByText('Camera board')).toBeInTheDocument();
  });
});
