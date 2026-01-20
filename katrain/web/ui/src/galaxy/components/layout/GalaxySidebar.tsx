import { useState } from 'react';
import { Box, List, ListItemButton, ListItemIcon, ListItemText, Typography, Avatar, Divider, Button } from '@mui/material';
import { useNavigate, useLocation } from 'react-router-dom';
import SportsEsportsIcon from '@mui/icons-material/SportsEsports';
import ScienceIcon from '@mui/icons-material/Science';
import AssessmentIcon from '@mui/icons-material/Assessment'; // Report
import LiveTvIcon from '@mui/icons-material/LiveTv'; // Live
import SettingsIcon from '@mui/icons-material/Settings';
import LogoutIcon from '@mui/icons-material/Logout';
import LoginIcon from '@mui/icons-material/Login';
import { useAuth } from '../../context/AuthContext';
import LoginModal from '../auth/LoginModal';

const GalaxySidebar = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const [loginOpen, setLoginOpen] = useState(false);

  const menuItems = [
    { text: 'Play', icon: <SportsEsportsIcon />, path: '/galaxy/play', disabled: false },
    { text: 'Research', icon: <ScienceIcon />, path: '/galaxy/research', disabled: false }, // Will be protected later
    { text: 'Report', icon: <AssessmentIcon />, path: '/galaxy/report', disabled: true },
    { text: 'Live', icon: <LiveTvIcon />, path: '/galaxy/live', disabled: true },
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
        <ListItemButton sx={{ borderRadius: 2, mb: 1 }}>
            <ListItemIcon sx={{ minWidth: 40 }}><SettingsIcon /></ListItemIcon>
            <ListItemText primary="Settings" />
        </ListItemButton>

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
                <LogoutIcon fontSize="small" sx={{ color: 'text.secondary', cursor: 'pointer' }} onClick={logout} />
            </Box>
        ) : (
            <Button 
                variant="outlined" 
                fullWidth 
                startIcon={<LoginIcon />}
                onClick={() => setLoginOpen(true)}
            >
                Sign In
            </Button>
        )}
      </Box>
      <LoginModal open={loginOpen} onClose={() => setLoginOpen(false)} />
    </Box>
  );
};

export default GalaxySidebar;