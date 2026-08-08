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
import { aiLadderStartBlock } from '../../../features/aiLadder/startGate';
import type { AiLadderCountingReason, AiLadderStatus } from '../../../features/aiLadder/types';

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
  const [endGameId, setEndGameId] = useState<string | null>(null);
  const activeBlockingGameId = status.view_state === 'ready' && status.blocking_game?.state === 'active'
    ? status.blocking_game.game_id
    : undefined;
  const receiptVisible = Boolean(lifecycleReceipt);
  const endDialogOpen = endGameId !== null && activeBlockingGameId === endGameId && !receiptVisible;

  useEffect(() => {
    if (endGameId !== null && (activeBlockingGameId !== endGameId || receiptVisible)) {
      setEndGameId(null);
    }
  }, [activeBlockingGameId, endGameId, receiptVisible]);

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

  const confirmEndGame = () => {
    if (
      !endGameId
      || blockingGame?.state !== 'active'
      || blockingGame.game_id !== endGameId
      || lifecycleReceipt
      || !onEndGame
    ) return;
    setEndGameId(null);
    onEndGame(endGameId);
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
    const primaryLabel = blockingGame.state === 'pending_settlement'
      ? '刷新状态'
      : blockingGame.ownership === 'other_device'
        ? '等待结算'
        : hasCurrentSession
          ? '继续对局'
          : '刷新状态';
    const primaryAction = () => {
      if (hasCurrentSession && blockingGame.session_id) {
        onContinue?.(blockingGame.session_id);
        return;
      }
      onRetry();
    };
    const stateCopy = blockingGame.state === 'pending_settlement'
      ? '本局已结束，成绩正在结算中。'
      : blockingGame.ownership === 'other_device'
        ? '该对局正在其他设备上进行，请等待对局结算。'
        : '你有一局正式对局尚未结束。';

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
              <Chip
                size="small"
                label={blockingGame.state === 'pending_settlement' ? '结算中' : '对局中'}
                variant="outlined"
                color={blockingGame.state === 'pending_settlement' ? 'warning' : 'success'}
              />
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
          <Button
            fullWidth
            size="large"
            variant="contained"
            onClick={primaryAction}
            disabled={lifecyclePending || (hasCurrentSession && !onContinue)}
            startIcon={lifecyclePending ? <CircularProgress size={18} color="inherit" /> : undefined}
            sx={{ minHeight: 54, fontSize: 18, fontWeight: 800 }}
          >
            {primaryLabel}
          </Button>
          {blockingGame.state === 'active' && (
            <Button
              fullWidth
              size="large"
              variant="outlined"
              color="error"
              onClick={() => setEndGameId(blockingGame.game_id)}
              disabled={lifecyclePending || !onEndGame}
              sx={{ minHeight: 48, fontWeight: 750 }}
            >
              结束该对局
            </Button>
          )}
        </Stack>
      </>
    );
  } else if (status.blocking_game === undefined && status.pending_settlement) {
    challengeContent = (
      <>
        <Typography color="text.secondary" fontWeight={650}>未完成对局</Typography>
        <Box sx={{ my: 'auto', py: 6 }}>
          <Typography sx={{ fontSize: 24, lineHeight: 1.4, fontWeight: 800 }}>
            本局已结束，成绩正在结算中。
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

      <Dialog open={endDialogOpen} onClose={() => setEndGameId(null)} aria-labelledby="end-game-dialog-title">
        <DialogTitle id="end-game-dialog-title">结束该对局？</DialogTitle>
        <DialogContent>
          <DialogContentText>结束后将按你认输处理，并计为本局负。此操作不可撤销。</DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button autoFocus onClick={() => setEndGameId(null)}>取消</Button>
          <Button color="error" onClick={confirmEndGame} disabled={lifecyclePending || !onEndGame}>确认结束</Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default AiLadderRatedSetup;
