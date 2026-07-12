import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
import SubPageBar from './SubPageBar';

const navigate = vi.fn();
vi.mock('react-router-dom', async (orig) => ({
  ...(await orig<typeof import('react-router-dom')>()),
  useNavigate: () => navigate,
}));

beforeEach(() => navigate.mockClear());

test('renders title and a back button', () => {
  render(<MemoryRouter><SubPageBar title="自由对弈" to="/kiosk/play" /></MemoryRouter>);
  expect(screen.getByText('自由对弈')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /返回|back/i })).toBeInTheDocument();
});

test('navigates to `to` when back pressed', () => {
  render(<MemoryRouter><SubPageBar title="x" to="/kiosk/play" /></MemoryRouter>);
  fireEvent.click(screen.getByRole('button', { name: /返回|back/i }));
  expect(navigate).toHaveBeenCalledWith('/kiosk/play');
});

test('prefers onBack over to', () => {
  const onBack = vi.fn();
  render(<MemoryRouter><SubPageBar title="x" to="/kiosk/play" onBack={onBack} /></MemoryRouter>);
  fireEvent.click(screen.getByRole('button', { name: /返回|back/i }));
  expect(onBack).toHaveBeenCalled();
  expect(navigate).not.toHaveBeenCalled();
});
