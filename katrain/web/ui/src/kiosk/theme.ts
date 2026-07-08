import { createTheme } from '@mui/material';

// Self-hosted fonts via @fontsource — no CDN dependency
import '@fontsource/noto-sans-sc/400.css';
import '@fontsource/noto-sans-sc/600.css';
import '@fontsource/noto-sans-sc/700.css';
import '@fontsource/jetbrains-mono/400.css';
import '@fontsource/jetbrains-mono/500.css';
import '@fontsource/newsreader/400.css';
import '@fontsource/newsreader/500.css';
import '@fontsource/newsreader/600.css';
import '@fontsource/hanken-grotesk/400.css';
import '@fontsource/hanken-grotesk/500.css';
import '@fontsource/hanken-grotesk/600.css';

const SANS = "'Hanken Grotesk','Noto Sans SC',sans-serif";
const SERIF = "'Newsreader','Noto Serif SC',serif"; // brand + greeting h1
const MONO = "'JetBrains Mono',monospace";           // clock / metrics

export const kioskTheme = createTheme({
  palette: {
    mode: 'dark',
    primary:   { main: '#58b57a', light: '#7ec994', dark: '#26463a' }, // jade / jade-deep
    secondary: { main: '#caa66f' }, // §4.3 --wood (board fallback)
    background: { default: '#0f1416', paper: '#18211f' }, // --slate / --raise
    text:      { primary: '#eef3f1', secondary: '#93a49d', disabled: '#5f716b' }, // ice/sub/dim
    divider:   '#2b3a35', // --hair
    success:   { main: '#58b57a' },
    warning:   { main: '#e0a24a' }, // THE single amber token
    error:     { main: '#e2685c' },
    info:      { main: '#5b9bd5' },
  },
  typography: {
    fontFamily: SANS,
    fontSize: 16,
    h1: { fontFamily: SERIF, fontWeight: 500 }, // brand / greeting
    h2: { fontFamily: SANS, fontWeight: 600 },
    h3: { fontFamily: SANS, fontWeight: 600 },
    h4: { fontFamily: SANS, fontWeight: 600 },
    h5: { fontFamily: SANS, fontWeight: 600 },
    h6: { fontFamily: SANS, fontWeight: 600 },
    body1: { fontFamily: SANS, fontSize: 16 },
    body2: { fontFamily: SANS, fontSize: 14 },
    button: { fontFamily: SANS, fontWeight: 600 },
    caption: { fontFamily: MONO, fontSize: 12 },
  },
  shape: { borderRadius: 12 },
  components: {
    MuiCssBaseline: {
      styleOverrides: { ':root': { '--raise2': '#1d2725' } },
    },
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
        root: { minWidth: 48, minHeight: 48, '&:active': { transform: 'scale(0.96)' } },
      },
    },
    MuiPaper: { styleOverrides: { root: { backgroundImage: 'none' } } },
  },
});
