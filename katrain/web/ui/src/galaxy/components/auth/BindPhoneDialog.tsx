import { useEffect, useState } from 'react';
import { Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, TextField } from '@mui/material';
import { API } from '../../../api';
import { useAuth } from '../../../context/AuthContext';
import { i18n } from '../../../i18n';
import { useTranslation } from '../../../hooks/useTranslation';
import CountryCodeSelect from './CountryCodeSelect';
import PhoneConsent from './PhoneConsent';

const TITLE_ID = 'bind-phone-dialog-title';

/** 绑定手机号。与登录框的验证码区块是同一套控件、同一条同意口径，差别只有两处：
 *
 *  1. purpose 是 `'bind'` 不是 `'login'` —— 走错的话后端 `verify_and_consume` 以
 *     `challenge_purpose_mismatch` 拒掉，而用户看到的是一句莫名其妙的失败；
 *  2. 成功后要 `refreshUser()` 让 `user.phone_bound` 翻面 —— 免费额度文案与侧栏入口都读它，
 *     不刷新的话两处都还停在旧状态，用户以为没绑上。
 */
const BindPhoneDialog = ({ open, onClose }: { open: boolean; onClose: () => void }) => {
  useTranslation();
  const { refreshUser } = useAuth();
  const [cc, setCc] = useState('+86');
  const [phone, setPhone] = useState('');
  const [smsCode, setSmsCode] = useState('');
  const [challengeId, setChallengeId] = useState('');
  const [consent, setConsent] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (cooldown <= 0) return;
    const id = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(id);
  }, [cooldown]);

  // 关掉即复位：下一次打开不许带着上一位用户的号、上一次的 challenge、还在跑的倒计时、
  // 以及上一位给出的同意 —— 同 LoginModal 的 handleClose，同一条口径。
  useEffect(() => {
    if (open) return;
    setPhone(''); setSmsCode(''); setChallengeId('');
    setConsent(false); setCooldown(0); setError(''); setSuccessMsg('');
  }, [open]);

  const describeError = (err: unknown): string => {
    const e = err as { code?: string; retryAfterSec?: number; message?: string };
    if (e?.code === 'phone_taken') {
      return i18n.t('auth:err_phone_taken', '这个号已经有账号了，可以直接用验证码登录那个账号');
    }
    if (e?.code === 'already_bound') {
      return i18n.t('auth:err_already_bound', '你的账号已经绑过手机号了。换号请联系客服');
    }
    if (e?.code === 'sms_cooldown' || e?.code === 'sms_quota_ip') {
      return `${i18n.t('auth:err_cooldown', '验证码发送太频繁，还需等待')} ${e.retryAfterSec ?? 60} ${i18n.t('auth:seconds', '秒')}`;
    }
    return e?.message || i18n.t('auth:err_failed', '操作失败');
  };

  const handleSendCode = async () => {
    setError(''); setSuccessMsg('');
    if (!phone.trim()) { setError(i18n.t('auth:err_phone_required', '请填写手机号')); return; }
    try {
      const res = await API.sendPhoneCode(`${cc}${phone.trim()}`, 'bind');
      setChallengeId(res.challenge_id);
      setCooldown(res.cooldown_sec);
      setSuccessMsg(i18n.t('auth:code_submitted', '验证码已提交发送，请查收短信'));
    } catch (err) { setError(describeError(err)); }
  };

  const handleBind = async () => {
    setError('');
    if (!smsCode.trim()) { setError(i18n.t('auth:err_code_required', '请填写验证码')); return; }
    setLoading(true);
    try {
      await API.bindPhone(challengeId, smsCode.trim());
      await refreshUser();      // 不刷新 = 额度文案与侧栏入口都还停在旧状态
      onClose();
    } catch (err) {
      setError(describeError(err));
    } finally { setLoading(false); }
  };

  return (
    /* aria-labelledby 要显式接：MUI 的 Dialog 不会自动把 DialogTitle 认成可访问名，
       不接的话 getByRole('dialog', { name: … }) 解析不出来。 */
    <Dialog
      open={open}
      onClose={onClose}
      aria-labelledby={TITLE_ID}
      PaperProps={{ sx: { borderRadius: 3, p: 1, minWidth: 360 } }}
    >
      <DialogTitle id={TITLE_ID}>{i18n.t('auth:bind_phone', '绑定手机号')}</DialogTitle>
      <DialogContent>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {successMsg && <Alert severity="success" sx={{ mb: 2 }}>{successMsg}</Alert>}
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
          <CountryCodeSelect value={cc} onChange={setCc} disabled={loading} />
          <TextField
            autoFocus margin="dense" fullWidth variant="outlined" disabled={loading}
            label={i18n.t('auth:phone', '手机号')}
            value={phone} onChange={(e) => setPhone(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleBind()}
          />
        </Box>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          <TextField
            margin="dense" fullWidth variant="outlined" disabled={loading}
            label={i18n.t('auth:sms_code', '验证码')}
            value={smsCode} onChange={(e) => setSmsCode(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleBind()}
          />
          <Button
            onClick={handleSendCode}
            disabled={loading || cooldown > 0 || !consent}
            sx={{ flex: 'none', whiteSpace: 'nowrap' }}
          >
            {cooldown > 0
              ? `${cooldown} ${i18n.t('auth:resend_after', '秒后可重发')}`
              : i18n.t('auth:get_code', '获取验证码')}
          </Button>
        </Box>
        <PhoneConsent checked={consent} onChange={setConsent} disabled={loading} />
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={loading}>{i18n.t('auth:cancel_btn', '取消')}</Button>
        <Button onClick={handleBind} variant="contained" disabled={loading}>
          {i18n.t('auth:bind_btn', '绑定')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default BindPhoneDialog;
