import { useEffect, useState } from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField, Alert, Box, Link } from '@mui/material';
import { useAuth } from '../../../context/AuthContext';
import { useSettings } from '../../../context/SettingsContext';
import { API } from '../../../api';
import { i18n } from '../../../i18n';
import CountryCodeSelect from './CountryCodeSelect';

interface LoginModalProps {
    open: boolean;
    onClose: () => void;
}

/** 三种模式，不是两个布尔量。原来的 `isRegister` 是二值取反（`setIsRegister(!isRegister)`），
 *  加进第三种之后取反没有意义 —— 所以换成显式的 `switchTo(next)`。 */
type LoginMode = 'login' | 'register' | 'phone';

const LoginModal = ({ open, onClose }: LoginModalProps) => {
    useSettings(); // Subscribe to translation changes
    const { login, loginByPhone } = useAuth();
    const [mode, setMode] = useState<LoginMode>('login');
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [cc, setCc] = useState('+86');
    const [phone, setPhone] = useState('');
    const [smsCode, setSmsCode] = useState('');
    const [challengeId, setChallengeId] = useState('');
    const [cooldown, setCooldown] = useState(0);
    const [error, setError] = useState('');
    const [successMsg, setSuccessMsg] = useState('');
    const [loading, setLoading] = useState(false);

    // setTimeout 而不是 setInterval：每一跳都自己取消，切模式/卸载时 cooldown 归 0
    // 就再也不排下一跳，不会有「关掉对话框后仍在跑的计时器」。
    useEffect(() => {
        if (cooldown <= 0) return;
        const id = setTimeout(() => setCooldown((c) => c - 1), 1000);
        return () => clearTimeout(id);
    }, [cooldown]);

    const fullPhone = `${cc}${phone.trim()}`;

    /** 后端的失败码 → 用户能照着做的一句话。吞成「操作失败」时我们其实已经知道
     *  是「还需等待 42 秒」，那是主动把已知信息扔掉。
     *
     *  后端把**全部**失败都发成 `{code}`，且**不带 message**（Task 7-10 的
     *  `HTTPException(400, detail={"code": e.code})`）。所以这张表必须覆盖后端会发的
     *  每一个码 —— 漏掉的那个会落到最后的兜底，而兜底在没有 message 时造出的是
     *  「请求失败 400」。**最高频的一次失败就是验证码填错**，它绝不能长这样。 */
    const describeError = (err: unknown): string => {
        const e = err as { code?: string; retryAfterSec?: number; message?: string };
        if (e?.code === 'sms_cooldown' || e?.code === 'sms_quota_ip') {
            return `${i18n.t('auth:err_cooldown', '验证码发送太频繁，还需等待')} ${e.retryAfterSec ?? 60} ${i18n.t('auth:seconds', '秒')}`;
        }
        if (e?.code === 'phone_not_bound') {
            return i18n.t('auth:err_phone_not_bound',
                '这个手机号还没有绑定账号。请先用用户名密码登录，再到左下角「设置 → 绑定手机号」绑定。');
        }
        const BY_CODE: Record<string, string> = {
            challenge_code_mismatch: i18n.t('auth:err_code_mismatch', '验证码不对，请检查后重填'),
            challenge_expired:       i18n.t('auth:err_code_expired', '验证码已过期，请重新获取'),
            challenge_consumed:      i18n.t('auth:err_code_used', '这个验证码已经用过了，请重新获取'),
            challenge_locked:        i18n.t('auth:err_code_locked', '错误次数太多，请重新获取验证码'),
            challenge_not_found:     i18n.t('auth:err_code_not_found', '验证码已失效，请重新获取'),
            challenge_purpose_mismatch: i18n.t('auth:err_code_purpose', '验证码用途不对，请重新获取'),
            bad_phone:               i18n.t('auth:err_bad_phone', '手机号格式不对，请检查区号与号码'),
            bad_purpose:             i18n.t('auth:err_bad_purpose', '请求有误，请刷新页面重试'),
            sms_quota_phone:         i18n.t('auth:err_quota_phone', '这个号码今天的验证码已达上限，请明天再试或联系客服'),
            sms_capacity:            i18n.t('auth:err_capacity', '短信通道今日已达上限，请稍后再试，或改用密码登录'),
            sms_provider_failed:     i18n.t('auth:err_provider', '发送失败，请重试'),
            phone_taken:             i18n.t('auth:err_phone_taken', '这个号已经有账号了，可以直接用验证码登录那个账号'),
            already_bound:           i18n.t('auth:err_already_bound', '你的账号已经绑过手机号了。换号请联系客服'),
            phone_unbound:           i18n.t('auth:err_phone_unbound', '请先绑定手机号'),
            phone_disabled_on_device: i18n.t('auth:err_on_device', '请在 modelstella.com 上完成手机号相关操作'),
            need_online_phone:       i18n.t('auth:err_need_online', '请在 modelstella.com 上完成手机号相关操作'),
        };
        if (e?.code && BY_CODE[e.code]) return BY_CODE[e.code];
        return e?.message || i18n.t('auth:err_failed', '操作失败');
    };

    const handleSendCode = async () => {
        setError('');
        setSuccessMsg('');
        if (!phone.trim()) {
            setError(i18n.t('auth:err_phone_required', '请填写手机号'));
            return;
        }
        try {
            const res = await API.sendPhoneCode(fullPhone, 'login');
            setChallengeId(res.challenge_id);
            setCooldown(res.cooldown_sec);
            // 我们拿不到运营商回执 ⇒ 只敢说「已提交发送」。说「已发送到您的手机」
            // 是在替运营商担保一件我们不知道的事（spec §2.3 状态诚实）。
            setSuccessMsg(i18n.t('auth:code_submitted', '验证码已提交发送，请查收短信'));
        } catch (err) {
            setError(describeError(err));
        }
    };

    const handleSubmit = async () => {
        setError('');
        setSuccessMsg('');

        // 这道守卫必须按模式分叉。原来是无差别的 `if (!username || !password)` ——
        // 验证码模式下两个都空，提交在这里当场短路，验证码那一支根本进不去。
        if (mode === 'phone') {
            if (!phone.trim()) {
                setError(i18n.t('auth:err_phone_required', '请填写手机号'));
                return;
            }
            if (!smsCode.trim()) {
                setError(i18n.t('auth:err_code_required', '请填写验证码'));
                return;
            }
        } else {
            if (!username || !password) {
                setError(i18n.t('auth:err_fill_all', '请填写全部字段'));
                return;
            }
            if (mode === 'register' && password !== confirmPassword) {
                setError(i18n.t('auth:err_pass_mismatch', '两次输入的密码不一致'));
                return;
            }
        }

        setLoading(true);
        try {
            if (mode === 'phone') {
                await loginByPhone(challengeId, smsCode.trim());
            } else if (mode === 'register') {
                // Register then login
                await API.register(username, password);
                setSuccessMsg(i18n.t('auth:success_register', '注册成功，正在登录…'));
                await login(username, password);
            } else {
                await login(username, password);
            }
            onClose();
            // Reset state slightly after close for smooth transition
            setTimeout(() => {
                setUsername('');
                setPassword('');
                setConfirmPassword('');
                // 不清 = 下次打开对话框带着上一位用户的手机号和一个还在跑的倒计时。
                setPhone('');
                setSmsCode('');
                setChallengeId('');
                setCooldown(0);
                setMode('login');
                setSuccessMsg('');
            }, 500);
        } catch (err) {
            setError(describeError(err));
        } finally {
            setLoading(false);
        }
    };

    /** 用户名**不清** —— 与原来的 `toggleMode` 一致（填了名字再决定去注册是常态）。
     *  手机那一组反过来必须清干净：号码是个人信息，模式切走了就不该留在框里。 */
    const switchTo = (next: LoginMode) => {
        setMode(next);
        setError('');
        setSuccessMsg('');
        setPassword('');
        setConfirmPassword('');
        setPhone('');
        setSmsCode('');
        setChallengeId('');
        setCooldown(0);
    };

    const linkSx = { textDecoration: 'none' } as const;

    return (
        <Dialog open={open} onClose={onClose} PaperProps={{ sx: { borderRadius: 3, p: 1, minWidth: 350 } }}>
            <DialogTitle>
                {/* 登录与验证码两模式共用一个标题：否则标题里的「验证码登录」会和切换链接的同名文本撞在一起。 */}
                {mode === 'register' ? i18n.t('auth:register_title', '注册账号') : i18n.t('auth:login_title', '登录智星盒')}
            </DialogTitle>
            <DialogContent>
                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
                {successMsg && <Alert severity="success" sx={{ mb: 2 }}>{successMsg}</Alert>}

                {mode !== 'phone' && (
                    <>
                        <TextField
                            autoFocus
                            margin="dense"
                            label={i18n.t('auth:username', '用户名')}
                            fullWidth
                            variant="outlined"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            disabled={loading}
                        />
                        <TextField
                            margin="dense"
                            label={i18n.t('auth:password', '密码')}
                            type="password"
                            fullWidth
                            variant="outlined"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            onKeyPress={(e) => e.key === 'Enter' && handleSubmit()}
                            disabled={loading}
                        />
                    </>
                )}

                {mode === 'register' && (
                    <TextField
                        margin="dense"
                        label={i18n.t('auth:confirm_password', '确认密码')}
                        type="password"
                        fullWidth
                        variant="outlined"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        onKeyPress={(e) => e.key === 'Enter' && handleSubmit()}
                        disabled={loading}
                    />
                )}

                {mode === 'phone' && (
                    <>
                        <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
                            <CountryCodeSelect value={cc} onChange={setCc} disabled={loading} />
                            <TextField
                                autoFocus
                                margin="dense"
                                label={i18n.t('auth:phone', '手机号')}
                                fullWidth
                                variant="outlined"
                                value={phone}
                                onChange={(e) => setPhone(e.target.value)}
                                onKeyPress={(e) => e.key === 'Enter' && handleSubmit()}
                                disabled={loading}
                            />
                        </Box>
                        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                            <TextField
                                margin="dense"
                                label={i18n.t('auth:sms_code', '验证码')}
                                fullWidth
                                variant="outlined"
                                value={smsCode}
                                onChange={(e) => setSmsCode(e.target.value)}
                                onKeyPress={(e) => e.key === 'Enter' && handleSubmit()}
                                disabled={loading}
                            />
                            <Button
                                onClick={handleSendCode}
                                disabled={loading || cooldown > 0}
                                sx={{ flex: 'none', whiteSpace: 'nowrap' }}
                            >
                                {cooldown > 0
                                    ? `${cooldown} ${i18n.t('auth:resend_after', '秒后可重发')}`
                                    : i18n.t('auth:get_code', '获取验证码')}
                            </Button>
                        </Box>
                    </>
                )}

                <Box sx={{ mt: 2, textAlign: 'center', display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                    {mode === 'login' && (
                        <>
                            <Link component="button" variant="body2" onClick={() => switchTo('phone')} disabled={loading} sx={linkSx}>
                                {i18n.t('auth:switch_to_phone', '验证码登录')}
                            </Link>
                            {/* 「忘记密码？」走的就是验证码登录 —— 验证码登录本身已经是完整的
                                「忘了密码也能进」出路，再做一个免鉴权 reset 是同一件事实现两遍。 */}
                            <Link component="button" variant="body2" onClick={() => switchTo('phone')} disabled={loading} sx={linkSx}>
                                {i18n.t('auth:forgot_password', '忘记密码？')}
                            </Link>
                            <Link component="button" variant="body2" onClick={() => switchTo('register')} disabled={loading} sx={linkSx}>
                                {i18n.t('auth:switch_to_register', '还没有账号？注册')}
                            </Link>
                        </>
                    )}
                    {mode === 'register' && (
                        <Link component="button" variant="body2" onClick={() => switchTo('login')} disabled={loading} sx={linkSx}>
                            {i18n.t('auth:switch_to_login', '已有账号？登录')}
                        </Link>
                    )}
                    {mode === 'phone' && (
                        <Link component="button" variant="body2" onClick={() => switchTo('login')} disabled={loading} sx={linkSx}>
                            {i18n.t('auth:switch_to_password', '密码登录')}
                        </Link>
                    )}
                </Box>
            </DialogContent>
            <DialogActions sx={{ px: 3, pb: 2 }}>
                <Button onClick={onClose} disabled={loading}>{i18n.t('auth:cancel_btn', '取消')}</Button>
                <Button onClick={handleSubmit} variant="contained" disabled={loading}>
                    {mode === 'register' ? i18n.t('auth:register_btn', '注册') : i18n.t('auth:login_btn', '登录')}
                </Button>
            </DialogActions>
        </Dialog>
    );
};

export default LoginModal;
