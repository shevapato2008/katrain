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
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import SettingsIcon from '@mui/icons-material/Settings';
import LogoutIcon from '@mui/icons-material/Logout';
import LoginIcon from '@mui/icons-material/Login';
import LanguageIcon from '@mui/icons-material/Language';
import GridOnIcon from '@mui/icons-material/GridOn';
import ContrastIcon from '@mui/icons-material/Contrast';
import TextFieldsIcon from '@mui/icons-material/TextFields';
import { useLocation } from 'react-router-dom';
import {
  BOARD_STYLE_OPTIONS,
  CHINESE_FONT_OPTIONS,
  STONE_STYLE_OPTIONS,
  useBoardAppearance,
  type StoneStyleOption,
} from '../../../components/board/stoneAppearance';
import { useAuth } from '../../../context/AuthContext';
import { useSettings } from '../../../context/SettingsContext';
import { useTranslation } from '../../../hooks/useTranslation';
import { useGameNavigation } from '../../context/GameNavigationContext';
import LoginModal from '../auth/LoginModal';
import { getGalaxyNavigation, isGalaxyNavigationActive } from './galaxyNavigation';
import type { GalaxySidebarState } from './useGalaxySidebar';

interface GalaxySidebarProps {
  sidebarState: GalaxySidebarState;
}

type SettingsSubMenu = null | 'language' | 'boardStyle' | 'stoneStyle' | 'chineseFont';

const StonePairBadge = ({ option, size = 14 }: { option: StoneStyleOption; size?: number }) => (
  <Box sx={{ display: 'inline-flex', alignItems: 'center', position: 'relative', width: size * 1.65, height: size, flexShrink: 0 }}>
    <Box
      sx={{
        width: size,
        height: size,
        borderRadius: '50%',
        bgcolor: option.blackSwatch,
        border: '1px solid',
        borderColor: option.rimColor ?? 'rgba(255,255,255,0.22)',
        boxShadow: '0 1px 2px rgba(0,0,0,0.45)',
      }}
    />
    <Box
      sx={{
        width: size,
        height: size,
        borderRadius: '50%',
        bgcolor: option.whiteSwatch,
        border: '1px solid rgba(0,0,0,0.25)',
        boxShadow: '0 1px 2px rgba(0,0,0,0.25)',
        position: 'absolute',
        left: size * 0.62,
      }}
    />
  </Box>
);

const SidebarContents = ({ overlay, closeOverlay }: { overlay: boolean; closeOverlay: () => void }) => {
  const { requestNavigation } = useGameNavigation();
  const location = useLocation();
  const { user, logout } = useAuth();
  const settings = useSettings();
  const appearance = useBoardAppearance();
  const { language, setLanguage, languages } = settings;
  const activeBoardStyle = settings.boardStyle ?? appearance.boardStyle;
  const activeStoneStyle = settings.stoneStyle ?? appearance.stoneStyle;
  const activeChineseFont = settings.chineseFont ?? 'wenkai';
  const { t } = useTranslation();
  const items = useMemo(() => getGalaxyNavigation(t), [t]);
  const [loginOpen, setLoginOpen] = useState(false);
  const [settingsAnchorEl, setSettingsAnchorEl] = useState<HTMLElement | null>(null);
  const [settingsSubMenu, setSettingsSubMenu] = useState<SettingsSubMenu>(null);

  const handleCloseLangMenu = () => {
    setSettingsAnchorEl(null);
    setSettingsSubMenu(null);
  };

  const currentLanguageName = languages.find((lang) => lang.code === language)?.name ?? '中文';
  const currentBoardOption = BOARD_STYLE_OPTIONS.find((opt) => opt.id === activeBoardStyle) ?? BOARD_STYLE_OPTIONS[0];
  const currentStoneOption = STONE_STYLE_OPTIONS.find((opt) => opt.id === activeStoneStyle) ?? STONE_STYLE_OPTIONS[0];
  const currentFontOption = CHINESE_FONT_OPTIONS.find((opt) => opt.id === activeChineseFont) ?? CHINESE_FONT_OPTIONS[0];

  const subMenuTitle =
    settingsSubMenu === 'language'
      ? t('settings.language', '语言')
      : settingsSubMenu === 'boardStyle'
        ? t('settings.board_style', '棋盘样式')
        : settingsSubMenu === 'stoneStyle'
          ? t('settings.stone_style', '棋子样式')
          : settingsSubMenu === 'chineseFont'
            ? t('settings.chinese_font', '中文字体')
            : '';

  const navigate = (path: string) => {
    if (overlay) closeOverlay();
    requestNavigation(path);
  };

  const handleLogout = async () => {
    await logout();
    navigate('/');
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
        <ListItemButton
          aria-label={t('sidebar.settings', '设置')}
          sx={{ borderRadius: 2, mb: 1 }}
          onClick={(event) => {
            setSettingsSubMenu(null);
            setSettingsAnchorEl(event.currentTarget);
          }}
        >
          <ListItemIcon sx={{ minWidth: 40 }}><SettingsIcon /></ListItemIcon>
          <ListItemText primary={t('Settings', 'Settings')} />
        </ListItemButton>
        <Menu
          anchorEl={settingsAnchorEl}
          open={Boolean(settingsAnchorEl)}
          onClose={handleCloseLangMenu}
          slotProps={{ paper: { sx: { minWidth: 260, borderRadius: 2 } } }}
        >
          {settingsSubMenu === null ? (
            <Box>
              <Box sx={{ px: 2, py: 1 }}>
                <Typography variant="overline" color="text.secondary">
                  {t('sidebar.settings', '设置')}
                </Typography>
              </Box>
              <MenuItem
                onClick={() => setSettingsSubMenu('language')}
                sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1.5, py: 1 }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
                  <LanguageIcon fontSize="small" sx={{ color: 'text.secondary' }} />
                  <Typography variant="body2">{t('settings.language', '语言')}</Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, color: 'text.secondary' }}>
                  <Typography variant="caption" color="text.secondary">{currentLanguageName}</Typography>
                  <ChevronRightIcon fontSize="small" />
                </Box>
              </MenuItem>
              <MenuItem
                onClick={() => setSettingsSubMenu('boardStyle')}
                sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1.5, py: 1 }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
                  <GridOnIcon fontSize="small" sx={{ color: 'text.secondary' }} />
                  <Typography variant="body2">{t('settings.board_style', '棋盘样式')}</Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, color: 'text.secondary' }}>
                  <Box
                    sx={{
                      width: 14,
                      height: 14,
                      borderRadius: '50%',
                      bgcolor: currentBoardOption.swatch,
                      border: '1px solid',
                      borderColor: currentBoardOption.borderColor,
                      flexShrink: 0,
                    }}
                  />
                  <Typography variant="caption" color="text.secondary">{currentBoardOption.label}</Typography>
                  <ChevronRightIcon fontSize="small" />
                </Box>
              </MenuItem>
              <MenuItem
                onClick={() => setSettingsSubMenu('stoneStyle')}
                sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1.5, py: 1 }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
                  <ContrastIcon fontSize="small" sx={{ color: 'text.secondary' }} />
                  <Typography variant="body2">{t('settings.stone_style', '棋子样式')}</Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, color: 'text.secondary' }}>
                  <StonePairBadge option={currentStoneOption} size={13} />
                  <Typography variant="caption" color="text.secondary">{currentStoneOption.label}</Typography>
                  <ChevronRightIcon fontSize="small" />
                </Box>
              </MenuItem>
              <MenuItem
                onClick={() => setSettingsSubMenu('chineseFont')}
                sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1.5, py: 1 }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
                  <TextFieldsIcon fontSize="small" sx={{ color: 'text.secondary' }} />
                  <Typography variant="body2">{t('settings.chinese_font', '中文字体')}</Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, color: 'text.secondary' }}>
                  <Typography variant="caption" color="text.secondary">{currentFontOption.label}</Typography>
                  <ChevronRightIcon fontSize="small" />
                </Box>
              </MenuItem>
            </Box>
          ) : (
            <Box>
              <MenuItem
                onClick={() => setSettingsSubMenu(null)}
                sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 1 }}
              >
                <ChevronLeftIcon fontSize="small" sx={{ color: 'text.secondary' }} />
                <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                  {t('settings.back', '返回设置')}
                </Typography>
                <Typography variant="body2" sx={{ ml: 'auto', fontWeight: 600 }}>
                  {subMenuTitle}
                </Typography>
              </MenuItem>
              <Divider sx={{ my: 0.5 }} />
              {settingsSubMenu === 'language' &&
                languages.map((lang) => {
                  const isSelected = language === lang.code;
                  return (
                    <MenuItem
                      key={lang.code}
                      selected={isSelected}
                      onClick={() => {
                        void setLanguage(lang.code);
                      }}
                      sx={{ minWidth: 220, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1.5 }}
                    >
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <LanguageIcon fontSize="small" sx={{ color: 'text.secondary' }} />
                        <ListItemText primary={lang.name} />
                      </Box>
                      {isSelected && <CheckIcon fontSize="small" color="primary" />}
                    </MenuItem>
                  );
                })}
              {settingsSubMenu === 'boardStyle' &&
                BOARD_STYLE_OPTIONS.map((opt) => {
                  const isSelected = activeBoardStyle === opt.id;
                  return (
                    <MenuItem
                      key={opt.id}
                      selected={isSelected}
                      onClick={() => {
                        appearance.setBoardStyle(opt.id);
                        settings.setBoardStyle?.(opt.id);
                      }}
                      sx={{ minWidth: 240, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1.5, py: 1 }}
                    >
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
                        <Box
                          sx={{
                            width: 20,
                            height: 20,
                            borderRadius: 1,
                            bgcolor: opt.swatch,
                            border: '1px solid',
                            borderColor: opt.borderColor,
                            flexShrink: 0,
                          }}
                        />
                        <Box>
                          <Typography variant="body2" sx={{ fontWeight: isSelected ? 600 : 400 }}>{opt.label}</Typography>
                          <Typography variant="caption" color="text.secondary">{opt.subtitle}</Typography>
                        </Box>
                      </Box>
                      {isSelected && <CheckIcon fontSize="small" color="primary" />}
                    </MenuItem>
                  );
                })}
              {settingsSubMenu === 'stoneStyle' &&
                STONE_STYLE_OPTIONS.map((opt) => {
                  const isSelected = activeStoneStyle === opt.id;
                  return (
                    <MenuItem
                      key={opt.id}
                      selected={isSelected}
                      onClick={() => {
                        appearance.setStoneStyle(opt.id);
                        settings.setStoneStyle?.(opt.id);
                      }}
                      sx={{ minWidth: 240, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1.5, py: 1 }}
                    >
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
                        <StonePairBadge option={opt} size={16} />
                        <Box>
                          <Typography variant="body2" sx={{ fontWeight: isSelected ? 600 : 400 }}>{opt.label}</Typography>
                          <Typography variant="caption" color="text.secondary">{opt.subtitle}</Typography>
                        </Box>
                      </Box>
                      {isSelected && <CheckIcon fontSize="small" color="primary" />}
                    </MenuItem>
                  );
                })}
              {settingsSubMenu === 'chineseFont' &&
                CHINESE_FONT_OPTIONS.map((opt) => {
                  const isSelected = activeChineseFont === opt.id;
                  return (
                    <MenuItem
                      key={opt.id}
                      selected={isSelected}
                      onClick={() => {
                        settings.setChineseFont?.(opt.id);
                      }}
                      sx={{ minWidth: 240, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1.5, py: 1 }}
                    >
                      <Box>
                        <Typography
                          variant="body2"
                          sx={{ fontFamily: opt.fontFamily, fontWeight: isSelected ? 600 : 400 }}
                        >
                          {opt.label}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">{opt.subtitle}</Typography>
                      </Box>
                      {isSelected && <CheckIcon fontSize="small" color="primary" />}
                    </MenuItem>
                  );
                })}
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
          left: Math.max(0, dockedWidth - 22),
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
