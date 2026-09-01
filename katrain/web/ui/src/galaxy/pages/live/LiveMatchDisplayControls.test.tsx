import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import LiveMatchDisplayControls, { type LiveMatchDisplayControlsProps } from './LiveMatchDisplayControls';

vi.mock('../../../hooks/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string, fallback: string) => `translated:${key}:${fallback}` }),
}));

const callbacks = () => ({
  onTryMoveToggle: vi.fn(),
  onTerritoryToggle: vi.fn(),
  onMoveNumbersToggle: vi.fn(),
  onAiMarkersToggle: vi.fn(),
  onCoordinatesToggle: vi.fn(),
  onClearTryMoves: vi.fn(),
});

const renderControls = (overrides: Partial<LiveMatchDisplayControlsProps> = {}) => {
  const handlers = callbacks();
  render(
    <LiveMatchDisplayControls
      tryMoveMode={false}
      showTerritory={false}
      showMoveNumbers={false}
      showAiMarkers={false}
      showCoordinates={false}
      ownershipAvailable
      tryMoves={[]}
      {...handlers}
      {...overrides}
    />,
  );
  return handlers;
};

const names = {
  tryMove: 'translated:live:try_move:Try Move',
  territory: 'translated:live:territory:Territory',
  moveNumbers: 'translated:live:move_numbers:Move Numbers',
  aiMarkers: 'translated:live:show_advice:Show Advice',
  coordinates: 'translated:Coordinates:Coordinates',
};

describe('LiveMatchDisplayControls', () => {
  it('renders four real, translated tool-grid buttons plus a coordinate switch, with the established icons and pressed state', () => {
    renderControls({
      tryMoveMode: true,
      showTerritory: false,
      showMoveNumbers: true,
      showAiMarkers: true,
      showCoordinates: false,
    });

    const expected = [
      [names.tryMove, 'TouchAppIcon', 'true'],
      [names.territory, 'MapIcon', 'false'],
      [names.moveNumbers, 'FormatListNumberedIcon', 'true'],
      ['translated:live:hide_advice:Hide Advice', 'TipsAndUpdatesIcon', 'true'],
    ] as const;

    for (const [name, icon, pressed] of expected) {
      const button = screen.getByRole('button', { name });
      // 工具格按钮渲染的是真的 <button>（ButtonBase），不是挂 onClick 的 div ——
      // 键盘可达，控件账本也看得见。
      expect(button.tagName).toBe('BUTTON');
      expect(button).toHaveClass('MuiButtonBase-root');
      expect(button).toHaveAttribute('aria-pressed', pressed);
      expect(button.querySelector(`[data-testid="${icon}"]`)).toBeInTheDocument();
    }

    // 坐标不在工具格里：它改的是棋盘刻度，不是棋盘上画什么分析信息（与死活题页对齐）。
    const coordinates = screen.getByRole('checkbox', { name: names.coordinates });
    expect(coordinates).not.toBeChecked();
    expect(screen.queryByRole('button', { name: names.coordinates })).not.toBeInTheDocument();
  });

  it('calls only the callback belonging to the clicked control', () => {
    const handlers = renderControls();
    const cases = [
      [names.tryMove, 'onTryMoveToggle'],
      [names.territory, 'onTerritoryToggle'],
      [names.moveNumbers, 'onMoveNumbersToggle'],
      [names.aiMarkers, 'onAiMarkersToggle'],
    ] as const;

    for (const [name, callback] of cases) {
      Object.values(handlers).forEach((handler) => handler.mockClear());
      fireEvent.click(screen.getByRole('button', { name }));
      for (const [handlerName, handler] of Object.entries(handlers)) {
        expect(handler).toHaveBeenCalledTimes(handlerName === callback ? 1 : 0);
      }
    }

    Object.values(handlers).forEach((handler) => handler.mockClear());
    fireEvent.click(screen.getByRole('checkbox', { name: names.coordinates }));
    for (const [handlerName, handler] of Object.entries(handlers)) {
      expect(handler).toHaveBeenCalledTimes(handlerName === 'onCoordinatesToggle' ? 1 : 0);
    }
  });

  it('disables unavailable territory while keeping its explanation reachable through a span wrapper', async () => {
    const user = userEvent.setup();
    const handlers = renderControls({ ownershipAvailable: false });
    const territory = screen.getByRole('button', { name: names.territory });

    expect(territory).toBeDisabled();
    expect(territory.parentElement).toHaveProperty('tagName', 'SPAN');
    expect(territory.parentElement).not.toHaveAttribute('aria-disabled', 'true');

    await user.hover(territory.parentElement!);
    expect(await screen.findByRole('tooltip')).toHaveTextContent(
      'translated:live:territory_needs_analysis:Territory (needs analysis)',
    );
    expect(handlers.onTerritoryToggle).not.toHaveBeenCalled();
  });

  it('shows the try path and a 40px clear action only while try mode has moves', () => {
    const handlers = renderControls({ tryMoveMode: true, tryMoves: ['D4', 'Q16'] });

    expect(screen.getByText('translated:live:try:TRY: D4 → Q16')).toBeInTheDocument();
    const clear = screen.getByRole('button', { name: 'translated:live:clear:Clear' });
    expect(clear).toHaveStyle({ minHeight: '40px' });
    fireEvent.click(clear);
    expect(handlers.onClearTryMoves).toHaveBeenCalledOnce();
  });

  it.each([
    { tryMoveMode: false, tryMoves: ['D4'] },
    { tryMoveMode: true, tryMoves: [] },
  ])('omits the clear row for $tryMoveMode / $tryMoves', (props) => {
    renderControls(props);
    expect(screen.queryByRole('button', { name: 'translated:live:clear:Clear' })).not.toBeInTheDocument();
  });

  /* 工具格栅格必须来自共用常量 `railStyles.toolGridSx`，不是本页自己写一份。
     2026-09-01 键改成「图标左、文字右」之后列数分了两档：窄档 2×2、宽档 1×4 ——
     横排一格要装下「图标 + 间隙 + 两字」，四列在 320 档只剩 67px，装不下。
     这条测试原来钉的是字面量 `repeat(4, minmax(0, 1fr))`：断言的对象变了，不是坏了，
     所以改写成两档各断言一次，而不是删掉——删掉等于这条栅格从此没人守。
     变异验证：把 `toolGridSx` 的 RAIL_WIDE 那一支删掉，下面第二条红；
     把基础值改回 `repeat(4, ...)`，第一条红。 */
  it('uses the shared tool grid: 2 columns narrow, 4 columns on a wide rail', () => {
    renderControls();
    expect(screen.getByTestId('live-match-display-controls-grid')).toHaveStyle({
      display: 'grid',
      gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
    });
    const css = Array.from(document.querySelectorAll('style')).map((n) => n.textContent ?? '').join('\n');
    expect(css).toMatch(
      /@container board-rail \(min-width: 460px\)\s*\{[^}]*grid-template-columns:\s*repeat\(4, minmax\(0, 1fr\)\)/,
    );
  });

  /* 跨页一致：坐标开关这一行在直播/复盘和对局页必须是同一种东西。
     窄档两端对齐（冻结稿的形状）；宽档必须**关掉** space-between —— 对局页那一组在
     520 档会排成两列，继续两端对齐的话每个滑块离下一列的标签只有 16px、离自己的标签 158px，
     邻近性整个反过来。这里只有一个开关排不出第二列，但要跟对局页用**同一条规则**，
     否则同一个「坐标」开关在两类页面上一个贴着标签、一个甩到 488px 外。
     这条钉的是那条规则来自**共用常量** `railToggleRowSx`，不是各页各写一份。
     变异验证：把 RAIL_WIDE 的 460 改成 9999（等于宽档规则永不生效），本条红。 */
  it('drops space-between on the shared wide-rail band so the switch stays next to its label', () => {
    renderControls();
    const css = Array.from(document.querySelectorAll('style')).map((n) => n.textContent ?? '').join('\n');
    expect(css).toContain('@container board-rail (min-width: 460px)');
    expect(css).toMatch(/@container board-rail \(min-width: 460px\)\s*\{[^}]*justify-content:\s*flex-start/);
  });
});
