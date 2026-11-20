// Isolated TEST artifact entry. This is intentionally separate from AppRouter
// and is never imported by the production application or its guarded routes.
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router-dom';
import { OGS_TEST_API_BASE } from '../../src/types/ogsVideo';
import { VisionProvider } from '../../src/kiosk/context/VisionContext';
import KioskViewport from '../../src/kiosk/components/layout/KioskViewport';
import { KioskFrame } from '../../src/kiosk/shell/KioskFrame';
import OgsCourseHomePage from '../../src/kiosk/pages/OgsCourseHomePage';
import OgsCourseChapterPage from '../../src/kiosk/pages/OgsCourseChapterPage';
import OgsCourseVideoPage from '../../src/kiosk/pages/OgsCourseVideoPage';
import OgsCourseExercisePage from '../../src/kiosk/pages/OgsCourseExercisePage';
import '../../src/kiosk-shell/fonts.css';
import '../../src/kiosk-shell/tokens.css';
import '../../src/kiosk-shell/go-tokens.css';
import './preview.css';

if (!OGS_TEST_API_BASE) throw new Error('The OGS TEST preview requires explicit TEST build configuration');

createRoot(document.getElementById('root')!).render(
  <BrowserRouter>
    <VisionProvider>
      <KioskViewport>
        <KioskFrame level={2} topbar={<header className="ogs-preview-topbar">
          <Link to="/kiosk/tutorial">OGS 围棋课程</Link>
          <span>TEST 只读预览 · 普通话视频</span>
        </header>}>
          <Routes>
            <Route path="/kiosk/tutorial" element={<OgsCourseHomePage />} />
            <Route path="/kiosk/tutorial/chapter/:chapterId" element={<OgsCourseChapterPage />} />
            <Route path="/kiosk/tutorial/lesson/:lessonId/videos" element={<OgsCourseVideoPage />} />
            <Route path="/kiosk/tutorial/lesson/:lessonId" element={<OgsCourseExercisePage />} />
            <Route path="/kiosk/tutorial/library" element={<section className="ogs-preview-library">
              <p>此 TEST 预览仅提供 OGS 课程；其他教材请使用正常应用入口。</p>
              <Link to="/kiosk/tutorial">返回 OGS 课程</Link>
            </section>} />
            <Route path="*" element={<Navigate to="/kiosk/tutorial" replace />} />
          </Routes>
        </KioskFrame>
      </KioskViewport>
    </VisionProvider>
  </BrowserRouter>,
);
