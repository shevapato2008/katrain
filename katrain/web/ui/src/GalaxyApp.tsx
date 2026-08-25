import { useMemo } from 'react';
import { Box, ThemeProvider } from '@mui/material';
import { Routes, Route, Navigate } from 'react-router-dom';
import { TsumegoProgressProvider } from './context/TsumegoProgressContext';
import { useSettings } from './context/SettingsContext';
import { createGalaxyTheme } from './galaxy/theme';
import './galaxy/assets/fonts/galaxy-fonts.css';
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
import TsumegoLevelsPage from './galaxy/pages/TsumegoLevelsPage';
import TsumegoCategoriesPage from './galaxy/pages/TsumegoCategoriesPage';
import TsumegoListPage from './galaxy/pages/TsumegoListPage';
import TsumegoUnitsPage from './galaxy/pages/TsumegoUnitsPage';
import TsumegoProblemPage from './galaxy/pages/TsumegoProblemPage';
import TutorialLandingPage from './galaxy/pages/tutorials/TutorialLandingPage';
import TutorialBooksPage from './galaxy/pages/tutorials/TutorialBooksPage';
import TutorialBookDetailPage from './galaxy/pages/tutorials/TutorialBookDetailPage';
import TutorialFigurePage from './galaxy/pages/tutorials/TutorialFigurePage';
import ReportsPage from './galaxy/pages/report/ReportsPage';
import ReportDetailPage from './galaxy/pages/report/ReportDetailPage';

const GalaxyApp = () => {
  const { language } = useSettings();
  const galaxyTheme = useMemo(() => createGalaxyTheme(language), [language]);

  console.log("GalaxyApp rendering");
  return (
    <ThemeProvider theme={galaxyTheme}>
      <Box
        className="galaxy-root"
        data-language={language}
        sx={{
          width: '100vw',
          height: '100dvh',
          overflow: 'hidden',
          fontSynthesis: 'none',
          /* galaxy 的「地板字体」。`theme.typography.*` 只能到达那些在自身根样式里展开了某个
             variant 的 MUI 组件（Button 展开 typography.button、Typography 按 variant 展开）；
             ButtonBase、裸 span/div、SVG <text> 一概拿不到，只能沿 DOM 继承。而继承链的顶端
             `<body>` 是**外层** zenTheme 的 CssBaseline 画的（AppRouter.tsx:30-31 → theme.ts:43
             的 `'Manrope', sans-serif`，零 CJK 字形，且 Manrope 全仓没有 @font-face），
             于是中文一路掉到系统默认字体 —— 同一页里 Typography 是霞鹜文楷、工具格按钮是黑体。
             这里把地板补在 galaxy 作用域的最外层，正是规范 §4.1「霞鹜文楷只在 cn/tw 两个中文
             locale 作用域内进入字体栈」说的那个作用域节点（它已经挂着 data-language）。
             取 `galaxyTheme` 的值而不是写死 CHINESE_UI_FONT：locale 门在 galaxy/theme.ts:8，
             写死等于把 jp/ko/en 也一并拖进中文字体栈。 */
          fontFamily: galaxyTheme.typography.fontFamily,
        }}
      >
        <TsumegoProgressProvider>
          <Routes>
          <Route element={<MainLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="play" element={<PlayMenu />} />
            <Route path="play/ai" element={<AiSetupPage />} />
            <Route path="play/game/:sessionId" element={<GamePage />} />
            <Route path="play/human" element={<HvHLobbyPage />} />
            <Route path="play/human/room/:sessionId" element={<GameRoomPage />} />
            <Route path="research" element={<ResearchPage />} />
            <Route path="report" element={<ReportsPage />} />
            <Route path="report/:taskId" element={<ReportDetailPage />} />
            <Route path="kifu" element={<KifuLibraryPage />} />
            <Route path="live" element={<LivePage />} />
            <Route path="live/:matchId" element={<LiveMatchPage />} />
            <Route path="tsumego" element={<TsumegoLevelsPage />} />
            <Route path="tsumego/:level" element={<TsumegoCategoriesPage />} />
            <Route path="tsumego/:level/:category" element={<TsumegoUnitsPage />} />
            <Route path="tsumego/:level/:category/:unit" element={<TsumegoListPage />} />
            <Route path="tsumego/problem/:problemId" element={<TsumegoProblemPage />} />
            <Route path="tutorials" element={<TutorialLandingPage />} />
            <Route path="tutorials/:category" element={<TutorialBooksPage />} />
            <Route path="tutorials/book/:bookId" element={<TutorialBookDetailPage />} />
            <Route path="tutorials/section/:sectionId" element={<TutorialFigurePage />} />
            <Route path="*" element={<Navigate to="/galaxy" replace />} />
          </Route>
          </Routes>
        </TsumegoProgressProvider>
      </Box>
    </ThemeProvider>
  );
};

export default GalaxyApp;
