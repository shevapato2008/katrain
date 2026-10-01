import { useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from '../../hooks/useTranslation';
import { useVision } from '../context/VisionContext';
import { PLATFORM_MARKS } from '../constants/platformMarks';
import KioskSetupBoard from '../components/board/KioskSetupBoard';
import { KioskPagebar } from '../shell/KioskPagebar';
import { playInputState, writePlayOnBoard } from '../utils/playInput';
import '../../kiosk-shell/golaxy-home.css';

const HOME = '/kiosk/play/cross-platform/golaxy';

const GolaxyPregameSetupPage = () => {
  const { mode } = useParams<{ mode: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { isVisionEnabled } = useVision();
  const [, setInputTick] = useState(0);
  const [roomTab, setRoomTab] = useState<'create' | 'join'>('create');
  const [roomNumber, setRoomNumber] = useState('');
  const input = playInputState(isVisionEnabled, 19);
  if (mode !== 'quick' && mode !== 'room') return <Navigate to={HOME} replace />;
  const quick = mode === 'quick';
  const title = quick ? t('platform:quick_match', '快速匹配') : t('platform:rooms', '房间');
  return <div className="kiosk-layout-b golaxy-pregame" data-testid="golaxy-pregame-page" data-mode={mode}>
    <KioskPagebar backLabel={t('platform:golaxy', '星阵围棋')} onBack={() => navigate(HOME)} title={<span className="golaxy-pregame__page-title"><img src={PLATFORM_MARKS.golaxy.src} alt="" />{title}</span>} />
    <h1 className="golaxy-pregame__heading">{title}<small>{quick ? t('platform:quick_pregame', '开局前选择落子方式，再由星阵匹配对手') : t('platform:room_pregame', '开局前选择落子方式，再创建或加入房间')}</small></h1>
    <div className="golaxy-pregame__layout">
      <div className="golaxy-pregame__board"><KioskSetupBoard size={19} /><small>{t('platform:pregame_preview', '19 路 · 开局预览')}</small></div>
      <div className="golaxy-pregame__panel">
        <div className="golaxy-pregame__input" data-testid="setup-input"><span>{t('setup:input_where', '落子')}</span><div role="group" aria-label={t('setup:input_where', '落子')}>
          <button type="button" aria-pressed={!input.onBoard} onClick={() => { writePlayOnBoard(false); setInputTick((n) => n + 1); }}>{t('setup:on_screen', '屏幕')}</button>
          <button type="button" aria-pressed={input.onBoard} disabled={!input.available} onClick={() => { writePlayOnBoard(true); setInputTick((n) => n + 1); }}>{t('setup:on_board', '实体盘')}</button>
        </div></div>
        {!input.available && <p>{t('setup:board_not_ready', '没标定过摄像头，当前使用屏幕落子')}</p>}
        {!quick && <div className="golaxy-pregame__tabs" role="tablist" aria-label={t('platform:room_mode', '房间方式')}>
          <button role="tab" aria-selected={roomTab === 'create'} onClick={() => setRoomTab('create')}>{t('platform:create_room', '创建房间')}</button>
          <button role="tab" aria-selected={roomTab === 'join'} onClick={() => setRoomTab('join')}>{t('platform:join_room', '加入房间')}</button>
        </div>}
        {!quick && roomTab === 'join' ? <label className="golaxy-pregame__field">{t('platform:room_number', '房间号')}<input aria-label={t('platform:room_number', '房间号')} inputMode="numeric" placeholder={t('platform:enter_room_number', '输入星阵房间号')} value={roomNumber} onChange={(event) => setRoomNumber(event.target.value)} /></label> : <div className="golaxy-pregame__field"><span>{t('platform:game', '对局')}</span><div data-testid="setup-board-size">{quick ? t('platform:quick_rules', '19 路 · 星阵快速匹配') : t('platform:room_rules', '19 路 · 房间对弈')}</div></div>}
        <p>{t('platform:remote_rules', '匹配与对局规则以星阵返回为准。')}</p>
        <p>{t('platform:pvp_protocol_pending', '星阵匹配与房间协议尚未确认，暂不能开局。')}</p>
        <button className="golaxy-pregame__submit" disabled>{quick ? t('platform:match_unavailable', '开始匹配 · 暂不可用') : roomTab === 'create' ? t('platform:create_unavailable', '创建房间 · 暂不可用') : t('platform:join_unavailable', '加入房间 · 暂不可用')}</button>
      </div>
    </div>
  </div>;
};
export default GolaxyPregameSetupPage;
