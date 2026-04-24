import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider, CssBaseline } from '@mui/material';
import { zenTheme } from './theme';
import { AuthProvider } from './context/AuthContext';
import { SettingsProvider } from './context/SettingsContext';
import ZenModeApp from './ZenModeApp';

// Code-split: kiosk and galaxy bundles load independently.
// Galaxy + VideoRecorder reach three.js (via Board3D / direct import),
// so they are excluded from the kiosk-2d build at the source level —
// the ternary collapses to `null` at compile time and Rollup drops
// the dynamic `import()` and its transitive chunk.
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
          <SettingsProvider>
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
