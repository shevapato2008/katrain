import { useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, CssBaseline } from '@mui/material';
import { kioskTheme } from './theme';
import { useAuth } from '../context/AuthContext';
import { useSettings } from '../context/SettingsContext';
import { TsumegoProgressProvider } from '../context/TsumegoProgressContext';
import { OrientationProvider } from './context/OrientationContext';
import { VisionProvider } from './context/VisionContext';
import { GeometryProvider } from './context/GeometryContext';
import PhysicalBoardGuard from './components/vision/PhysicalBoardGuard';
import RotationWrapper from './components/layout/RotationWrapper';
import KioskAuthGuard from './components/guards/KioskAuthGuard';
import KioskLayout from './components/layout/KioskLayout';
import LoginPage from './pages/LoginPage';
import PlaceholderPage from './pages/PlaceholderPage';
import PlayPage from './pages/PlayPage';
import AiSetupPage from './pages/AiSetupPage';
import PvpLocalSetupPage from './pages/PvpLocalSetupPage';
import GamePage from './pages/GamePage';
import TsumegoPage from './pages/TsumegoPage';
import TsumegoCategoriesPage from './pages/TsumegoCategoriesPage';
import TsumegoLevelPage from './pages/TsumegoLevelPage';
import TsumegoUnitsPage from './pages/TsumegoUnitsPage';
import TsumegoUnitListPage from './pages/TsumegoUnitListPage';
import TsumegoProblemPage from './pages/TsumegoProblemPage';
import ResearchPage from './pages/ResearchPage';
import KifuPage from './pages/KifuPage';
import BaipuListPage from './pages/BaipuListPage';
import BaipuSessionPage from './pages/BaipuSessionPage';
import LivePage from './pages/LivePage';
import LiveMatchPage from './pages/LiveMatchPage';
import LobbyPage from './pages/LobbyPage';
import SettingsPage from './pages/SettingsPage';
import VisionSetupPage from './pages/VisionSetupPage';
import PlatformConnectPage from './pages/PlatformConnectPage';
import PlatformLobbyPage from './pages/PlatformLobbyPage';
import PlatformEngineSetupPage from './pages/PlatformEngineSetupPage';
import TutorialCategoriesPage from './pages/TutorialCategoriesPage';
import TutorialBooksPage from './pages/TutorialBooksPage';
import TutorialBookDetailPage from './pages/TutorialBookDetailPage';
import TutorialSectionPage from './pages/TutorialSectionPage';

const KioskRoutes = () => {
  const { user } = useAuth();

  return (
    <Routes>
      {/* Public */}
      <Route path="login" element={<LoginPage />} />

      {/* Auth-protected */}
      <Route element={<KioskAuthGuard />}>
        {/* Fullscreen — no nav rail */}
        <Route path="play/ai/game/:sessionId" element={<PhysicalBoardGuard requireRecognition><GamePage /></PhysicalBoardGuard>} />
        <Route path="play/pvp/local/game/:sessionId" element={<PhysicalBoardGuard requireRecognition><GamePage /></PhysicalBoardGuard>} />
        <Route path="play/pvp/room/:sessionId" element={<PhysicalBoardGuard requireRecognition><GamePage /></PhysicalBoardGuard>} />
        <Route path="play/cross-platform/engine/game/:sessionId" element={<PhysicalBoardGuard requireRecognition><GamePage engineMode /></PhysicalBoardGuard>} />

        {/* Standard — with nav rail */}
        <Route element={<KioskLayout username={user?.username} />}>
          <Route index element={<Navigate to="play" replace />} />
          <Route path="play" element={<PlayPage />} />
          <Route path="play/ai/setup/:mode" element={<AiSetupPage />} />
          <Route path="play/pvp/setup" element={<PvpLocalSetupPage />} />
          <Route path="play/pvp/lobby" element={<LobbyPage />} />
          <Route path="play/cross-platform" element={<PlatformConnectPage />} />
          <Route path="play/cross-platform/lobby" element={<PlatformLobbyPage />} />
          <Route path="play/cross-platform/engine/:platform" element={<PlatformEngineSetupPage />} />
          {/* Tsumego — 5-level navigation (static `problem`/`all` win over dynamic params in v6 best-match) */}
          <Route path="tsumego" element={<TsumegoPage />} />
          <Route path="tsumego/problem/:problemId" element={<PhysicalBoardGuard><TsumegoProblemPage /></PhysicalBoardGuard>} />
          <Route path="tsumego/:level" element={<TsumegoCategoriesPage />} />
          <Route path="tsumego/:level/all" element={<TsumegoLevelPage />} />
          <Route path="tsumego/:level/:category" element={<TsumegoUnitsPage />} />
          <Route path="tsumego/:level/:category/:unit" element={<TsumegoUnitListPage />} />
          <Route path="research" element={<ResearchPage />} />
          <Route path="kifu" element={<KifuPage />} />
          <Route path="kifu/:kifuId" element={<PlaceholderPage />} />
          <Route path="baipu" element={<BaipuListPage />} />
          <Route path="baipu/session/:source" element={<PhysicalBoardGuard><BaipuSessionPage /></PhysicalBoardGuard>} />
          <Route path="live" element={<LivePage />} />
          <Route path="live/:matchId" element={<LiveMatchPage />} />
          {/* Tutorial (read-only mirror) — static `book`/`section` win over dynamic `:category` in v6 best-match */}
          <Route path="tutorial" element={<TutorialCategoriesPage />} />
          <Route path="tutorial/:category" element={<TutorialBooksPage />} />
          <Route path="tutorial/book/:bookId" element={<TutorialBookDetailPage />} />
          <Route path="tutorial/section/:sectionId" element={<TutorialSectionPage />} />
          <Route path="vision/setup" element={<VisionSetupPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="play" replace />} />
        </Route>
      </Route>
    </Routes>
  );
};

const KioskApp = () => {
  const { setLanguage } = useSettings();
  useEffect(() => {
    // The kiosk is a Chinese-market terminal: default to Simplified Chinese
    // unless the user has explicitly picked a language before (persisted in
    // localStorage by useSettings). Runs once on mount; a later user choice
    // in Settings wins because it writes the same localStorage key.
    if (!localStorage.getItem('katrain_language')) {
      setLanguage('cn');
    }
  }, [setLanguage]);

  // Kiosk tab title — scoped to kiosk routes so galaxy's shared index.html title is untouched.
  useEffect(() => {
    document.title = '智星盒 StellaBox';
  }, []);

  return (
    <ThemeProvider theme={kioskTheme}>
      <CssBaseline />
      <OrientationProvider>
        <VisionProvider>
          <GeometryProvider>
            <TsumegoProgressProvider>
              <RotationWrapper>
                <KioskRoutes />
              </RotationWrapper>
            </TsumegoProgressProvider>
          </GeometryProvider>
        </VisionProvider>
      </OrientationProvider>
    </ThemeProvider>
  );
};

export default KioskApp;
