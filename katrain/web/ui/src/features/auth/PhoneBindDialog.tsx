import { useEffect, useId, useRef, useState } from 'react';
import { Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, TextField, Typography } from '@mui/material';
import { API, ApiError, type PhoneAuthErrorDetail, type PhoneBindingStatus, type PhoneChallenge } from '../../api';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../hooks/useTranslation';

export const canBindPhone = (user: { username: string; is_admin?: boolean } | null, isGuest: boolean) => {
  const name = user?.username.trim().toLowerCase();
  return Boolean(user && !isGuest && !user.is_admin && name !== 'guest' && name !== 'admin' && !name?.startsWith('admin:'));
};
const newFlow = () => Array.from(crypto.getRandomValues(new Uint8Array(16)), v => v.toString(16).padStart(2, '0')).join('');
const normalizePhone = (phone: string) => phone.trim().replace(/^(?:\+86|0086)/, '');
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
  identity_changed: ['auth:otp_identity_changed', '登录身份已变化，请重新开始'],
  authentication_required: ['auth:bind_auth_required', '请重新登录后绑定手机号'],
  bind_not_allowed: ['auth:bind_not_allowed', '当前账号暂不支持绑定手机号'],
  phone_in_use: ['auth:bind_phone_in_use', '此手机号已绑定其他账号，请使用其他手机号'],
  bind_reauth_failed: ['auth:bind_reauth_failed', '当前账号密码不正确，请重新输入'],
  bind_reauth_locked: ['auth:bind_reauth_locked', '密码验证次数过多，请{seconds}秒后再试'],
  bind_failed: ['auth:bind_failed', '绑定未完成，请稍后重试'],
};
interface Props { open: boolean; onClose: () => void; onBound?: (value: { bound: true; masked_phone: string }) => void; kiosk?: boolean; container?: HTMLElement | null; }

export default function PhoneBindDialog({ open, onClose, onBound, kiosk = false, container }: Props) {
  const { user, isGuest, isStrictBoxKiosk, identityKey, token } = useAuth();
  const eligible = canBindPhone(user, isGuest) && !isStrictBoxKiosk;
  // Remount the private form on any credential change; its cleanup retires all work.
  // The key is an in-memory scope index, never a DOM attribute or persisted value.
  const owner = useRef({ identityKey, token, revision: 0 });
  if (owner.current.identityKey !== identityKey || owner.current.token !== token) {
    owner.current = { identityKey, token, revision: owner.current.revision + 1 };
  }
  return <Dialog open={open && eligible} onClose={onClose} maxWidth="xs" fullWidth container={kiosk ? container : undefined}
    PaperProps={{ sx: { borderRadius: 3, p: 1, width: 'calc(100% - 32px)', m: 2,
      ...(kiosk ? { maxWidth: 480 } : {
        '& .MuiInputLabel-root.Mui-focused:not(.Mui-error)': { color: 'text.secondary' },
        '& .MuiOutlinedInput-root.Mui-focused:not(.Mui-error) .MuiOutlinedInput-notchedOutline': { borderColor: 'primary.light' },
        '& .MuiButton-outlinedPrimary:not(.Mui-disabled), & .MuiButton-textPrimary:not(.Mui-disabled)': { color: 'text.secondary' },
        '& .MuiButton-outlinedPrimary:not(.Mui-disabled)': { borderColor: 'primary.light' },
      }),
    } }}>
    {open && eligible && <BindForm key={owner.current.revision} onClose={onClose} onBound={onBound} kiosk={kiosk} />}
  </Dialog>;
}

function BindForm({ onClose, onBound, kiosk }: Pick<Props, 'onClose' | 'onBound' | 'kiosk'>) {
  const { t } = useTranslation();
  const { token, identityKey } = useAuth();
  const identity = useRef({ token, identityKey }); identity.current = { token, identityKey };
  const id = useId();
  const [status, setStatus] = useState<PhoneBindingStatus | null>(null);
  const [statusError, setStatusError] = useState(false);
  const [phone, setPhone] = useState(''); const [code, setCode] = useState(''); const [password, setPassword] = useState('');
  const [challenge, setChallenge] = useState<PhoneChallenge | null>(null);
  const [sending, setSending] = useState(false); const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(''); const [success, setSuccess] = useState(false);
  const [retryAt, setRetryAt] = useState(0); const [lockAt, setLockAt] = useState(0); const [expiresAt, setExpiresAt] = useState(0);
  const [now, setNow] = useState(Date.now());
  const flow = useRef(''); if (!flow.current) flow.current = newFlow();
  const revision = useRef(0); const controller = useRef<AbortController | null>(null);
  const startRequest = () => {
    controller.current?.abort(); const request = new AbortController(); controller.current = request;
    const version = ++revision.current; const captured = { token, identityKey };
    return { request, current: () => revision.current === version && !request.signal.aborted && identity.current.token === captured.token && identity.current.identityKey === captured.identityKey };
  };
  const loadStatus = async () => {
    const { request, current } = startRequest(); setStatusError(false); setStatus(null);
    try { const result = await API.phoneStatus(token, request.signal); if (current()) setStatus(result); }
    catch { if (current()) setStatusError(true); }
  };
  useEffect(() => {
    void loadStatus();
    return () => { revision.current += 1; controller.current?.abort(); flow.current = ''; };
    // Form ownership is enforced by the parent key and by each request snapshot.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    if (!retryAt && !expiresAt && !lockAt) return;
    const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer);
  }, [retryAt, expiresAt, lockAt]);
  const remaining = Math.max(0, Math.ceil((retryAt - now) / 1000));
  const locked = Math.max(0, Math.ceil((lockAt - now) / 1000));
  const expired = Boolean(challenge && expiresAt <= now);
  const handleError = (failure: unknown, sendingSms = false) => {
    const detail = failure instanceof ApiError ? failure.detail as PhoneAuthErrorDetail | undefined : undefined;
    const name = detail?.code && messages[detail.code] ? detail.code : sendingSms ? 'sms_unavailable' : 'bind_failed';
    setError(name);
    const retry = detail?.retry_after;
    if (retry && Number.isFinite(retry)) {
      if (name === 'bind_reauth_locked' || name === 'otp_locked') setLockAt(Date.now() + retry * 1000);
      else setRetryAt(Date.now() + retry * 1000);
      setNow(Date.now());
    }
    if (name.startsWith('challenge_')) { setCode(''); setChallenge(null); }
    if (name === 'bind_reauth_failed' || name === 'bind_reauth_locked') setPassword('');
    if (name === 'identity_changed' || name === 'authentication_required' || name === 'bind_not_allowed') {
      setPhone(''); setCode(''); setPassword(''); setChallenge(null);
    }
  };
  const send = async () => {
    if (sending || submitting || remaining || locked || !/^1[0-9]{10}$/.test(normalizePhone(phone))) return;
    const { request, current } = startRequest(); setSending(true); setError(''); setChallenge(null); setCode('');
    setRetryAt(Date.now() + 60000); setNow(Date.now());
    try {
      const result = await API.createPhoneBindChallenge({ phone: normalizePhone(phone), purpose: 'bind', flow_id: flow.current }, token, request.signal);
      if (current()) { setChallenge(result); setExpiresAt(Date.now() + result.expires_in * 1000); setRetryAt(Date.now() + result.retry_after * 1000); setNow(Date.now()); }
    } catch (failure) { if (current()) handleError(failure, true); }
    finally { if (current()) setSending(false); }
  };
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); if (!challenge || !/^[0-9]{6}$/.test(code) || !password || submitting || locked) return;
    if (Date.now() >= expiresAt) { setError('challenge_expired'); return; }
    const { request, current } = startRequest(); setError(''); setSubmitting(true);
    try {
      const result = await API.phoneBind({ challenge_id: challenge.challenge_id, code, flow_id: flow.current, current_password: password }, token, request.signal);
      if (!current()) return;
      setPassword(''); setPhone(''); setCode(''); setChallenge(null); flow.current = newFlow();
      setStatus(result); setSuccess(true); onBound?.(result);
    } catch (failure) { if (current()) handleError(failure); }
    finally { if (current()) setSubmitting(false); }
  };
  const bound = status?.bound === true;
  const message = messages[error];
  return <>
    <DialogTitle>{t('auth:bind_title', '绑定手机号')}</DialogTitle>
    <DialogContent>
      {statusError ? <Alert severity="error" action={<Button onClick={loadStatus}>{t('auth:bind_retry', '重试')}</Button>}>{t('auth:bind_load_error', '暂时无法读取手机号绑定状态')}</Alert>
        : !status ? <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', py: 2 }}><CircularProgress size={20} /><Typography>{t('auth:bind_loading', '正在核对绑定状态…')}</Typography></Box>
        : bound ? <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {success && <Alert severity="success">{t('auth:bind_success', '手机号绑定成功')}</Alert>}
          <Typography color="text.secondary">{t('auth:bind_bound_label', '已绑定手机号')}</Typography><Typography>{status.masked_phone}</Typography>
          <Typography variant="body2" color="text.secondary">{t('auth:bind_policy', '绑定后可用短信验证码登录，原有余额和会员保留；绑定不重复赠送积分。')}</Typography>
        </Box> : <Box component="form" id={id} onSubmit={submit} noValidate sx={{ display: 'flex', flexDirection: 'column', gap: kiosk ? 1.5 : 2, pt: 1 }}>
          <TextField fullWidth autoFocus type="tel" autoComplete="tel-national" label={t('auth:otp_phone', '手机号（中国大陆 +86）')} value={phone}
            onChange={e => { revision.current += 1; controller.current?.abort(); flow.current = newFlow(); setPhone(e.target.value); setCode(''); setPassword(''); setChallenge(null); setError(''); setSending(false); setSubmitting(false); setRetryAt(0); setExpiresAt(0); }}
            error={error === 'invalid_phone'} slotProps={{ htmlInput: { maxLength: 17 } }} />
          <Box sx={{ display: 'flex', gap: 1, minWidth: 0 }}><TextField fullWidth autoComplete="one-time-code" label={t('auth:otp_code', '短信验证码')} value={code}
            onChange={e => { if (/^[0-9]{0,6}$/.test(e.target.value)) setCode(e.target.value); }} error={error === 'invalid_code'}
            slotProps={{ htmlInput: { inputMode: 'numeric', maxLength: 6, pattern: '[0-9]{6}' } }} sx={{ minWidth: 0 }} />
            <Button type="button" variant="outlined" onClick={send} disabled={sending || submitting || remaining > 0 || locked > 0 || !/^1[0-9]{10}$/.test(normalizePhone(phone))} sx={{ minWidth: 116, minHeight: 56, px: 1, flexShrink: 0 }}>
              {sending ? <CircularProgress size={20} aria-label={t('auth:otp_sending', '发送中…')} /> : remaining ? t('auth:otp_retry', '{seconds}秒后重发').replace('{seconds}', String(remaining)) : t('auth:otp_send', '获取验证码')}
            </Button></Box>
          <TextField fullWidth type="password" autoComplete="current-password" label={t('auth:bind_password', '当前账号密码')} value={password} onChange={e => setPassword(e.target.value)}
            error={error === 'bind_reauth_failed'} slotProps={{ htmlInput: { maxLength: 1024 } }} />
          {message && <Alert severity="error">{t(...message).replace('{seconds}', String(locked))}</Alert>}
          {challenge && !error && <Alert severity={expired || challenge.delivery === 'unknown' ? 'warning' : 'info'}>
            {expired ? t('auth:otp_challenge_expired', '验证码已过期，请重新获取') : challenge.delivery === 'unknown' ? t('auth:otp_unknown', '发送状态未确认；若收到验证码仍可验证。请等待冷却结束后再决定是否重发。') : t('auth:otp_requested', '验证码已请求，有效期5分钟，请查看短信。')}
          </Alert>}
          <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.65 }}>{t('auth:bind_policy', '绑定后可用短信验证码登录，原有余额和会员保留；绑定不重复赠送积分。')}</Typography>
        </Box>}
    </DialogContent>
    <DialogActions sx={{ px: 3, pb: 2, gap: 1 }}><Button onClick={onClose} sx={{ minHeight: 44 }}>{bound ? t('auth:bind_done', '完成') : t('auth:cancel_btn', '取消')}</Button>
      {status && !bound && <Button form={id} type="submit" variant="contained" disabled={!challenge || !/^[0-9]{6}$/.test(code) || !password || expired || sending || submitting || locked > 0} sx={{ minHeight: 48 }}>
        {submitting ? t('auth:bind_submitting', '绑定中…') : t('auth:bind_submit', '确认绑定')}
      </Button>}
    </DialogActions>
  </>;
}
