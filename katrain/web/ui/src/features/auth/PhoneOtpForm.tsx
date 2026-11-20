import { useEffect, useRef, useState } from 'react';
import { ChevronLeft, CircleCheck } from 'lucide-react';
import { API, ApiError, type PhoneChallenge, type PhoneAuthErrorDetail } from '../../api';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../hooks/useTranslation';
import AuthField from './AuthField';
import { newPasswordValid, publicUsernameError } from './namedSignupValidation';
import { showAuthNotice } from './AuthNotice';

const newFlow = () => Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, '0')).join('');
const normalizePhone = (value: string) => value.trim().replace(/^(?:\+86|0086)/, '');
const errorMessages: Record<string, [string, string]> = {
  invalid_phone: ['auth:otp_invalid_phone', '请输入中国大陆11位手机号'],
  invalid_code: ['auth:otp_invalid_code', '请输入正确的6位数字验证码'],
  challenge_invalid: ['auth:otp_challenge_invalid', '验证码已失效，请重新获取'],
  challenge_expired: ['auth:otp_challenge_expired', '验证码已过期，请重新获取'],
  challenge_used: ['auth:otp_challenge_used', '验证码已使用，请重新获取'],
  sms_limited: ['auth:otp_sms_limited', '短信请求过于频繁，请稍后再试'],
  otp_locked: ['auth:otp_locked', '验证码错误次数过多，请稍后再试'],
  sms_unavailable: ['auth:otp_unavailable', '短信服务暂不可用，请稍后重试或使用账号密码登录'],
  sms_rejected: ['auth:otp_rejected', '短信发送被拒绝，请稍后重试或使用账号密码登录'],
  identity_changed: ['auth:otp_identity_changed', '登录身份已变化，请重新开始'],
  invalid_public_username: ['auth:invalid_public_username', '用户名需为2–24个字母、数字、下划线或连字符'],
  reserved_public_username: ['auth:reserved_public_username', '请换一个用户名'],
  public_username_taken: ['auth:public_username_taken', '用户名已被使用'],
  phone_in_use: ['auth:continue_phone_in_use', 'This account is linked to another phone. Sign in to the original account to manage its phone.'],
  bind_reauth_failed: ['auth:continue_password_incorrect', 'The original account password is incorrect. Try again.'],
  bind_reauth_locked: ['auth:continue_password_locked', 'Too many password attempts. Try again in {seconds} seconds.'],
  invalid_password: ['auth:new_password_invalid', '密码至少15个字符'],
  password_too_long: ['auth:password_too_long', '密码过长，请缩短'],
};
export type PhoneFormMode = 'login' | 'register' | 'name' | 'complete';
interface Props {
  onSuccess: () => void;
  initialMode?: 'login' | 'register';
  onModeChange?: (mode: PhoneFormMode) => void;
  onExistingLogin?: () => void;
  onNotice?: (message: string) => void;
}

export default function PhoneOtpForm({ onSuccess, initialMode = 'login', onModeChange, onExistingLogin, onNotice = showAuthNotice }: Props) {
  const { t } = useTranslation();
  const { loginPhone, continuePhone, registerPhone, identityKey } = useAuth();
  const [mode, setMode] = useState<PhoneFormMode>(initialMode);
  const [verifiedForProfile, setVerifiedForProfile] = useState(false);
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [passwordRequired, setPasswordRequired] = useState(false);
  const [lockAt, setLockAt] = useState(0);
  const [challenge, setChallenge] = useState<PhoneChallenge | null>(null);
  const [sending, setSending] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [retryAt, setRetryAt] = useState(0);
  const [expiresAt, setExpiresAt] = useState(0);
  const [now, setNow] = useState(Date.now());
  const flow = useRef('');
  if (!flow.current) flow.current = newFlow();
  const revision = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const reset = () => {
    revision.current += 1;
    controller.current?.abort(); controller.current = null;
    flow.current = newFlow();
    setCode(''); setPassword(''); setPasswordRequired(false); setLockAt(0); setChallenge(null); setVerifiedForProfile(false); setError(''); setSending(false); setSubmitting(false); setRetryAt(0); setExpiresAt(0);
  };
  const retireProof = (reason: string) => {
    revision.current += 1; controller.current?.abort(); controller.current = null;
    setChallenge(null); setExpiresAt(0); setCode(''); setPassword('');
    setVerifiedForProfile(false); setPasswordRequired(false);
    setSending(false); setSubmitting(false); setError(reason);
  };
  useEffect(() => {
    reset(); setPhone(''); setUsername(''); setPassword(''); setMode(initialMode);
    return () => { revision.current += 1; controller.current?.abort(); flow.current = ''; };
    // Each canonical identity owns its private fields and outstanding work.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [identityKey]);
  useEffect(() => {
    if (!retryAt && !expiresAt && !lockAt) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [retryAt, expiresAt, lockAt]);
  useEffect(() => {
    if (!challenge || !expiresAt) return;
    const deadline = setTimeout(() => retireProof('challenge_expired'), Math.max(0, expiresAt - Date.now()));
    return () => clearTimeout(deadline);
    // Only a new proof/deadline replaces this timer; private input edits cannot extend it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [challenge, expiresAt]);

  const remaining = Math.max(0, Math.ceil((retryAt - now) / 1000));
  const expired = Boolean(challenge && expiresAt <= now);
  const locked = Math.max(0, Math.ceil((lockAt - now) / 1000));
  const completing = mode === 'complete' || mode === 'name';
  const retireRequest = () => { revision.current += 1; controller.current?.abort(); controller.current = null; setSubmitting(false); setSending(false); };
  const backToPhone = () => { reset(); setPhone(''); setUsername(''); setMode('login'); onModeChange?.('login'); };
  const needsCode = !completing || !verifiedForProfile || expired || !challenge;
  const phoneValid = /^1[0-9]{10}$/.test(normalizePhone(phone));
  const showError = (err: unknown) => {
    const detail = err instanceof ApiError ? err.detail as PhoneAuthErrorDetail | undefined : undefined;
    const name = detail?.code && errorMessages[detail.code] ? detail.code : 'sms_unavailable';
    setError(name);
    if (detail?.retry_after && Number.isFinite(detail.retry_after)) {
      if (name === 'bind_reauth_locked' || name === 'otp_locked') setLockAt(Date.now() + Math.max(0, detail.retry_after) * 1000);
      else setRetryAt(Date.now() + Math.max(0, detail.retry_after) * 1000);
      setNow(Date.now());
    }
    if (['bind_reauth_failed', 'bind_reauth_locked', 'phone_in_use'].includes(name)) setPassword('');
    if (['challenge_invalid', 'challenge_expired', 'challenge_used'].includes(name)) retireProof(name);
    if (name === 'identity_changed') { setPassword(''); setUsername(''); setPhone(''); reset(); setMode(initialMode); onModeChange?.(initialMode); }
  };
  const send = async () => {
    if (sending || submitting || remaining || locked) return;
    if (!phoneValid) { setError('invalid_phone'); return; }
    setError(''); setSending(true); setChallenge(null); setCode(''); setPassword(''); setPasswordRequired(false); setVerifiedForProfile(false);
    // A lost response may follow an accepted SMS; retain the local cooldown.
    setRetryAt(Date.now() + 60000); setNow(Date.now());
    const version = revision.current;
    const request = new AbortController(); controller.current = request;
    const current = () => version === revision.current && !request.signal.aborted;
    try {
      const result = await API.createPhoneChallenge({ phone: normalizePhone(phone), purpose: 'login', flow_id: flow.current }, request.signal);
      if (!current()) return;
      setChallenge(result); setRetryAt(Date.now() + result.retry_after * 1000); setExpiresAt(Date.now() + result.expires_in * 1000); setNow(Date.now());
    } catch (err) { if (current()) showError(err); }
    finally { if (current()) setSending(false); }
  };
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (submitting || sending || locked) return;
    if (mode === 'register') {
      const nameError = publicUsernameError(username);
      if (nameError) { setError(nameError); return; }
      if (!newPasswordValid(password)) {
        setError(new TextEncoder().encode(password).length > 72 ? 'password_too_long' : 'invalid_password'); return;
      }
    }
    if (completing && !username.trim()) { setError('invalid_public_username'); return; }
    if (completing && passwordRequired && !password) return;
    if (!phoneValid) { setError('invalid_phone'); return; }
    if (!challenge || Date.now() >= expiresAt) { retireProof('challenge_expired'); return; }
    if (!/^[0-9]{6}$/.test(code)) { setError('invalid_code'); return; }
    setError(''); setSubmitting(true);
    const version = revision.current;
    const request = new AbortController(); controller.current = request;
    const current = () => version === revision.current && !request.signal.aborted;
    try {
      const verified = { challenge_id: challenge.challenge_id, code, flow_id: flow.current };
      if (mode === 'login') await loginPhone(verified, request.signal);
      else if (completing) {
        const result = await continuePhone({ ...verified, public_username: username, ...(passwordRequired ? { current_password: password } : {}) }, request.signal);
        if (!current()) return;
        if (result.signup_grant_credits === 5000) onNotice?.(t('auth:signup_grant_success', '注册成功，已赠送50积分'));
      } else {
        const result = await registerPhone({ ...verified, public_username: username, password }, request.signal);
        if (!current()) return;
        onNotice?.(result.signup_grant_credits === 5000
          ? t('auth:signup_grant_success', '注册成功，已赠送50积分')
          : completing ? t('auth:profile_success', '设置完成') : t('auth:signup_success', '注册成功'));
      }
      if (current()) onSuccess();
    } catch (err) {
      if (!current()) return;
      const detail = err instanceof ApiError ? err.detail as { code?: string; mode?: string } | undefined : undefined;
      if (err instanceof ApiError && err.status === 409 && detail?.code === 'profile_required') {
        const nextMode = detail.mode === 'complete' ? 'complete' : 'name';
        setMode(nextMode); setVerifiedForProfile(true); setPassword(''); setPasswordRequired(false); onModeChange?.(nextMode); setError('');
      } else if (err instanceof ApiError && err.status === 409 && detail?.code === 'account_password_required' && completing) {
        setVerifiedForProfile(true); setPasswordRequired(true); setPassword(''); setError('');
      } else showError(err);
    } finally { if (current()) setSubmitting(false); }
  };
  const message = errorMessages[error];
  const fieldError = (...names: string[]) => names.includes(error) && message ? t(...message) : undefined;
  const isFieldError = ['invalid_phone', 'invalid_code', 'invalid_public_username', 'reserved_public_username', 'public_username_taken', 'invalid_password', 'password_too_long', 'bind_reauth_failed'].includes(error);
  return <>
    {completing && <p className="named-auth-context">{verifiedForProfile && !expired && <CircleCheck aria-hidden="true" />}{verifiedForProfile && !expired ? t('auth:continue_verified_phone', '{phone} · Verified').replace('{phone}', `${normalizePhone(phone).slice(0, 3)} **** ${normalizePhone(phone).slice(-4)}`) : `${t('auth:phone_label', '手机号')} ${normalizePhone(phone).slice(0, 3)} **** ${normalizePhone(phone).slice(-4)}`}</p>}
    <form onSubmit={submit} noValidate data-step={completing ? 'name' : mode}>
      <div className="named-auth-fields">
        {mode !== 'login' && <>
          <AuthField autoFocus label={completing ? t('auth:username', '用户名') : t('auth:public_username', '用户名（昵称）')} placeholder={completing ? t('auth:continue_username_placeholder', 'Choose a unique public username') : t('auth:public_username_placeholder', '设置公开用户名')} autoComplete="username" value={username} onChange={e => { retireRequest(); setUsername(e.target.value); setPassword(''); setPasswordRequired(false); setLockAt(0); setError(''); }} error={fieldError('invalid_public_username', 'reserved_public_username', 'public_username_taken')} />
          {mode === 'register' && <AuthField label={t('auth:password', '密码')} placeholder={t('auth:new_password_placeholder', '设置登录密码')} type="password" autoComplete="new-password" value={password} onChange={e => { setPassword(e.target.value); setError(''); }} error={fieldError('invalid_password', 'password_too_long')} />}
          {completing && !passwordRequired && <p className="named-auth-context">{t('auth:continue_public_name_hint', 'Your unique username will be public.')}</p>}
          {completing && passwordRequired && <>
            <p className="named-auth-context named-auth-existing-hint">{t('auth:continue_password_required', 'This username exists. Verify the original account password.')}</p>
            <AuthField autoFocus label={t('auth:continue_original_password', 'Original password')} placeholder={t('auth:continue_password_placeholder', 'Enter the original account password')} type="password" autoComplete="current-password" value={password}
              onChange={e => { retireRequest(); setPassword(e.target.value); setError(''); }} error={fieldError('bind_reauth_failed')} />
          </>}
        </>}
        {!completing && <AuthField type="tel" autoComplete="tel-national" label={t('auth:phone_label', '手机号')} placeholder={t('auth:phone_placeholder', '中国大陆 +86')}
          value={phone} onChange={e => { reset(); setPhone(e.target.value); }} error={fieldError('invalid_phone')} maxLength={17} />}
        {needsCode && <AuthField label={t('auth:code_label', '验证码')} placeholder={t('auth:code_placeholder', '6 位验证码')} value={code} autoComplete="one-time-code" inputMode="numeric" maxLength={6} pattern="[0-9]{6}"
          onChange={e => { if (/^[0-9]{0,6}$/.test(e.target.value)) { retireRequest(); setCode(e.target.value); setError(''); } }} error={fieldError('invalid_code')}
          action={<button type="button" className="named-auth-send" onClick={send} disabled={sending || submitting || remaining > 0 || locked > 0}>
            {sending ? t('auth:otp_sending', '发送中…') : remaining ? t('auth:otp_retry', '{seconds}秒后重发').replace('{seconds}', String(remaining)) : t('auth:otp_send', '获取验证码')}
          </button>} />}
      </div>
      {message && !isFieldError && <p className="named-auth-message" role="alert">{t(...message).replace('{seconds}', String(locked))}</p>}
      {expired && error !== 'challenge_expired' && <p className="named-auth-message" role="alert">{t('auth:otp_challenge_expired', '验证码已过期，请重新获取')}</p>}
      {challenge?.delivery === 'unknown' && !error && !expired && <p className="named-auth-context" role="status">{t('auth:otp_unknown', '发送状态未确认；若收到验证码仍可验证。请等待冷却结束后再决定是否重发。')}</p>}
      <button type="submit" className="named-auth-primary" disabled={!challenge || sending || submitting || expired || locked > 0 || (passwordRequired && !password)}>
        {submitting ? t('auth:otp_verifying', '验证中…') : mode === 'login' || completing ? t('auth:continue_submit', 'Continue') : t('auth:register_submit', '注册并登录')}
      </button>
    </form>
    {completing && <div className="named-auth-footer">
      <button type="button" className="named-auth-text" onClick={backToPhone}><ChevronLeft aria-hidden="true" />{t('auth:continue_change_phone', 'Change phone number')}</button>
      {error === 'phone_in_use' && onExistingLogin && <button type="button" className="named-auth-text" onClick={onExistingLogin}>{t('auth:continue_original_login', 'Sign in to original account')}</button>}
    </div>}
  </>;
}
