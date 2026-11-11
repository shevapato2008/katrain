import { useEffect, useRef, useState } from 'react';
import { Alert, Box, Button, Tab, Tabs, TextField } from '@mui/material';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../hooks/useTranslation';
import PhoneOtpForm from './PhoneOtpForm';
import { ApiError } from '../../api';

export default function LoginMethods({ onSuccess }: { onSuccess: () => void }) {
  const { t } = useTranslation();
  const { login, identityKey } = useAuth();
  const [tab, setTab] = useState('phone');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);
  const revision = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const resetPrivateForm = () => {
    revision.current += 1; controller.current?.abort();
    setUsername(''); setPassword(''); setError(false); setLoading(false);
  };
  useEffect(() => {
    resetPrivateForm();
    return () => { revision.current += 1; controller.current?.abort(); };
    // Each resolved identity owns the private password form and pending work.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [identityKey]);
  const changeTab = (value: string) => {
    revision.current += 1; controller.current?.abort(); setTab(value); setUsername(''); setPassword(''); setError(false); setLoading(false);
  };
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); if (!username || !password || loading) return;
    const version = revision.current; setLoading(true); setError(false);
    controller.current = new AbortController();
    try { await login(username, password, controller.current.signal); if (revision.current === version) onSuccess(); }
    catch (failure) {
      if (revision.current === version) {
        if (failure instanceof ApiError && (failure.detail as { code?: string } | undefined)?.code === 'identity_changed') {
          // A logout can leave identityKey null -> null. The context generation
          // still rejects that retired candidate; clear its private fields here.
          resetPrivateForm();
        } else setError(true);
      }
    }
    finally { if (revision.current === version) setLoading(false); }
  };
  return <Box sx={{ minWidth: 0 }}>
    <Tabs value={tab} onChange={(_, value: string) => changeTab(value)} variant="fullWidth" aria-label={t('auth:otp_method', '登录方式')} sx={{ mb: 2.5, minHeight: 48 }}>
      <Tab value="phone" label={t('auth:otp_tab', '短信验证码')} sx={{ minWidth: 0, minHeight: 48, px: 1 }} />
      <Tab value="password" label={t('auth:password_tab', '账号密码')} sx={{ minWidth: 0, minHeight: 48, px: 1 }} />
    </Tabs>
    {tab === 'phone' ? <PhoneOtpForm onSuccess={onSuccess} /> : <Box component="form" onSubmit={submit} sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {error && <Alert severity="error">{t('Login failed', '登录失败')}</Alert>}
      <TextField fullWidth autoFocus autoComplete="username" label={t('auth:username', '用户名')} value={username} onChange={e => setUsername(e.target.value)} />
      <TextField fullWidth type="password" autoComplete="current-password" label={t('auth:password', '密码')} value={password} onChange={e => setPassword(e.target.value)} />
      <Button type="submit" fullWidth variant="contained" disabled={!username || !password || loading} sx={{ minHeight: 48 }}>
        {loading ? t('Logging in...', '登录中...') : t('Login', '登录')}
      </Button>
    </Box>}
  </Box>;
}
