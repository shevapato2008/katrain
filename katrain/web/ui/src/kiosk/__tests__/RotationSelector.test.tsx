import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import RotationSelector from '../components/layout/RotationSelector';

const mockSetRotation = vi.fn();
vi.mock('../context/OrientationContext', () => ({
  useOrientation: () => ({ rotation: 0, isPortrait: false, setRotation: mockSetRotation }),
}));

const r = (ui: React.ReactElement) => render(<ThemeProvider theme={kioskTheme}>{ui}</ThemeProvider>);

describe('RotationSelector', () => {
  beforeEach(() => { mockSetRotation.mockClear(); });

  it('renders rotation icon button', () => {
    r(<RotationSelector />);
    expect(screen.getByTestId('rotation-selector-button')).toBeInTheDocument();
  });

  it('opens popover with 4 options', () => {
    r(<RotationSelector />);
    fireEvent.click(screen.getByTestId('rotation-selector-button'));
    ['0°', '90°', '180°', '270°'].forEach((l) =>
      expect(screen.getByText(l)).toBeInTheDocument()
    );
  });

  it('calls setRotation and closes on selection', async () => {
    r(<RotationSelector />);
    fireEvent.click(screen.getByTestId('rotation-selector-button'));
    fireEvent.click(screen.getByText('90°'));
    expect(mockSetRotation).toHaveBeenCalledWith(90);
    await waitFor(() => {
      expect(screen.queryByText('270°')).not.toBeInTheDocument();
    });
  });

  it('highlights current rotation', () => {
    r(<RotationSelector />);
    fireEvent.click(screen.getByTestId('rotation-selector-button'));
    expect(screen.getByText('0°').closest('[data-selected]')).toHaveAttribute('data-selected', 'true');
  });
});
