import { useEffect, useId, useRef, useState } from 'react';
import { Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, TextField, Typography } from '@mui/material';
import { API, ApiError, type PhoneAuthErrorDetail, type PhoneBindingStatus, type PhoneChallenge } from '../../api';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../hooks/useTranslation';
import { canBindPhone } from './PhoneBindDialog';
import { newPasswordValid } from './namedSignupValidation';

const newFlow = () => Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, '0')).join('');
const normalizePhone = (value: string) => value.trim().replace(/^(?:\+86|0086)/, '');
const messages: Record<string, [string, string]> = {
  invalid_phone: ['auth:otp_invalid_phone', '请输入中国大陆11位手机号'],
  invalid_code: ['auth:otp_invalid_code', '请输入正确的6位数字验证码'],
  challenge_invalid: ['auth:otp_challenge_invalid', '验证码已失效，请重新获取'],
  challenge_expired: ['auth:otp_challenge_expired', '验证码已过期，请重新获取'],
  challenge_used: ['auth:otp_challenge_used', '验证码已使用，请重新获取'],
  sms_limited: ['auth:otp_sms_limited', '短信请求过于频繁，请稍后再试'],
  otp_locked: ['auth:otp_locked', '验证码错误次数过多，请稍后再试'],
  sms_unavailable: ['auth:bind_sms_unavailable', '短信服务暂不可用，请稍后重试'],
  sms_rejected: ['auth:bind_sms_rejected', '短信发送被拒绝，请稍后重试'],
  invalid_password: ['auth:new_password_invalid', '密码至少15个字符'],
  password_too_long: ['auth:password_too_long', '密码过长，请缩短'],
  phone_verification_required: ['auth:password_phone_mismatch', 'Use the phone currently linked to this account.'],
  identity_changed: ['auth:otp_identity_changed', '登录身份已变化，请重新开始'],
  authentication_required: ['auth:password_auth_required', 'Sign in again before setting a password.'],
  bind_not_allowed: ['auth:password_not_allowed', 'This account cannot set a password here.'],
  password_failed: ['auth:password_failed', 'Could not save password. Try again.'],
};
interface Props { open: boolean; onClose: () => void; kiosk?: boolean; container?: HTMLElement | null; }

export default function PhonePasswordDialog({ open, onClose, kiosk = false, container }: Props) {
  const { user, isGuest, isStrictBoxKiosk, identityKey, token } = useAuth();
  const eligible = canBindPhone(user, isGuest) && !isStrictBoxKiosk;
  const owner = useRef({ identityKey, token, revision: 0 });
  if (owner.current.identityKey !== identityKey || owner.current.token !== token) {
    owner.current = { identityKey, token, revision: owner.current.revision + 1 };
  }
  return <Dialog open={open && eligible} onClose={onClose} maxWidth="xs" fullWidth container={kiosk ? container : undefined}
    PaperProps={{ sx: { borderRadius: 3, p: 1, width: 'calc(100% - 32px)', m: 2, ...(kiosk ? { maxWidth: 480 } : {}) } }}>
    {open && eligible && <PasswordForm key={owner.current.revision} onClose={onClose} kiosk={kiosk} />}
  </Dialog>;
}

function PasswordForm({ onClose, kiosk }: Pick<Props, 'onClose' | 'kiosk'>) {
  const { t } = useTranslation();
  const { identityKey, token } = useAuth();
  const identity = useRef({ identityKey, token }); identity.current = { identityKey, token };
  const id = useId();
  const [status, setStatus] = useState<PhoneBindingStatus | null>(null);
  const [statusError, setStatusError] = useState(false);
  const [phone, setPhone] = useState(''); const [code, setCode] = useState(''); const [password, setPassword] = useState('');
  const [challenge, setChallenge] = useState<PhoneChallenge | null>(null);
  const [sending, setSending] = useState(false); const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(''); const [success, setSuccess] = useState(false);
  const [retryAt, setRetryAt] = useState(0); const [expiresAt, setExpiresAt] = useState(0); const [lockAt, setLockAt] = useState(0);
  const [now, setNow] = useState(Date.now());
  const flow = useRef(''); if (!flow.current) flow.current = newFlow();
  const revision = useRef(0); const controller = useRef<AbortController | null>(null);
  const retire = () => { revision.current += 1; controller.current?.abort(); controller.current = null; setSending(false); setSubmitting(false); };
  const retireProof = (reason: string) => {
    retire(); setChallenge(null); setExpiresAt(0); setCode(''); setPassword(''); setError(reason);
  };
  const startRequest = () => {
    controller.current?.abort(); const request = new AbortController(); controller.current = request;
    const version = ++revision.current; const captured = { identityKey, token };
    return { request, current: () => revision.current === version && !request.signal.aborted && identity.current.identityKey === captured.identityKey && identity.current.token === captured.token };
  };
  const loadStatus = async () => {
    const { request, current } = startRequest(); setStatusError(false); setStatus(null);
    try { const result = await API.phoneStatus(token, request.signal); if (current()) setStatus(result); }
    catch { if (current()) setStatusError(true); }
  };
  useEffect(() => {
    void loadStatus();
    return () => { revision.current += 1; controller.current?.abort(); flow.current = ''; };
    // The parent key scopes this private form to the captured account credential.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    if (!retryAt && !expiresAt && !lockAt) return;
    const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer);
  }, [retryAt, expiresAt, lockAt]);
  useEffect(() => {
    if (!challenge || !expiresAt) return;
    const deadline = setTimeout(() => retireProof('challenge_expired'), Math.max(0, expiresAt - Date.now()));
    return () => clearTimeout(deadline);
    // Only a new proof/deadline replaces this timer; input edits cannot extend it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [challenge, expiresAt]);
  const remaining = Math.max(0, Math.ceil((retryAt - now) / 1000));
  const locked = Math.max(0, Math.ceil((lockAt - now) / 1000));
  const expired = Boolean(challenge && expiresAt <= now);
  const phoneValid = /^1[0-9]{10}$/.test(normalizePhone(phone));
  const handleError = (failure: unknown, sendingSms = false) => {
    const detail = failure instanceof ApiError ? failure.detail as PhoneAuthErrorDetail | undefined : undefined;
    const name = detail?.code && messages[detail.code] ? detail.code : sendingSms ? 'sms_unavailable' : 'password_failed';
    setError(name);
    if (detail?.retry_after && Number.isFinite(detail.retry_after)) {
      if (name === 'otp_locked') setLockAt(Date.now() + detail.retry_after * 1000);
      else setRetryAt(Date.now() + detail.retry_after * 1000);
      setNow(Date.now());
    }
    if (name.startsWith('challenge_') || name === 'phone_verification_required') retireProof(name);
    if (['identity_changed', 'authentication_required', 'bind_not_allowed'].includes(name)) {
      setPhone(''); setCode(''); setPassword(''); setChallenge(null);
    }
  };
  const send = async () => {
    if (!status?.bound || !phoneValid || sending || submitting || remaining || locked) return;
    const { request, current } = startRequest(); setSending(true); setError(''); setChallenge(null); setCode(''); setPassword('');
    setRetryAt(Date.now() + 60000); setNow(Date.now());
    try {
      const result = await API.createPhonePasswordChallenge({ phone: normalizePhone(phone), purpose: 'login', flow_id: flow.current }, token, request.signal);
      if (current()) { setChallenge(result); setRetryAt(Date.now() + result.retry_after * 1000); setExpiresAt(Date.now() + result.expires_in * 1000); setNow(Date.now()); }
    } catch (failure) { if (current()) handleError(failure, true); }
    finally { if (current()) setSending(false); }
  };
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); if (!status?.bound || !challenge || sending || submitting || locked) return;
    if (!newPasswordValid(password)) { setError(new TextEncoder().encode(password).length > 72 ? 'password_too_long' : 'invalid_password'); return; }
    if (Date.now() >= expiresAt) { retireProof('challenge_expired'); return; }
    if (!/^[0-9]{6}$/.test(code)) { setError('invalid_code'); return; }
    const { request, current } = startRequest(); setError(''); setSubmitting(true);
    try {
      await API.phonePassword({ challenge_id: challenge.challenge_id, code, flow_id: flow.current, new_password: password }, token, request.signal);
      if (!current()) return;
      setPhone(''); setCode(''); setPassword(''); setChallenge(null); flow.current = newFlow(); setSuccess(true);
    } catch (failure) { if (current()) handleError(failure); }
    finally { if (current()) setSubmitting(false); }
  };
  const message = messages[error];
  return <>
    <DialogTitle>{t('auth:password_settings_title', 'Set or reset password')}</DialogTitle>
    <DialogContent>
      {statusError ? <Alert severity="error" action={<Button onClick={loadStatus}>{t('auth:bind_retry', '重试')}</Button>}>{t('auth:bind_load_error', '暂时无法读取手机号绑定状态')}</Alert>
        : !status ? <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', py: 2 }}><CircularProgress size={20} /><Typography>{t('auth:bind_loading', '正在核对绑定状态…')}</Typography></Box>
        : success ? <Alert severity="success">{t('auth:password_success', 'Password saved')}</Alert>
        : !status.bound ? <Typography>{t('auth:password_phone_required', 'Bind a phone before setting a password.')}</Typography>
        : <Box component="form" id={id} onSubmit={submit} noValidate sx={{ display: 'flex', flexDirection: 'column', gap: kiosk ? 1.5 : 2, pt: 1 }}>
          <Typography variant="body2" color="text.secondary">{t('auth:password_settings_hint', 'Use a new SMS code sent to your current phone to set a password. SMS sign-in remains available.')}</Typography>
          <Typography variant="body2" color="text.secondary">{t('auth:bind_bound_label', '已绑定手机号')} {status.masked_phone}</Typography>
          <TextField fullWidth autoFocus type="tel" autoComplete="tel-national" label={t('auth:otp_phone', '手机号（中国大陆 +86）')} value={phone}
            onChange={event => { retire(); flow.current = newFlow(); setPhone(event.target.value); setCode(''); setPassword(''); setChallenge(null); setError(''); setRetryAt(0); setExpiresAt(0); setLockAt(0); }}
            error={error === 'invalid_phone'} slotProps={{ htmlInput: { maxLength: 17 } }} />
          <Box sx={{ display: 'flex', gap: 1, minWidth: 0 }}><TextField fullWidth autoComplete="one-time-code" label={t('auth:otp_code', '短信验证码')} value={code}
            onChange={event => { if (/^[0-9]{0,6}$/.test(event.target.value)) { retire(); setCode(event.target.value); setError(''); } }} error={error === 'invalid_code'}
            slotProps={{ htmlInput: { inputMode: 'numeric', maxLength: 6, pattern: '[0-9]{6}' } }} sx={{ minWidth: 0 }} />
            <Button type="button" variant="outlined" onClick={send} disabled={!phoneValid || sending || submitting || remaining > 0 || locked > 0} sx={{ minWidth: 116, minHeight: 56, px: 1, flexShrink: 0 }}>
              {sending ? t('auth:otp_sending', '发送中…') : remaining ? t('auth:otp_retry', '{seconds}秒后重发').replace('{seconds}', String(remaining)) : t('auth:otp_send', '获取验证码')}
            </Button></Box>
          <TextField fullWidth type="password" autoComplete="new-password" label={t('auth:password_new', 'New password')} value={password}
            onChange={event => { retire(); setPassword(event.target.value); setError(''); }} error={error === 'invalid_password' || error === 'password_too_long'} />
          {message && <Alert severity="error">{t(...message)}</Alert>}
          {challenge && !error && <Typography variant="body2" color="text.secondary" role="status">
            {expired ? t('auth:otp_challenge_expired', '验证码已过期，请重新获取') : challenge.delivery === 'unknown' ? t('auth:otp_unknown', '发送状态未确认；若收到验证码仍可验证。请等待冷却结束后再决定是否重发。') : t('auth:otp_requested', '验证码已请求，有效期5分钟，请查看短信。')}
          </Typography>}
        </Box>}
    </DialogContent>
    <DialogActions sx={{ px: 3, pb: 2, gap: 1 }}>
      <Button onClick={onClose} sx={{ minHeight: 44 }}>{success ? t('auth:bind_done', '完成') : t('auth:cancel_btn', '取消')}</Button>
      {status?.bound && !success && <Button form={id} type="submit" variant="contained" disabled={!challenge || !/^[0-9]{6}$/.test(code) || !password || expired || sending || submitting || locked > 0} sx={{ minHeight: 48 }}>
        {submitting ? t('auth:password_submitting', 'Saving…') : t('auth:password_submit', 'Save password')}
      </Button>}
    </DialogActions>
  </>;
}
