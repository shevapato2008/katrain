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
    expect(screen.getByLabelText(/main time/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/byoyomi length/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/byoyomi periods/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/minimal time use/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/count down sound/i)).toBeInTheDocument();
  });

  it('does not render when closed', () => {
    render(<TimeSettingsDialog open={false} onClose={vi.fn()} />);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('updates main time on input change', () => {
    render(<TimeSettingsDialog open={true} onClose={vi.fn()} />);
    
    const input = screen.getByLabelText(/main time/i);
    fireEvent.change(input, { target: { value: '90' } });
    
    expect(mockUpdateTimeSettings).toHaveBeenCalledWith({ mainTime: 90 });
  });

  it('updates sound toggle on click', () => {
    render(<TimeSettingsDialog open={true} onClose={vi.fn()} />);
    
    const checkbox = screen.getByLabelText(/count down sound/i);
    fireEvent.click(checkbox);
    
    expect(mockUpdateTimeSettings).toHaveBeenCalledWith({ sound: false });
  });
});
