import { render, screen } from '@testing-library/react';
import { describe, test, expect } from 'vitest';
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

describe('GameControlPanel', () => {
  // The 3D board was removed from the kiosk on 2026-07-13 (freed ~321MB Mali GPU contending
  // with KataGo's OpenCL). Guard against reintroducing the toggle; core controls must remain.
  test('renders core controls and NO 3D toggle', () => {
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
  });
});
