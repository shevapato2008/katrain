import { interpolate } from '../../utils/interpolate';
import { useTranslation } from '../../../hooks/useTranslation';
import { useState, type ReactNode } from 'react';
import { Dialog, DialogActions, DialogContent, DialogTitle, Button } from '@mui/material';
import type { GameState, LobbyTerritoryResult } from '../../../api';
import { PlayerCardSurface } from '../../shell/PlayerCardSurface';
import { Icon } from '../../shell/icons';
import { presentPlayerRank, UNKNOWN_RANK, type PlayerRanks } from '../../utils/playerRank';
import './LobbyGamePanel.css';

interface Props {
  gameState: GameState;
  sessionId?: string;
  playerRanks?: PlayerRanks;
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

export default function LobbyGamePanel({ gameState: gs, playerRanks, setupLine, connected, isGameOver, blocked, counting,
  countDisabled = false, statusSlot, hardwareFault, physicalPlay, analysisToggles, onToggleAnalysis, onAction, onExit, territory }: Props) {
  const { t } = useTranslation();
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
  const title = !connected ? t("连接尚未就绪", "连接尚未就绪") : isGameOver ? t("本局已结束", "本局已结束")
    : stopped || counting ? t("正在数子", "正在数子") : mine ? t("轮到你落子", "轮到你落子") : t("等待对方落子", "等待对方落子");
  const detail = !connected ? t("请先不要继续落子，恢复后核对最新盘面。", "请先不要继续落子，恢复后核对最新盘面。")
    : isGameOver ? t("正式结果以服务端终局为准。", "正式结果以服务端终局为准。")
    : stopped || counting ? t("结果尚未确定，请稍候。", "结果尚未确定，请稍候。")
    : mine ? physicalPlay ? interpolate(t("请落{value1}子，识别确认后自动同步给对方。", "请落{value1}子，识别确认后自动同步给对方。"), { value1: myColor === 'B' ? t("黑", "黑") : t("白", "白") })
      : interpolate(t("请在棋盘落{value1}子。", "请在棋盘落{value1}子。"), { value1: myColor === 'B' ? t("黑", "黑") : t("白", "白") })
    : t("对方落子后，棋盘和下一手提示会自动更新。", "对方落子后，棋盘和下一手提示会自动更新。");
  const territoryLine = territory.phase === 'loading' ? t("正在查询领地…", "正在查询领地…")
    : territory.phase === 'error' ? t("领地未取得，请重试", "领地未取得，请重试")
    : territory.result ? interpolate(t("领地参考 · 黑 {value1} · 白 {value2}", "领地参考 · 黑 {value1} · 白 {value2}"), { value1: territory.result.black_area.toFixed(1), value2: territory.result.white_area.toFixed(1) }) : null;
  return <>
    <header className="lobby-game__head" data-testid="game-pagebar">
      <button type="button" className="lobby-game__key lobby-game__back" onClick={onExit}><Icon name="arrow-left" />{t("退出对局", "退出对局")}</button>
      <h2>{t("大厅对局", "大厅对局")}</h2><span title={setupLine}>{setupLine}</span>
    </header>
    <div className="lobby-game__seats kiosk-player-pair">
      {(['W', 'B'] as const).map((color, index) => {
        const rank = presentPlayerRank(playerRanks?.[color] ?? UNKNOWN_RANK, t);
        const turn = active && gs.player_to_move === color;
        return <section className="lobby-game__seat kiosk-player-card" data-testid="lobby-player" data-turn={turn} key={color} aria-label={interpolate(t("{value1}方玩家", "{value1}方玩家"), { value1: color === 'B' ? t('Black', '黑') : t('White', '白') })}>
          <PlayerCardSurface left={index === 0} />
          <div className="lobby-game__name"><span className={`lobby-game__stone lobby-game__stone--${color}`} />
            <strong title={gs.players_info[color].name} aria-label={interpolate(t("{name}{value2}", "{name}{value2}"), { name: gs.players_info[color].name, value2: color === myColor ? t('（你）', '（你）') : '' })}>{gs.players_info[color].name}</strong><span className="kiosk-player-rank" title={rank.title} aria-label={rank.title}>{rank.label}</span></div>
          <div className="lobby-game__move">{turn ? <>{t("第", "第")} <b>{gs.current_node_index + 1}</b> {t("手", "手")}</> : t("不限时", "不限时")}</div>
          <div className="lobby-game__seat-foot"><span>{!connected ? t("等待重连", "等待重连") : isGameOver ? t("已结束", "已结束")
            : stopped || blocked || counting ? t("等待确认", "等待确认") : turn ? color === myColor ? t("轮到你", "轮到你") : t("对方回合", "对方回合") : t("等待中", "等待中")}</span>
            <span>{t("提子", "提子")} <b>{gs.prisoner_count[color]}</b></span></div>
        </section>;
      })}
    </div>
    <section className="lobby-game__status" aria-label={t("在线对局状态", "在线对局状态")} aria-live="polite">
      <div className="lobby-game__status-head"><strong>{t("对局状态", "对局状态")}</strong><span>{connected ? t("已连接", "已连接") : t("未连接", "未连接")}</span></div>
      {statusSlot || (hardwareFault ? <div role="alert" className="lobby-game__fault">{hardwareFault}</div> : <><h3>{title}</h3><p>{detail}</p></>)}
      {statusSlot && hardwareFault && <p className="lobby-game__fault">{hardwareFault}</p>}
    </section>
    <div className="lobby-game__toggles" role="group" aria-label={t("棋盘显示", "棋盘显示")}>
      <button className="lobby-game__key" type="button" aria-pressed={analysisToggles.coords} onClick={() => onToggleAnalysis('coords')}><Icon name="grid-nine" />{t("坐标", "坐标")}</button>
      <button className="lobby-game__key" type="button" aria-pressed={analysisToggles.numbers} onClick={() => onToggleAnalysis('numbers')}><Icon name="list-numbers" />{t("手数", "手数")}</button>
      <button className="lobby-game__key lobby-game__help" type="button" aria-label={t("大厅对局说明", "大厅对局说明")} onClick={() => setHelpOpen(true)}><Icon name="info" /></button>
    </div>
    <div className="lobby-game__actions" data-testid="game-actions">
      <button className="lobby-game__key" type="button" aria-pressed={territory.visible} aria-busy={territory.phase === 'loading'} disabled={territory.disabled} onClick={territory.request}><Icon name="map-trifold" />{t("领地", "领地")}</button>
      <button className="lobby-game__key" type="button" disabled={!canCount} onClick={() => onAction('count')}><Icon name="squares-four" />{t("数子", "数子")}</button>
      <button className="lobby-game__key" type="button" disabled={!active || !mine || counting} onClick={() => onAction('pass')}><Icon name="hand-pointing" />{t("停一手", "停一手")}</button>
      <button className="lobby-game__key lobby-game__danger" type="button" disabled={!active || !myColor || counting} onClick={() => onAction('resign')}><Icon name="flag" />{t("认输", "认输")}</button>
    </div>
    <footer className="lobby-game__footer">
      <div><span>{isGameOver ? t("本局已有正式结果", "本局已有正式结果") : stopped ? t("正式结果尚未确定", "正式结果尚未确定") : interpolate(t("满 {countMin} 手可数子", "满 {countMin} 手可数子"), { countMin: countMin })}</span>
        {territoryLine && <span role={territory.phase === 'error' ? 'alert' : 'status'}>{territoryLine}</span>}</div>
      <p>{t("仅供参考，正式胜负以数子为准", "仅供参考，正式胜负以数子为准")}</p>
    </footer>
    <Dialog open={helpOpen} onClose={() => setHelpOpen(false)} className="kiosk-game-side-dialog">
      <DialogTitle>{t("大厅对局说明", "大厅对局说明")}</DialogTitle><DialogContent>
        {t("大厅对局不计升降段位。满", "大厅对局不计升降段位。满")}{countMin} {t("手后可请求数子，由对方确认；停一手仅在自己的回合可用。 领地仅供本人参考，不决定正式胜负。局面变化后需重新查询。退出时可先离开，或确认认输并退出。", "手后可请求数子，由对方确认；停一手仅在自己的回合可用。 领地仅供本人参考，不决定正式胜负。局面变化后需重新查询。退出时可先离开，或确认认输并退出。")}</DialogContent><DialogActions><Button onClick={() => setHelpOpen(false)}>{t("知道了", "知道了")}</Button></DialogActions>
    </Dialog>
  </>;
}
