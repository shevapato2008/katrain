// 共享外壳的样式,**全站只在这里引一次**,顺序不可换:
//   fonts.css   先声明字族,tokens.css 的 --font-* 才指得到它;
//   tokens.css  991 行几何与结构类,整份定义在 `.kiosk {}` 里(见 shell/KioskFrame.tsx);
//   go-tokens.css 给共享外壳那组「各棋类必须自行赋值」的语义色赋围棋青毡,必须在 tokens.css 之后;
//   seclabel.css 组标题;
//   icon.css     `.kiosk-icon` 包裹层(display:contents);
//   card.css     模式卡的 is-soon / .soon / .dot 三个状态(tokens.css 里没有)。
// 后三个是**本地补的**(共享 tokens.css 里没有这些规则),必须排在 tokens.css 之后 ——
// card.css 里有一条 `.kiosk-card { position: relative }` 和 tokens.css 的 `.kiosk-card`
// 同名同权重,靠后来居上生效。
// go-screens.css(围棋屏级类)Task 9 才建,那之前不要加进来。
//
// 引在 KioskApp.tsx 而不是 main.tsx:AppRouter 是 lazy(() => import('./kiosk/KioskApp')),
// 引在这里 CSS 就落进 kiosk 分块,galaxy 不受影响;kiosk-2d 构建里 galaxy 整条被 DCE。
import '../kiosk-shell/fonts.css';
import '../kiosk-shell/tokens.css';
import '../kiosk-shell/go-tokens.css';
import '../kiosk-shell/seclabel.css';
import '../kiosk-shell/icon.css';
import '../kiosk-shell/card.css';

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
import GameHistoryPage from './pages/GameHistoryPage';
import BaipuListPage from './pages/BaipuListPage';
import BaipuSessionPage from './pages/BaipuSessionPage';
import LivePage from './pages/LivePage';
import LiveMatchPage from './pages/LiveMatchPage';
import LobbyPage from './pages/LobbyPage';
import SettingsPage from './pages/SettingsPage';
import ReportsPage from './pages/ReportsPage';
import ReportDetailPage from './pages/ReportDetailPage';
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
          {/* 升降级对弈 has its own page: nothing about the opponent is chosen here,
              so it shares no controls with free play. Static path wins over the
              dynamic :mode below in v6 best-match. */}
          <Route path="play/ai/setup/:mode" element={<AiSetupPage />} />
          <Route path="play/pvp/setup" element={<PvpLocalSetupPage />} />
          <Route path="play/pvp/lobby" element={<LobbyPage />} />
          <Route path="play/pvp/history" element={<GameHistoryPage />} />
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
          <Route path="report" element={<ReportsPage />} />
          <Route path="report/:taskId" element={<ReportDetailPage />} />
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
