import { Box } from '@mui/material';
import { Outlet } from 'react-router-dom';
import { GameNavigationProvider } from '../../context/GameNavigationContext';
import GalaxyBottomNav from './GalaxyBottomNav';
import GalaxySidebar from './GalaxySidebar';
import GalaxyTopBar from './GalaxyTopBar';
import { useGalaxySidebar } from './useGalaxySidebar';

const MainLayoutChrome = () => {
  const sidebarState = useGalaxySidebar();
  const mobile = sidebarState.mode === 'mobile';

  return (
    <Box
      className="galaxy-root"
      sx={{ width: '100vw', height: '100dvh', overflow: 'hidden', display: 'flex', flexDirection: 'column', bgcolor: 'background.default' }}
    >
      <GalaxyTopBar />
      <Box sx={{ position: 'relative', display: 'flex', flex: 1, minHeight: 0 }}>
        {!mobile && <GalaxySidebar sidebarState={sidebarState} />}
        <Box
          component="main"
          data-testid="galaxy-main"
          /* `overflowY: 'auto'` 是 2026-08-23 补的，修一个既有缺陷：
             `galaxy-root` 是 `height:100dvh; overflow:hidden`（应用外壳不该整页滚，对的），
             而这里原来**没有 overflow** ⇒ 计算值 `visible`。于是「自己不管滚动」的内容页
             一旦比视口高，多出来的部分就被外壳静默裁掉、**滚轮推不动**。
             实测：1440x900 下死活题难度页内容高 1702 / 可视 848，三次滚轮纹丝不动；
             430 档 `/galaxy/play` 946 / 828 同病。棋盘页没事，因为 `BoardPageShell`
             自带 `height:100%` + 自己的 `overflowY:auto`。
             加在这一层而不是逐页加：缺陷在「谁负责滚」这条链上，不在某一页。
             对棋盘页是空操作 —— shell 的 `height:100%` 正好等于本容器内高，永不溢出。 */
          sx={{ flex: 1, minWidth: 0, minHeight: 0, display: 'flex', flexDirection: 'column', overflowY: 'auto', pb: 0, boxSizing: 'border-box' }}
        >
          <Outlet />
        </Box>
      </Box>
      {mobile && <GalaxyBottomNav />}
    </Box>
  );
};

const MainLayout = () => (
  <GameNavigationProvider>
    <MainLayoutChrome />
  </GameNavigationProvider>
);

export default MainLayout;
