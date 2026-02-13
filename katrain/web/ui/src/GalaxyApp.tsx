import { Routes, Route, Navigate, useParams } from 'react-router-dom';
import MainLayout from './galaxy/components/layout/MainLayout';
import Dashboard from './galaxy/pages/Dashboard';
import ResearchPage from './galaxy/pages/ResearchPage';
import PlayMenu from './galaxy/pages/PlayMenu';
import AiSetupPage from './galaxy/pages/AiSetupPage';
import GamePage from './galaxy/pages/GamePage';
import HvHLobbyPage from './galaxy/pages/HvHLobbyPage';
import GameRoomPage from './galaxy/pages/GameRoomPage';
import KifuLibraryPage from './galaxy/pages/KifuLibraryPage';
import LivePage from './galaxy/pages/live/LivePage';
import LiveMatchPage from './galaxy/pages/live/LiveMatchPage';
import TsumegoHubPage from './galaxy/pages/TsumegoHubPage';
import TsumegoLevelsPage from './galaxy/pages/TsumegoLevelsPage';
import TsumegoCategoriesPage from './galaxy/pages/TsumegoCategoriesPage';
import TsumegoListPage from './galaxy/pages/TsumegoListPage';
import TsumegoUnitsPage from './galaxy/pages/TsumegoUnitsPage';
import TsumegoProblemPage from './galaxy/pages/TsumegoProblemPage';
import AiSolverPage from './galaxy/pages/AiSolverPage';
import { AuthProvider } from './galaxy/context/AuthContext';
import { SettingsProvider } from './galaxy/context/SettingsContext';

// Helper component for backward-compatible redirects (React Router <Navigate> doesn't interpolate :param)
function RedirectWithParams({ to }: { to: (params: Record<string, string>) => string }) {
  const params = useParams();
  return <Navigate to={to(params as Record<string, string>)} replace />;
}

const GalaxyApp = () => {
  console.log("GalaxyApp rendering");
  return (
    <AuthProvider>
      <SettingsProvider>
        <Routes>
          <Route element={<MainLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="play" element={<PlayMenu />} />
          <Route path="play/ai" element={<AiSetupPage />} />
          <Route path="play/game/:sessionId" element={<GamePage />} />
          <Route path="play/human" element={<HvHLobbyPage />} />
          <Route path="play/human/room/:sessionId" element={<GameRoomPage />} />
          <Route path="research" element={<ResearchPage />} />
          <Route path="kifu" element={<KifuLibraryPage />} />
          <Route path="live" element={<LivePage />} />
          <Route path="live/:matchId" element={<LiveMatchPage />} />
          {/* Tsumego hub */}
          <Route path="tsumego" element={<TsumegoHubPage />} />
          {/* Tsumego workbook routes */}
          <Route path="tsumego/workbook" element={<TsumegoLevelsPage />} />
          <Route path="tsumego/workbook/:level" element={<TsumegoCategoriesPage />} />
          <Route path="tsumego/workbook/:level/:category" element={<TsumegoUnitsPage />} />
          <Route path="tsumego/workbook/:level/:category/:unit" element={<TsumegoListPage />} />
          {/* Tsumego AI solver */}
          <Route path="tsumego/ai-solver" element={<AiSolverPage />} />
          {/* Tsumego problem page (unchanged) */}
          <Route path="tsumego/problem/:problemId" element={<TsumegoProblemPage />} />
          {/* Backward-compatible redirects for old routes */}
          <Route path="tsumego/:level" element={<RedirectWithParams to={(p) => `/galaxy/tsumego/workbook/${p.level}`} />} />
          <Route path="tsumego/:level/:category" element={<RedirectWithParams to={(p) => `/galaxy/tsumego/workbook/${p.level}/${p.category}`} />} />
          <Route path="tsumego/:level/:category/:unit" element={<RedirectWithParams to={(p) => `/galaxy/tsumego/workbook/${p.level}/${p.category}/${p.unit}`} />} />
          <Route path="*" element={<Navigate to="/galaxy" replace />} />
        </Route>
      </Routes>
      </SettingsProvider>
    </AuthProvider>
  );
};

export default GalaxyApp;
