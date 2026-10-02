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
const MATCH_TIMES = [
  { id: 'fast', name: '快棋', details: '1 分 · 15 秒 × 3' },
  { id: 'normal', name: '普通', details: '10 分 · 30 秒 × 3' },
  { id: 'slow', name: '慢棋', details: '30 分 · 40 秒 × 3' },
] as const;
type MatchTime = typeof MATCH_TIMES[number]['id'];

const GolaxyPregameSetupPage = () => {
  const { mode } = useParams<{ mode: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { isVisionEnabled } = useVision();
  const [, setInputTick] = useState(0);
  const [roomTab, setRoomTab] = useState<'create' | 'mine' | 'join'>('create');
  const [roomNumber, setRoomNumber] = useState('');
  const [matchTimes, setMatchTimes] = useState<MatchTime[]>(['fast', 'normal', 'slow']);
  const input = playInputState(isVisionEnabled, 19);
  if (mode !== 'quick' && mode !== 'room') return <Navigate to={HOME} replace />;
  const quick = mode === 'quick';
  const title = quick ? t('platform:quick_match', '快速匹配') : t('platform:rooms', '房间');
  const toggleTime = (id: MatchTime) => setMatchTimes((selected) => selected.includes(id)
    ? selected.length > 1 ? selected.filter((choice) => choice !== id) : selected
    : [...selected, id]);
  return <div className="kiosk-layout-b golaxy-pregame" data-testid="golaxy-pregame-page" data-mode={mode}>
    <KioskPagebar backLabel={t('platform:golaxy', '星阵围棋')} onBack={() => navigate(HOME)} title={<span className="golaxy-pregame__page-title"><img src={PLATFORM_MARKS.golaxy.src} alt="" />{title}</span>} />
    <h1 className="golaxy-pregame__heading">{title}<small>{quick ? t('platform:quick_pregame', '落子位置与匹配用时在开局前设置') : t('platform:room_pregame', '创建、找回或按房号进入星阵房间')}</small></h1>
    <div className="golaxy-pregame__layout">
      <div className="golaxy-pregame__board"><KioskSetupBoard size={19} /><small>{t('platform:pregame_preview', '19 路 · 空盘预览')}</small></div>
      <div className="golaxy-pregame__panel">
        <div className="golaxy-pregame__input" data-testid="setup-input"><span>{t('setup:input_where', '落子')}</span><div role="group" aria-label={t('setup:input_where', '落子')}>
          <button type="button" aria-pressed={!input.onBoard} onClick={() => { writePlayOnBoard(false); setInputTick((n) => n + 1); }}>{t('setup:on_screen', '屏幕')}</button>
          <button type="button" aria-pressed={input.onBoard} disabled={!input.available} onClick={() => { writePlayOnBoard(true); setInputTick((n) => n + 1); }}>{t('setup:on_board', '实体盘')}</button>
        </div></div>
        {!input.available && <p>{t('setup:board_not_ready', '没标定过摄像头，当前使用屏幕落子')}</p>}
        {quick ? <div className="golaxy-pregame__quick">
          <div className="golaxy-pregame__section-head">{t('platform:match_times', '匹配用时 · 可多选')}</div>
          <div className="golaxy-pregame__times" role="group" aria-label={t('platform:match_times', '匹配用时 · 可多选')}>
            {MATCH_TIMES.map((choice) => <button key={choice.id} className="golaxy-pregame__time" type="button" aria-pressed={matchTimes.includes(choice.id)} onClick={() => toggleTime(choice.id)}>
              <b>{t(`platform:match_time_${choice.id}`, choice.name)}</b><small>{t(`platform:match_time_${choice.id}_details`, choice.details)}</small><span aria-hidden="true">{matchTimes.includes(choice.id) ? '✓' : ''}</span>
            </button>)}
          </div>
          <div className="golaxy-pregame__ai"><div><span>{t('platform:allow_ai_match', '允许匹配 AI 对手')}</span><small id="golaxy-ai-unavailable">{t('platform:ai_match_unavailable', 'AI 对手暂不可用，当前只匹配棋友')}</small></div><button type="button" role="switch" aria-label={t('platform:allow_ai_match', '允许匹配 AI 对手')} aria-checked={false} aria-describedby="golaxy-ai-unavailable" disabled /></div>
        </div> : <div className="golaxy-pregame__room">
          <div className="golaxy-pregame__tabs" role="tablist" aria-label={t('platform:room_mode', '房间方式')}>
            <button type="button" role="tab" aria-selected={roomTab === 'create'} onClick={() => setRoomTab('create')}>{t('platform:create_room', '创建房间')}</button>
            <button type="button" role="tab" aria-selected={roomTab === 'mine'} onClick={() => setRoomTab('mine')}>{t('platform:my_room', '我的房间')}</button>
            <button type="button" role="tab" aria-selected={roomTab === 'join'} onClick={() => setRoomTab('join')}>{t('platform:join_room', '加入房间')}</button>
          </div>
          <div className="golaxy-pregame__room-content">
            {roomTab === 'create' ? <>
              <h2>{t('platform:create_golaxy_room', '创建星阵房间')}</h2><p>{t('platform:create_room_hint', '创建后在房间内设置对局，再等待另一位棋手加入。')}</p><p className="golaxy-pregame__role">{t('platform:create_room_rules', '创建后与棋友确认对局规则。')}</p>
            </> : roomTab === 'mine' ? <>
              <h2>{t('platform:my_room', '我的房间')}</h2><p>{t('platform:my_room_hint', '显示星阵返回的当前账号所建房间。')}</p><div className="golaxy-pregame__my-empty">{t('platform:my_room_unavailable', '尚未接通我的房间')}</div>
            </> : <>
              <h2>{t('platform:join_golaxy_room', '加入星阵房间')}</h2><label className="golaxy-pregame__field">{t('platform:room_number', '房间号')}<input aria-label={t('platform:room_number', '房间号')} inputMode="numeric" placeholder={t('platform:enter_room_number', '请输入星阵房间号')} value={roomNumber} onChange={(event) => setRoomNumber(event.target.value)} /></label><p className="golaxy-pregame__role">{t('platform:join_room_role', '按房号进入可能是观战身份，仍需确认可对弈席位。')}</p>
            </>}
          </div>
        </div>}
        <div className="golaxy-pregame__notes"><p>{quick ? t('platform:match_times_hint', '可多选用时；至少选择一种。星阵完成匹配后才进入对局。') : t('platform:join_room_hint', '加入房间后仍需确认对局身份和开局状态。')}</p><p>{t('platform:pvp_start_unavailable', '星阵开局功能暂不可用，请稍后再试。')}</p></div>
        <button type="button" className="golaxy-pregame__submit" disabled>{quick ? t('platform:match_unavailable', '开始匹配 · 暂不可用') : roomTab === 'create' ? t('platform:create_unavailable', '创建房间 · 暂不可用') : roomTab === 'mine' ? t('platform:my_room_open_unavailable', '打开我的房间 · 暂不可用') : t('platform:join_unavailable', '加入房间 · 暂不可用')}</button>
      </div>
    </div>
  </div>;
};
export default GolaxyPregameSetupPage;
