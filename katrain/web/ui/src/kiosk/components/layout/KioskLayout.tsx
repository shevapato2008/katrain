import { Box } from '@mui/material';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { ImmersiveProvider, useImmersive } from '../../context/ImmersiveContext';
import { KioskFrame } from '../../shell/KioskFrame';
import { KioskTopbar } from '../../shell/KioskTopbar';
import { KioskDock } from '../../shell/KioskDock';
import { dockLevelOf } from '../../shell/dockRoutes';
import { GoConsoleRail } from './GoConsoleRail';

/**
 * 哪些 L1 屏出左边的镜像栏。规范 §5 的判据是**「这个模块的活动会不会发生在实体盘上」**——
 * 对弈/训练营/课程/棋谱会,看直播不会。
 * 现在覆盖 `/kiosk/play`(Task 10)、`/kiosk/tsumego`(Task 12)、`/kiosk/kifu`(Task 15)
 * 和 `/kiosk/tutorial`(Task 17)。**棋谱这一项过判据靠的是摆谱**:选中的谱要一手一手
 * 摆到实体盘上、灯点着下一手,那正是「活动发生在实体盘上」;**课程过判据靠的是「课上的图
 * 会摆到盘上」**,同步行那句话说的就是它。
 * 复盘不走这条路 —— 它的左栏装的不是实体盘镜像,见下面的 `SELF_LAYOUT_ROUTES`。
 * ⚠️ 比的是**整条 pathname 相等**,不是前缀 —— `/kiosk/tsumego/15k` 是 L2,`dockLevelOf` 已经
 * 把它挡在外面了,但这里写成 `startsWith` 会让两条判据各说各的,而只有一条会被人记住。
 */
const RAIL_ROUTES = ['/kiosk/play', '/kiosk/tsumego', '/kiosk/kifu', '/kiosk/tutorial'];

/**
 * 自己拼两栏的屏。**复盘的左栏装的不是实体盘镜像**,是「选中的那一局」——
 * 它的内容跟着页面里的选中状态走,外壳拿不到那个状态,所以这一屏的
 * `.kiosk-layout-l1` 由页面自己出。外壳只负责别再往它外面套一层滚动容器
 * (那层 `<Box overflow:auto>` 会让 434 高的两栏在自己里面再滚一次)。
 */
const SELF_LAYOUT_ROUTES = ['/kiosk/report', '/kiosk/settings'];
interface KioskLayoutProps { username?: string }

const KioskShell = ({ username }: KioskLayoutProps) => {
  const { immersive } = useImmersive();
  const location = useLocation();
  const navigate = useNavigate();

  // 层级**只**由 dockRoutes 的词典说了算,不由路由前缀、也不由 immersive 说了算。
  // 一个真相来源:Dock 出不出、中间区 434 还是 516、主页键给不给,全从这一个数派生。
  const level = dockLevelOf(location.pathname);
  const showRail = !immersive && level === 1 && RAIL_ROUTES.includes(location.pathname);

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
      {/* ⚠️ `.kiosk-layout-l1` 是 `grid-template-columns: 296px 680px`(tokens.css:430),
          **右栏由页面自己提供根节点** —— `<Outlet/>` 渲染出来的那一层就是第二列。
          各屏改造完之前它们的老 `<Box>` 会直接落进网格第二列、尺寸当场变成 680,
          这是**预期的中间态**;Task 7 之后各屏的根换成 `.kiosk-side`。

          没有左栏的那一支保留旧的 `<Box component="main" overflow:auto>` 外壳:
          计划写的是裸 `<Outlet/>`,但那会把**每一个**二级页的滚动容器一起抽掉,而
          `.kiosk-content` 自己是 `overflow: visible` —— 内容会溢到 Dock 上。
          本 Task 只动有左栏的那一支,一次只改一层。 */}
      {showRail ? (
        <div className="kiosk-layout-l1">
          <GoConsoleRail
            // 课程屏那句同步行是「课上的图会摆到盘上 / 等选课」—— 规范 §5 允许的唯一差别。
            {...(location.pathname === '/kiosk/tutorial'
              ? { syncLeft: '课上的图会摆到盘上', syncRight: '等选课' }
              : {})}
          />
          <Outlet />
        </div>
      ) : level === 1 && SELF_LAYOUT_ROUTES.includes(location.pathname) ? (
        <Outlet />
      ) : (
        <Box component="main" sx={{ height: '100%', minHeight: 0, overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
          <Outlet />
        </Box>
      )}
    </KioskFrame>
  );
};

const KioskLayout = ({ username }: KioskLayoutProps) => (
  <ImmersiveProvider>
    <KioskShell username={username} />
  </ImmersiveProvider>
);

export default KioskLayout;
