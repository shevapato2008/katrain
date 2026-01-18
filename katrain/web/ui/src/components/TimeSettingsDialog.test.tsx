import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import TimeSettingsDialog from './TimeSettingsDialog';
import { useSessionSettings } from '../hooks/useSessionSettings';

// Mock the hook
vi.mock('../hooks/useSessionSettings', () => ({
  useSessionSettings: vi.fn(),
}));

// Mock translation hook
vi.mock('../hooks/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

describe('TimeSettingsDialog', () => {
  const mockUpdateTimeSettings = vi.fn();
  const defaultSettings = {
    mainTime: 60,
    byoyomiLength: 30,
    byoyomiPeriods: 5,
    minimalTimeUsage: 0,
    sound: true,
  };

  beforeEach(() => {
    vi.mocked(useSessionSettings).mockReturnValue({
      timeSettings: defaultSettings,
      teachingSettings: {} as any,
      updateTimeSettings: mockUpdateTimeSettings,
      updateTeachingSettings: vi.fn(),
    });
    mockUpdateTimeSettings.mockClear();
  });

  it('renders correctly when open', () => {
    render(<TimeSettingsDialog open={true} onClose={vi.fn()} />);
    
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByLabelText(/Main Time/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Byoyomi Length/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Byoyomi Periods/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Minimal time usage/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Sound/i)).toBeInTheDocument();
  });

  it('does not render when closed', () => {
    render(<TimeSettingsDialog open={false} onClose={vi.fn()} />);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('updates main time on input change', () => {
    render(<TimeSettingsDialog open={true} onClose={vi.fn()} />);
    
    const input = screen.getByLabelText(/Main Time/i);
    fireEvent.change(input, { target: { value: '90' } });
    
    expect(mockUpdateTimeSettings).toHaveBeenCalledWith({ mainTime: 90 });
  });

  it('updates sound toggle on click', () => {
    render(<TimeSettingsDialog open={true} onClose={vi.fn()} />);
    
    const checkbox = screen.getByLabelText(/Sound/i);
    fireEvent.click(checkbox);
    
    expect(mockUpdateTimeSettings).toHaveBeenCalledWith({ sound: false });
  });
});
