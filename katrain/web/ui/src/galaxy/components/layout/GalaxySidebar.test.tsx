import { render, screen, fireEvent } from '@testing-library/react';
import GalaxySidebar from './GalaxySidebar';
import { AuthProvider, useAuth } from '../../context/AuthContext';
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

// Mock hooks
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

describe('GalaxySidebar', () => {
  it('renders login button when not authenticated', () => {
    (useAuth as Mock).mockReturnValue({ isAuthenticated: false, user: null, login: vi.fn() });
    
    render(
      <MemoryRouter>
        <GalaxySidebar />
      </MemoryRouter>
    );

    expect(screen.getByText('Login')).toBeInTheDocument();
    expect(screen.queryByText('💎')).not.toBeInTheDocument();
  });

  it('renders user profile when authenticated', () => {
    (useAuth as Mock).mockReturnValue({ 
      isAuthenticated: true, 
      user: { username: 'TestUser', rank: '5d', credits: 500 }, 
      logout: vi.fn() 
    });

    render(
      <MemoryRouter>
        <GalaxySidebar />
      </MemoryRouter>
    );

    expect(screen.getByText('TestUser')).toBeInTheDocument();
    expect(screen.getByText('5d')).toBeInTheDocument(); // Avatar content
    expect(screen.getByText('💎 500')).toBeInTheDocument();
    expect(screen.queryByText('Login')).not.toBeInTheDocument();
  });
});
