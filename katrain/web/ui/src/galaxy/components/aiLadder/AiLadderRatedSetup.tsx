import RefreshRoundedIcon from '@mui/icons-material/RefreshRounded';
import { Alert, Box, Button, Chip, CircularProgress, Divider, Paper, Skeleton, Stack, Typography } from '@mui/material';
import { AI_LADDER_COPY, formatPlacementProgress } from '../../../features/aiLadder/copy';
import { aiLadderStartBlock } from '../../../features/aiLadder/startGate';
import type { AiLadderStatus } from '../../../features/aiLadder/types';

interface AiLadderRatedSetupProps {
  status: AiLadderStatus;
  color: string;
  mainTime: number;
  byoLength: number;
  byoPeriods: number;
  startPending: boolean;
  onColorChange: (color: 'B' | 'W') => void;
  onRetry: () => void;
  onStart: () => void;
}

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
  onColorChange,
  onRetry,
  onStart,
}: AiLadderRatedSetupProps) => {
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

  return (
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
      </Box>
    </Paper>
  );
};

export default AiLadderRatedSetup;
