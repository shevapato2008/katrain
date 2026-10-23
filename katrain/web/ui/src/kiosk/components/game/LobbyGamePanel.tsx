import { useId, useState, type ReactNode } from 'react';
import { Dialog, DialogActions, DialogContent, DialogTitle, Button } from '@mui/material';
import type { GameState, LobbyTerritoryResult } from '../../../api';
import { Icon } from '../../shell/icons';
import './LobbyGamePanel.css';

interface Props {
  gameState: GameState;
  setupLine: string;
  connected: boolean;
  isGameOver: boolean;
  blocked: boolean;
  counting: boolean;
  countDisabled?: boolean;
  statusSlot: ReactNode;
  hardwareFault: string | null;
  physicalPlay?: boolean;
  analysisToggles: Record<string, boolean>;
  onToggleAnalysis: (key: string) => void;
  onAction: (action: string) => void;
  onExit: () => void;
  territory: { phase: 'idle' | 'loading' | 'result' | 'error'; visible: boolean; disabled: boolean;
    result?: LobbyTerritoryResult; request: () => void };
}

function SeatSurface({ left, turn }: { left: boolean; turn: boolean }) {
  const id = useId();
  return <svg className="lobby-game__seat-surface" viewBox="0 0 234 126" preserveAspectRatio="none" aria-hidden="true">
    <defs><linearGradient id={id} x2="0.8" y2="1"><stop stopColor={turn ? '#2b6244' : '#26362c'} />
      <stop offset="1" stopColor={turn ? '#1c432f' : '#15231b'} /></linearGradient></defs>
    <path d={left ? 'M14 1 H218 Q233 1 230 15 L214 111 Q211 125 197 125 H14 Q1 125 1 112 V14 Q1 1 14 1 Z'
      : 'M36 1 H220 Q233 1 233 14 V112 Q233 125 220 125 H17 Q1 125 4 111 L20 15 Q22 1 36 1 Z'}
      fill={`url(#${id})`} stroke={turn ? '#69c98a' : '#405948'} strokeWidth="1.5" />
  </svg>;
}

export default function LobbyGamePanel({ gameState: gs, setupLine, connected, isGameOver, blocked, counting,
  countDisabled = false, statusSlot, hardwareFault, physicalPlay, analysisToggles, onToggleAnalysis, onAction, onExit, territory }: Props) {
  const [helpOpen, setHelpOpen] = useState(false);
  const myColor = gs.platform_my_color ?? gs.my_color;
  const mine = !!myColor && gs.player_to_move === myColor;
  const countMin = gs.count_min_moves ?? 100;
  // Preserve the existing formal-count gate; private territory uses current_node_index separately.
  const moves = gs.history?.length ?? 0;
  const stopped = !!gs.awaiting_count;
  const countRetry = stopped && !!gs.degraded;
  const canCount = !countDisabled && connected && !!myColor && !isGameOver && !counting && !blocked
    && (!stopped || countRetry) && (countRetry || moves >= countMin);
  const active = connected && !isGameOver && !blocked && !stopped;
  const title = !connected ? '连接尚未就绪' : isGameOver ? '本局已结束'
    : stopped || counting ? '正在数子' : mine ? '轮到你落子' : '等待对方落子';
  const detail = !connected ? '请先不要继续落子，恢复后核对最新盘面。'
    : isGameOver ? '正式结果以服务端终局为准。'
    : stopped || counting ? '结果尚未确定，请稍候。'
    : mine ? physicalPlay ? `请落${myColor === 'B' ? '黑' : '白'}子，识别确认后自动同步给对方。`
      : `请在棋盘落${myColor === 'B' ? '黑' : '白'}子。`
    : '对方落子后，棋盘和下一手提示会自动更新。';
  const territoryLine = territory.phase === 'loading' ? '正在查询领地…'
    : territory.phase === 'error' ? '领地未取得，请重试'
    : territory.result ? `领地参考 · 黑 ${territory.result.black_area.toFixed(1)} · 白 ${territory.result.white_area.toFixed(1)}` : null;
  return <>
    <header className="lobby-game__head" data-testid="game-pagebar">
      <button type="button" className="lobby-game__key lobby-game__back" onClick={onExit}><Icon name="arrow-left" />退出对局</button>
      <h2>大厅对局</h2><span>{setupLine}</span>
    </header>
    <div className="lobby-game__seats">
      {(['W', 'B'] as const).map((color, index) => {
        const turn = active && gs.player_to_move === color;
        return <section className="lobby-game__seat" data-testid="lobby-player" data-turn={turn} key={color} aria-label={`${color === 'B' ? '黑' : '白'}方玩家`}>
          <SeatSurface left={index === 0} turn={turn} />
          <div className="lobby-game__name"><span className={`lobby-game__stone lobby-game__stone--${color}`} />
            <strong title={gs.players_info[color].name}>{color === 'B' ? '黑' : '白'} · {gs.players_info[color].name}{color === myColor ? '（你）' : ''}</strong></div>
          <div className="lobby-game__move">{turn ? <>第 <b>{gs.current_node_index + 1}</b> 手</> : '不限时'}</div>
          <div className="lobby-game__seat-foot"><span>{!connected ? '等待重连' : isGameOver ? '已结束'
            : stopped || blocked || counting ? '等待确认' : turn ? color === myColor ? '轮到你' : '对方回合' : '等待中'}</span>
            <span>提子 <b>{gs.prisoner_count[color]}</b></span></div>
        </section>;
      })}
    </div>
    <section className="lobby-game__status" aria-label="在线对局状态" aria-live="polite">
      <div className="lobby-game__status-head"><strong>对局状态</strong><span>{connected ? '已连接' : '未连接'}</span></div>
      {statusSlot || (hardwareFault ? <div role="alert" className="lobby-game__fault">{hardwareFault}</div> : <><h3>{title}</h3><p>{detail}</p></>)}
      {statusSlot && hardwareFault && <p className="lobby-game__fault">{hardwareFault}</p>}
    </section>
    <div className="lobby-game__toggles" role="group" aria-label="棋盘显示">
      <button className="lobby-game__key" type="button" aria-pressed={analysisToggles.coords} onClick={() => onToggleAnalysis('coords')}><Icon name="grid-nine" />坐标</button>
      <button className="lobby-game__key" type="button" aria-pressed={analysisToggles.numbers} onClick={() => onToggleAnalysis('numbers')}><Icon name="list-numbers" />手数</button>
      <button className="lobby-game__key lobby-game__help" type="button" aria-label="大厅对局说明" onClick={() => setHelpOpen(true)}><Icon name="info" /></button>
    </div>
    <div className="lobby-game__actions" data-testid="game-actions">
      <button className="lobby-game__key" type="button" aria-pressed={territory.visible} aria-busy={territory.phase === 'loading'} disabled={territory.disabled} onClick={territory.request}><Icon name="map-trifold" />领地</button>
      <button className="lobby-game__key" type="button" disabled={!canCount} onClick={() => onAction('count')}><Icon name="squares-four" />数子</button>
      <button className="lobby-game__key" type="button" disabled={!active || !mine || counting} onClick={() => onAction('pass')}><Icon name="hand-pointing" />停一手</button>
      <button className="lobby-game__key lobby-game__danger" type="button" disabled={!active || !myColor || counting} onClick={() => onAction('resign')}><Icon name="flag" />认输</button>
    </div>
    <footer className="lobby-game__footer">
      <div><span>{isGameOver ? '本局已有正式结果' : stopped ? '正式结果尚未确定' : `满 ${countMin} 手可数子`}</span>
        {territoryLine && <span role={territory.phase === 'error' ? 'alert' : 'status'}>{territoryLine}</span>}</div>
      <p>仅供参考，正式胜负以数子为准</p>
    </footer>
    <Dialog open={helpOpen} onClose={() => setHelpOpen(false)} className="kiosk-game-side-dialog">
      <DialogTitle>大厅对局说明</DialogTitle><DialogContent>
        大厅对局不计升降段位。满 {countMin} 手后可请求数子，由对方确认；停一手仅在自己的回合可用。
        领地仅供本人参考，不决定正式胜负。局面变化后需重新查询。退出时可先离开，或确认认输并退出。
      </DialogContent><DialogActions><Button onClick={() => setHelpOpen(false)}>知道了</Button></DialogActions>
    </Dialog>
  </>;
}
