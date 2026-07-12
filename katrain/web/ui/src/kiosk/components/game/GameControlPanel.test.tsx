import { render, screen, fireEvent } from '@testing-library/react';
import { vi, describe, test, expect } from 'vitest';
import GameControlPanel from './GameControlPanel';
import type { GameState } from '../../../api';

const mockGameState: GameState = {
  game_id: 'test-game',
  board_size: [19, 19],
  komi: 6.5,
  handicap: 0,
  ruleset: '日本',
  current_node_id: 0,
  current_node_index: 0,
  history: [{ node_id: 0, score: 0, winrate: 0.5 }],
  player_to_move: 'B',
  stones: [],
  last_move: null,
  prisoner_count: { B: 0, W: 0 },
  analysis: null,
  commentary: '',
  is_root: true,
  is_pass: false,
  end_result: null,
  children: [],
  ghost_stones: [],
  players_info: {
    B: { player_type: 'human', player_subtype: '', name: '张三', calculated_rank: '2D', periods_used: 0, main_time_used: 0 },
    W: { player_type: 'ai', player_subtype: 'katago', name: 'KataGo', calculated_rank: '5D', periods_used: 0, main_time_used: 0 },
  },
  note: '',
  ui_state: {
    show_children: false, show_dots: false, show_hints: false, show_policy: false,
    show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false,
  },
} as GameState;

describe('GameControlPanel — 3D toggle', () => {
  test('renders a 3D toggle wired to view3d', () => {
    const onToggle = vi.fn();
    render(
      <GameControlPanel
        gameState={mockGameState}
        onAction={() => {}}
        onNavigate={() => {}}
        analysisToggles={{}}
        onToggleAnalysis={onToggle}
        isGameOver={false}
      />
    );
    const btn = screen.getByText('3D');
    fireEvent.click(btn);
    expect(onToggle).toHaveBeenCalledWith('view3d');
  });

  test('hides the 3D toggle when WebGL is unavailable, keeping other controls', () => {
    vi.stubGlobal('WebGLRenderingContext', undefined);
    try {
      render(
        <GameControlPanel
          gameState={mockGameState}
          onAction={() => {}}
          onNavigate={() => {}}
          analysisToggles={{}}
          onToggleAnalysis={() => {}}
          isGameOver={false}
        />
      );
      expect(screen.queryByText('3D')).toBeNull();
      expect(screen.getByText('领地')).toBeInTheDocument();
      expect(screen.getByText('数子')).toBeInTheDocument();
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
