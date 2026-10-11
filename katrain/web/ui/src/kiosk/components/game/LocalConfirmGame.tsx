import { useEffect, useLayoutEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button } from '@mui/material';
import Board from '../../../components/Board';
import type { GameState } from '../../../api';
import { useTranslation } from '../../../hooks/useTranslation';
import { formatGtpCoord } from '../../../utils/gtpCoord';
import { colsFor, rowsFor } from '../../shell/goBoard';
import { Icon } from '../../shell/icons';
import { useVoice } from '../../hooks/useVoice';
import { useGoClock, type GoClockReading } from './goClock';
import './LocalConfirmGame.css';

interface Props {
  gameState: GameState;
  input: 'screen' | 'physical';
  point: { x: number; y: number } | null;
  busy: boolean;
  failed: boolean;
  analysisToggles: Record<string, boolean>;
  onToggle: (key: string) => void;
  onSelect: (x: number, y: number) => void;
  onConfirm: () => void;
  onPass: () => void;
  onCount: () => void;
  onResign: (color: 'B' | 'W') => void;
  onExit: () => void;
  onPaintedNode: (nodeId: number) => void;
  onExpired: () => void;
  blocked?: boolean;
}

const clockText = (seconds: number) => {
  const total = Math.ceil(Math.max(0, seconds));
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
};

export default function LocalConfirmGame({ gameState, input, point, busy, failed, analysisToggles,
  onToggle, onSelect, onConfirm, onPass, onCount, onResign, onExit, onPaintedNode, onExpired, blocked = false }: Props) {
  const { t } = useTranslation();
  const { speak, stop } = useVoice();
  useEffect(() => {
    if (gameState.current_node_index > gameState.handicap) return;
    const key = `local-confirm-guide:${gameState.game_id}`;
    try { if (sessionStorage.getItem(key)) return; sessionStorage.setItem(key, '1'); } catch { /* advisory */ }
    speak(input === 'physical' ? 'local_confirm_physical' : 'local_confirm_screen');
  }, [gameState.game_id, gameState.current_node_index, gameState.handicap, input, speak]);
  const [dialog, setDialog] = useState<'guide' | 'pass' | 'B' | 'W' | null>(null);
  const [headerSlot, setHeaderSlot] = useState<HTMLElement | null>(null);
  useLayoutEffect(() => {
    // The parent shell mounts the slot in the same commit as this page.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setHeaderSlot(document.getElementById('kiosk-topbar-actions'));
  }, []);
  const blackClock = useGoClock(gameState, 'B', busy ? undefined : onExpired);
  const whiteClock = useGoClock(gameState, 'W', busy ? undefined : onExpired);
  const [frozen, setFrozen] = useState<{ B: GoClockReading | null; W: GoClockReading | null } | null>(null);
  const closeDialog = () => { setDialog(null); stop(); };
  const beginConfirm = () => { setFrozen({ B: blackClock, W: whiteClock }); onConfirm(); };
  const activeColor = gameState.player_to_move === 'W' ? 'W' : 'B';
  const size = gameState.board_size[0];
  const selected = point ? formatGtpCoord(point.x, point.y, size) : null;
  const confirmation = gameState.local_confirmation;
  const capable = confirmation?.enabled === true && !blocked;
  const reason = confirmation?.reason;
  const error = failed || !!reason;
  const minMoves = gameState.count_min_moves ?? 100;
  const countAvailable = gameState.current_node_index >= minMoves || !!gameState.awaiting_count;
  const guidance = input === 'physical'
    ? t('game:local_physical_steps', '落子、拿除提子后，移开双手，再按确认。')
    : t('game:local_screen_steps', '点击棋盘选点，可再次点击改选，最后按确认。');
  const errorTitle = reason === 'multiple_stones' ? t('game:local_multiple_stones', '请只保留这一手')
    : reason === 'capture_remaining' ? t('game:local_capture_remaining', '请拿除提子')
      : reason === 'no_stone' ? t('game:local_no_stone', '还没看到新棋子')
        : reason === 'illegal_move' ? t('game:local_illegal_move', '请重新选择落点')
          : reason === 'unavailable' ? t('game:local_prepare_title', '请先准备好实体盘')
          : t('game:local_retry_title', '这一手尚未确认');
  const errorBody = reason === 'multiple_stones' ? t('game:local_multiple_steps', '拿回多下的棋子，再确认。')
    : reason === 'capture_remaining' ? t('game:local_capture_steps', '拿除叉号处的棋子，再确认。')
      : reason === 'no_stone' ? t('game:local_no_stone_steps', '落下一颗棋子，再确认。')
        : reason === 'unavailable' && input === 'physical' ? t('game:local_prepare_retry', '整理盘面，检查相机与标定。')
          : input === 'screen' ? t('game:local_screen_retry', '可改选位置，再确认。')
          : t('game:local_physical_retry', '移开双手，盘面稳定后重试。');

  const header = <div className="lc-header">
    <strong>{t('game:local_pvp', '本地对局')}</strong>
    <span>{t('game:local_move_number', '第 {n} 手').replace('{n}', String(gameState.current_node_index))} · {t('game:board_lines', '{n} 路').replace('{n}', String(size))}</span>
    <button type="button" onClick={() => setDialog('guide')}><Icon name="speaker-high" />{t('game:local_guide', '落子说明')}</button>
    <button type="button" disabled={busy} onClick={onExit}><Icon name="arrow-left" />{t('game:exit_game', '退出对局')}</button>
  </div>;

  const seat = (color: 'B' | 'W') => {
    const active = color === activeColor;
    const ownError = active && error && !busy;
    const label = color === 'B' ? t('game:black_side', '黑方') : t('game:white_side', '白方');
    const other = color === 'B' ? t('game:white_side', '白方') : t('game:black_side', '黑方');
    const clock = busy && frozen ? frozen[color] : color === 'B' ? blackClock : whiteClock;
    const running = active && !busy && gameState.timer?.paused === false;
    const copy = busy ? t('game:local_both_paused', '双方计时已暂停')
      : !active ? null : ownError ? errorBody : selected ? t('game:local_change_selection', '可改选位置') : null;
    return <section key={color} aria-label={`${label}玩家面板`} className={`lc-seat ${active ? 'is-active' : 'is-waiting'}${busy && active ? ' is-busy' : ''}${ownError ? ' is-error' : ''}`}>
      <div className="lc-seat-head"><span className="lc-stone-disc" aria-hidden="true"><img src={`/assets/img/${color}_stone.png`} alt="" /></span>
        <div><div className="lc-side">{label}<span className="lc-pill">{busy ? active ? t('game:local_confirming', '确认中') : t('game:local_wait_short', '请稍候') : ownError ? t('game:local_needs_attention', '待处理') : active ? t('game:local_playing', '走棋中') : t('game:local_waiting', '等待中')}</span></div>
          <div className="lc-name">{gameState.players_info[color].name || label}</div></div>
      </div>
      <div className={`lc-clock-block${clock?.byoLeft != null ? ' is-byoyomi' : ''}`}>
        <div className="lc-clock-top"><span>{clock?.byoLeft != null ? t('game:local_byoyomi', '读秒时间') : t('game:local_main_left', '剩余主时间')}</span>
          <span className={running ? 'is-running' : ''}>{running ? t('game:local_clock_running', '计时中') : t('game:local_clock_paused', '已暂停')}</span></div>
        <div className="lc-clock">{clock ? clockText(clock.byoLeft ?? clock.mainLeft) : t('game:untimed', '不限时')}</div>
        <div className="lc-clock-sub">{clock?.byoLeft != null ? `${t('game:local_periods_left', '剩 {n} 次').replace('{n}', String(clock.periodsLeft))} · ${gameState.timer?.settings.byo_length} ${t('game:seconds', '秒')}`
          : clock ? `${t('game:local_byoyomi', '读秒')} ${gameState.timer?.settings.byo_length} ${t('game:seconds', '秒')} × ${gameState.timer?.settings.byo_periods} ${t('game:times', '次')}` : null}</div>
      </div>
      <div className="lc-instruction" aria-live={active ? 'polite' : undefined}>
        <h2>{busy ? active ? input === 'physical' ? t('game:local_recognizing', '正在识别') : t('game:local_submitting', '正在确认') : t('game:local_wait_short', '请稍候')
          : !active ? `${t('game:local_wait', '等待')}${other}` : ownError ? errorTitle : selected ? `${t('game:local_selected', '已选')} ${selected}` : t('game:local_your_turn', '轮到你落子')}</h2>
        {copy && <p>{copy}</p>}
      </div>
      <div className="lc-view-toggles" aria-label={t('game:local_board_display', '棋盘显示')}>
        {['coords', 'numbers'].map(key => <button key={key} type="button" aria-pressed={!!analysisToggles[key]} onClick={() => onToggle(key)}>
          <Icon name={key === 'coords' ? 'grid-nine' : 'list-numbers'} />
          <span>{key === 'coords' ? t('Coordinates', '坐标') : t('Move Numbers', '手数')}</span>
          <span className="lc-toggle-state">{analysisToggles[key] ? t('On', '开') : t('Off', '关')}</span>
        </button>)}
      </div>
      <div className="lc-actions">
        <button type="button" disabled={!active || busy || !capable} onClick={() => setDialog('pass')}>{t('game:pass', '停一手')}</button>
        <button type="button" title={!countAvailable ? t('game:local_count_threshold', '数子需满 {n} 手').replace('{n}', String(minMoves)) : undefined} disabled={!active || busy || blocked || !countAvailable} onClick={onCount}>{t('game:count_stones', '数子')}</button>
        <button type="button" className="lc-resign" disabled={busy || blocked} onClick={() => setDialog(color)}>{t('Resign', '认输')}</button>
      </div>
      <button type="button" className="lc-confirm" disabled={!active || busy || !capable || (input === 'screen' && !point)} onClick={beginConfirm}>
        <span className="lc-confirm-label">{busy && active ? <span className="lc-spinner" aria-hidden="true" /> : active ? <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 4 4L19 6" /></svg> : null}
          {busy ? active ? input === 'physical' ? t('game:local_recognizing', '正在识别') : t('game:local_submitting', '正在确认') : t('game:local_wait_short', '请稍候') : active ? ownError ? t('game:local_confirm_again', '重新确认') : t('game:local_confirm_move', '确认落子') : `${t('game:local_wait', '等待')}${other}`}</span>
        <small>{busy ? t('game:local_both_paused', '双方计时已暂停') : active ? selected ? `${selected} · ${t('game:local_confirm_switch', '确认后换方')}` : input === 'screen' ? t('game:local_select_first', '先在棋盘选点') : t('game:local_confirm_switch', '确认后换方') : t('game:local_wait_confirm', '对方确认后再落子')}</small>
      </button>
    </section>;
  };

  return <>
    {headerSlot ? createPortal(header, headerSlot) : null}
    <div className="lc-arena" data-testid="local-confirm-game">
      {seat('B')}
      <div className="kiosk-board lc-board" data-testid="game-board">
        {['top', 'left'].map((side) => <div key={side} className={`kiosk-board__ruler kiosk-board__ruler--${side}`}>
          {(side === 'top' ? colsFor(size) : rowsFor(size)).map((text, i) => <span key={i}>{analysisToggles.coords ? text : ''}</span>)}</div>)}
        <div className="kiosk-board__play">
          <Board gameState={gameState} onMove={onSelect} analysisToggles={analysisToggles} externalRulers
            interactionDisabled={input === 'physical' || busy || !capable}
            previewMove={point ? { ...point, color: activeColor } : null} onPaintedNode={onPaintedNode} />
          {(confirmation?.points ?? []).map(({ row, col }) => <span key={`${row}-${col}`} className={`lc-board-marker${reason === 'capture_remaining' ? ' is-capture' : ''}`}
            aria-label={formatGtpCoord(col, size - 1 - row, size)} style={{ left: `${(col + 0.5) / size * 100}%`, top: `${(row + 0.5) / size * 100}%` }}>{reason === 'capture_remaining' ? '×' : ''}</span>)}
        </div>
        {['right', 'bottom'].map((side) => <div key={side} className={`kiosk-board__ruler kiosk-board__ruler--${side}`}>
          {(side === 'bottom' ? colsFor(size) : rowsFor(size)).map((text, i) => <span key={i}>{analysisToggles.coords ? text : ''}</span>)}</div>)}
      </div>
      {seat('W')}
    </div>
    <Dialog open={dialog !== null} onClose={busy ? undefined : closeDialog} className="kiosk-local-dialog">
      <DialogTitle>{dialog === 'guide' ? t('game:local_guide', '落子说明') : dialog === 'pass' ? t('game:local_pass_confirm', '确认停一手？') : `${dialog === 'B' ? t('game:black_side', '黑方') : t('game:white_side', '白方')}${t('game:local_resign_question', '认输？')}`}</DialogTitle>
      <DialogContent>
        <p>{dialog === 'guide' ? guidance : dialog === 'pass' ? point ? t('game:local_pass_discard', '停一手会放弃当前预选位置。') : input === 'physical' ? t('game:local_pass_physical', '请确认实体盘没有尚未确认的落子。') : t('game:local_pass_body', '停一手后将轮到对方。') : t('game:resign_local_body', '对方记中盘胜，这局会存进历史对局。')}</p>
        {dialog === 'guide' && <>
          <p>{t('game:local_guide_clock', '确认时双方计时暂停，成功后对方计时；失败仍由本方计时。听到确认音、对方区域亮起后，再下下一手。')}</p>
        </>}
      </DialogContent>
      <DialogActions>
        <Button onClick={closeDialog} disabled={busy}>{dialog === 'guide' ? t('game:local_got_it', '知道了') : t('Cancel', '取消')}</Button>
        {dialog === 'guide' ? <Button onClick={() => speak(input === 'physical' ? 'local_confirm_physical' : 'local_confirm_screen')}>{t('game:local_play_guide', '播放说明')}</Button>
          : <Button variant="contained" color={dialog === 'pass' ? 'primary' : 'error'} disabled={busy || blocked} onClick={() => {
            const action = dialog; closeDialog();
            if (action === 'pass') { setFrozen({ B: blackClock, W: whiteClock }); onPass(); }
            else if (action === 'B' || action === 'W') onResign(action);
          }}>{dialog === 'pass' ? t('game:local_pass_accept', '确认停一手') : dialog === 'B' ? t('game:local_black_resign_accept', '确认黑方认输') : t('game:local_white_resign_accept', '确认白方认输')}</Button>}
      </DialogActions>
    </Dialog>
  </>;
}
