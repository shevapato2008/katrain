import { createTheme } from '@mui/material';

// Self-hosted fonts via @fontsource — no CDN dependency
import '@fontsource/noto-sans-sc/400.css';
import '@fontsource/noto-sans-sc/600.css';
import '@fontsource/noto-sans-sc/700.css';
import '@fontsource/noto-serif-sc/700.css';
import '@fontsource/jetbrains-mono/400.css';
import '@fontsource/jetbrains-mono/500.css';

export const kioskTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#5cb57a',   // jade-glow
      light: '#7ec994',
      dark: '#2d5a3d',   // jade-deep
    },
    secondary: {
      main: '#8b7355',   // wood-amber
    },
    background: {
      default: '#1a1714', // ink-black
      paper: '#252019',
    },
    text: {
      primary: '#e8e4dc',  // stone-white (14:1 on ink-black)
      secondary: '#9a9590', // mist (~4.7:1 on ink-black, WCAG AA)
      disabled: '#3d3a36',
    },
    divider: 'rgba(232, 228, 220, 0.08)',
    success: { main: '#5cb57a' },
    warning: { main: '#c49a3c' },
    error: { main: '#c45d3e' },    // ember
    info: { main: '#5b9bd5' },
  },
  typography: {
    fontFamily: "'Noto Sans SC', 'Noto Sans', sans-serif",
    fontSize: 16,
    h1: { fontFamily: "'Noto Serif SC', 'Noto Serif', serif", fontWeight: 700 },
    h2: { fontFamily: "'Noto Sans SC', sans-serif", fontWeight: 700 },
    h3: { fontFamily: "'Noto Sans SC', sans-serif", fontWeight: 600 },
    h4: { fontFamily: "'Noto Sans SC', sans-serif", fontWeight: 600 },
    h5: { fontFamily: "'Noto Sans SC', sans-serif", fontWeight: 600 },
    h6: { fontFamily: "'Noto Sans SC', sans-serif", fontWeight: 600 },
    body1: { fontFamily: "'Noto Sans SC', sans-serif", fontSize: 16 },
    body2: { fontFamily: "'Noto Sans SC', sans-serif", fontSize: 14 },
    button: { fontFamily: "'Noto Sans SC', sans-serif", fontWeight: 600 },
    caption: { fontFamily: "'JetBrains Mono', monospace", fontSize: 12 },
  },
  shape: { borderRadius: 12 },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none' as const,
          borderRadius: '12px',
          padding: '12px 24px',
          fontSize: '1rem',
          transition: 'transform 100ms ease-out, background-color 150ms',
          '&:active': { transform: 'scale(0.96)' },
        },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: {
          minWidth: 48,
          minHeight: 48,
          '&:active': { transform: 'scale(0.96)' },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: { backgroundImage: 'none' },
      },
    },
  },
});
