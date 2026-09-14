import { useMemo, useState } from 'react';
import {
  Avatar,
  Box,
  Button,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Typography,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import CloseIcon from '@mui/icons-material/Close';
import SettingsIcon from '@mui/icons-material/Settings';
import PhoneIphoneIcon from '@mui/icons-material/PhoneIphone';
import KeyIcon from '@mui/icons-material/Key';
import LogoutIcon from '@mui/icons-material/Logout';
import LoginIcon from '@mui/icons-material/Login';
import LanguageIcon from '@mui/icons-material/Language';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../../../context/AuthContext';
import { useSettings } from '../../../context/SettingsContext';
import { useTranslation } from '../../../hooks/useTranslation';
import { useGameNavigation } from '../../context/GameNavigationContext';
import LoginModal from '../auth/LoginModal';
import BindPhoneDialog from '../auth/BindPhoneDialog';
import { getGalaxyNavigation, isGalaxyNavigationActive } from './galaxyNavigation';
import type { GalaxySidebarState } from './useGalaxySidebar';

interface GalaxySidebarProps {
  sidebarState: GalaxySidebarState;
}

const SidebarContents = ({ overlay, closeOverlay }: { overlay: boolean; closeOverlay: () => void }) => {
  const { requestNavigation } = useGameNavigation();
  const location = useLocation();
  const { user, logout, phoneLoginEnabled } = useAuth();
  const { language, setLanguage, languages } = useSettings();
  const { t } = useTranslation();
  const items = useMemo(() => getGalaxyNavigation(t), [t]);
  const [loginOpen, setLoginOpen] = useState(false);
  const [settingsAnchorEl, setSettingsAnchorEl] = useState<HTMLElement | null>(null);
  const [bindOpen, setBindOpen] = useState(false);
  const [setPwOpen, setSetPwOpen] = useState(false);

  const navigate = (path: string) => {
    if (overlay) closeOverlay();
    requestNavigation(path);
  };

  const handleLogout = async () => {
    await logout();
    navigate('/galaxy');
  };

  return (
    <Box
      data-testid={overlay ? 'galaxy-sidebar-overlay' : undefined}
      sx={{ height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column', bgcolor: 'background.paper' }}
    >
      {overlay && (
        <Box sx={{ height: 52, px: 1, display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
          <IconButton
            aria-label={t('galaxy.close_navigation', 'Close navigation')}
            onClick={closeOverlay}
            style={{ width: 44, height: 44 }}
          >
            <CloseIcon />
          </IconButton>
        </Box>
      )}
      <List component="nav" data-testid="galaxy-sidebar-nav" style={{ overflowY: 'auto' }} sx={{ flex: 1, minHeight: 0, pt: overlay ? 0 : 2 }}>
        {items.map((item) => {
          const active = isGalaxyNavigationActive(location.pathname, item.path);
          return (
            <ListItemButton
              key={item.key}
              selected={active}
              onClick={() => navigate(item.path)}
              sx={{ mx: 1, borderRadius: 2, '&.Mui-selected': { bgcolor: 'primary.dark', '&:hover': { bgcolor: 'primary.dark' } } }}
            >
              <ListItemIcon sx={{ minWidth: 40, color: active ? 'primary.main' : 'text.secondary' }}>{item.icon}</ListItemIcon>
              <ListItemText
                primary={item.label}
                primaryTypographyProps={{ fontWeight: active ? 600 : 400, color: active ? 'text.primary' : 'text.secondary' }}
              />
            </ListItemButton>
          );
        })}
      </List>
      <Divider />
      <Box data-testid="galaxy-sidebar-account" sx={{ p: 2, flex: 'none' }}>
        <ListItemButton sx={{ borderRadius: 2, mb: 1 }} onClick={(event) => setSettingsAnchorEl(event.currentTarget)}>
          <ListItemIcon sx={{ minWidth: 40 }}><SettingsIcon /></ListItemIcon>
          <ListItemText primary={t('Settings', 'Settings')} />
        </ListItemButton>
        <Menu anchorEl={settingsAnchorEl} open={Boolean(settingsAnchorEl)} onClose={() => setSettingsAnchorEl(null)}>
          <Box sx={{ px: 2, py: 1 }}><Typography variant="overline" color="text.secondary">{t('Language', 'Language')}</Typography></Box>
          {languages.map((lang) => (
            <MenuItem
              key={lang.code}
              selected={language === lang.code}
              onClick={() => { setLanguage(lang.code); setSettingsAnchorEl(null); }}
              sx={{ minWidth: 160, display: 'flex', gap: 1 }}
            >
              <LanguageIcon fontSize="small" sx={{ color: 'text.secondary' }} />
              <ListItemText primary={lang.name} />
            </MenuItem>
          ))}
          {/* 账号那几项整组挂在 `phoneLoginEnabled` 上：绑号与改密码都要验证码，
              这台服务器没有手机功能时它们点下去只会撞上 404（`_guard_phone_endpoint`）。
              连分隔线一起收掉，否则菜单底部会剩一条指向空处的线。 */}
          {user && phoneLoginEnabled && <Divider sx={{ my: 0.5 }} />}
          {user && phoneLoginEnabled && !user.phone_bound && (
            <MenuItem
              onClick={() => { setBindOpen(true); setSettingsAnchorEl(null); }}
              sx={{ minWidth: 160, display: 'flex', gap: 1 }}
            >
              <PhoneIphoneIcon fontSize="small" sx={{ color: 'text.secondary' }} />
              <ListItemText primary={t('auth:bind_phone', '绑定手机号')} />
            </MenuItem>
          )}
          {user && phoneLoginEnabled && (
            <MenuItem
              onClick={() => { setSetPwOpen(true); setSettingsAnchorEl(null); }}
              sx={{ minWidth: 160, display: 'flex', gap: 1 }}
            >
              <KeyIcon fontSize="small" sx={{ color: 'text.secondary' }} />
              <ListItemText primary={t('auth:set_password', '修改密码')} />
            </MenuItem>
          )}
          {/* 已绑号只报状态，不给「换绑 / 解绑」—— 本轮没做那条路径，
              而 Task 11 的额度短路（不给未绑号建 allowance=0 的桶）正是以「不存在解绑」为前提的。 */}
          {user && phoneLoginEnabled && user.phone_bound && (
            <Box sx={{ px: 2, py: 1 }}>
              <Typography variant="caption" color="text.secondary">
                {t('auth:phone_bound_already', '手机号已绑定')}
              </Typography>
            </Box>
          )}
        </Menu>
        {user ? (
          <Box sx={{ p: 1.5, bgcolor: 'background.default', borderRadius: 2, display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Avatar sx={{ width: 32, height: 32, bgcolor: 'primary.main', fontSize: '0.75rem' }}>{user.rank === '20k' ? '?' : user.rank}</Avatar>
            <Box sx={{ flex: 1, minWidth: 0, overflow: 'hidden' }}>
              <Typography variant="subtitle2" noWrap>{user.username}</Typography>
              <Typography variant="caption" color="primary.main" sx={{ fontWeight: 600 }}>{user.rank === '20k' ? t('No Rank', 'No Rank') : user.rank}</Typography>
            </Box>
            <IconButton aria-label={t('Logout', 'Logout')} size="small" onClick={handleLogout}><LogoutIcon fontSize="small" /></IconButton>
          </Box>
        ) : (
          <Button variant="outlined" fullWidth startIcon={<LoginIcon />} onClick={() => setLoginOpen(true)}>{t('Login', 'Sign In')}</Button>
        )}
      </Box>
      <LoginModal open={loginOpen} onClose={() => setLoginOpen(false)} />
      <BindPhoneDialog open={bindOpen} onClose={() => setBindOpen(false)} />
      {/* 同一个壳，只换 purpose —— 改密码的前四步与绑定一模一样。 */}
      <BindPhoneDialog open={setPwOpen} purpose="set_password" onClose={() => setSetPwOpen(false)} />
    </Box>
  );
};

const GalaxySidebar = ({
  sidebarState: { mode, dockedWidth, dockedExpanded, overlayOpen, toggle, closeOverlay, toggleButtonRef },
}: GalaxySidebarProps) => {
  const { t } = useTranslation();
  if (mode === 'mobile') return null;

  const overlay = mode === 'narrow-overlay';
  const toggleLabel = overlay && overlayOpen
    ? t('galaxy.close_navigation', 'Close navigation')
    : dockedExpanded && !overlay
      ? t('galaxy.collapse_navigation', 'Collapse navigation')
      : t('galaxy.expand_navigation', 'Expand navigation');

  return (
    <>
      <Box
        data-testid="galaxy-sidebar-wrapper"
        style={{ width: dockedWidth }}
        sx={{ flex: `0 0 ${dockedWidth}px`, minWidth: 0, height: '100%', overflow: 'hidden', borderRight: dockedWidth ? '1px solid' : 0, borderColor: 'divider' }}
      >
        {!overlay && dockedExpanded && <SidebarContents overlay={false} closeOverlay={closeOverlay} />}
      </Box>
      <IconButton
        ref={toggleButtonRef}
        data-testid="galaxy-sidebar-toggle"
        aria-label={toggleLabel}
        aria-expanded={overlay ? overlayOpen : dockedExpanded}
        onClick={toggle}
        style={{
          width: 44,
          height: 44,
          position: 'absolute',
          left: dockedWidth,
          top: '50%',
          transform: 'translateY(-50%)',
        }}
        sx={{ zIndex: (theme) => theme.zIndex.drawer + 2, bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider' }}
      >
        {dockedExpanded && !overlay ? <ChevronLeftIcon /> : <MenuIcon />}
      </IconButton>
      {overlay && (
        <Drawer
          variant="temporary"
          open={overlayOpen}
          onClose={closeOverlay}
          ModalProps={{ keepMounted: false }}
          slotProps={{ paper: { sx: { width: 280, maxWidth: 'calc(100vw - 56px)' } } }}
        >
          <SidebarContents overlay closeOverlay={closeOverlay} />
        </Drawer>
      )}
    </>
  );
};

export default GalaxySidebar;
