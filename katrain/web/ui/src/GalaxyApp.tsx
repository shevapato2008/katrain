import { Routes, Route, Navigate } from 'react-router-dom';
import MainLayout from './galaxy/components/layout/MainLayout';
import Dashboard from './galaxy/pages/Dashboard';
import ResearchPage from './galaxy/pages/ResearchPage';
import PlayMenu from './galaxy/pages/PlayMenu';
import AiSetupPage from './galaxy/pages/AiSetupPage';
import GamePage from './galaxy/pages/GamePage';
import HvHLobbyPage from './galaxy/pages/HvHLobbyPage';
import GameRoomPage from './galaxy/pages/GameRoomPage';
import TsumegoLevelsPage from './galaxy/pages/TsumegoLevelsPage';
import TsumegoCategoriesPage from './galaxy/pages/TsumegoCategoriesPage';
import TsumegoListPage from './galaxy/pages/TsumegoListPage';
import { AuthProvider } from './galaxy/context/AuthContext';
import { SettingsProvider } from './galaxy/context/SettingsContext';

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
          <Route path="tsumego" element={<TsumegoLevelsPage />} />
          <Route path="tsumego/:level" element={<TsumegoCategoriesPage />} />
          <Route path="tsumego/:level/:category" element={<TsumegoListPage />} />
          <Route path="*" element={<Navigate to="/galaxy" replace />} />
        </Route>
      </Routes>
      </SettingsProvider>
    </AuthProvider>
  );
};

export default GalaxyApp;
