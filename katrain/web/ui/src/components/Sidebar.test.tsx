import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Sidebar from './Sidebar';

// Mock translation hook
vi.mock('../hooks/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

describe('Sidebar', () => {
  const defaultProps = {
    gameState: null,
    settings: {
      showPassAlert: true,
      playPassSound: true,
      showEndAlert: true,
      playEndSound: true,
    },
    onUpdateSettings: vi.fn(),
    onNewGame: vi.fn(),
    onLoadSGF: vi.fn(),
    onSaveSGF: vi.fn(),
    onAISettings: vi.fn(),
    onAnalyzeGame: vi.fn(),
    onGameReport: vi.fn(),
    onLanguageChange: vi.fn(),
    onSwapPlayers: vi.fn(),
    onTimeSettings: vi.fn(),
    onTeachingSettings: vi.fn(),
  };

  it('renders Time Settings and Teaching Settings buttons as enabled', () => {
    render(<Sidebar {...defaultProps} />);
    
    // Find by text content (mocked translation returns key)
    const timeBtn = screen.getByText('menu:clocksettings').closest('div[role="button"]');
    const teachBtn = screen.getByText('menu:teachsettings').closest('div[role="button"]');
    
    expect(timeBtn).not.toBeDisabled();
    expect(teachBtn).not.toBeDisabled();
  });

  it('calls onTimeSettings when Time Settings button is clicked', () => {
    render(<Sidebar {...defaultProps} />);
    const timeBtn = screen.getByText('menu:clocksettings');
    fireEvent.click(timeBtn);
    expect(defaultProps.onTimeSettings).toHaveBeenCalled();
  });

  it('calls onTeachingSettings when Teaching Settings button is clicked', () => {
    render(<Sidebar {...defaultProps} />);
    const teachBtn = screen.getByText('menu:teachsettings');
    fireEvent.click(teachBtn);
    expect(defaultProps.onTeachingSettings).toHaveBeenCalled();
  });
});
