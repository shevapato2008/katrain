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
import { AI_LADDER_COPY, formatPlacementProgress } from '../../../features/aiLadder/copy';
import { aiLadderExits, formatCountdown, useCountdown } from '../../../features/aiLadder/exits';
import type { AiLadderExit, AiLadderExitKind } from '../../../features/aiLadder/exits';
import { aiLadderStartBlock } from '../../../features/aiLadder/startGate';
import type { AiLadderBlockingGame, AiLadderCountingReason, AiLadderStatus } from '../../../features/aiLadder/types';

interface AiLadderRatedSetupProps {
  status: AiLadderStatus;
  color: string;
  mainTime: number;
  byoLength: number;
  byoPeriods: number;
  startPending: boolean;
  lifecyclePending?: boolean;
  lifecycleError?: string;
  lifecycleReceipt?: { counted: boolean; reason: AiLadderCountingReason | null };
  onColorChange: (color: 'B' | 'W') => void;
  onRetry: () => void;
  onStart: () => void;
  onContinue?: (sessionId: string) => void;
  onEndGame?: (gameId: string) => void;
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

// 两条出路是**两笔不同的买卖**,所以动词、颜色、后果三处都分家。用户按之前必须知道
// 自己按的是哪一笔:认输动段位,放弃不动。只靠一句二次确认来区分,是在按下之后才说。
const EXIT_COPY: Record<AiLadderExitKind, {
  label: string;
  cost: string;
  color: 'error' | 'warning';
  dialogTitle: string;
  dialogBody: string;
  confirm: string;
}> = {
  resign: {
    label: '认输并结束',
    cost: '按认输计入本局，段位会变',
    color: 'error',
    dialogTitle: '认输并结束这一局？',
    dialogBody: '这一局将按你认输处理，计为本局负，并计入升降级。此操作不可撤销。',
    confirm: '确认认输',
  },
  release: {
    label: '放弃等待成绩',
    cost: '本局作废，不计入升降级，段位不变',
    color: 'warning',
    dialogTitle: '不再等这一局的成绩？',
    dialogBody:
      '这一局已经下完，但成绩始终没有送到云端。放弃等待只会把账号放开，本局作废、不计入升降级、段位不变。'
      + '如果那台设备之后又把成绩送到了，这一局仍然按它真实的结果计算。',
    confirm: '确认放弃等待',
  },
};

/** 一扇门:按钮 + 后果行,没到点就禁用并在下面走秒。 */
const ExitAction = ({ exit, onArm, disabled, elsewhere }: {
  exit: AiLadderExit;
  onArm: () => void;
  disabled: boolean;
  /** 这一局在别的设备上 —— 只影响措辞,不影响这扇门开不开。 */
  elsewhere: boolean;
}) => {
  const remaining = useCountdown(exit.ready ? null : exit.readyInSeconds);
  const copy = EXIT_COPY[exit.kind];
  // 自己这局叫「认输」,别人那局叫「替它认输」—— 后者动的是一台你此刻碰不到的机器上的棋,
  // 措辞得让人知道自己在替谁做决定。同一个按钮在两种归属下说同一句话,会把「我不想下了」
  // 和「我要中止另一台上的对局」说成一件事。
  const label = exit.kind === 'resign' && elsewhere ? '替它认输' : copy.label;
  // 等的时候也要说清**在等什么**:门关着的理由是那台机器还在报生存,不是系统在忙。
  const waiting = exit.kind === 'resign' && elsewhere
    ? `那台设备还在联机 · ${formatCountdown(remaining ?? 0)} 后可用`
    : `${formatCountdown(remaining ?? 0)} 后可用`;
  // 表走完了就当它开了 —— 服务端的到期时刻和它自己那道闸吃的是同一个常量,两侧边界
  // 各有一条测试钉着。若真差了那么一下,用户看到的是一次 409 + 重试,而不是一个
  // 永远停在 0:00 的按钮。
  const armed = exit.ready || (remaining !== null && remaining <= 0);

  return (
    <Box>
      <Button
        fullWidth
        size="large"
        variant="outlined"
        color={copy.color}
        onClick={onArm}
        disabled={disabled || !armed}
        sx={{ minHeight: 48, fontWeight: 750 }}
      >
        {label}
      </Button>
      <Typography
        variant="caption"
        component="p"
        sx={{
          mt: 0.75,
          textAlign: 'center',
          color: armed ? 'text.secondary' : `${copy.color}.light`,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {armed ? copy.cost : waiting}
      </Typography>
    </Box>
  );
};

const blockingStateChip = (game: AiLadderBlockingGame, resumable: boolean) => {
  // 「结算中」这三个字对送不出去的成绩是句假话 —— 没有人在结算,是送不到。
  if (game.state === 'pending_settlement') return { label: '成绩未送达', color: 'warning' as const };
  if (game.ownership === 'other_device') {
    return game.can_force_resign
      ? { label: '已失联', color: 'warning' as const }
      : { label: '对局中', color: 'success' as const };
  }
  return resumable ? { label: '对局中', color: 'success' as const } : { label: '已中断', color: 'warning' as const };
};

const blockingCopy = (game: AiLadderBlockingGame, resumable: boolean) => {
  if (game.state === 'pending_settlement') {
    return game.can_release_abandoned_settlement
      ? '已经等了 30 分钟。你可以不再等这个成绩，先开新局。'
      : '本局已经下完，成绩还没送到云端。系统会一直重试。';
  }
  if (game.ownership === 'other_device') {
    return game.can_force_resign
      ? '那台设备已经很久没有联机。你可以在这里替它认输，把账号放开。'
      : '这一局正在你的另一台设备上进行。回到那台接着下，或者在这里替它认输。';
  }
  return resumable
    ? '你有一局正式对局尚未结束。'
    : '这一局在本机开始，但本机的对局进程已经不在了 —— 接不回来。';
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
}: AiLadderRatedSetupProps) => {
  // 待确认的那一次操作,连**是哪一扇门**一起记住 —— 只记 game_id 的话,弹窗就得
  // 自己再推一遍「这是认输还是放弃」,而那个判断在服务端已经因为算了两次错了两次。
  const [armedExit, setArmedExit] = useState<{ gameId: string; kind: AiLadderExitKind } | null>(null);
  const liveBlockingGame = status.view_state === 'ready' ? status.blocking_game : undefined;
  // 弹窗开着的时候,底下那一格会自己变(后台每 15 秒复查一次)。判据不能只是「还是同一局」——
  // 同一局从「在下」变成「成绩未送达」之后,认输就不再是它的出路了(服务端会直接拒),
  // 而屏上那句「计为本局负」当场变成假话。所以钉的是**这扇门还在不在**。
  const armedStillOffered = armedExit !== null
    && liveBlockingGame !== undefined
    && liveBlockingGame !== null
    && liveBlockingGame.game_id === armedExit.gameId
    && aiLadderExits(liveBlockingGame).some((exit) => exit.kind === armedExit.kind && exit.ready);
  const receiptVisible = Boolean(lifecycleReceipt);
  const dialogOpen = armedStillOffered && !receiptVisible;

  useEffect(() => {
    if (armedExit !== null && (!armedStillOffered || receiptVisible)) {
      setArmedExit(null);
    }
  }, [armedExit, armedStillOffered, receiptVisible]);

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

  const confirmExit = () => {
    if (!armedExit || !blockingGame || blockingGame.game_id !== armedExit.gameId || lifecycleReceipt || !onEndGame) {
      return;
    }
    setArmedExit(null);
    // 两条出路打的是同一个 `/end`:走哪一条由**服务端按行状态**决定,不由前端挑。
    // 前端只负责把后果说对 —— 让它自己选路,就等于把同一个判断又实现了一遍。
    onEndGame(armedExit.gameId);
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
    const hasCurrentSession = blockingGame.state === 'active'
      && blockingGame.ownership === 'current_device'
      && Boolean(blockingGame.session_id);
    const exits = aiLadderExits(blockingGame);
    // 能接着下的时候,「接着下」才是主按钮;接不回来的时候,主按钮不能是一个
    // **永远刷不回来**的「刷新状态」—— 棋盘随进程没了,刷多少次都一样。
    const primaryLabel = hasCurrentSession ? '继续对局' : '刷新状态';
    const primaryAction = () => {
      if (hasCurrentSession && blockingGame.session_id) {
        onContinue?.(blockingGame.session_id);
        return;
      }
      onRetry();
    };
    const stateChip = blockingStateChip(blockingGame, hasCurrentSession);
    const stateCopy = blockingCopy(blockingGame, hasCurrentSession);
    const refreshFirst = hasCurrentSession || exits.length === 0;
    const refreshButton = (
      <Button
        fullWidth
        size="large"
        variant={refreshFirst ? 'contained' : 'outlined'}
        onClick={primaryAction}
        disabled={lifecyclePending || (hasCurrentSession && !onContinue)}
        startIcon={lifecyclePending ? <CircularProgress size={18} color="inherit" /> : undefined}
        sx={{ minHeight: 54, fontSize: 18, fontWeight: 800 }}
      >
        {primaryLabel}
      </Button>
    );

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
                label={blockingGame.ownership === 'current_device' ? '当前设备' : '其他设备'}
                variant="outlined"
              />
            </Stack>
          </Box>
        </Stack>

        <Divider sx={{ my: 3 }} />
        <Typography color="text.secondary">{stateCopy}</Typography>
        {lifecycleError && <Alert severity="error" sx={{ mt: 2 }}>{lifecycleError}</Alert>}

        <Stack spacing={1.5} sx={{ mt: 'auto', pt: 4 }}>
          {/* 次序跟着「用户在这一格能做什么」走,不跟着按钮的重要性走:
              能接着下 → 「继续对局」在最上,出路排它后面;
              接不回来 → **出路在上、刷新在下**,因为刷新是这一格里唯一没用的动作
              (棋盘随进程没了,刷多少次都刷不回来)。参考稿六格都是这个次序。 */}
          {refreshFirst && refreshButton}
          {exits.map((exit) => (
            <ExitAction
              key={exit.kind}
              exit={exit}
              disabled={lifecyclePending || !onEndGame}
              elsewhere={blockingGame.ownership === 'other_device'}
              onArm={() => setArmedExit({ gameId: blockingGame.game_id, kind: exit.kind })}
            />
          ))}
          {!refreshFirst && refreshButton}
        </Stack>
      </>
    );
  } else if (status.blocking_game === undefined && status.pending_settlement) {
    challengeContent = (
      <>
        <Typography color="text.secondary" fontWeight={650}>未完成对局</Typography>
        <Box sx={{ my: 'auto', py: 6 }}>
          <Typography sx={{ fontSize: 24, lineHeight: 1.4, fontWeight: 800 }}>
            本局已经下完，成绩还没送到云端。系统会一直重试。
          </Typography>
          {lifecycleError && <Alert severity="error" sx={{ mt: 2 }}>{lifecycleError}</Alert>}
        </Box>
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

        {status.pending_settlement && <Alert severity="info" sx={{ mt: 2 }}>成绩结算中，暂不能开始新对局</Alert>}
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

      {/* 两扇门各一套文案。共用一句「结束该对局？」会把「记一场负」和「什么都不记」
          说成同一件事,而它们是这块屏上唯一需要被分清的两件事。 */}
      <Dialog open={dialogOpen} onClose={() => setArmedExit(null)} aria-labelledby="ladder-exit-dialog-title">
        <DialogTitle id="ladder-exit-dialog-title">{armedExit && EXIT_COPY[armedExit.kind].dialogTitle}</DialogTitle>
        <DialogContent>
          <DialogContentText>{armedExit && EXIT_COPY[armedExit.kind].dialogBody}</DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button autoFocus onClick={() => setArmedExit(null)}>取消</Button>
          <Button
            color={armedExit ? EXIT_COPY[armedExit.kind].color : 'error'}
            onClick={confirmExit}
            disabled={lifecyclePending || !onEndGame}
          >
            {armedExit && EXIT_COPY[armedExit.kind].confirm}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default AiLadderRatedSetup;
