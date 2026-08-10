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
  it('renders five real, translated MUI toggle buttons with the established icons and selected state', () => {
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
      [names.coordinates, 'GridOnIcon', 'false'],
    ] as const;

    for (const [name, icon, pressed] of expected) {
      const button = screen.getByRole('button', { name });
      expect(button).toHaveClass('MuiToggleButton-root');
      expect(button).toHaveAttribute('aria-pressed', pressed);
      expect(button).toHaveStyle({ minHeight: '40px' });
      expect(button.querySelector(`[data-testid="${icon}"]`)).toBeInTheDocument();
    }
  });

  it('calls only the callback belonging to the clicked control', () => {
    const handlers = renderControls();
    const cases = [
      [names.tryMove, 'onTryMoveToggle'],
      [names.territory, 'onTerritoryToggle'],
      [names.moveNumbers, 'onMoveNumbersToggle'],
      [names.aiMarkers, 'onAiMarkersToggle'],
      [names.coordinates, 'onCoordinatesToggle'],
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

  it('uses an equal-width wrapping grid suitable for the 320px rail', () => {
    renderControls();
    expect(screen.getByTestId('live-match-display-controls-grid')).toHaveStyle({
      display: 'grid',
      gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
    });
  });
});
