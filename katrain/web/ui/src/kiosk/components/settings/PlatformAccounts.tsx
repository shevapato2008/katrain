import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { API, type PlatformInfo } from '../../../api';
import { useAuth } from '../../../context/AuthContext';
import { useTranslation } from '../../../hooks/useTranslation';
import { PLATFORM_META } from '../../constants/platforms';
import { platformErrorMessage } from '../../utils/platformErrorMessage';

/** Manage the account saved on this box; platform status remains the source of truth. */
const PlatformAccounts = () => {
  const { token, isAuthenticated } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [accounts, setAccounts] = useState<PlatformInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [logoutTarget, setLogoutTarget] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async (failureMessage = '没能读取平台账号') => {
    if (!isAuthenticated) return;
    setLoading(true);
    try {
      const { platforms } = await API.platformStatus(token);
      setAccounts(platforms.filter((entry) => !PLATFORM_META[entry.platform]?.comingSoon || entry.connected || !!entry.saved_username));
      setError('');
    } catch (cause) {
      setError(failureMessage === '没能读取平台账号'
        ? platformErrorMessage(cause, failureMessage) : failureMessage);
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated, token]);

  useEffect(() => { void refresh(); }, [refresh]);

  const disconnect = async (platform: string) => {
    setBusy(true);
    try {
      await API.platformLogout(platform, token);
      setAccounts((current) => current.map((account) => account.platform === platform
        ? { ...account, connected: false, saved_username: undefined } : account));
      setLogoutTarget(null);
      await refresh('账号已删除，但没能刷新平台状态');
    } catch (cause) {
      setError(platformErrorMessage(cause, t('platform:logout_failed', '断开失败，请重试')));
      setLogoutTarget(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="kiosk-row">
        <span className="kiosk-row__t">
          <b>{t('settings:platforms', '跨平台账号')}</b>
          <em>{t('settings:platforms_sub', '在对弈首页选择星阵围棋或 OGS 连接')}</em>
        </span>
        <span className="kiosk-row__end">
          <button type="button" className="kiosk-btn kiosk-btn--secondary" onClick={() => navigate('/kiosk/play')}>
            {t('settings:go_connect', '去连接')}
          </button>
        </span>
      </div>
      {loading && accounts.length === 0 && <p className="setnote">{t('lobby:loading', '正在读…')}</p>}
      {error && <p role="alert" className="setnote">{error} <button type="button" onClick={() => { void refresh(); }}>{t('Retry', '重试')}</button></p>}
      {accounts.map((account) => {
        const name = PLATFORM_META[account.platform]?.labelCn ?? account.platform;
        const savedOffline = !account.connected && !!account.saved_username;
        return <div className="kiosk-row" data-testid={`platform-account-${account.platform}`} key={account.platform}>
          <span className="kiosk-row__t">
            <b>{name}</b>
            <em>{account.connected
              ? `${t('platform:connected', '已连接')}${account.saved_username ? ` · ${account.saved_username}` : ''}`
              : savedOffline
                ? `${t('platform:saved_offline', '账号已保存 · 当前未连接')} · ${account.saved_username}`
                : t('platform:disconnected', '未连接')}</em>
          </span>
          {(account.connected || savedOffline) && <span className="kiosk-row__end">
            <button type="button" className="kiosk-btn kiosk-btn--secondary" disabled={busy} onClick={() => setLogoutTarget(account.platform)}>
              {savedOffline ? t('platform:delete_account', '删除账号') : t('platform:logout', '登出')}
            </button>
          </span>}
        </div>;
      })}
      {logoutTarget && <div className="cdlg" data-testid="platform-logout-confirm">
        <div className="cdlg__box wdlg" role="dialog" aria-modal="true">
          <h3>{(accounts.find((account) => account.platform === logoutTarget)?.connected
            ? t('platform:logout_ask', '断开 {name}？')
            : t('platform:delete_ask', '删除 {name} 账号？'))
            .replace('{name}', PLATFORM_META[logoutTarget]?.labelCn ?? logoutTarget)}</h3>
          <p className="wdlg__lead">{t('platform:logout_body', '这台盒子上就不再是这个号了。再进去要重新登录一次。')}</p>
          <div className="cdlg__acts">
            <button type="button" className="ghost" disabled={busy} onClick={() => setLogoutTarget(null)}>{t('cancel', '取消')}</button>
            <button type="button" className="main" disabled={busy} onClick={() => { void disconnect(logoutTarget); }}>
              {accounts.find((account) => account.platform === logoutTarget)?.connected
                ? t('platform:logout', '登出') : t('platform:delete_account', '删除账号')}
            </button>
          </div>
        </div>
      </div>}
    </>
  );
};

export default PlatformAccounts;
