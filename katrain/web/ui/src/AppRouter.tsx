import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider, CssBaseline } from '@mui/material';
import { zenTheme } from './theme';
import { AuthProvider } from './context/AuthContext';
import { SettingsProvider } from './context/SettingsContext';
import ZenModeApp from './ZenModeApp';

// Code-split: kiosk and galaxy bundles load independently.
// Galaxy + VideoRecorder reach three.js (via Board3D / direct import),
// so they are excluded from the kiosk-2d build. Vite's `define`
// substitutes __KIOSK_2D_ONLY__ with the literal true/false before
// Rollup runs, making the unused branch eligible for tree-shaking.
// npm run verify:kiosk-2d is the final gate against regressions.
const KioskApp = lazy(() => import('./kiosk/KioskApp'));
const GalaxyApp = __KIOSK_2D_ONLY__
  ? null
  : lazy(() => import('./GalaxyApp'));
const VideoRecorderPage = __KIOSK_2D_ONLY__
  ? null
  : lazy(() => import('./pages/VideoRecorderPage'));

const AppRouter = () => {
  return (
    <ThemeProvider theme={zenTheme}>
      <CssBaseline />
      <BrowserRouter>
        <AuthProvider>
          <SettingsProvider defaultLanguage={__KIOSK_2D_ONLY__ ? 'cn' : undefined}>
            <Suspense fallback={null}>
              <Routes>
                <Route path="/kiosk/*" element={<KioskApp />} />
                {!__KIOSK_2D_ONLY__ && GalaxyApp && (
                  <Route path="/galaxy/*" element={<GalaxyApp />} />
                )}
                {!__KIOSK_2D_ONLY__ && VideoRecorderPage && (
                  <Route path="/record" element={<VideoRecorderPage />} />
                )}
                <Route path="/*" element={<ZenModeApp />} />
              </Routes>
            </Suspense>
          </SettingsProvider>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
};

export default AppRouter;
