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
  on3dToggle: vi.fn(),
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
      view3d={false}
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
  moveNumbers: 'translated:Move Numbers:手数',
  aiMarkers: 'translated:live:show_advice:Show Advice',
  coordinates: 'translated:Coordinates:坐标',
  view3d: 'translated:3D:3D',
};

describe('LiveMatchDisplayControls', () => {
  it('groups three equally sized board display buttons with the established icons and pressed state', () => {
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
      [names.coordinates, 'GridOnIcon', 'false'],
      [names.view3d, 'ViewInArIcon', 'false'],
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

    expect(screen.getByTestId('board-display-controls')).toContainElement(screen.getByRole('button', { name: names.coordinates }));
  });

  it('calls only the callback belonging to the clicked control', () => {
    const handlers = renderControls();
    const cases = [
      [names.tryMove, 'onTryMoveToggle'],
      [names.territory, 'onTerritoryToggle'],
      [names.moveNumbers, 'onMoveNumbersToggle'],
      [names.coordinates, 'onCoordinatesToggle'],
      [names.view3d, 'on3dToggle'],
      [names.aiMarkers, 'onAiMarkersToggle'],
    ] as const;

    for (const [name, callback] of cases) {
      Object.values(handlers).forEach((handler) => handler.mockClear());
      fireEvent.click(screen.getByRole('button', { name }));
      for (const [handlerName, handler] of Object.entries(handlers)) {
        expect(handler).toHaveBeenCalledTimes(handlerName === callback ? 1 : 0);
      }
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

  it('shows the try path and enables the clear action when there are trial moves', () => {
    const handlers = renderControls({ tryMoveMode: true, tryMoves: ['D4', 'Q16'] });

    expect(screen.getByText('translated:live:try:TRY: D4 → Q16')).toBeInTheDocument();
    const clear = screen.getByRole('button', { name: 'translated:live:clear:清空' });
    expect(clear).not.toBeDisabled();
    fireEvent.click(clear);
    expect(handlers.onClearTryMoves).toHaveBeenCalledOnce();
  });

  it.each([
    { tryMoveMode: false, tryMoves: ['D4'] },
    { tryMoveMode: true, tryMoves: [] },
  ])('keeps the clear action disabled without trial moves', (props) => {
    renderControls(props);
    expect(screen.getByRole('button', { name: 'translated:live:clear:清空' })).toBeDisabled();
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

  it('keeps the three board display actions in their own equal-width group', () => {
    renderControls();
    const group = screen.getByTestId('board-display-controls');
    expect(group).toHaveStyle({ gridTemplateColumns: 'repeat(3,minmax(0,1fr))' });
    expect(group.querySelectorAll('button')).toHaveLength(3);
  });
});
