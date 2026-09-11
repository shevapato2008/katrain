import { useEffect, useState } from 'react';
import { Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, TextField, Typography } from '@mui/material';
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
/** `'bind'` 绑号，`'set_password'` 用同一个壳改密码。
 *
 *  为什么共用：两条流程的前四步一模一样（区号 + 手机号 + 发码 + 填码），
 *  差别只在 purpose、多一个新密码框、提交打哪个端点。拆成两个组件等于把倒计时、
 *  错误码映射、关掉即复位这三件事各写两遍。 */
export type PhoneDialogPurpose = 'bind' | 'set_password';

const BindPhoneDialog = ({ open, onClose, purpose = 'bind' }: {
  open: boolean; onClose: () => void; purpose?: PhoneDialogPurpose;
}) => {
  useTranslation();
  const { user, refreshUser } = useAuth();
  const isSetPassword = purpose === 'set_password';
  /* set_password 不重复要求同意：它的前置就是这个号已经绑在这个账号上
     （未绑号下面换成引导去绑），收集手机号的同意在绑定那一刻已经给过 ——
     再问一次是**为已经持有的数据要同意**。 */
  const requireConsent = !isSetPassword;
  const needsPhoneFirst = isSetPassword && !user?.phone_bound;
  const [cc, setCc] = useState('+86');
  const [phone, setPhone] = useState('');
  const [smsCode, setSmsCode] = useState('');
  const [challengeId, setChallengeId] = useState('');
  const [consent, setConsent] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [newPassword, setNewPassword] = useState('');
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
    setConsent(false); setCooldown(0); setError(''); setSuccessMsg(''); setNewPassword('');
  }, [open]);

  const describeError = (err: unknown): string => {
    const e = err as { code?: string; retryAfterSec?: number; message?: string };
    if (e?.code === 'phone_taken') {
      return i18n.t('auth:err_phone_taken', '这个号已经有账号了，可以直接用验证码登录那个账号');
    }
    if (e?.code === 'challenge_phone_mismatch') {
      return i18n.t('auth:err_challenge_phone_mismatch',
        '验证码发到的号码不是这个账号绑定的手机号。请填写你绑定过的那个号。');
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
      const res = await API.sendPhoneCode(`${cc}${phone.trim()}`, isSetPassword ? 'set_password' : 'bind');
      setChallengeId(res.challenge_id);
      setCooldown(res.cooldown_sec);
      setSuccessMsg(i18n.t('auth:code_submitted', '验证码已提交发送，请查收短信'));
    } catch (err) { setError(describeError(err)); }
  };

  const handleSubmit = async () => {
    setError('');
    if (!smsCode.trim()) { setError(i18n.t('auth:err_code_required', '请填写验证码')); return; }
    if (isSetPassword && !newPassword.trim()) {
      setError(i18n.t('auth:err_new_password_required', '请填写新密码')); return;
    }
    setLoading(true);
    try {
      if (isSetPassword) {
        await API.setPassword(challengeId, smsCode.trim(), newPassword);
        /* 不关窗，先把这句说出来：改密码**踢不掉**已签发的凭据，refresh token 是 90 天
           （auth.py:540-542 的 docstring 明写「UI 必须把这句说出来」）。
           用户以为改完就安全了 —— 不说出来就是给他一个错的安全承诺。 */
        setSuccessMsg(i18n.t('auth:set_password_other_devices',
          '密码已经改好了。已经登录的设备不会被强制退出，最长 90 天内仍可继续使用。'));
      } else {
        await API.bindPhone(challengeId, smsCode.trim());
        await refreshUser();      // 不刷新 = 额度文案与侧栏入口都还停在旧状态
        onClose();
      }
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
      <DialogTitle id={TITLE_ID}>
        {isSetPassword ? i18n.t('auth:set_password', '修改密码') : i18n.t('auth:bind_phone', '绑定手机号')}
      </DialogTitle>
      <DialogContent>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {successMsg && <Alert severity="success" sx={{ mb: 2 }}>{successMsg}</Alert>}
        {/* 未绑号改密码在后端是 400 phone_unbound（auth.py:548-552）——
            让他填完一整张表再被拒，是把一个**已知**的失败藏到最后一步。 */}
        {needsPhoneFirst ? (
          <Typography variant="body2" color="text.secondary" sx={{ py: 1 }}>
            {i18n.t('auth:set_password_needs_phone',
              '修改密码需要先绑定手机号。请先在「设置 → 绑定手机号」完成绑定，再回来改密码。')}
          </Typography>
        ) : (
        <>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
          <CountryCodeSelect value={cc} onChange={setCc} disabled={loading} />
          <TextField
            autoFocus margin="dense" fullWidth variant="outlined" disabled={loading}
            label={i18n.t('auth:phone', '手机号')}
            value={phone} onChange={(e) => setPhone(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSubmit()}
          />
        </Box>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          <TextField
            margin="dense" fullWidth variant="outlined" disabled={loading}
            label={i18n.t('auth:sms_code', '验证码')}
            value={smsCode} onChange={(e) => setSmsCode(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSubmit()}
          />
          <Button
            onClick={handleSendCode}
            disabled={loading || cooldown > 0 || (requireConsent && !consent)}
            sx={{ flex: 'none', whiteSpace: 'nowrap' }}
          >
            {cooldown > 0
              ? `${cooldown} ${i18n.t('auth:resend_after', '秒后可重发')}`
              : i18n.t('auth:get_code', '获取验证码')}
          </Button>
        </Box>
        {isSetPassword && (
          <TextField
            margin="dense" fullWidth variant="outlined" type="password" disabled={loading}
            label={i18n.t('auth:new_password', '新密码')}
            value={newPassword} onChange={(e) => setNewPassword(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSubmit()}
          />
        )}
        {requireConsent && <PhoneConsent checked={consent} onChange={setConsent} disabled={loading} />}
        </>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={loading}>{i18n.t('auth:cancel_btn', '取消')}</Button>
        {!needsPhoneFirst && (
          <Button onClick={handleSubmit} variant="contained" disabled={loading}>
            {isSetPassword ? i18n.t('auth:set_password_btn', '确认修改') : i18n.t('auth:bind_btn', '绑定')}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};

export default BindPhoneDialog;
