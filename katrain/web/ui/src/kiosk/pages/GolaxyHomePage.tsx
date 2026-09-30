import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { API, type PlatformInfo } from '../../api';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../hooks/useTranslation';
import { useVision } from '../context/VisionContext';
import { PLATFORM_MARKS } from '../constants/platformMarks';
import { KioskCard } from '../shell/KioskCard';
import { KioskPagebar } from '../shell/KioskPagebar';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import { playInputState, writePlayOnBoard } from '../utils/playInput';
import '../../kiosk-shell/golaxy-home.css';

type Connection =
  | { kind: 'loading' }
  | { kind: 'error' }
  | { kind: 'disconnected' }
  | { kind: 'connected'; account: PlatformInfo };

const GolaxyHomePage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { token, isAuthenticated } = useAuth();
  const { isVisionEnabled } = useVision();
  const [connection, setConnection] = useState<Connection>({ kind: 'loading' });
  const [retry, setRetry] = useState(0);
  const [, setInputTick] = useState(0);
  // Reading the preference on each render reflects the last tap without a second copy of that state.
  const input = playInputState(isVisionEnabled, 19);

  useEffect(() => {
    let cancelled = false;
    if (!isAuthenticated) {
      setConnection({ kind: 'disconnected' });
      return;
    }
    setConnection({ kind: 'loading' });
    API.platformStatus(token)
      .then(({ platforms }) => {
        if (cancelled) return;
        const account = platforms.find((entry) => entry.platform === 'golaxy');
        setConnection(account?.connected ? { kind: 'connected', account } : { kind: 'disconnected' });
      })
      .catch(() => { if (!cancelled) setConnection({ kind: 'error' }); });
    return () => { cancelled = true; };
  }, [isAuthenticated, token, retry]);

  const chooseInput = (onBoard: boolean) => {
    if (onBoard && !input.available) return;
    writePlayOnBoard(onBoard);
    setInputTick((tick) => tick + 1);
  };

  return (
    <div className="kiosk-layout-b golaxy-home" data-testid="golaxy-home-page">
      <KioskPagebar
        backLabel={t('platform:back_to_play', '返回对弈')}
        onBack={() => navigate('/kiosk/play')}
        title={<span className="golaxy-home__title">
          <img src={PLATFORM_MARKS.golaxy.src} alt="" />
          <strong>{t('platform:golaxy', '星阵围棋')}</strong>
          {connection.kind === 'connected' && <small>{t('platform:connected', '已连接')} · {connection.account.saved_username || t('platform:current_golaxy_account', '当前星阵账号')}</small>}
        </span>}
        status={connection.kind === 'connected' ? t('platform:connected', '已连接') : undefined}
      />

      <div className="golaxy-home__scroll">
        {connection.kind === 'loading' && <div className="golaxy-home__state" role="status">{t('platform:loading_connection', '正在读取星阵连接')}</div>}
        {connection.kind === 'error' && (
          <div className="golaxy-home__state" role="alert">
            <p>{t('platform:connection_check_failed', '没能读取星阵连接状态')}</p>
            <button type="button" onClick={() => setRetry((count) => count + 1)}>{t('common:retry', '重试')}</button>
          </div>
        )}
        {connection.kind === 'disconnected' && (
          <div className="golaxy-home__state">
            <p>{t('platform:not_connected', '星阵账号未连接')}</p>
            <button type="button" onClick={() => navigate('/kiosk/play/cross-platform/login/golaxy')}>{t('platform:connect_golaxy', '连接星阵')}</button>
          </div>
        )}
        {connection.kind === 'connected' && (
          <>
            <div className="golaxy-home__input">
              <span className="golaxy-home__input-label">{t('setup:input_where', '落子')}</span>
              <div className="golaxy-home__input-seg" role="group" aria-label={t('setup:input_where', '落子方式')}>
                <button type="button" aria-pressed={!input.onBoard} onClick={() => chooseInput(false)}>{t('setup:on_screen', '屏幕')}</button>
                <button type="button" aria-pressed={input.onBoard} disabled={!input.available} onClick={() => chooseInput(true)}>{t('setup:on_board', '实体盘')}</button>
              </div>
              <div className="golaxy-home__size"><span>{t('setup:board_size', '路数')}</span><b>19 路</b></div>
            </div>
            {!input.available && <p className="golaxy-home__input-hint">{t('setup:board_not_ready', '没标定过摄像头，当前使用屏幕落子')}</p>}

            <section className="golaxy-home__section">
              <KioskSecLabel zh={t('platform:start_game', '开一局')} en="Start" />
              <div className="kiosk-cards golaxy-home__cards">
                <KioskCard title={t('platform:quick_match', '快速匹配')} sub={t('platform:pvp_not_connected', '人人对弈还没接通')} icon="users" disabled />
                <KioskCard title={t('platform:rooms', '房间')} sub={t('platform:pvp_not_connected', '人人对弈还没接通')} icon="grid-nine" disabled />
                <KioskCard title={t('platform:engine_play', '人机对弈')} sub={t('platform:engine_setup', '星阵 AI · 选档开局')} icon="robot" onClick={() => navigate('/kiosk/play/cross-platform/engine/golaxy')} />
              </div>
            </section>

            <section className="golaxy-home__section">
              <KioskSecLabel zh={t('platform:players', '棋友')} en="Players" />
              <p className="golaxy-home__empty">{t('platform:pvp_not_connected', '人人对弈还没接通')}</p>
            </section>
          </>
        )}
      </div>
    </div>
  );
};

export default GolaxyHomePage;
