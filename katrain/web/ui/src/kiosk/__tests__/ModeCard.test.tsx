import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { SportsEsports } from '@mui/icons-material';
import { kioskTheme } from '../theme';
import ModeCard from '../components/common/ModeCard';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const renderCard = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter>
        <ModeCard
          title="自由对弈"
          subtitle="随意选择AI强度"
          icon={<SportsEsports />}
          to="/kiosk/play/ai/setup/free"
        />
      </MemoryRouter>
    </ThemeProvider>
  );

describe('ModeCard', () => {
  it('renders title and subtitle', () => {
    renderCard();
    expect(screen.getByText('自由对弈')).toBeInTheDocument();
    expect(screen.getByText('随意选择AI强度')).toBeInTheDocument();
  });

  it('navigates to target on click', () => {
    renderCard();
    fireEvent.click(screen.getByText('自由对弈'));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/ai/setup/free');
  });
});
