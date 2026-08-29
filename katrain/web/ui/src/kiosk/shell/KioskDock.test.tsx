import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { KioskDock } from './KioskDock';
import { DOCK_TABS } from './dockRoutes';

/**
 * 替换 `__tests__/Dock.test.tsx`(随旧 `components/layout/Dock.tsx` 一起删)。
 * 旧那份有两条断言是**反的**:它断言 8 项、并断言「设置**不**在 Dock 里」。
 * 规范 §3 的词典是六项,§1 说设置就在 Dock 里(顶栏因此没有齿轮,D9)。
 *
 * ⚠️ **2026-08-25 起围棋是七项** —— 补了「成长」(屏 22,钉在复盘之后、课程之前)。
 * 那一项**围棋独有**:它靠 `ai_ladder_game_ledger`(每局带 `user_color` 和 `opponent_rung`),
 * 另外三家(象棋 / 国象 / 五子棋)有没有同形的账本要各自查 —— **不能拿这里的结论去推它们**。
 * 共享外壳的上限是 `--dock-max-items` = 7,没破。
 *
 * 这里不断言尺寸/位置/高亮的长相 —— 那些是布局结论,归
 * `tests/kiosk-shell-geometry.spec.ts` 在真浏览器里量。jsdom 没有布局引擎。
 */
describe('KioskDock', () => {
  it('渲染共享词典的七项,顺序不变', () => {
    render(<KioskDock pathname="/kiosk/play" onTab={vi.fn()} />);
    expect(screen.getAllByRole('button').map((b) => b.textContent))
      .toEqual(['对弈', '训练营', '棋谱', '复盘', '成长', '课程', '设置']);
  });

  it('「设置」在 Dock 里 —— 顶栏的齿轮因此才拆得掉(§1 / D9)', () => {
    render(<KioskDock pathname="/kiosk/play" onTab={vi.fn()} />);
    expect(screen.getByRole('button', { name: '设置' })).toBeInTheDocument();
  });

  it('下了 Dock 的三条不出现在 Dock 上 —— 路由还在,入口在别的屏里', () => {
    render(<KioskDock pathname="/kiosk/play" onTab={vi.fn()} />);
    for (const gone of ['研究', '摆谱', '直播']) {
      expect(screen.queryByText(gone)).not.toBeInTheDocument();
    }
  });

  it('当前项带 aria-current="page",**只有一个**', () => {
    render(<KioskDock pathname="/kiosk/play" onTab={vi.fn()} />);
    const on = screen.getAllByRole('button').filter((b) => b.getAttribute('aria-current') === 'page');
    expect(on).toHaveLength(1);
    expect(on[0]).toHaveTextContent('对弈');
  });

  it('二/三级页高亮父项:做题屏亮训练营', () => {
    render(<KioskDock pathname="/kiosk/tsumego/problem/42" onTab={vi.fn()} />);
    expect(screen.getByRole('button', { name: '训练营' })).toHaveAttribute('aria-current', 'page');
  });

  it('下了 Dock 的路由上一个都不亮 —— 不许乱认父项', () => {
    render(<KioskDock pathname="/kiosk/baipu" onTab={vi.fn()} />);
    expect(screen.getAllByRole('button').filter((b) => b.getAttribute('aria-current') === 'page'))
      .toHaveLength(0);
  });

  it('点一项把它的路由交出去 —— 导航由调用方做,Dock 自己不 navigate', () => {
    const onTab = vi.fn();
    render(<KioskDock pathname="/kiosk/play" onTab={onTab} />);
    fireEvent.click(screen.getByRole('button', { name: '训练营' }));
    expect(onTab).toHaveBeenCalledWith('/kiosk/tsumego');
  });

  it('图标是内联 svg 且跟随 currentColor —— 选中那一格靠它翻成 --ink', () => {
    const { container } = render(<KioskDock pathname="/kiosk/play" onTab={vi.fn()} />);
    // 每一项一个图标 —— 数字跟着 `DOCK_TABS` 走(2026-08-25 起七项)。
    expect(container.querySelectorAll('.kiosk-dock__item svg')).toHaveLength(DOCK_TABS.length);
    expect(container.querySelector('img')).toBeNull();
  });

  it('选中项取 -fill 那一份图标,没选中的取线描版', () => {
    const { container } = render(<KioskDock pathname="/kiosk/play" onTab={vi.fn()} />);
    const svgs = [...container.querySelectorAll('.kiosk-dock__item svg')].map((s) => s.innerHTML);
    // 对弈选中、训练营没选中。同一个名字的两份 svg 路径不同,内容必然不等。
    const solo = render(<KioskDock pathname="/kiosk/tsumego" onTab={vi.fn()} />);
    const svgs2 = [...solo.container.querySelectorAll('.kiosk-dock__item svg')].map((s) => s.innerHTML);
    expect(svgs[0]).not.toBe(svgs2[0]);   // 对弈:选中 vs 没选中
    expect(svgs[1]).not.toBe(svgs2[1]);   // 训练营:没选中 vs 选中
  });
});
