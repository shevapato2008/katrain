import { createTheme } from '@mui/material';

export const zenTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#4a6b5c', // Muted jade accent
      light: '#5d8270',
      dark: '#2f4539',
    },
    background: {
      default: '#0f0f0f', // Deep charcoal
      paper: '#252525', // Tertiary bg
    },
    text: {
      primary: '#f5f3f0', // Primary text
      secondary: '#b8b5b0', // Secondary text
      disabled: '#4a4845',
    },
    divider: 'rgba(255, 255, 255, 0.05)',
    success: {
      main: '#30a06e',
    },
    warning: {
      main: '#e89639',
    },
    error: {
      main: '#e16b5c',
    },
    info: {
      main: '#5b9bd5',
    },
  },
  typography: {
    fontFamily: "'Manrope', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif",
    fontSize: 16,
    h1: { fontFamily: "'Manrope', sans-serif", fontWeight: 600 },
    h2: { fontFamily: "'Manrope', sans-serif", fontWeight: 600 },
    h3: { fontFamily: "'Manrope', sans-serif", fontWeight: 600 },
    h4: { fontFamily: "'Manrope', sans-serif", fontWeight: 600 },
    h5: { fontFamily: "'Manrope', sans-serif", fontWeight: 600 },
    h6: { fontFamily: "'Manrope', sans-serif", fontWeight: 600 },
    body1: { fontFamily: "'Manrope', sans-serif" },
    body2: { fontFamily: "'Manrope', sans-serif" },
    button: { fontFamily: "'Manrope', sans-serif", fontWeight: 600 },
  },
  shape: {
    borderRadius: 8,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          borderRadius: '8px',
          padding: '8px 16px',
          transition: 'all 150ms cubic-bezier(0.4, 0, 0.2, 1)',
          '&:hover': {
            transform: 'scale(1.02)',
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          borderRadius: '12px',
        },
      },
    },
  },
});
