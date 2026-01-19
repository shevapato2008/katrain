import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import TeachingSettingsDialog from './TeachingSettingsDialog';
import { useSessionSettings } from '../hooks/useSessionSettings';

// Mock the hook
vi.mock('../hooks/useSessionSettings', () => ({
  useSessionSettings: vi.fn(),
}));

// Mock translation hook
vi.mock('../hooks/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

describe('TeachingSettingsDialog', () => {
  const mockUpdateTeachingSettings = vi.fn();
  const defaultTeachingSettings = {
    showDots: [true, true, true, true, true, true],
    saveFeedback: [true, true, true, true, false, false],
    evalThresholds: [12, 6, 3, 1.5, 0.5, 0],
    showAI: true,
    topMovesShow: 'top_move_delta_score',
    visits: {
      fast: 25,
      low: 100,
      max: 500,
    },
  };

  beforeEach(() => {
    vi.mocked(useSessionSettings).mockReturnValue({
      timeSettings: {} as any,
      teachingSettings: defaultTeachingSettings,
      updateTimeSettings: vi.fn(),
      updateTeachingSettings: mockUpdateTeachingSettings,
    });
    mockUpdateTeachingSettings.mockClear();
  });

  it('renders correctly when open', () => {
    render(<TeachingSettingsDialog open={true} onClose={vi.fn()} />);
    
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText(/teacher settings/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/show ai dots/i)).toBeInTheDocument();
  });

  it('updates showAI toggle on click', () => {
    render(<TeachingSettingsDialog open={true} onClose={vi.fn()} />);
    
    const checkbox = screen.getByLabelText(/show ai dots/i);
    fireEvent.click(checkbox);
    
    expect(mockUpdateTeachingSettings).toHaveBeenCalledWith({ showAI: false });
  });

  it('updates showDots checkbox on click', () => {
    render(<TeachingSettingsDialog open={true} onClose={vi.fn()} />);
    
    // There are multiple show dots checkboxes, let's find one by index
    const checkboxes = screen.getAllByLabelText(/show dots/i);
    fireEvent.click(checkboxes[0]);
    
    const expectedShowDots = [...defaultTeachingSettings.showDots];
    expectedShowDots[0] = !expectedShowDots[0];
    
    expect(mockUpdateTeachingSettings).toHaveBeenCalledWith({ showDots: expectedShowDots });
  });
});
