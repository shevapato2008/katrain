import { useState } from 'react';
import { Box, List, ListItemButton, ListItemIcon, ListItemText, Typography, Avatar, Divider, Button, Menu, MenuItem } from '@mui/material';
import { useNavigate, useLocation } from 'react-router-dom';
import SportsEsportsIcon from '@mui/icons-material/SportsEsports';
import ScienceIcon from '@mui/icons-material/Science';
import AssessmentIcon from '@mui/icons-material/Assessment'; // Report
import LiveTvIcon from '@mui/icons-material/LiveTv'; // Live
import SettingsIcon from '@mui/icons-material/Settings';
import LogoutIcon from '@mui/icons-material/Logout';
import LoginIcon from '@mui/icons-material/Login';
import LanguageIcon from '@mui/icons-material/Language';
import { useAuth } from '../../context/AuthContext';
import { useSettings } from '../../context/SettingsContext';
import { i18n } from '../../../i18n';
import LoginModal from '../auth/LoginModal';

const GalaxySidebar = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const { language, setLanguage, languages } = useSettings();
  const [loginOpen, setLoginOpen] = useState(false);
  const [settingsAnchorEl, setSettingsAnchorEl] = useState<null | HTMLElement>(null);

  const handleLogout = async () => {
    await logout();
    // Navigate to home after logout
    navigate('/galaxy');
  };

  const handleSettingsClick = (event: React.MouseEvent<HTMLElement>) => {
    setSettingsAnchorEl(event.currentTarget);
  };

  const handleSettingsClose = () => {
    setSettingsAnchorEl(null);
  };

  const handleLanguageSelect = (code: string) => {
    setLanguage(code);
    handleSettingsClose();
  };

  const menuItems = [
    { text: i18n.t('btn:Play', 'Play'), icon: <SportsEsportsIcon />, path: '/galaxy/play', disabled: false },
    { text: i18n.t('Research', 'Research'), icon: <ScienceIcon />, path: '/galaxy/research', disabled: false }, // Will be protected later
    { text: i18n.t('analysis:report', 'Report'), icon: <AssessmentIcon />, path: '/galaxy/report', disabled: true },
    { text: i18n.t('Live', 'Live'), icon: <LiveTvIcon />, path: '/galaxy/live', disabled: false },
  ];

  return (
    <Box sx={{ 
      width: 240, 
      height: '100vh', 
      bgcolor: 'background.paper', 
      borderRight: '1px solid rgba(255,255,255,0.05)',
      display: 'flex',
      flexDirection: 'column'
    }}>
      {/* Logo Area */}
      <Box sx={{ p: 3, display: 'flex', alignItems: 'center', gap: 2, cursor: 'pointer' }} onClick={() => navigate('/galaxy')}>
         {/* Use existing icon or placeholder */}
         <Box sx={{ width: 32, height: 32, bgcolor: 'primary.main', borderRadius: '50%' }} /> 
         <Typography variant="h6" fontWeight="bold">Galaxy Go</Typography>
      </Box>

      <Divider sx={{ mb: 2 }} />

      {/* Navigation */}
      <List component="nav" sx={{ flexGrow: 1 }}>
        {menuItems.map((item) => {
          const isActive = location.pathname.startsWith(item.path);
          return (
            <ListItemButton 
              key={item.text} 
              onClick={() => !item.disabled && navigate(item.path)}
              disabled={item.disabled}
              selected={isActive}
              sx={{
                mx: 1,
                borderRadius: 2,
                '&.Mui-selected': {
                    bgcolor: 'primary.dark',
                    '&:hover': { bgcolor: 'primary.dark' }
                }
              }}
            >
              <ListItemIcon sx={{ minWidth: 40, color: isActive ? 'primary.main' : 'text.secondary' }}>
                {item.icon}
              </ListItemIcon>
              <ListItemText 
                primary={item.text} 
                primaryTypographyProps={{ 
                    fontWeight: isActive ? 600 : 400,
                    color: isActive ? 'text.primary' : 'text.secondary'
                }} 
              />
            </ListItemButton>
          );
        })}
      </List>

      <Divider sx={{ mt: 2 }} />

      {/* Bottom Area: Settings & User */}
      <Box sx={{ p: 2 }}>
        <ListItemButton 
          sx={{ borderRadius: 2, mb: 1 }}
          onClick={handleSettingsClick}
        >
            <ListItemIcon sx={{ minWidth: 40 }}><SettingsIcon /></ListItemIcon>
            <ListItemText primary={i18n.t('Settings', 'Settings')} />
        </ListItemButton>

        <Menu
          anchorEl={settingsAnchorEl}
          open={Boolean(settingsAnchorEl)}
          onClose={handleSettingsClose}
          anchorOrigin={{
            vertical: 'top',
            horizontal: 'right',
          }}
          transformOrigin={{
            vertical: 'bottom',
            horizontal: 'left',
          }}
          sx={{ mb: 2 }}
        >
          <Box sx={{ px: 2, py: 1 }}>
            <Typography variant="overline" color="text.secondary">{i18n.t('Language', 'Language')}</Typography>
          </Box>
          {languages.map((lang) => (
            <MenuItem 
              key={lang.code} 
              onClick={() => handleLanguageSelect(lang.code)}
              selected={language === lang.code}
              sx={{ minWidth: 160, display: 'flex', gap: 1 }}
            >
              <LanguageIcon fontSize="small" sx={{ color: 'text.secondary' }} />
              <ListItemText primary={lang.name} />
            </MenuItem>
          ))}
        </Menu>

        {user ? (
            <Box sx={{ p: 1.5, bgcolor: 'background.default', borderRadius: 2, display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <Avatar sx={{ width: 32, height: 32, bgcolor: 'primary.main', fontSize: '0.75rem' }}>
                    {user.rank === '20k' ? '?' : user.rank}
                </Avatar>
                <Box sx={{ flexGrow: 1, minWidth: 0, overflow: 'hidden' }}>
                    <Typography variant="subtitle2" noWrap>{user.username}</Typography>
                    <Typography variant="caption" color="primary.main" sx={{ fontWeight: 600 }}>
                        {user.rank === '20k' ? 'No Rank' : user.rank}
                    </Typography>
                </Box>
                <LogoutIcon fontSize="small" sx={{ color: 'text.secondary', cursor: 'pointer' }} onClick={handleLogout} />
            </Box>
        ) : (
            <Button 
                variant="outlined" 
                fullWidth 
                startIcon={<LoginIcon />}
                onClick={() => setLoginOpen(true)}
            >
                {i18n.t('Login', 'Sign In')}
            </Button>
        )}
      </Box>
      <LoginModal open={loginOpen} onClose={() => setLoginOpen(false)} />
    </Box>
  );
};

export default GalaxySidebar;