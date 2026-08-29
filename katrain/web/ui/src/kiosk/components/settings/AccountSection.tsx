import { useState } from 'react';
import { Dialog, DialogContent, DialogTitle } from '@mui/material';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '../../../context/AuthContext';
import { useTranslation } from '../../../hooks/useTranslation';
import { useAiLadderStatus } from '../../../features/aiLadder/useAiLadderStatus';
import AiLadderStatusCard from '../../../features/aiLadder/AiLadderStatusCard';

/**
 * 设置屏「账号与平台」那一组的前两行。
 *
 * 2026-08-23 从 MUI 卡片重排成外壳的 `.kiosk-row` —— 上一版是一张 `background.paper` 的卡
 * 加一条满宽的红色退出按钮,夹在两组 `.kiosk-row` 中间**像是从别的应用里剪进来的**。
 * 现在它就是两行:一行账号,一行 AI 段位。
 *
 * **详情仍旧是个对话框**(`AiLadderStatusCard` 那张卡还没重画)——
 * 但它只在点开之后才出现,不再占着这一组的正面。
 */
export default function AccountSection() {
  const { user, logout, token } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { status, retry } = useAiLadderStatus(token ?? undefined, Boolean(user));
  const [detailsOpen, setDetailsOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
    navigate('/kiosk/login', { replace: true });
  };

  // `AiLadderStatus` 是个联合类型 —— 只有 ready 那一支才有 placement / net_score /
  // current_opponent。先收窄成一个变量,别在下面每处各判一次。
  const ready = status.view_state === 'ready' ? status : null;
  const placement = ready?.placement_state ?? null;
  const entry = placement?.phase === 'placed' ? placement.rung : ready?.current_opponent;
  const netScore = ready ? (ready.net_score > 0 ? `+${ready.net_score}` : String(ready.net_score)) : null;

  return (
    <>
      <div className="kiosk-row">
        <span className="kiosk-row__t">
          <b>{user?.username ?? t('Guest', '访客')}</b>
          <em>
            {user
              ? `${t('Signed in', '已登录')} · ${t('StellaBox account', '智星盒账户')}`
              : t('settings:guest_sub', '这台盒子上的本地档案')}
          </em>
        </span>
        <span className="kiosk-row__end">
          {user ? (
            <button
              type="button"
              className="kiosk-btn kiosk-btn--pill rvdanger"
              data-testid="settings-logout"
              onClick={() => void handleLogout()}
            >
              {t('Sign out', '退出登录')}
            </button>
          ) : (
            <button
              type="button"
              className="kiosk-btn kiosk-btn--secondary"
              onClick={() => navigate('/kiosk/login')}
            >
              {t('settings:sign_in', '登录')}
            </button>
          )}
        </span>
      </div>

      {user && ready && (
        <div className="kiosk-row" data-testid="ai-ladder-account-summary">
          <span className="kiosk-row__t">
            <b>
              {placement?.phase === 'placed'
                ? `AI段位：${placement.rung.rank_name}`
                : `定级进度 ${placement?.completed_games ?? 0}/5`}
            </b>
            <em>累计净胜分：{netScore}</em>
          </span>
          <span className="kiosk-row__end">
            {entry && (
              <>
                <span className={entry.certification_status === 'certified' ? 'kiosk-tag kiosk-tag--win' : 'kiosk-tag'}>
                  {entry.certification_status === 'certified' ? '已认证' : '认证中'}
                </span>
                <span className="kiosk-tag">{entry.route === 'local' ? '本地对弈' : '服务器对弈'}</span>
              </>
            )}
            <button type="button" className="kiosk-btn kiosk-btn--pill" onClick={() => setDetailsOpen(true)}>
              查看AI段位详情
            </button>
          </span>
        </div>
      )}

      {/* 读不到段位的时候**照实说**,不拿一行空白顶替 —— 那张卡自己会讲是加载中还是失败。 */}
      {user && status.view_state !== 'ready' && (
        <div className="kiosk-row" data-testid="ai-ladder-account-fallback">
          <AiLadderStatusCard status={status} onRetry={retry} compact />
        </div>
      )}

      <Dialog open={detailsOpen} onClose={() => setDetailsOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>AI段位详情</DialogTitle>
        <DialogContent><AiLadderStatusCard status={status} onRetry={retry} compact /></DialogContent>
      </Dialog>
    </>
  );
}
