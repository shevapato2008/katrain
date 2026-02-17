import { Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, CssBaseline } from '@mui/material';
import { kioskTheme } from './theme';
import { KioskAuthProvider, useKioskAuth } from './context/KioskAuthContext';
import KioskAuthGuard from './components/guards/KioskAuthGuard';
import KioskLayout from './components/layout/KioskLayout';
import LoginPage from './pages/LoginPage';
import PlaceholderPage from './pages/PlaceholderPage';
import PlayPage from './pages/PlayPage';
import AiSetupPage from './pages/AiSetupPage';
import GamePage from './pages/GamePage';
import TsumegoPage from './pages/TsumegoPage';

const KioskRoutes = () => {
  const { user } = useKioskAuth();

  return (
    <Routes>
      {/* Public */}
      <Route path="login" element={<LoginPage />} />

      {/* Auth-protected */}
      <Route element={<KioskAuthGuard />}>
        {/* Fullscreen — no nav rail */}
        <Route path="play/ai/game/:sessionId" element={<GamePage />} />
        <Route path="play/pvp/local/game/:sessionId" element={<GamePage />} />
        <Route path="play/pvp/room/:sessionId" element={<GamePage />} />

        {/* Standard — with nav rail */}
        <Route element={<KioskLayout username={user?.name} />}>
          <Route index element={<Navigate to="play" replace />} />
          <Route path="play" element={<PlayPage />} />
          <Route path="play/ai/setup/:mode" element={<AiSetupPage />} />
          <Route path="play/pvp/setup" element={<PlaceholderPage />} />
          <Route path="tsumego" element={<TsumegoPage />} />
          <Route path="tsumego/problem/:problemId" element={<PlaceholderPage />} />
          <Route path="research" element={<PlaceholderPage />} />
          <Route path="kifu" element={<PlaceholderPage />} />
          <Route path="live" element={<PlaceholderPage />} />
          <Route path="live/:matchId" element={<PlaceholderPage />} />
          <Route path="settings" element={<PlaceholderPage />} />
          <Route path="*" element={<Navigate to="play" replace />} />
        </Route>
      </Route>
    </Routes>
  );
};

const KioskApp = () => (
  <ThemeProvider theme={kioskTheme}>
    <CssBaseline />
    <KioskAuthProvider>
      <KioskRoutes />
    </KioskAuthProvider>
  </ThemeProvider>
);

export default KioskApp;
