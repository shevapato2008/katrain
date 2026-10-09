import { lazy, Suspense, useMemo } from 'react';
import { Box, ThemeProvider } from '@mui/material';
import { Routes, Route, Navigate } from 'react-router-dom';
import { TsumegoProgressProvider } from './context/TsumegoProgressContext';
import { useSettings } from './context/SettingsContext';
import { createGalaxyTheme } from './galaxy/theme';
import './galaxy/assets/fonts/galaxy-fonts.css';
import './kiosk-shell/fonts.css';
import MainLayout from './galaxy/components/layout/MainLayout';
const Dashboard = lazy(() => import('./galaxy/pages/Dashboard'));
const ResearchPage = lazy(() => import('./galaxy/pages/ResearchPage'));
const PlayMenu = lazy(() => import('./galaxy/pages/PlayMenu'));
const AiSetupPage = lazy(() => import('./galaxy/pages/AiSetupPage'));
const GamePage = lazy(() => import('./galaxy/pages/GamePage'));
const HvHLobbyPage = lazy(() => import('./galaxy/pages/HvHLobbyPage'));
const GameRoomPage = lazy(() => import('./galaxy/pages/GameRoomPage'));
import KifuLibraryPage from './galaxy/pages/KifuLibraryPage';
const KifuReportDetailPage = lazy(() => import('./galaxy/pages/KifuReportDetailPage'));
const LivePage = lazy(() => import('./galaxy/pages/live/LivePage'));
const LiveMatchPage = lazy(() => import('./galaxy/pages/live/LiveMatchPage'));
const TsumegoLevelsPage = lazy(() => import('./galaxy/pages/TsumegoLevelsPage'));
const TsumegoCategoriesPage = lazy(() => import('./galaxy/pages/TsumegoCategoriesPage'));
const TsumegoListPage = lazy(() => import('./galaxy/pages/TsumegoListPage'));
const TsumegoUnitsPage = lazy(() => import('./galaxy/pages/TsumegoUnitsPage'));
const TsumegoProblemPage = lazy(() => import('./galaxy/pages/TsumegoProblemPage'));
const TutorialLandingPage = lazy(() => import('./galaxy/pages/tutorials/TutorialLandingPage'));
const TutorialBooksPage = lazy(() => import('./galaxy/pages/tutorials/TutorialBooksPage'));
const TutorialBookDetailPage = lazy(() => import('./galaxy/pages/tutorials/TutorialBookDetailPage'));
const TutorialFigurePage = lazy(() => import('./galaxy/pages/tutorials/TutorialFigurePage'));
const ReportsPage = lazy(() => import('./galaxy/pages/report/ReportsPage'));
const ReportDetailPage = lazy(() => import('./galaxy/pages/report/ReportDetailPage'));

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
          <Suspense fallback={null}><Routes>
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
            <Route path="kifu/:albumId/replay" element={<KifuReportDetailPage replayOnly />} />
            <Route path="kifu/:albumId/report" element={<KifuReportDetailPage />} />
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
          </Routes></Suspense>
        </TsumegoProgressProvider>
      </Box>
    </ThemeProvider>
  );
};

export default GalaxyApp;
