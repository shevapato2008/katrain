import { useEffect, useRef, useState } from 'react';
import { Alert, Box, Button, CircularProgress, TextField, Typography } from '@mui/material';
import { API, ApiError, type PhoneChallenge, type PhoneAuthErrorDetail } from '../../api';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../hooks/useTranslation';

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
  phone_verification_required: ['auth:otp_verification_required', '请使用短信验证码完成注册'],
};

export default function PhoneOtpForm({ onSuccess }: { onSuccess: () => void }) {
  const { t } = useTranslation();
  const { loginPhone, identityKey } = useAuth();
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
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
    setCode(''); setChallenge(null); setError(''); setSending(false); setSubmitting(false); setRetryAt(0); setExpiresAt(0);
  };
  useEffect(() => {
    reset(); setPhone('');
    return () => { revision.current += 1; controller.current?.abort(); flow.current = ''; };
    // Each identity owns its private form and outstanding work.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [identityKey]);
  useEffect(() => {
    if (!retryAt && !expiresAt) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [retryAt, expiresAt]);

  const remaining = Math.max(0, Math.ceil((retryAt - now) / 1000));
  const expired = Boolean(challenge && expiresAt <= now);
  const phoneValid = /^1[0-9]{10}$/.test(normalizePhone(phone));
  const showError = (err: unknown) => {
    const detail = err instanceof ApiError ? err.detail as PhoneAuthErrorDetail | undefined : undefined;
    const name = detail?.code && errorMessages[detail.code] ? detail.code : 'sms_unavailable';
    setError(name);
    if (detail?.retry_after && Number.isFinite(detail.retry_after)) {
      setRetryAt(Date.now() + Math.max(0, detail.retry_after) * 1000); setNow(Date.now());
    }
    if (['challenge_invalid', 'challenge_expired', 'challenge_used', 'identity_changed'].includes(name)) {
      setChallenge(null); setCode('');
    }
  };
  const send = async () => {
    if (sending || submitting || remaining) return;
    if (!phoneValid) { setError('invalid_phone'); return; }
    setError(''); setSending(true); setChallenge(null); setCode('');
    // A response can be lost after the provider accepted the send. Keep the
    // local wait even on a transport failure; the server owns all limits.
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
    if (!challenge || submitting || sending) return;
    if (Date.now() >= expiresAt) { setError('challenge_expired'); return; }
    if (!/^[0-9]{6}$/.test(code)) { setError('invalid_code'); return; }
    setError(''); setSubmitting(true);
    const version = revision.current;
    const request = new AbortController(); controller.current = request;
    const current = () => version === revision.current && !request.signal.aborted;
    try {
      await loginPhone({ challenge_id: challenge.challenge_id, code, flow_id: flow.current }, request.signal);
      if (current()) onSuccess();
    } catch (err) { if (current()) showError(err); }
    finally { if (current()) setSubmitting(false); }
  };
  const message = errorMessages[error];
  return (
    <Box component="form" onSubmit={submit} noValidate sx={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
      <TextField fullWidth autoFocus type="tel" autoComplete="tel-national" label={t('auth:otp_phone', '手机号（中国大陆 +86）')}
        value={phone} onChange={e => { reset(); setPhone(e.target.value); }} error={error === 'invalid_phone'}
        slotProps={{ htmlInput: { maxLength: 17, 'aria-describedby': 'phone-otp-policy' } }} />
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'start', minWidth: 0 }}>
        <TextField fullWidth label={t('auth:otp_code', '短信验证码')} value={code} autoComplete="one-time-code"
          onChange={e => { if (/^[0-9]{0,6}$/.test(e.target.value)) setCode(e.target.value); }} error={error === 'invalid_code'}
          slotProps={{ htmlInput: { inputMode: 'numeric', maxLength: 6, pattern: '[0-9]{6}' } }} sx={{ minWidth: 0 }} />
        <Button type="button" variant="outlined" onClick={send} disabled={sending || submitting || !phoneValid || remaining > 0}
          sx={{ minHeight: 56, minWidth: 116, px: 1, flexShrink: 0 }}>
          {sending ? <CircularProgress size={20} aria-label={t('auth:otp_sending', '发送中…')} /> : remaining ? t('auth:otp_retry', '{seconds}秒后重发').replace('{seconds}', String(remaining)) : t('auth:otp_send', '获取验证码')}
        </Button>
      </Box>
      {message && <Alert severity="error">{t(...message)}</Alert>}
      {challenge && !error && <Alert severity={expired || challenge.delivery === 'unknown' ? 'warning' : 'info'}>
        {expired ? t('auth:otp_challenge_expired', '验证码已过期，请重新获取') : challenge.delivery === 'unknown'
          ? t('auth:otp_unknown', '发送状态未确认；若收到验证码仍可验证。请等待冷却结束后再决定是否重发。')
          : t('auth:otp_requested', '验证码已请求，有效期5分钟，请查看短信。')}
      </Alert>}
      <Typography id="phone-otp-policy" variant="body2" color="text.secondary" sx={{ lineHeight: 1.65 }}>
        {t('auth:otp_signup_policy', '未注册手机号首次验证将创建账号。新手机号首次注册赠50积分；同手机号已领取或绑定过不重复赠送。')}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.65 }}>
        {t('auth:otp_existing_account', '已有账号请用账号密码登录后绑定手机号。')}
      </Typography>
      <Button type="submit" fullWidth variant="contained" disabled={!challenge || !/^[0-9]{6}$/.test(code) || expired || sending || submitting} sx={{ minHeight: 48 }}>
        {submitting ? t('auth:otp_verifying', '验证中…') : t('auth:otp_submit', '验证并登录')}
      </Button>
    </Box>
  );
}
