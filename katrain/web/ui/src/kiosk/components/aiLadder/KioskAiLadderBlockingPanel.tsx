import { useState } from 'react';
import { Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle, Button } from '@mui/material';
import {
  blockingCopy,
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
import './rankedState.css';

interface KioskAiLadderBlockingPanelProps {
  game: AiLadderBlockingGame;
  pending: boolean;
  /**
   * **必填,不是 `error?:`。** 可选 prop 看起来像契约,其实是个建议 —— 谁不传都编译得过,
   * 防御强度等于「写代码的人记得」。国象正是这么掉进去的:那块屏唯一的按钮按下去失败,
   * 错误写进了另一格的 state,屏上什么都不发生,按钮弹回可按。
   * (对照:`onRetrySettlement?` 的 `?` 保留 —— 那是真的可选**能力**。
   * 判据:可选的应该是「这块屏有没有这个能力」,不是「这块屏说不说实话」。)
   */
  error: string;
  syncRetryPending: boolean;
  onContinue: (sessionId: string) => void;
  onEndGame: (gameId: string) => void;
  /** 只有盒子有 outbox。网页直连时不传,「立即重试」就不出现。 */
  onRetrySettlement?: (gameId: string) => void;
}

/**
 * 时长 → 屏上那句话。`null` 走 `absent`,**不退化成「0 秒」** ——
 * 「那件事还没发生过」和「刚刚发生」是相反的两件事。
 */
const formatAge = (seconds: number | null | undefined, absent: string): string => {
  if (typeof seconds !== 'number') return absent;
  if (seconds < 60) return `${seconds} 秒前`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟前`;
  return `${Math.floor(seconds / 3600)} 小时前`;
};

/** 参考屏 seal 槽位里是奖杯,这里换成围棋的棋子 —— 同一个几何槽位,换本棋种的符号。 */
const SealMark = () => (
  <svg viewBox="0 0 24 24" aria-hidden focusable="false">
    <circle cx="12" cy="12" r="8" />
  </svg>
);

/**
 * kiosk 上的「有一局挡着新局」,**骨架照共享外壳的象棋样屏,配色用围棋青毡**。
 *
 * 这一版换掉的是**几何**,不是文案也不是盒子链:
 *   · 从前整屏走 MUI 默认尺度,而另外三家都 `import tokens.css`(991 行结构 token)——
 *     围棋这条跨仓依赖从来没建立过,不是忘了 import。颜色一直是对的,几何从来没接进来。
 *   · 中段空得像没加载完,根因是缺**两列事实格**那一层;补上它同时解决「空」和「信息不足」。
 *   · 动作从竖排堆叠改成并排贴底等宽。
 *
 * ⚠️ 根节点必须挂 `.kiosk`:`tokens.css` 整份定义在那个类上,渲染到外面 `var()` **静默求空**、
 * 字体掉回 sans、且**不报错**。
 *
 * **承重结论原样保留**:叙述区仍是 `overflow-y: auto` 且 `scrollTop` 真能推,而必需信息
 * (标题 =「这是哪一局 / 为什么挡着」)仍在**不参与滚动**的头部。改外观不动盒子链 ——
 * 但余量数一定变,四图和余量表都重打了。
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
  // blockingCopy/displaceCopy 每次 render 才查 i18n;没有这个订阅,切语言这块面板不动。
  useTranslation();
  // 举起的确认落在**哪一局**上,而不是一个裸的布尔 —— 后台每 15 秒复查一次,弹窗开着的时候
  // 底下那一格会自己变。换成了另一局,这个 `armed` 自己就是假的(派生值,不需要 effect 去追);
  // 还是同一局但状态变了,弹窗留着、而里面每一句都从**当下**这份数据现算。
  const [armedGameId, setArmedGameId] = useState<string | null>(null);
  const armed = armedGameId === game.game_id;
  const remaining = useCountdown(
    game.sync?.state === 'waiting' ? game.sync.next_attempt_in_seconds : null,
  );

  const resumable = isResumableHere(game);
  // 徽标在这一版**没有位置了**:它的那句话(「未了结」/「成绩未送达」)已经由标题说出来,
  // 再摆一格就是标题的回声。galaxy 那块屏仍然用 `blockingStateChip`,那边的头部没有这句话。
  const displace = displaceCopy(game);
  const canRetrySync = Boolean(onRetrySettlement)
    && game.state === 'pending_settlement'
    && isSyncRetryable(game.sync);

  // 状态条的语气:三档各有**字符前缀 + 颜色**两个通道,不靠颜色单跑。
  const tone = error
    ? 'error'
    : (game.sync?.state === 'waiting' || game.sync?.state === 'sending' ? 'progress' : undefined);

  return (
    <div className="kiosk ranked-state" data-testid="kiosk-ladder-blocking-panel">
      <div className="ranked-state__head" data-testid="kiosk-ladder-blocking-header">
        <div className="ranked-state__seal"><SealMark /></div>
        <div style={{ minWidth: 0 }}>
          {/* 主角是**问题**,不是段位名。从前全屏最大的字是 `opponent_rank_name`,
              而那是**被挡住那一局**的对手段位 —— 用户会把它读成「我正要开的这局」。 */}
          <h2 data-testid="kiosk-ladder-state-line">{blockingCopy(game, resumable)}</h2>
          <p>未完成对局 · {game.ownership === 'current_device' ? '当前设备' : '其他设备'}</p>
        </div>
      </div>

      <div className="ranked-state__scroll" data-testid="kiosk-ladder-blocking-body">
        {/* 状态条只在**真有实况可报**时出现:错误,或者 outbox 有话说。
            没有实况时它会退化成复读下面那格事实(「未了结」/「未了结」)——
            一句话在同一屏上说两遍,不是信息是噪声。状态条空着比复读诚实。 */}
        {(error || game.sync) && (
          <div
            className="ranked-state__status"
            data-tone={tone}
            role={error ? 'alert' : undefined}
            data-testid="kiosk-ladder-sync-line"
          >
            {error || (game.sync ? settlementSyncText(game.sync, remaining) : '')}
          </div>
        )}

      </div>

      {/* 事实格**在可滚区外面**。它承载的是必需的**数**(重试几次、什么档位、执什么色),
          而上面那条状态条长度不可控(错误文案/长译文都往那儿去)。把两者放在同一个可滚区里,
          状态条一长就把这些数顶出静止帧 —— 用户据以决定的东西被一句解释挤走了。
          ⇒ 变长的那个滚,必需的那个钉住。 */}
      <div className="ranked-state__facts" data-testid="kiosk-ladder-blocking-facts">
          <div className="ranked-state__fact">
            <span>对手档位</span>
            <b data-testid="kiosk-ladder-blocking-name">{game.opponent_rank_name}</b>
          </div>
          <div className="ranked-state__fact">
            <span>我执</span>
            <b>{game.user_color === 'B' ? '● 黑棋' : '○ 白棋'}</b>
          </div>
          {/* 这两格摆的是**诊断数**,不是身份也不是标题的回声。
              判据一句:**每一格都必须是标题读完之后还不知道的事。**
              曾经这里是「这一局的状态」(永远是标题的缩写)和「成绩同步」(复读状态条),
              于是同一个数一屏印两遍、同一句话说三遍。 */}
          <div className="ranked-state__fact">
            <span>对方设备心跳</span>
            {/* 只报**距今多久**,**不配失联阈值** —— 象棋那屏配了,因为它的模型里还有接管窗口;
                围棋把那一整套删了,再摆个阈值等于把删掉的判据从 UI 里长回来。 */}
            <b className={typeof game.heartbeat_age_seconds === 'number' ? 'mono' : undefined}>
              {formatAge(game.heartbeat_age_seconds, '未收到过')}
            </b>
          </div>
          <div className="ranked-state__fact">
            <span>成绩已压</span>
            {/* 状态条已经说了「重试几次 / 还有多久」,所以这格**不复读它**,报的是另一件事:
                这笔成绩压了多久。没进 pending 就是「不适用」,不是「0」。 */}
            <b className={typeof game.pending_since_seconds === 'number' ? 'mono' : undefined} data-testid="kiosk-ladder-sync-fact">
              {formatAge(game.pending_since_seconds, '不适用')}
            </b>
          </div>
      </div>

      {/* 代价行在动作行**上面** —— 照参考屏。放在按钮下面时,手指已经在按钮上了才读到
          「按下去会发生什么」,那等于按下之后才说。 */}
      <p className="ranked-state__cost">{displace.cost}</p>

      <div className="ranked-state__actions" data-testid="kiosk-ladder-blocking-actions">
        {resumable && (
          <button
            type="button"
            className="primary"
            onClick={() => game.session_id && onContinue(game.session_id)}
            disabled={pending}
          >
            继续对局
          </button>
        )}
        {canRetrySync && (
          // 守卫 2:站在**有在途结算的这台盒子**前的人,第一个看到的必须是「把成绩救回去」,
          // 不是「认输」。云端只知道「成绩还没到」,是排队、退避、试完了还是被拒收全在这台
          // 机器的 outbox 里 —— 而那恰好是他唯一想问的事。
          <button
            type="button"
            className="primary"
            onClick={() => onRetrySettlement?.(game.game_id)}
            disabled={syncRetryPending}
          >
            {syncRetryPending ? '正在重试…' : '立即重试'}
          </button>
        )}
        {/* 破坏性按钮**屏上不描红** —— 照象棋模板:屏上 `.primary` 是实心 accent、次级是描边,
            真正变红在**不可回头那一步**(二次确认框)。国象和围棋上一版是屏上就描边。
            两派都自洽,差异是「吓人吓在屏上,还是吓在不可回头那一步」——
            **这条归 Fan,不由我们私下约**,先照参考屏做,两版都留着。 */}
        <button
          type="button"
          onClick={() => setArmedGameId(game.game_id)}
          disabled={pending}
        >
          {displace.button}
        </button>
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
    </div>
  );
};

export default KioskAiLadderBlockingPanel;
