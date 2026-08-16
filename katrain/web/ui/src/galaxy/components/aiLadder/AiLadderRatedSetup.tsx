import { useEffect, useState } from 'react';
import RefreshRoundedIcon from '@mui/icons-material/RefreshRounded';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Divider,
  Paper,
  Skeleton,
  Stack,
  Typography,
} from '@mui/material';
import {
  blockingCopy,
  blockingStateChip,
  displaceCopy,
  isResumableHere,
  isSyncRetryable,
  ownershipLabel,
  settlementSyncText,
} from '../../../features/aiLadder/blockingCopy';
import { AI_LADDER_COPY, formatPlacementProgress } from '../../../features/aiLadder/copy';
import { useCountdown } from '../../../features/aiLadder/countdown';
import { aiLadderStartBlock } from '../../../features/aiLadder/startGate';
import { useTranslation } from '../../../hooks/useTranslation';
import type {
  AiLadderCountingReason,
  AiLadderSettlementSync,
  AiLadderStatus,
} from '../../../features/aiLadder/types';

interface AiLadderRatedSetupProps {
  status: AiLadderStatus;
  color: string;
  mainTime: number;
  byoLength: number;
  byoPeriods: number;
  startPending: boolean;
  lifecyclePending?: boolean;
  /** 必填,不是 `lifecycleError?:` —— 见 KioskAiLadderBlockingPanel 里同一个 prop 的说明。 */
  lifecycleError: string;
  lifecycleReceipt?: { counted: boolean; reason: AiLadderCountingReason | null };
  onColorChange: (color: 'B' | 'W') => void;
  onRetry: () => void;
  onStart: () => void;
  onContinue?: (sessionId: string) => void;
  onEndGame?: (gameId: string) => void;
  /** 只有盒子有 outbox。网页直连时不传,「立即重试」就不出现。 */
  onRetrySettlement?: (gameId: string) => void;
  syncRetryPending?: boolean;
}

const notCountedMessages: Record<AiLadderCountingReason, string> = {
  engine_unavailable: '本局不计入升降级：棋力服务未能正常完成对局',
  inconclusive: '本局不计入升降级：对局没有形成有效胜负',
  opponent_not_eligible: '本局不计入升降级：本局对手尚未通过计分认证',
  opponent_rung_mismatch: '本局不计入升降级：对手档位与开局快照不一致',
  invalid_game_type: '本局不计入升降级：对局类型不符合升降级规则',
};

const receiptMessage = (counted: boolean, reason: AiLadderCountingReason | null) => {
  if (counted) return '本局已计入升降级，当前段位与本阶进度已更新。';
  return (reason ? notCountedMessages[reason] : null) ?? '本局不计入升降级：服务器判定本局不计入。';
};

const Stone = ({ white = false }: { white?: boolean }) => (
  <Box
    aria-hidden
    sx={{
      width: 84,
      height: 84,
      borderRadius: '50%',
      flex: '0 0 auto',
      bgcolor: white ? '#e8e8e2' : '#090a09',
      border: white ? '1px solid rgba(255,255,255,.55)' : '1px solid rgba(255,255,255,.08)',
      boxShadow: white
        ? 'inset -12px -14px 20px rgba(0,0,0,.20), 0 10px 22px rgba(0,0,0,.28)'
        : 'inset 14px 12px 22px rgba(255,255,255,.13), inset -12px -16px 22px rgba(0,0,0,.65), 0 12px 26px rgba(0,0,0,.38)',
    }}
  />
);

/**
 * 「上一局的成绩还在送」那一格上的一行字 —— 数全部来自盒子的 outbox,一个都不是前端推的。
 *
 * 走秒归 `useCountdown`,它数的是**时长**,所以盒子的钟偏不进这个数。数到 0 之后改说
 * 「即将重试」而不是「正在重试」:队列是每 60 秒排空一次的(`SYNC_DRAIN_INTERVAL`),
 * 到期只保证「下一轮会带上它」,不保证此刻正在发。也不许停在一个 0:00 —— 那是这块屏
 * 唯一会被当成卡死的画面。
 */
const SettlementSyncLine = ({ sync }: { sync: AiLadderSettlementSync }) => {
  const remaining = useCountdown(sync.state === 'waiting' ? sync.next_attempt_in_seconds : null);
  const text = settlementSyncText(sync, remaining);

  return (
    <Typography
      variant="body2"
      sx={{
        mt: 1.5,
        color: sync.state === 'refused' || sync.state === 'exhausted' ? 'warning.light' : 'text.secondary',
        fontVariantNumeric: 'tabular-nums',
      }}
    >
      {text}
    </Typography>
  );
};

const Conditions = ({ mainTime, byoLength, byoPeriods }: Pick<AiLadderRatedSetupProps, 'mainTime' | 'byoLength' | 'byoPeriods'>) => (
  <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '18px 28px' }}>
    {[
      ['棋盘', '19路'],
      ['规则', '中国规则'],
      ['贴目', '贴目 7.5'],
      ['用时', `${mainTime} 分钟 · ${byoPeriods}×${byoLength}秒`],
    ].map(([label, value]) => (
      <Box key={label}>
        <Typography variant="caption" color="text.secondary">{label}</Typography>
        <Typography sx={{ mt: 0.25, fontWeight: 750 }}>{value}</Typography>
      </Box>
    ))}
  </Box>
);

const AiLadderRatedSetup = ({
  status,
  color,
  mainTime,
  byoLength,
  byoPeriods,
  startPending,
  lifecyclePending = false,
  lifecycleError,
  lifecycleReceipt,
  onColorChange,
  onRetry,
  onStart,
  onContinue,
  onEndGame,
  onRetrySettlement,
  syncRetryPending = false,
}: AiLadderRatedSetupProps) => {
  // blockingCopy/displaceCopy 里的每一句都在 render 时才查 i18n;没有这个订阅,
  // 语言切换之后这块面板会一直说首次渲染时那门语言。
  useTranslation();
  // 待确认的那一局。只有一个动作了(开新局),所以只需要记住它落在哪一局上。
  const [armedGameId, setArmedGameId] = useState<string | null>(null);
  const liveBlockingGame = status.view_state === 'ready' ? status.blocking_game : undefined;
  // 弹窗开着的时候,底下那一格会自己变(后台每 15 秒复查一次)。价钱现在只有一个,但弹窗里
  // 多说的那一句仍然跟着状态走:同一局从「在下」变成「成绩未送达」,那句话要从「还没下完」
  // 变成「会覆盖它真实的结果,想保住就先用立即重试」。所以它每次都从**当下**这份数据算,
  // 不在按下的那一刻抄一份存起来 —— 否则用户照着一句已经不成立的话按下不可撤销的按钮。
  const armedGame = armedGameId !== null && liveBlockingGame && liveBlockingGame.game_id === armedGameId
    ? liveBlockingGame
    : null;
  const receiptVisible = Boolean(lifecycleReceipt);
  const dialogOpen = armedGame !== null && !receiptVisible;

  useEffect(() => {
    if (armedGameId !== null && (armedGame === null || receiptVisible)) {
      setArmedGameId(null);
    }
  }, [armedGameId, armedGame, receiptVisible]);

  if (lifecycleReceipt && status.view_state !== 'ready') {
    return (
      <Paper component="section" sx={{ width: '100%', p: { xs: 3, md: 4 }, borderRadius: 3 }}>
        <Typography sx={{ fontSize: 34, lineHeight: 1.15, fontWeight: 800 }}>结算已完成</Typography>
        <Alert severity={lifecycleReceipt.counted ? 'success' : 'warning'} sx={{ mt: 3 }}>
          {receiptMessage(lifecycleReceipt.counted, lifecycleReceipt.reason)}
        </Alert>
      </Paper>
    );
  }

  if (status.view_state === 'loading') {
    return <Paper sx={{ p: 4, borderRadius: 3 }}><Skeleton height={420} /></Paper>;
  }

  if (status.view_state === 'error') {
    return (
      <Paper sx={{ p: 4, borderRadius: 3 }}>
        <Alert severity="error" sx={{ mb: 2 }}>{status.message || AI_LADDER_COPY.loadError}</Alert>
        <Button variant="outlined" onClick={onRetry}>重试</Button>
      </Paper>
    );
  }

  const placement = status.placement_state;
  const placed = placement.phase === 'placed';
  const publicRank = placement.phase === 'placed' ? placement.rung.rank_name : '定级中';
  const opponent = status.current_opponent;
  const block = aiLadderStartBlock(status);
  const resultText = status.recent_ranked_results.map((result) => AI_LADDER_COPY.outcome[result]).join(' ');
  const blockingGame = status.blocking_game;

  const confirmDisplace = () => {
    if (!armedGame || lifecycleReceipt || !onEndGame) return;
    setArmedGameId(null);
    // 打的是同一个 `/end`:记负还是什么都不记,由**服务端按那一行的状态**决定,不由前端挑。
    // 前端只负责把后果说对 —— 让它自己选路,就等于把同一个判断又实现了一遍。
    onEndGame(armedGame.game_id);
  };

  let challengeContent;
  if (lifecycleReceipt) {
    challengeContent = (
      <>
        <Typography color="text.secondary" fontWeight={650}>本局挑战</Typography>
        <Box sx={{ my: 'auto', py: 6 }}>
          <Typography sx={{ fontSize: 34, lineHeight: 1.15, fontWeight: 800 }}>结算已完成</Typography>
          <Alert severity={lifecycleReceipt.counted ? 'success' : 'warning'} sx={{ mt: 3 }}>
            {receiptMessage(lifecycleReceipt.counted, lifecycleReceipt.reason)}
          </Alert>
        </Box>
      </>
    );
  } else if (blockingGame) {
    const hasCurrentSession = isResumableHere(blockingGame);
    const sync = blockingGame.sync;
    // 重试只对「网络坏了」有意义。已经被云端在事实上拒收的那一份,再按一次还是同一个
    // 答复;给一个按不出结果的按钮,比不给更坏。
    const canRetrySync = Boolean(onRetrySettlement)
      && blockingGame.state === 'pending_settlement'
      && isSyncRetryable(sync);
    const stateChip = blockingStateChip(blockingGame, hasCurrentSession);
    const stateCopy = blockingCopy(blockingGame, hasCurrentSession);
    const displace = displaceCopy(blockingGame);

    challengeContent = (
      <>
        <Typography color="text.secondary" fontWeight={650}>未完成对局</Typography>
        <Stack direction="row" alignItems="center" gap={3} sx={{ mt: 3 }}>
          <Stone white={blockingGame.user_color === 'W'} />
          <Box>
            <Typography variant="h6" fontWeight={800}>智星棋手</Typography>
            <Typography sx={{ mt: 0.5, fontSize: 34, lineHeight: 1.1, fontWeight: 800 }}>
              {blockingGame.opponent_rank_name}
            </Typography>
            <Stack direction="row" gap={1} sx={{ mt: 1.5, flexWrap: 'wrap' }}>
              <Chip size="small" label={stateChip.label} variant="outlined" color={stateChip.color} />
              <Chip
                size="small"
                label={ownershipLabel(blockingGame)}
                variant="outlined"
                data-testid="galaxy-ladder-ownership"
              />
            </Stack>
          </Box>
        </Stack>

        <Divider sx={{ my: 3 }} />
        <Typography color="text.secondary">{stateCopy}</Typography>
        {sync && <SettlementSyncLine sync={sync} />}
        {lifecycleError && <Alert severity="error" sx={{ mt: 2 }}>{lifecycleError}</Alert>}

        <Stack spacing={1.5} sx={{ mt: 'auto', pt: 4 }}>
          {/* 这里只放**会改变什么**的按钮。曾经还有一个「刷新状态」,它做的事
              (重问一次 `/status`)这块屏本来就每 15 秒自己在做
              (`useAiLadderStatus` 的 `AI_LADDER_BLOCKED_REFRESH_MS`),
              所以它在每一格都是别的按钮的真子集,或者干脆什么都改不了。 */}
          {hasCurrentSession && (
            <Button
              fullWidth
              size="large"
              variant="contained"
              onClick={() => blockingGame.session_id && onContinue?.(blockingGame.session_id)}
              disabled={lifecyclePending || !onContinue}
              startIcon={lifecyclePending ? <CircularProgress size={18} color="inherit" /> : undefined}
              sx={{ minHeight: 54, fontSize: 18, fontWeight: 800 }}
            >
              继续对局
            </Button>
          )}
          {canRetrySync && (
            <Button
              fullWidth
              size="large"
              variant="contained"
              onClick={() => onRetrySettlement?.(blockingGame.game_id)}
              disabled={syncRetryPending}
              startIcon={syncRetryPending ? <CircularProgress size={18} color="inherit" /> : undefined}
              sx={{ minHeight: 54, fontSize: 18, fontWeight: 800 }}
            >
              {syncRetryPending ? '正在重试…' : '立即重试'}
            </Button>
          )}
          <Box>
            <Button
              fullWidth
              size="large"
              variant="outlined"
              color={displace.color}
              onClick={() => setArmedGameId(blockingGame.game_id)}
              disabled={lifecyclePending || !onEndGame}
              sx={{ minHeight: 48, fontWeight: 750 }}
            >
              {displace.button}
            </Button>
            {/* 代价写在按钮下面,不写在二次确认里 —— 写在弹窗里等于按下之后才说。 */}
            <Typography
              variant="caption"
              component="p"
              sx={{ mt: 0.75, textAlign: 'center', color: 'text.secondary' }}
            >
              {displace.cost}
            </Typography>
          </Box>
        </Stack>
      </>
    );
  } else if (status.blocking_game === undefined && status.pending_settlement) {
    // **这一格够得着,别删** —— 判据按「链路」不按「模块」,而这条链路是真的:
    //
    //   盒端前端(新) → 盒端服务端(新) → **云端 ranked_api(可能旧)**
    //
    // 盒子上 `/status` 是**转发**到云端的(`ai_ladder.py` 的 `_is_board` 分支直接
    // 把云端 payload 发回来)。云端要是还没上这一版,payload 里根本没有 `blocking_game`
    // 这个键 ⇒ 前端读到 `undefined` ⇒ 落到这一格。前端产物和盒端服务端是同一份 artifact,
    // 所以「旧服务端 + 新界面」在**同进程内**不可能;但跨到云端那一跳可能,而那一跳正是
    // 这个字段的来源。
    //
    // ⇒ **部署顺序约束:云端 ranked_api 必须先于盒子上线。** 顺序反了的失败长这样:
    // 用户在盒子上看到「这一局已经下完,成绩还没送到云端」+ 一个「刷新状态」,
    // **没有认输出口** —— 而这一格里前端手上没有 game_id,`/end` 物理上打不出去,
    // 不是没接线。所以这里不修前端,修的是上线顺序。
    challengeContent = (
      <>
        <Typography color="text.secondary" fontWeight={650}>未完成对局</Typography>
        <Box sx={{ my: 'auto', py: 6 }}>
          <Typography sx={{ fontSize: 24, lineHeight: 1.4, fontWeight: 800 }}>
            这一局已经下完，成绩还没送到云端。
          </Typography>
          {lifecycleError && <Alert severity="error" sx={{ mt: 2 }}>{lifecycleError}</Alert>}
        </Box>
        {/* 「刷新状态」只在这一格活下来:自动复查的开关是 `blocking_game` 存在
            (`useAiLadderStatus` 的 `blocked`),而这一格恰恰没有它 —— 老服务端只回了
            一个 `pending_settlement` 标志。没有轮询、也没有别的动作,手动问一次就是
            这里唯一能推进事情的办法。 */}
        <Button
          fullWidth
          size="large"
          variant="contained"
          onClick={onRetry}
          disabled={lifecyclePending}
          startIcon={lifecyclePending ? <CircularProgress size={18} color="inherit" /> : undefined}
          sx={{ minHeight: 54, fontSize: 18, fontWeight: 800 }}
        >
          刷新状态
        </Button>
      </>
    );
  } else {
    challengeContent = (
      <>
        <Typography color="text.secondary" fontWeight={650}>本局挑战</Typography>
        <Stack direction="row" alignItems="center" gap={3} sx={{ mt: 3 }}>
          <Stone white={color === 'W'} />
          <Box>
            <Typography variant="h6" fontWeight={800}>智星棋手</Typography>
            <Typography sx={{ mt: 0.5, fontSize: 34, lineHeight: 1.1, fontWeight: 800 }}>{opponent?.rank_name ?? '—'}</Typography>
            <Stack direction="row" gap={1} sx={{ mt: 1.5 }}>
              <Chip size="small" label={opponent?.certification_status === 'certified' ? '已认证' : '暂定'} variant="outlined" color="success" />
              <Chip size="small" label="计入升降级" variant="outlined" color="success" />
            </Stack>
          </Box>
        </Stack>

        <Divider sx={{ my: 3 }} />
        <Conditions mainTime={mainTime} byoLength={byoLength} byoPeriods={byoPeriods} />
        <Divider sx={{ my: 3 }} />

        <Stack direction="row" alignItems="center" justifyContent="space-between" gap={2}>
          <Typography color="text.secondary">选择执子</Typography>
          <Stack direction="row" sx={{ p: 0.5, border: '1px solid', borderColor: 'divider', borderRadius: 2 }}>
            <Button onClick={() => onColorChange('B')} variant={color === 'B' ? 'contained' : 'text'} color="inherit" sx={{ minWidth: 76 }}>● 黑棋</Button>
            <Button onClick={() => onColorChange('W')} variant={color === 'W' ? 'contained' : 'text'} color="inherit" sx={{ minWidth: 76 }}>○ 白棋</Button>
          </Stack>
        </Stack>

        {/* 同一条判据:这块屏也分不出 waiting/exhausted/refused,所以说的是三种状态下都为真的
            那句。前半句取共享文案(跟着语言走),后半句仍是硬编码中文 —— 那是既有欠账,
            不在这次范围里,记着。 */}
        {status.pending_settlement && (
          <Alert severity="info" sx={{ mt: 2 }}>{AI_LADDER_COPY.pendingSettlement}，暂不能开始新对局</Alert>
        )}
        {block === 'rung_not_certified' && <Alert severity="warning" sx={{ mt: 2 }}>{AI_LADDER_COPY.unavailable}</Alert>}

        <Box sx={{ mt: 'auto', pt: 4 }}>
          <Button
            fullWidth
            size="large"
            variant="contained"
            onClick={onStart}
            disabled={block !== null || startPending}
            startIcon={startPending ? <CircularProgress size={18} color="inherit" /> : undefined}
            sx={{ minHeight: 54, fontSize: 18, fontWeight: 800 }}
          >
            {startPending ? '正在开始…' : '开始正式对局'}
          </Button>
          <Stack direction="row" justifyContent="center" alignItems="center" gap={0.75} sx={{ mt: 1.5, color: 'text.secondary' }}>
            <RefreshRoundedIcon sx={{ fontSize: 16 }} />
            <Typography variant="caption">开始前需要联网完成正式预约</Typography>
          </Stack>
        </Box>
      </>
    );
  }

  return (
    <>
      <Paper
        component="section"
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', lg: 'minmax(0, 1fr) minmax(340px, 402px)' },
          overflow: 'hidden',
          borderRadius: 3,
          border: '1px solid',
          borderColor: 'divider',
          bgcolor: 'background.paper',
          boxShadow: '0 18px 50px rgba(0,0,0,.18)',
        }}
      >
      <Box sx={{ p: { xs: 3, md: 4 }, minHeight: { lg: 560 }, display: 'flex', flexDirection: 'column' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 3, flexWrap: 'wrap' }}>
          <Box>
            <Typography color="text.secondary" fontWeight={650}>当前段位</Typography>
            <Stack direction="row" alignItems="baseline" gap={1.5} sx={{ mt: 1 }}>
              <Typography data-testid="current-rank" sx={{ fontSize: { xs: 64, md: 88 }, lineHeight: 1, fontWeight: 800, letterSpacing: '-0.07em' }}>
                {publicRank}
              </Typography>
              {placed && <Typography color="text.secondary" sx={{ fontSize: 22, fontWeight: 700 }}>41 阶棋力体系</Typography>}
            </Stack>
            {!placed && (
              <Typography sx={{ mt: 2, color: 'text.secondary' }}>
                {placement.phase === 'placement' && formatPlacementProgress(placement.completed_games, placement.total_games)}
              </Typography>
            )}
          </Box>

          <Box sx={{ minWidth: 220 }}>
            <Typography color="text.secondary" fontWeight={650}>最近五局</Typography>
            <Typography sx={{ mt: 1.25, wordSpacing: 12, fontWeight: 750 }}>{resultText || '暂无记录'}</Typography>
          </Box>
        </Box>

        <Box sx={{ mt: 'auto', pt: 6 }}>
          <Stack direction="row" alignItems="baseline" justifyContent="space-between" gap={2}>
            <Box>
              <Typography sx={{ fontSize: 20, fontWeight: 800 }}>本阶进度</Typography>
              <Typography variant="body2" color="text.secondary">最近对局只作展示，净胜分决定晋降级</Typography>
            </Box>
            <Typography sx={{ fontSize: 46, lineHeight: 1, fontWeight: 800, color: 'success.light' }}>
              {status.net_score > 0 ? '+' : ''}{status.net_score}
            </Typography>
          </Stack>

          <Box sx={{ mt: 4 }}>
            <Stack direction="row" justifyContent="space-between" sx={{ mb: 1.5 }}>
              <Typography variant="body2" color="error.light" fontWeight={700}>净负 3 局 · 降级</Typography>
              <Typography variant="body2" color="success.light" fontWeight={700}>净胜 3 局 · 晋级</Typography>
            </Stack>
            <Box sx={{ height: 4, bgcolor: 'divider', position: 'relative', mx: 1 }}>
              {[0, 1, 2, 3, 4, 5, 6].map((step) => (
                <Box key={step} sx={{ position: 'absolute', left: `${step * 16.666}%`, top: '50%', transform: 'translate(-50%,-50%)', width: step === status.net_score + 3 ? 22 : 10, height: step === status.net_score + 3 ? 22 : 10, borderRadius: '50%', bgcolor: step <= status.net_score + 3 ? 'success.light' : 'background.paper', border: '2px solid', borderColor: step === 0 ? 'error.light' : 'text.disabled', boxShadow: step === status.net_score + 3 ? '0 0 0 7px rgba(135,181,158,.14)' : 'none' }} />
              ))}
            </Box>
            <Stack direction="row" justifyContent="space-between" sx={{ mt: 2, color: 'text.secondary' }}>
              {[-3, -2, -1, 0, 1, 2, 3].map((value) => <Typography key={value} variant="caption">{value > 0 ? `+${value}` : value}</Typography>)}
            </Stack>
          </Box>

        </Box>
      </Box>

      <Box sx={{ p: { xs: 3, md: 4 }, borderLeft: { lg: '1px solid' }, borderTop: { xs: '1px solid', lg: 0 }, borderColor: 'divider !important', display: 'flex', flexDirection: 'column' }}>
        {challengeContent}
      </Box>
      </Paper>

      {/* 标题、正文、确认按钮全部按 `armedGame` 现算 —— 同一块弹窗要说两件不同的事:
          有棋盘的那两格是「认输、记一场负」,`reserved` 那格是「让掉、不记成绩」。
          弹窗文案写死成其中一句,另一格就是当着用户的面承诺一个不会发生的后果。 */}
      <Dialog open={dialogOpen} onClose={() => setArmedGameId(null)} aria-labelledby="ladder-exit-dialog-title">
        <DialogTitle id="ladder-exit-dialog-title">{armedGame ? displaceCopy(armedGame).title : '认输那一局？'}</DialogTitle>
        <DialogContent>
          <DialogContentText>{armedGame && displaceCopy(armedGame).body}</DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button autoFocus onClick={() => setArmedGameId(null)}>取消</Button>
          <Button
            color={armedGame ? displaceCopy(armedGame).color : 'error'}
            onClick={confirmDisplace}
            disabled={lifecyclePending || !onEndGame}
          >
            {armedGame ? displaceCopy(armedGame).confirm : '确认认输'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default AiLadderRatedSetup;
