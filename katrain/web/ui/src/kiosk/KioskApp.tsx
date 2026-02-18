import { Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, CssBaseline } from '@mui/material';
import { kioskTheme } from './theme';
import { useAuth } from '../context/AuthContext';
import KioskAuthGuard from './components/guards/KioskAuthGuard';
import KioskLayout from './components/layout/KioskLayout';
import LoginPage from './pages/LoginPage';
import PlaceholderPage from './pages/PlaceholderPage';
import PlayPage from './pages/PlayPage';
import AiSetupPage from './pages/AiSetupPage';
import GamePage from './pages/GamePage';
import TsumegoPage from './pages/TsumegoPage';
import ResearchPage from './pages/ResearchPage';
import KifuPage from './pages/KifuPage';
import LivePage from './pages/LivePage';
import SettingsPage from './pages/SettingsPage';

const KioskRoutes = () => {
  const { user } = useAuth();

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
        <Route element={<KioskLayout username={user?.username} />}>
          <Route index element={<Navigate to="play" replace />} />
          <Route path="play" element={<PlayPage />} />
          <Route path="play/ai/setup/:mode" element={<AiSetupPage />} />
          <Route path="play/pvp/setup" element={<PlaceholderPage />} />
          <Route path="tsumego" element={<TsumegoPage />} />
          <Route path="tsumego/:levelId" element={<PlaceholderPage />} />
          <Route path="tsumego/problem/:problemId" element={<PlaceholderPage />} />
          <Route path="research" element={<ResearchPage />} />
          <Route path="kifu" element={<KifuPage />} />
          <Route path="kifu/:kifuId" element={<PlaceholderPage />} />
          <Route path="live" element={<LivePage />} />
          <Route path="live/:matchId" element={<PlaceholderPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="play" replace />} />
        </Route>
      </Route>
    </Routes>
  );
};

const KioskApp = () => (
  <ThemeProvider theme={kioskTheme}>
    <CssBaseline />
    <KioskRoutes />
  </ThemeProvider>
);

export default KioskApp;
