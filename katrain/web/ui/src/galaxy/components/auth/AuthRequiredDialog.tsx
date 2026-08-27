import { useState } from 'react';
import { Button, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle } from '@mui/material';
import LoginIcon from '@mui/icons-material/Login';
import { useTranslation } from '../../../hooks/useTranslation';
import LoginModal from './LoginModal';

interface AuthRequiredDialogProps {
    open: boolean;
    onClose: () => void;
    /** 为什么这一步需要登录。留空时说一句通用的。 */
    message?: string;
}

/**
 * 「这一步需要登录」——**说清楚原因，并且当场给一个能按的入口**。
 *
 * 它替掉的是把服务端的 401 报文原样贴到屏上那种做法（`Request failed 401:
 * {"detail":"Not authenticated"}`）：那串字对用户既没说是什么事，也没说下一步该做什么，
 * 而下一步其实只有一个动作。侧边栏底部确实有登录按钮，但「需要登录」这句话出现在页面
 * 中间时，旁边没有可按的东西 —— 与 ReportsPage 未登录支同一个判断（见那里的注释）。
 *
 * 关掉登录框不等于关掉这条提示：登录成功时 `LoginModal` 自己会 `onClose`，此时
 * 上层的 `isAuthenticated` 已经翻成 true，调用方据此决定接下来显示什么。这里只负责
 * 把两个框串起来，不猜调用方要跳哪。
 */
const AuthRequiredDialog = ({ open, onClose, message }: AuthRequiredDialogProps) => {
    const { t } = useTranslation(); // 订阅语言切换，切了当场重渲染
    const [loginOpen, setLoginOpen] = useState(false);

    return (
        <>
            <Dialog open={open} onClose={onClose} PaperProps={{ sx: { borderRadius: 3, minWidth: 320 } }}>
                <DialogTitle>{t('auth:login_required_title', '需要登录')}</DialogTitle>
                <DialogContent>
                    <DialogContentText data-testid="login-required-message">
                        {message || t('auth:login_required_generic', '该功能需要登录后使用。')}
                    </DialogContentText>
                </DialogContent>
                <DialogActions sx={{ px: 3, pb: 2 }}>
                    <Button onClick={onClose} color="inherit">
                        {t('cancel', '取消')}
                    </Button>
                    <Button
                        data-testid="login-required-action"
                        variant="contained"
                        startIcon={<LoginIcon />}
                        onClick={() => setLoginOpen(true)}
                    >
                        {t('auth:go_login', '去登录')}
                    </Button>
                </DialogActions>
            </Dialog>
            <LoginModal open={loginOpen} onClose={() => setLoginOpen(false)} />
        </>
    );
};

export default AuthRequiredDialog;
