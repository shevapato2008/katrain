import React from 'react';
import { AppBar, Toolbar, Typography, Box, IconButton, FormControlLabel, Checkbox, Button } from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import { useTranslation } from '../hooks/useTranslation';

interface TopBarProps {
  onMenuClick: () => void;
  analysisToggles: Record<string, boolean>;
  onToggleChange: (key: string) => void;
  status: string;
  engine?: "local" | "cloud" | null;
  user?: any;
  onLoginClick: () => void;
  onRegisterClick: () => void;
  onLogoutClick: () => void;
}

const TopBar: React.FC<TopBarProps> = ({ 
  onMenuClick, analysisToggles, onToggleChange, status, engine, 
  user, onLoginClick, onRegisterClick, onLogoutClick 
}) => {
  const { t } = useTranslation();
  return (
    <AppBar
      position="static"
      elevation={0}
      sx={{
        bgcolor: 'rgba(26, 26, 26, 0.95)',
        backdropFilter: 'blur(10px)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
      }}
    >
      <Toolbar variant="dense" sx={{ minHeight: 56 }}>
        <IconButton
          edge="start"
          aria-label="menu"
          onClick={onMenuClick}
          sx={{
            mr: 2,
            color: '#b8b5b0',
            '&:hover': {
              bgcolor: 'rgba(255, 255, 255, 0.05)',
              color: '#4a6b5c',
            },
          }}
        >
          <MenuIcon />
        </IconButton>
        <Typography
          variant="h6"
          component="div"
          sx={{
            flexGrow: 1,
            display: 'flex',
            alignItems: 'center',
            color: '#f5f3f0',
            fontWeight: 600,
            fontSize: '1.125rem',
            mr: 2
          }}
        >
          弈航
          <Typography
            variant="caption"
            sx={{
              ml: 1,
              color: '#7a7772',
              fontSize: '0.75rem',
              fontWeight: 400,
              textTransform: 'uppercase',
              letterSpacing: '0.5px',
            }}
          >
            {t('WEB UI')}
          </Typography>
        </Typography>

        <Box sx={{ display: 'flex', gap: 1, mr: 2, alignItems: 'center', flexWrap: 'wrap' }}>
          {['children', 'eval', 'hints', 'policy', 'ownership', 'coords', 'numbers', 'score', 'winrate'].map((t_key) => {
            const labels: Record<string, string> = {
              children: t('analysis:nextmoves').replace('\n', ' '),
              eval: t('analysis:dots').replace('\n', ' '),
              hints: t('analysis:topmoves').replace('\n', ' '),
              policy: t('analysis:policy').replace('\n', ' '),
              ownership: t('analysis:territory').replace('\n', ' '),
              coords: t('analysis:coordinates', 'Coordinates'),
              numbers: t('analysis:numbers', 'Numbers'),
              score: t('tab:score'),
              winrate: t('tab:winrate')
            };
            return (
              <FormControlLabel
                key={t_key}
                control={
                  <Checkbox
                    checked={analysisToggles[t_key] || false}
                    onChange={() => onToggleChange(t_key)}
                    size="small"
                    sx={{
                      p: 0.5,
                      color: '#7a7772',
                      '&.Mui-checked': {
                        color: '#4a6b5c',
                      },
                      '&:hover': {
                        bgcolor: 'rgba(255, 255, 255, 0.05)',
                      },
                    }}
                  />
                }
                label={
                  <Typography
                    variant="body2"
                    sx={{
                      whiteSpace: 'nowrap',
                      color: analysisToggles[t_key] ? '#f5f3f0' : '#b8b5b0',
                      fontSize: '0.875rem',
                      fontWeight: analysisToggles[t_key] ? 600 : 400,
                      transition: 'color 150ms',
                    }}
                  >
                    {labels[t_key] || t_key}
                  </Typography>
                }
                sx={{
                  mr: 0,
                  ml: 0,
                  '&:hover': {
                    '& .MuiTypography-root': {
                      color: '#f5f3f0',
                    },
                  },
                }}
              />
            );
          })}
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {engine && (
              <Typography
                variant="caption"
                sx={{
                  px: 1,
                  py: 0.25,
                  borderRadius: 1,
                  bgcolor: engine === 'cloud' ? 'rgba(91, 155, 213, 0.2)' : 'rgba(48, 160, 110, 0.2)',
                  color: engine === 'cloud' ? '#5b9bd5' : '#30a06e',
                  fontWeight: 700,
                  fontSize: '0.7rem',
                  textTransform: 'uppercase',
                  border: '1px solid',
                  borderColor: engine === 'cloud' ? 'rgba(91, 155, 213, 0.3)' : 'rgba(48, 160, 110, 0.3)',
                }}
              >
                {engine}
              </Typography>
            )}
            <Box
              sx={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                bgcolor: '#30a06e',
                animation: 'pulse 2s ease-in-out infinite',
                '@keyframes pulse': {
                  '0%, 100%': { opacity: 1 },
                  '50%': { opacity: 0.5 },
                },
              }}
            />
            <Typography
              variant="body2"
              noWrap
              sx={{
                maxWidth: 200,
                color: '#b8b5b0',
                fontSize: '0.875rem',
                fontFamily: 'var(--font-mono)',
              }}
            >
              {status}
            </Typography>
          </Box>

          <Box sx={{ display: 'flex', gap: 1 }}>
            {user ? (
              <>
                <Typography variant="body2" sx={{ alignSelf: 'center', color: '#f5f3f0', fontWeight: 600 }}>
                  {user.username}
                </Typography>
                <Button size="small" variant="outlined" color="inherit" onClick={onLogoutClick} sx={{ color: '#b8b5b0', borderColor: 'rgba(255,255,255,0.2)' }}>
                  {t("Logout")}
                </Button>
              </>
            ) : (
              <>
                <Button size="small" variant="outlined" color="primary" onClick={onLoginClick}>
                  {t("Login")}
                </Button>
                <Button size="small" variant="contained" color="primary" onClick={onRegisterClick}>
                  {t("Register")}
                </Button>
              </>
            )}
          </Box>
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default TopBar;