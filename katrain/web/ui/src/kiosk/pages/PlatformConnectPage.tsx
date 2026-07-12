import { useEffect, useState } from 'react';
import {
  Box, Typography, Dialog, DialogTitle, DialogContent,
  DialogActions, Button, TextField, CircularProgress, Chip,
} from '@mui/material';
import { Login, Logout } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../hooks/useTranslation';
import { API, type PlatformInfo } from '../../api';
import SubPageBar from '../components/layout/SubPageBar';
import { PLATFORM_META } from '../constants/platforms';

const PlatformConnectPage = () => {
  const { t } = useTranslation();
  const { token } = useAuth();
  const navigate = useNavigate();
  const [platforms, setPlatforms] = useState<PlatformInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [loginDialog, setLoginDialog] = useState<string | null>(null);
  const [loginForm, setLoginForm] = useState({ username: '', password: '' });
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState('');
  const [smsLoading, setSmsLoading] = useState(false);
  const [smsCountdown, setSmsCountdown] = useState(0);

  const fetchStatus = async () => {
    if (!token) return;
    try {
      const data = await API.platformStatus(token);
      setPlatforms(data.platforms);
    } catch (e) {
      console.error('Failed to fetch platform status', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchStatus(); }, [token]);

  // SMS countdown ticker: re-arms a 1s timeout each tick until it reaches 0.
  useEffect(() => {
    if (smsCountdown <= 0) return;
    const timer = setTimeout(() => setSmsCountdown((c) => Math.max(0, c - 1)), 1000);
    return () => clearTimeout(timer);
  }, [smsCountdown]);

  const closeLoginDialog = () => {
    setLoginDialog(null);
    setLoginForm({ username: '', password: '' });
    setLoginError('');
    setSmsCountdown(0);
    setSmsLoading(false);
  };

  const handleSendSms = async () => {
    if (!loginDialog || !token) return;
    if (!loginForm.username.trim()) {
      setLoginError(t('Enter phone number first', '请先输入手机号'));
      return;
    }
    setSmsLoading(true);
    setLoginError('');
    try {
      await API.platformSmsRequest(loginDialog, loginForm.username, token);
      setSmsCountdown(60);
    } catch (e: any) {
      setLoginError(e.message || t('Failed to send code', '验证码发送失败'));
    } finally {
      setSmsLoading(false);
    }
  };

  const handleLogin = async () => {
    if (!loginDialog || !token) return;
    setLoginLoading(true);
    setLoginError('');
    try {
      const isSms = PLATFORM_META[loginDialog]?.login?.passLabel === 'Verification Code';
      const creds = isSms
        ? { username: loginForm.username, sms_code: loginForm.password }
        : { username: loginForm.username, password: loginForm.password };
      await API.platformLogin(loginDialog, creds, token);
      closeLoginDialog();
      await fetchStatus();
    } catch (e: any) {
      setLoginError(e.message || t('Login failed', '登录失败'));
    } finally {
      setLoginLoading(false);
    }
  };

  const handleLogout = async (platform: string) => {
    if (!token) return;
    try {
      await API.platformLogout(platform, token);
      await fetchStatus();
    } catch (e) {
      console.error('Logout failed', e);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <SubPageBar title={t('Cross-Platform Play', '跨平台对弈')} to="/kiosk/play" />
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, p: 3, flex: 1, minHeight: 0, overflow: 'auto' }}>
      <Typography variant="body2" sx={{ color: 'text.secondary' }}>
        {t('Connect to Go platforms and play through your smart board', '连接围棋平台，通过智能棋盘对弈')}
      </Typography>

      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', flex: 1 }}>
        {platforms.map((p) => {
          const meta = PLATFORM_META[p.platform] || { label: p.platform, labelCn: p.platform, color: '#888' };
          return (
            <Box
              key={p.platform}
              sx={{
                flex: '1 1 calc(50% - 8px)',
                minWidth: 200,
                minHeight: 140,
                borderRadius: 3,
                bgcolor: 'background.paper',
                border: '1px solid',
                borderColor: p.connected ? 'success.main' : 'divider',
                p: 2.5,
                display: 'flex',
                flexDirection: 'column',
                gap: 1.5,
              }}
            >
              {/* Header */}
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: p.connected ? 'success.main' : 'text.disabled' }} />
                  <Typography variant="h6" sx={{ color: 'text.primary' }}>
                    {t(meta.label, meta.labelCn)}
                  </Typography>
                </Box>
                {p.connected && (
                  <Chip label={p.saved_username} size="small" color="success" variant="outlined" />
                )}
              </Box>

              {/* Capabilities */}
              <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                {p.supports_live_play && <Chip label={t('Live Play', '实时对弈')} size="small" variant="outlined" />}
                {p.supports_automatch && <Chip label={t('Automatch', '自动匹配')} size="small" variant="outlined" />}
                {p.supports_rooms && <Chip label={t('Rooms', '房间')} size="small" variant="outlined" />}
                {p.supports_engine_play && <Chip label={t('Engine Play', '人机对弈')} size="small" variant="outlined" />}
                {meta.comingSoon && <Chip label={t('Coming Soon', '即将支持')} size="small" color="warning" variant="outlined" />}
              </Box>

              {/* Actions */}
              <Box sx={{ display: 'flex', gap: 1, mt: 'auto' }}>
                {meta.comingSoon ? (
                  <Button variant="outlined" size="small" disabled sx={{ flex: 1, minHeight: 44, opacity: 0.5 }}>
                    {t('Coming Soon', '即将支持')}
                  </Button>
                ) : p.connected ? (
                  <>
                    <Button
                      variant="contained"
                      size="small"
                      sx={{ flex: 1, minHeight: 44 }}
                      onClick={() =>
                        navigate(
                          p.supports_engine_play
                            ? `/kiosk/play/cross-platform/engine/${p.platform}`
                            : `/kiosk/play/cross-platform/lobby?platform=${p.platform}`
                        )
                      }
                    >
                      {p.supports_engine_play ? t('Play vs AI', '人机对弈') : t('Enter Lobby', '进入大厅')}
                    </Button>
                    <Button
                      variant="outlined"
                      size="small"
                      color="error"
                      sx={{ minHeight: 44, minWidth: 44 }}
                      onClick={() => handleLogout(p.platform)}
                    >
                      <Logout fontSize="small" />
                    </Button>
                  </>
                ) : (
                  <Button
                    variant="outlined"
                    size="small"
                    sx={{ flex: 1, minHeight: 44 }}
                    startIcon={<Login />}
                    onClick={() => {
                      setLoginDialog(p.platform);
                      setLoginForm({ username: p.saved_username || '', password: '' });
                      setLoginError('');
                      setSmsCountdown(0);
                    }}
                  >
                    {t('Login', '登录')}
                  </Button>
                )}
              </Box>
            </Box>
          );
        })}
      </Box>

      {/* Login Dialog */}
      <Dialog open={!!loginDialog} onClose={closeLoginDialog} maxWidth="xs" fullWidth>
        <DialogTitle>
          {loginDialog && t(
            `Login to ${PLATFORM_META[loginDialog]?.label}`,
            `登录 ${PLATFORM_META[loginDialog]?.labelCn}`
          )}
        </DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          {(() => {
            const loginCfg = loginDialog ? PLATFORM_META[loginDialog]?.login : null;
            const isSms = loginCfg?.passLabel === 'Verification Code';
            return (
              <>
                <TextField
                  label={t(loginCfg?.userLabel || 'Username', loginCfg?.userLabelCn || '用户名')}
                  type={loginCfg?.userType || 'text'}
                  value={loginForm.username}
                  onChange={(e) => setLoginForm({ ...loginForm, username: e.target.value })}
                  fullWidth
                  autoFocus
                />
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
                  <TextField
                    label={t(loginCfg?.passLabel || 'Password', loginCfg?.passLabelCn || '密码')}
                    type={isSms ? 'text' : 'password'}
                    value={loginForm.password}
                    onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })}
                    fullWidth
                    onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
                  />
                  {isSms && (
                    <Button
                      variant="outlined"
                      sx={{ minHeight: 56, minWidth: 128, whiteSpace: 'nowrap' }}
                      disabled={smsLoading || smsCountdown > 0}
                      onClick={handleSendSms}
                    >
                      {smsCountdown > 0
                        ? t(`Resend(${smsCountdown}s)`, `重新获取(${smsCountdown}s)`)
                        : smsLoading
                          ? <CircularProgress size={20} />
                          : t('Get Code', '获取验证码')}
                    </Button>
                  )}
                </Box>
              </>
            );
          })()}
          {loginError && (
            <Typography variant="body2" color="error">{loginError}</Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={closeLoginDialog}>{t('Cancel', '取消')}</Button>
          <Button onClick={handleLogin} variant="contained" disabled={loginLoading}>
            {loginLoading ? <CircularProgress size={20} /> : t('Login', '登录')}
          </Button>
        </DialogActions>
      </Dialog>
      </Box>
    </Box>
  );
};

export default PlatformConnectPage;
