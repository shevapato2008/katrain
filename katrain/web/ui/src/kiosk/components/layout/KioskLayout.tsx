import { Box } from '@mui/material';
import { Outlet, useLocation } from 'react-router-dom';
import { ImmersiveProvider, useImmersive } from '../../context/ImmersiveContext';
import { KioskFrame } from '../../shell/KioskFrame';
import Header from './Header';
import Dock from './Dock';
import SmartBoardConsole from './SmartBoardConsole';
import { L1_PATHS } from './navTabs';

const CONSOLE_ROUTES = ['/kiosk/play'];
interface KioskLayoutProps { username?: string }

const KioskShell = ({ username }: KioskLayoutProps) => {
  const { immersive } = useImmersive();
  const location = useLocation();
  const isL1 = L1_PATHS.includes(location.pathname);
  const showConsole = !immersive && CONSOLE_ROUTES.includes(location.pathname);
  const showDock = !immersive && isL1; // Dock only on first-level pages
  return (
    <KioskFrame
      level={showDock ? 1 : 2}
      topbar={immersive ? undefined : (
        // 过渡期垫片(Task 3 拆):`.kiosk-content` 是 `position:absolute; top:--topbar-h`,
        // 而旧 `Header` 是普通流里的 MUI Box —— 不钉住它,内容会盖在顶栏上。
        // 真顶栏(`.kiosk-topbar`)自己就带这套定位,那时这层 div 一起删。
        <div style={{ position: 'absolute', left: 0, right: 0, top: 0, zIndex: 2 }}>
          <Header
            username={username}
            showHome={isL1}
            onHome={() => window.location.assign('http://127.0.0.1:8080/launcher')}
          />
        </div>
      )}
      dock={showDock ? (
        // 同上(Task 4 拆)。⚠️ 旧 Dock 自己高 86,而 `--dock-h` 是 82 ——
        // 过渡期它会往上多盖 4px。Task 4 换成 `.kiosk-dock` 之后这 4px 自己消失,
        // 别在这里用 overflow:hidden 去裁它(那会把 Dock 自己切掉一条)。
        <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, zIndex: 2 }}>
          <Dock />
        </div>
      ) : undefined}
    >
      {/* 内容区暂时保持现状:左栏与 <Outlet/> 的两栏化留给 Task 5,
          本 Task 只把画布和作用域立起来 —— 一次只改一层,断点才定位得到。 */}
      <Box sx={{ display: 'flex', height: '100%', minHeight: 0 }}>
        {showConsole && <SmartBoardConsole />}
        <Box component="main" sx={{ flex: 1, minWidth: 0, minHeight: 0, overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
          <Outlet />
        </Box>
      </Box>
    </KioskFrame>
  );
};

const KioskLayout = ({ username }: KioskLayoutProps) => (
  <ImmersiveProvider>
    <KioskShell username={username} />
  </ImmersiveProvider>
);

export default KioskLayout;
