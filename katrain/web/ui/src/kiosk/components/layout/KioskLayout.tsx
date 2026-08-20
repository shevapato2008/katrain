import { Box } from '@mui/material';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { ImmersiveProvider, useImmersive } from '../../context/ImmersiveContext';
import { KioskFrame } from '../../shell/KioskFrame';
import { KioskTopbar } from '../../shell/KioskTopbar';
import { KioskDock } from '../../shell/KioskDock';
import { dockLevelOf } from '../../shell/dockRoutes';
import SmartBoardConsole from './SmartBoardConsole';

const CONSOLE_ROUTES = ['/kiosk/play'];
interface KioskLayoutProps { username?: string }

const KioskShell = ({ username }: KioskLayoutProps) => {
  const { immersive } = useImmersive();
  const location = useLocation();
  const navigate = useNavigate();

  // 层级**只**由 dockRoutes 的词典说了算,不由路由前缀、也不由 immersive 说了算。
  // 一个真相来源:Dock 出不出、中间区 434 还是 516、主页键给不给,全从这一个数派生。
  const level = dockLevelOf(location.pathname);
  const showConsole = !immersive && CONSOLE_ROUTES.includes(location.pathname);

  return (
    <KioskFrame
      level={level}
      // ⚠️ 已登记的冲突(Task 4):`immersive` 会把顶栏一起抽掉,而规范 §5 防跳铁律 1
      // 写死「顶栏永远占 y 0–56,任何层级、任何模块都不变高、不隐藏」。本 Task 只把
      // **Dock** 归 `dockLevelOf` 管,`immersive` 对顶栏的作用先原样留着 ——
      // 它有五个消费者(研究/复盘详情/摆谱对局/做题/直播),删它超出本 Task 的范围。
      topbar={immersive ? undefined : (
        <KioskTopbar
          identity={{ username }}
          // 主页键只在一级页出现(规范 §6「一级页面可在固定系统动作区显示主页入口」)。
          // 二/三级页要退的是**这一屏**,那是页控条上的返回,不是回智星盒主页。
          onHome={level === 1 ? () => window.location.assign('http://127.0.0.1:8080/launcher') : undefined}
        />
      )}
      // Dock 不再看 immersive:今天五个设 immersive 的页面全在 L2,`level === 1` 已经把它们
      // 挡在外面了,再叠一个条件只会多出一条永远不走的分支。
      dock={level === 1 ? (
        <KioskDock pathname={location.pathname} onTab={(p) => navigate(p)} />
      ) : undefined}
    >
      {/* 内容区暂时保持现状:左栏与 <Outlet/> 的两栏化留给 Task 5,
          本 Task 只换 Dock 和层级判定 —— 一次只改一层,断点才定位得到。 */}
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
