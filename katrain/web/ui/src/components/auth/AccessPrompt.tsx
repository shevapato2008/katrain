import { useId } from 'react';
import { Dialog, useTheme } from '@mui/material';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import WifiOffOutlinedIcon from '@mui/icons-material/WifiOffOutlined';
import { useMembershipI18n } from '../../features/membership/useMembershipI18n';
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
  const { t } = useMembershipI18n();
  const id = useId();
  const metadata = accessMetadata[feature];
  const membership = feature === 'membership';
  const label = membership ? t('membership:auth_label', '会员与用量')
    : surface === 'kiosk' && feature === 'hall' ? t('在线大厅', '在线大厅') : t(metadata.label, metadata.label);
  const checking = status === 'checking';
  const unavailable = status === 'unavailable';
  const title = checking ? t('membership:auth_checking_title', '正在确认登录状态')
    : unavailable ? t('membership:auth_unavailable_title', '暂时无法确认登录状态')
      : status === 'expired' ? t('membership:auth_expired_title', '请重新登录')
        : action ? feature === 'analysis' ? t('登录后使用引擎分析', '登录后使用引擎分析')
          : feature === 'cloud' ? t('登录后查看{feature}', '登录后查看{feature}', { feature: label })
            : t('登录后继续{feature}', '登录后继续{feature}', { feature: label })
          : t('登录后进入{feature}', '登录后进入{feature}', { feature: label });
  const description = checking ? t('membership:auth_checking_description', '请稍候，确认完成后将自动继续。')
    : unavailable ? t('membership:auth_unavailable_description', '网络或服务暂时不可用，请重试。你的登录凭据仍会保留。')
      : status === 'expired' ? action ? t('登录状态已失效。当前棋盘仍会保留。登录后可继续使用。', '登录状态已失效。当前棋盘仍会保留。登录后可继续使用。')
        : t('登录状态已失效。已暂停读取{feature}中的个人内容。登录后可继续使用。', '登录状态已失效。已暂停读取{feature}中的个人内容。登录后可继续使用。', { feature: label })
        : message || t(metadata.description, metadata.description);
  const note = checking ? t('membership:auth_checking_note', '确认期间不读取账号内容。')
    : unavailable ? t('membership:auth_unavailable_note', '无需退出账号，可在连接恢复后重试。')
      : strictBox ? t('membership:auth_box_note', '将在智星盒主页完成登录，再从围棋入口回到此模块。')
        : action ? feature === 'cloud' ? t('登录后返回当前棋谱分组，当前棋盘不会被清空。', '登录后返回当前棋谱分组，当前棋盘不会被清空。')
          : t('登录后仍需确认原操作，当前棋盘不会被清空。', '登录后仍需确认原操作，当前棋盘不会被清空。')
          : t('membership:auth_return_note', '登录完成后回到当前页面，无需重新寻找入口。');
  const membershipTitle = checking ? t('membership:auth_checking_title', '正在确认登录状态')
    : unavailable ? t('membership:auth_unavailable_title', '暂时无法确认登录状态')
      : status === 'expired' ? t('membership:auth_expired_title', '请重新登录')
        : t('membership:auth_login_title', '登录后查看会员与用量');
  const membershipDescription = checking ? t('membership:auth_checking_description', '请稍候，确认完成后将自动继续。')
    : unavailable ? t('membership:auth_unavailable_description', '网络或服务暂时不可用，请重试。你的登录凭据仍会保留。')
      : status === 'expired' ? t('membership:auth_expired_description', '登录状态已失效。已暂停读取会员与用量中的个人内容。登录后可继续使用。')
        : t('membership:auth_description', '登录后查看会员用量、API 积分与订单。');
  const membershipNote = checking ? t('membership:auth_checking_note', '确认期间不读取账号内容。')
    : unavailable ? t('membership:auth_unavailable_note', '无需退出账号，可在连接恢复后重试。')
      : strictBox ? t('membership:auth_box_note', '将在智星盒主页完成登录，再从围棋入口回到此模块。')
        : t('membership:auth_return_note', '登录完成后回到当前页面，无需重新寻找入口。');
  const membershipPrimary = checking ? t('membership:auth_checking_action', '正在确认')
    : unavailable ? t('membership:retry', '重试')
      : strictBox ? t('membership:auth_box_login', '去盒子主页登录') : t('membership:auth_login_continue', '登录并继续');
  return <Dialog
    open={open}
    aria-labelledby={`${id}-title`}
    aria-describedby={`${id}-description`}
    onClose={(_event, reason) => { if (reason === 'escapeKeyDown') onBack(); }}
    className={`access-modal access-${surface}`}
    slotProps={{
      backdrop: { sx: { backgroundColor: 'rgba(7,14,10,.42)' } },
      paper: { className: 'access-dialog', style: { fontFamily: surface === 'kiosk'
        ? '"SmartBox Serif", var(--kiosk-cjk-font, "SmartBox Kai"), "SmartBox Kai", serif'
        : theme.typography.fontFamily } },
    }}
  >
    <div className="access-symbol" aria-hidden="true">{checking ? <span className="access-loading" /> : unavailable ? <WifiOffOutlinedIcon /> : <LockOutlinedIcon />}</div>
    <p className="access-eyebrow">{label}</p>
    <h2 id={`${id}-title`}>{membership ? membershipTitle : title}</h2>
    <p className="access-description" id={`${id}-description`} data-testid="login-required-message">{membership ? membershipDescription : description}</p>
    <p className="access-next-note">{membership ? membershipNote : note}</p>
    <div className="access-actions">
      <button type="button" className="access-button" autoFocus={checking} onClick={onBack}>{membership ? t('membership:back_to_play', '返回对弈') : action ? t('继续浏览', '继续浏览') : t(metadata.backLabel, metadata.backLabel)}</button>
      <button type="button" className="access-button access-primary" data-testid="login-required-action" autoFocus={!checking} disabled={checking} onClick={onPrimary}>
        {membership ? membershipPrimary : checking ? t('membership:auth_checking_action', '正在确认') : unavailable ? t('membership:retry', '重试') : strictBox ? t('membership:auth_box_login', '去盒子主页登录') : t('membership:auth_login_continue', '登录并继续')}
      </button>
    </div>
    {status === 'guest' && feature === 'hall' && !action && <p className="access-quiet">{t('auth:hall_privacy_note', '未登录时不显示棋友名单和进行中的对局。')}</p>}
  </Dialog>;
}
