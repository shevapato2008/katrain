import { useId } from 'react';
import { Dialog, useTheme } from '@mui/material';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import WifiOffOutlinedIcon from '@mui/icons-material/WifiOffOutlined';
import { useTranslation } from '../../hooks/useTranslation';
import type { AuthStatus } from '../../context/AuthContext';
import { accessMetadata, type AccessFeature } from './accessPolicy';
import './accessPrompt.css';

interface AccessPromptProps {
  open: boolean;
  surface: 'galaxy' | 'kiosk';
  status: AuthStatus;
  feature: AccessFeature;
  onPrimary: () => void;
  onBack: () => void;
  strictBox?: boolean;
  action?: boolean;
  message?: string;
}

/** Presentation only: surface adapters own login, retry, navigation and authorization. */
export function AccessPrompt({ open, surface, status, feature, onPrimary, onBack, strictBox, action, message }: AccessPromptProps) {
  const theme = useTheme();
  const { t } = useTranslation();
  const id = useId();
  const metadata = accessMetadata[feature];
  const label = t(`auth:feature_${surface}_${feature}`, surface === 'kiosk' && feature === 'hall' ? '在线大厅' : metadata.label);
  const checking = status === 'checking';
  const unavailable = status === 'unavailable';
  const title = checking ? '正在确认登录状态' : unavailable ? '暂时无法确认登录状态' : status === 'expired' ? '请重新登录'
    : action ? feature === 'analysis' ? '登录后使用引擎分析' : feature === 'cloud' ? '登录后查看' + label : '登录后继续' + label : '登录后进入' + label;
  const description = checking ? '请稍候，确认完成后将自动继续。' : unavailable ? '网络或服务暂时不可用，请重试。你的登录凭据仍会保留。'
    : status === 'expired' ? `登录状态已失效。${action ? '当前棋盘仍会保留。' : '已暂停读取' + label + '中的个人内容。'}登录后可继续使用。`
    : message || t(`auth:feature_${feature}_description`, metadata.description);
  const note = checking ? '确认期间不读取账号内容。' : unavailable ? '无需退出账号，可在连接恢复后重试。'
    : strictBox ? '将在智星盒主页完成登录，再从围棋入口回到此模块。'
    : action ? feature === 'cloud' ? '登录后返回当前棋谱分组，当前棋盘不会被清空。' : '登录后仍需确认原操作，当前棋盘不会被清空。' : '登录完成后回到当前页面，无需重新寻找入口。';
  return <Dialog
    open={open}
    aria-labelledby={`${id}-title`}
    aria-describedby={`${id}-description`}
    onClose={(_event, reason) => { if (reason === 'escapeKeyDown') onBack(); }}
    className={`access-modal access-${surface}`}
    slotProps={{
      backdrop: { sx: { backgroundColor: 'rgba(7,14,10,.42)' } },
      paper: { className: 'access-dialog', style: { fontFamily: surface === 'kiosk' ? '"SmartBox Kai", "Kaiti SC", serif' : theme.typography.fontFamily } },
    }}
  >
    <div className="access-symbol" aria-hidden="true">{checking ? <span className="access-loading" /> : unavailable ? <WifiOffOutlinedIcon /> : <LockOutlinedIcon />}</div>
    <p className="access-eyebrow">{label}</p>
    <h2 id={`${id}-title`}>{t(`auth:gate_${status}_${action ? 'action' : 'page'}_${feature}`, title)}</h2>
    <p className="access-description" id={`${id}-description`} data-testid="login-required-message">{message && status === 'guest' ? message : t(`auth:gate_description_${status}_${feature}`, description)}</p>
    <p className="access-next-note">{t(`auth:gate_note_${status}_${strictBox ? 'box' : action ? 'action' : 'page'}`, note)}</p>
    <div className="access-actions">
      <button type="button" className="access-button" autoFocus={checking} onClick={onBack}>{t(action ? 'auth:continue_browsing' : `auth:feature_${feature}_back`, action ? '继续浏览' : metadata.backLabel)}</button>
      <button type="button" className="access-button access-primary" data-testid="login-required-action" autoFocus={!checking} disabled={checking} onClick={onPrimary}>
        {t(checking ? 'auth:checking' : unavailable ? 'auth:retry' : strictBox ? 'auth:box_login' : 'auth:login_continue', checking ? '正在确认' : unavailable ? '重试' : strictBox ? '去盒子主页登录' : '登录并继续')}
      </button>
    </div>
    {status === 'guest' && feature === 'hall' && !action && <p className="access-quiet">{t('auth:hall_privacy_note', '未登录时不显示棋友名单和进行中的对局。')}</p>}
  </Dialog>;
}
