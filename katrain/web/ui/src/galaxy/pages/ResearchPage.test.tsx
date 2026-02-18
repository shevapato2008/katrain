import { render, screen } from '@testing-library/react';
import ResearchPage from './ResearchPage';
import { useAuth } from '../../context/AuthContext';
import { vi, describe, it, expect, Mock } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

// Mock useAuth
vi.mock('../../context/AuthContext', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    useAuth: vi.fn(),
  };
});

// Mock Board component as it's complex and legacy
vi.mock('../../components/Board', () => ({
  default: () => <div data-testid="mock-board">Board Component</div>
}));

// Mock Board component as it's complex and legacy
vi.mock('../../components/Board', () => ({
  default: () => <div data-testid="mock-board">Board Component</div>
}));

// Mock AnalysisPanel
vi.mock('../../components/AnalysisPanel', () => ({
  default: () => <div data-testid="mock-analysis">Analysis Panel</div>
}));

// Mock ScoreGraph
vi.mock('../../components/ScoreGraph', () => ({
  default: () => <div data-testid="mock-graph">Score Graph</div>
}));

// Mock useGameSession
vi.mock('../hooks/useGameSession', () => ({
  useGameSession: () => ({
    gameState: { 
        board_size: 19, 
        stones: [], 
        player_to_move: 'B',
        history: [],
        current_node_id: 0,
        game_id: 'test'
    },
    onMove: vi.fn(),
    onNavigate: vi.fn()
  })
}));

describe('ResearchPage', () => {
  it('renders login reminder when not authenticated', () => {
    (useAuth as Mock).mockReturnValue({ isAuthenticated: false });
    
    render(
      <MemoryRouter>
        <ResearchPage />
      </MemoryRouter>
    );

    expect(screen.getByText(/Login Required/i)).toBeInTheDocument();
    expect(screen.queryByTestId('mock-board')).not.toBeInTheDocument();
  });

  it('renders board and analysis when authenticated', () => {
    (useAuth as Mock).mockReturnValue({ isAuthenticated: true });
    
    render(
      <MemoryRouter>
        <ResearchPage />
      </MemoryRouter>
    );

    expect(screen.getByTestId('mock-board')).toBeInTheDocument();
    expect(screen.getByTestId('mock-analysis')).toBeInTheDocument();
  });
});
