import { useMemo, useState, type ReactElement } from 'react';
import { BottomNavigation, BottomNavigationAction, Menu, MenuItem, Paper } from '@mui/material';
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import PhoneIphoneIcon from '@mui/icons-material/PhoneIphone';
import KeyIcon from '@mui/icons-material/Key';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../../../context/AuthContext';
import { useTranslation } from '../../../hooks/useTranslation';
import { useGameNavigation } from '../../context/GameNavigationContext';
import BindPhoneDialog from '../auth/BindPhoneDialog';
import { getGalaxyNavigation, isGalaxyNavigationActive } from './galaxyNavigation';

export const GALAXY_BOTTOM_NAV_HEIGHT = 64;

interface MoreMenuState {
  pathname: string;
  anchor: HTMLElement | null;
}

/** 「更多」菜单里的一项有两种形态：**去一条路由**，或者**就地开一个对话框**。
 *
 *  不给对话框编一个假 path 再在 `requestNavigation` 里特判 —— 那是把「开对话框」
 *  伪装成「导航」：下一个读这段代码的人会拿着那个 path 去 `galaxyNavigation.tsx`
 *  里找一条根本不存在的路由，而 `isGalaxyNavigationActive` 还会拿它跟 pathname 比。 */
type MoreEntry =
  | { kind: 'route'; key: string; label: string; icon: ReactElement; path: string }
  | { kind: 'dialog'; key: string; label: string; icon: ReactElement; open: () => void };

const GalaxyBottomNav = () => {
  const { t } = useTranslation();
  const { user, phoneLoginEnabled } = useAuth();
  const { requestNavigation } = useGameNavigation();
  const { pathname } = useLocation();
  const items = useMemo(() => getGalaxyNavigation(t), [t]);
  const directItems = items.slice(0, 5);
  const [moreMenu, setMoreMenu] = useState<MoreMenuState>({ pathname, anchor: null });
  const [bindOpen, setBindOpen] = useState(false);
  const [setPwOpen, setSetPwOpen] = useState(false);
  const moreMenuIdentityChanged = moreMenu.pathname !== pathname;
  if (moreMenuIdentityChanged) setMoreMenu({ pathname, anchor: null });
  const moreAnchor = moreMenuIdentityChanged ? null : moreMenu.anchor;

  /* 账号那两项本来只在侧栏的「设置」菜单里（GalaxySidebar.tsx:117-134），而移动档整个
     侧栏不挂（MainLayout.tsx:21）⇒ 拿手机打开的人**绑不了号也改不了密码**，而验证码
     登录本身就是个手机功能。这里是侧栏那个「设置」菜单在移动档的对应物，逐条照搬它的
     显示条件：没账号就没有可绑的对象；已绑号本轮不做换绑/解绑（同 :135-136 的口径）。 */
  /* 整组挂在 `phoneLoginEnabled` 上 —— 与侧栏那个「设置」菜单同一条口径
     （GalaxySidebar.tsx 的 `user && phoneLoginEnabled && …`）：绑号与改密码都要验证码，
     这台服务器没有手机功能时它们点下去只会撞上 404。 */
  const accountEntries: MoreEntry[] = !phoneLoginEnabled ? [] : [
    ...(user && !user.phone_bound
      ? [{
        kind: 'dialog' as const,
        key: 'bind-phone',
        label: t('auth:bind_phone', '绑定手机号'),
        icon: <PhoneIphoneIcon />,
        open: () => setBindOpen(true),
      }]
      : []),
    ...(user
      ? [{
        kind: 'dialog' as const,
        key: 'set-password',
        label: t('auth:set_password', '修改密码'),
        icon: <KeyIcon />,
        open: () => setSetPwOpen(true),
      }]
      : []),
  ];
  const moreEntries: MoreEntry[] = [
    ...items.slice(5).map((item) => ({ kind: 'route' as const, ...item })),
    ...accountEntries,
  ];

  const activeItem = items.find((item) => isGalaxyNavigationActive(pathname, item.path));

  return (
    <Paper
      component="nav"
      aria-label={t('galaxy.primary_navigation', 'Primary navigation')}
      data-testid="galaxy-bottom-nav"
      elevation={10}
      style={{ position: 'fixed' }}
      sx={{ left: 0, right: 0, bottom: 0, zIndex: (theme) => theme.zIndex.appBar, pb: 'env(safe-area-inset-bottom)' }}
    >
      <BottomNavigation value={activeItem?.key ?? false} showLabels sx={{ height: GALAXY_BOTTOM_NAV_HEIGHT }}>
        {directItems.map((item) => (
          <BottomNavigationAction
            key={item.key}
            data-testid="galaxy-bottom-destination"
            value={item.key}
            label={item.label}
            aria-label={item.label}
            icon={item.icon}
            onClick={() => requestNavigation(item.path)}
          />
        ))}
        <BottomNavigationAction
          value="more"
          label={t('More', 'More')}
          aria-label={t('More', 'More')}
          icon={<MoreHorizIcon />}
          onClick={(event) => setMoreMenu({ pathname, anchor: event.currentTarget })}
        />
      </BottomNavigation>
      <Menu anchorEl={moreAnchor} open={Boolean(moreAnchor)} onClose={() => setMoreMenu({ pathname, anchor: null })}>
        {moreEntries.map((entry) => (
          <MenuItem
            key={entry.key}
            selected={entry.kind === 'route' && isGalaxyNavigationActive(pathname, entry.path)}
            onClick={() => {
              setMoreMenu({ pathname, anchor: null });
              if (entry.kind === 'route') requestNavigation(entry.path);
              else entry.open();
            }}
          >
            {entry.icon}
            {entry.label}
          </MenuItem>
        ))}
      </Menu>
      {/* 与侧栏 GalaxySidebar.tsx:159-161 同一条口径：同一个壳，只换 purpose。
          对话框本来就设计成可多处挂载（billing/FreeQuotaNotice.tsx:67 是第二处先例）。 */}
      <BindPhoneDialog open={bindOpen} onClose={() => setBindOpen(false)} />
      <BindPhoneDialog open={setPwOpen} purpose="set_password" onClose={() => setSetPwOpen(false)} />
    </Paper>
  );
};

export default GalaxyBottomNav;
