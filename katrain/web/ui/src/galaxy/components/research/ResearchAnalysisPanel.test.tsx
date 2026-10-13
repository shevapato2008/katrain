import { render } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { ComponentProps } from 'react';
import ResearchAnalysisPanel from './ResearchAnalysisPanel';
import { writeAudioPref } from '../../../utils/audioPrefs';

const props: ComponentProps<typeof ResearchAnalysisPanel> = {
  playerBlack: '黑方', playerWhite: '白方', currentMove: 0, totalMoves: 4,
  onMoveChange: vi.fn(), winrate: 0.5, scoreLead: 0,
  showMoveNumbers: false, onToggleMoveNumbers: vi.fn(), onPass: vi.fn(),
  editMode: null, onEditModeChange: vi.fn(), placeMode: 'alternate', onPlaceModeChange: vi.fn(),
  showHints: false, onToggleHints: vi.fn(), showTerritory: false, onToggleTerritory: vi.fn(), onClear: vi.fn(),
};

afterEach(() => {
  writeAudioPref('sfx', true);
  vi.restoreAllMocks();
});

it('does not create or play its own audio when the real panel receives cursor or pass updates', () => {
  const audio = vi.spyOn(globalThis, 'Audio');
  const play = vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined);
  writeAudioPref('sfx', false);
  const { rerender } = render(<ResearchAnalysisPanel {...props} />);
  // These snapshots can arrive from analysis frontier, pass, or an explicit parent navigation.
  rerender(<ResearchAnalysisPanel {...props} currentMove={3} />);
  rerender(<ResearchAnalysisPanel {...props} currentMove={4} children={[['B', null]]} />);
  writeAudioPref('sfx', true);
  rerender(<ResearchAnalysisPanel {...props} currentMove={1} />);
  rerender(<ResearchAnalysisPanel {...props} currentMove={1} />);
  expect(audio).not.toHaveBeenCalled();
  expect(play).not.toHaveBeenCalled();
});
