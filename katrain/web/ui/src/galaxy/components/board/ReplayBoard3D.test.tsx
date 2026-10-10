import { render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';

import ReplayBoard3D from './ReplayBoard3D';

vi.mock('../../../components/Board3D', () => ({
  default: ({ gameState, analysisToggles, readOnly }: { gameState: { stones: unknown; analysis: { ownership: unknown } }; analysisToggles: unknown; readOnly: boolean }) =>
    <pre data-testid="board-state">{JSON.stringify({ stones: gameState.stones, ownership: gameState.analysis.ownership, analysisToggles, readOnly })}</pre>,
}));

it('replays captures and sends matching board display state into 3D', async () => {
  render(<ReplayBoard3D
    moves={['A1', 'B1', 'pass', 'A2']}
    currentMove={4} boardSize={3}
    showCoordinates showMoveNumbers showAiMarkers={false} showTerritory
    ownership={[[1, 0, 0], [0, 0, 0], [0, 0, -1]]}
  />);
  const state = JSON.parse((await screen.findByTestId('board-state')).textContent ?? '{}');
  expect(state.analysisToggles).toMatchObject({ coords: true, numbers: true, ownership: true });
  expect(state.ownership[0][2]).toBe(-1);
  expect(state.ownership[2][0]).toBe(1);
  expect(state.readOnly).toBe(true);
  expect(state.stones).toEqual(expect.arrayContaining([expect.arrayContaining(['W', [1, 0]])]));
  expect(state.stones.some((stone: [string, [number, number]]) => stone[1][0] === 0 && stone[1][1] === 0)).toBe(false);
});
