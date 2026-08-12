import { useState } from 'react';
import { Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle, Button } from '@mui/material';
import {
  blockingCopy,
  blockingStateChip,
  displaceCopy,
  isResumableHere,
  isSyncRetryable,
  settlementSyncText,
} from '../../../features/aiLadder/blockingCopy';
import { useCountdown } from '../../../features/aiLadder/countdown';
import { useTranslation } from '../../../hooks/useTranslation';
import type { AiLadderBlockingGame } from '../../../features/aiLadder/types';
import '../../../kiosk-shell/tokens.css';
import '../../../kiosk-shell/go-tokens.css';
import './blockingPanel.css';

interface KioskAiLadderBlockingPanelProps {
  game: AiLadderBlockingGame;
  pending: boolean;
  /**
   * **必填,不是 `error?:`。** 可选 prop 看起来像契约,其实是个建议 —— 谁不传都编译得过,
   * 防御强度等于「写代码的人记得」。国象正是这么掉进去的:那块屏唯一的按钮按下去失败,
   * 错误写进了另一格的 state,屏上什么都不发生,按钮弹回可按。
   * (对照:`onRetrySettlement?` 的 `?` 保留 —— 那是真的可选**能力**。)
   */
  error: string;
  syncRetryPending: boolean;
  onContinue: (sessionId: string) => void;
  onEndGame: (gameId: string) => void;
  /** 只有盒子有 outbox。网页直连时不传,「立即重试」就不出现。 */
  onRetrySettlement?: (gameId: string) => void;
}

/** 时长 → 「多久之前」。`null` 走 absent,**不退化成 0** —— 没发生过和刚发生是相反的两件事。 */
const formatSpan = (seconds: number): string => {
  if (seconds < 60) return `${seconds} 秒`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟`;
  return `${Math.floor(seconds / 3600)} 小时`;
};
const formatAge = (seconds: number | null | undefined, absent: string): string =>
  typeof seconds === 'number' ? `${formatSpan(seconds)}前` : absent;
/** 「已经持续了多久」。和上面差一个「前」:心跳是时点,成绩已压是时段。 */
const formatDuration = (seconds: number | null | undefined, absent: string): string =>
  typeof seconds === 'number' ? formatSpan(seconds) : absent;

/**
 * 挡局屏的**右栏**(`kiosk-side`)。左栏是那块实体棋盘,由页面挂 `SmartBoardConsole`。
 *
 * **这一版一行新布局 CSS 都没写** —— 全用共享外壳 `tokens.css` 里本来就有的类:
 * `kiosk-side__fixed` / `kiosk-section` / `kiosk-seclabel` / `kiosk-status` / `kiosk-btn`。
 *
 * 上一版的根因就在这儿:我们**导入了共享骨架,然后没用它** —— 去抄了 `sample-xiangqi`
 * 模板里的 `.ranked-state__*`(那是象棋自己的局部 CSS,不是共享外壳),自造了一套。
 * `import` 成功、构建绿、什么都没报错,而那个文件里的九个类一个都没被引用。
 * **「没有报错」不携带「用上了」。**
 *
 * 右栏是**一叠卡**(`kiosk-section` × N),不是一张大卡里塞东西 —— 见 `sample-go/02-game.png`。
 *
 * ⚠️ 根节点必须挂 `.kiosk`:`tokens.css` 整份定义在那个类上,渲染到外面 `var()` 静默求空、
 * 字体掉回 sans、**且不报错**。
 */
const KioskAiLadderBlockingPanel = ({
  game,
  pending,
  error,
  syncRetryPending,
  onContinue,
  onEndGame,
  onRetrySettlement,
}: KioskAiLadderBlockingPanelProps) => {
  useTranslation();
  // 举起的确认落在**哪一局**上,而不是一个裸布尔:后台每 15 秒复查,换成另一局时这个
  // `armed` 自己就是假的(派生值,不需要 effect 去追);还是同一局但状态变了,弹窗留着,
  // 而里面每一句都从**当下**这份数据现算。
  const [armedGameId, setArmedGameId] = useState<string | null>(null);
  const armed = armedGameId === game.game_id;
  const remaining = useCountdown(
    game.sync?.state === 'waiting' ? game.sync.next_attempt_in_seconds : null,
  );

  const resumable = isResumableHere(game);
  const chip = blockingStateChip(game, resumable);
  const displace = displaceCopy(game);
  const canRetrySync = Boolean(onRetrySettlement)
    && game.state === 'pending_settlement'
    && isSyncRetryable(game.sync);
  const statusLine = error || (game.sync ? settlementSyncText(game.sync, remaining) : '');

  return (
    <div className="kiosk kiosk-side" data-testid="kiosk-ladder-blocking-panel">
      <div className="kiosk-side__fixed">
        {/* ① 状态卡:标题就是那句「这是哪一局 / 为什么挡着」。主角是**问题**,不是段位名 ——
               段位名是被挡住那一局的对手,摆成最大的字会被读成「我正要开的这局」。 */}
        <section className="kiosk-section" data-testid="kiosk-ladder-blocking-header">
          <div className="kiosk-seclabel">
            <h2>未完成对局</h2>
            <em>Unfinished</em>
            <span className="rule" />
            <b className="secval">{game.ownership === 'current_device' ? '当前设备' : '其他设备'}</b>
          </div>
          <p className="ladder-title" data-testid="kiosk-ladder-state-line">{blockingCopy(game, resumable)}</p>
        </section>

        {/* ② outbox 卡:只在**真有实况可报**时出现。没有实况时它会退化成复读下面那格事实,
               一句话在同一屏上说两遍不是信息是噪声。 */}
        {statusLine && (
          <section className="kiosk-section ladder-status-section">
            <p
              className={`ladder-status${error ? ' is-error' : ''}`}
              role={error ? 'alert' : undefined}
              data-testid="kiosk-ladder-sync-line"
              id="kiosk-ladder-blocking-body"
            >
              {statusLine}
            </p>
          </section>
        )}

        {/* ③ 事实卡:走共享的 `kiosk-status`(它本来就是「标签 + 值」的格子)。
               判据:**每一格都必须是标题读完之后还不知道的事** —— 所以没有「这一局的状态」
               那种标题的缩写。 */}
        <section className="kiosk-section" data-testid="kiosk-ladder-blocking-facts">
          <div className="kiosk-status kiosk-status--2">
            <div className="kiosk-status__cell">
              <span className="kiosk-status__k">对手档位</span>
              <b className="kiosk-status__v" data-testid="kiosk-ladder-blocking-name">{game.opponent_rank_name}</b>
            </div>
            <div className="kiosk-status__cell">
              <span className="kiosk-status__k">我执</span>
              <b className="kiosk-status__v">{game.user_color === 'B' ? '● 黑棋' : '○ 白棋'}</b>
            </div>
            <div className="kiosk-status__cell">
              {/* 标签跟着 `ownership` 走:心跳是 origin-only 上报的,而 `current_device`
                  的定义就是「origin 是这台机器」⇒ 那一格里它是**本机自己的**心跳。
                  **只报距今多久,不配失联阈值** —— 象棋那屏配了阈值,因为它的模型里还有
                  接管窗口;围棋把那一整套删了,再摆阈值等于把删掉的判据从 UI 长回来。 */}
              <span className="kiosk-status__k">
                {game.ownership === 'current_device' ? '本机心跳' : '对方设备心跳'}
              </span>
              <b className="kiosk-status__v">{formatAge(game.heartbeat_age_seconds, '未收到过')}</b>
            </div>
            <div className="kiosk-status__cell">
              <span className="kiosk-status__k">成绩已压</span>
              <b className="kiosk-status__v" data-testid="kiosk-ladder-sync-fact">
                {formatDuration(game.pending_since_seconds, '不适用')}
              </b>
            </div>
          </div>
        </section>

        {/* ④ 代价 + 动作,贴底。代价在按钮**上面** —— 放下面时手指已经在按钮上了才读到。 */}
        <section className="kiosk-section ladder-foot">
          <p className="ladder-cost">{displace.cost}</p>
          <div className="ladder-actions" data-testid="kiosk-ladder-blocking-actions">
            {resumable && (
              <button
                type="button"
                className="kiosk-btn kiosk-btn--primary"
                onClick={() => game.session_id && onContinue(game.session_id)}
                disabled={pending}
              >
                继续对局
              </button>
            )}
            {canRetrySync && (
              // 守卫 2:站在**有在途结算的这台盒子**前的人,第一个看到的必须是「把成绩救回去」,
              // 不是「认输」。云端只知道「成绩还没到」,是排队、退避、试完了还是被拒收
              // 全在这台机器的 outbox 里 —— 而那恰好是他唯一想问的事。
              <button
                type="button"
                className="kiosk-btn kiosk-btn--primary"
                onClick={() => onRetrySettlement?.(game.game_id)}
                disabled={syncRetryPending}
              >
                {syncRetryPending ? '正在重试…' : '立即重试'}
              </button>
            )}
            {/* 破坏性按钮**屏上不描红** —— 照象棋模板:屏上次级是描边,红留给不可回头那一步
                (二次确认)。国象与我们更早那版是屏上就描边。**这条归 Fan**,两版都留着。 */}
            <button
              type="button"
              className="kiosk-btn kiosk-btn--secondary"
              onClick={() => setArmedGameId(game.game_id)}
              disabled={pending}
            >
              {displace.button}
            </button>
          </div>
        </section>
      </div>

      <Dialog open={armed} onClose={() => setArmedGameId(null)} aria-labelledby="kiosk-ladder-exit-title">
        <DialogTitle id="kiosk-ladder-exit-title">{displace.title}</DialogTitle>
        <DialogContent>
          <DialogContentText>{displace.body}</DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button autoFocus onClick={() => setArmedGameId(null)} sx={{ minHeight: 44 }}>取消</Button>
          <Button
            color={displace.color}
            disabled={pending}
            onClick={() => {
              setArmedGameId(null);
              // 打的是同一个 `/end`:记负还是什么都不记,由**服务端按那一行的状态**决定。
              // 前端只负责把后果说对 —— 让它自己选路,就等于把同一个判断又实现了一遍。
              onEndGame(game.game_id);
            }}
            sx={{ minHeight: 44 }}
          >
            {displace.confirm}
          </Button>
        </DialogActions>
      </Dialog>
      {/* `chip.label` 这一版没有位置:它那句话已经由标题说出来。保留读取是为了让
          `blockingStateChip` 的契约仍被这块屏消费(galaxy 那边还在用它渲染徽标)。 */}
      <span hidden data-testid="kiosk-ladder-chip-label">{chip.label}</span>
    </div>
  );
};

export default KioskAiLadderBlockingPanel;
