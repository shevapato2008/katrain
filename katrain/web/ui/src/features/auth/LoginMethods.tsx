import { useEffect, useRef, useState } from 'react';
import { X } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../hooks/useTranslation';
import PhoneOtpForm, { type PhoneFormMode } from './PhoneOtpForm';
import AuthField from './AuthField';
import { ApiError } from '../../api';
import './namedAuth.css';

interface Props { onSuccess: () => void; surface?: 'galaxy' | 'kiosk'; onClose?: () => void; onGuest?: () => void; onNotice?: (message: string) => void; }
export default function LoginMethods({ onSuccess, surface = 'galaxy', onClose, onGuest, onNotice }: Props) {
  const { t } = useTranslation();
  const { login, identityKey } = useAuth();
  const [tab, setTab] = useState('phone');
  const [mode, setMode] = useState<PhoneFormMode>('login');
  const [formKey, setFormKey] = useState(0);
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
    resetPrivateForm(); setMode('login');
    return () => { revision.current += 1; controller.current?.abort(); };
    // Each canonical identity owns its private fields and pending work.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [identityKey]);
  const changeView = (nextMode: 'login' | 'register', nextTab = 'phone') => {
    resetPrivateForm(); setMode(nextMode); setTab(nextTab); setFormKey(key => key + 1);
  };
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); if (!username || !password || loading) return;
    const version = revision.current; setLoading(true); setError(false);
    controller.current = new AbortController();
    try { await login(username, password, controller.current.signal); if (revision.current === version) onSuccess(); }
    catch (failure) {
      if (revision.current === version) {
        if (failure instanceof ApiError && (failure.detail as { code?: string } | undefined)?.code === 'identity_changed') resetPrivateForm();
        else setError(true);
      }
    }
    finally { if (revision.current === version) setLoading(false); }
  };
  return <div className="named-auth" data-surface={surface}>
    <header className="named-auth-heading"><h1 id="named-auth-title">{mode === 'login' ? t('Login', '登录') : mode === 'register' ? t('auth:named_register_title', '注册') : mode === 'complete' ? t('auth:continue_legacy_title', 'Set username') : t('auth:continue_name_title', 'Set public username')}</h1>
      {onClose && <button type="button" className="named-auth-close" onClick={onClose} aria-label={t('auth:close', '关闭')}><X aria-hidden="true" /></button>}
    </header>
    {mode === 'login' && <div className="named-auth-tabs" role="tablist" aria-label={t('auth:otp_method', '登录方式')}>
      {(['phone', 'password'] as const).map(value => <button type="button" role="tab" key={value} aria-selected={tab === value} onClick={() => changeView('login', value)}>
        {value === 'phone' ? t('auth:otp_tab', '短信验证码') : t('auth:password_tab', '账号密码')}
      </button>)}
    </div>}
    {tab === 'phone' ? <PhoneOtpForm key={formKey} initialMode={mode === 'register' ? 'register' : 'login'} onModeChange={setMode} onSuccess={onSuccess} onExistingLogin={() => changeView('login', 'password')} onNotice={onNotice} /> : <form onSubmit={submit}>
      <div className="named-auth-fields">
        <AuthField autoFocus autoComplete="username" label={t('auth:username', '用户名')} value={username} onChange={e => setUsername(e.target.value)} />
        <AuthField type="password" autoComplete="current-password" label={t('auth:password', '密码')} value={password} onChange={e => setPassword(e.target.value)} />
      </div>
      {error && <p className="named-auth-message" role="alert">{t('Login failed', '登录失败')}</p>}
      <button type="submit" className="named-auth-primary" disabled={!username || !password || loading}>{loading ? t('Logging in...', '登录中...') : t('Login', '登录')}</button>
    </form>}
    {mode === 'login' && surface === 'kiosk' && onGuest && <div className="named-auth-footer">
      <button type="button" className="named-auth-text" onClick={onGuest}>{t('auth:guest_entry', '访客登录')}</button>
    </div>}
  </div>;
}
