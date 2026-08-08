import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import CloudOutlinedIcon from '@mui/icons-material/CloudOutlined';
import ComputerOutlinedIcon from '@mui/icons-material/ComputerOutlined';
import HourglassTopRoundedIcon from '@mui/icons-material/HourglassTopRounded';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  LinearProgress,
  Skeleton,
  Stack,
  Typography,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import {
  AI_LADDER_COPY,
  formatNetScore,
  formatNetScoreValueText,
  formatOutcomeLabel,
  formatPlacementProgress,
  formatPlacementProgressLabel,
} from './copy';
import { useTranslation } from '../../hooks/useTranslation';
import type { AiLadderCatalogEntry, AiLadderRankedOutcome, AiLadderStatus } from './types';

interface AiLadderStatusCardProps {
  status: AiLadderStatus;
  onPrimaryAction?: () => void;
  onRetry?: () => void;
  compact?: boolean;
}

const RouteChip = ({ entry }: { entry: AiLadderCatalogEntry }) => {
  const RouteIcon = entry.route === 'local' ? ComputerOutlinedIcon : CloudOutlinedIcon;
  return <Chip size="small" icon={<RouteIcon />} label={AI_LADDER_COPY.route[entry.route]} variant="outlined" />;
};

const CertificationChip = ({ entry }: { entry: AiLadderCatalogEntry }) => (
  <Chip
    size="small"
    color={entry.certification_status === 'certified' ? 'success' : 'warning'}
    label={AI_LADDER_COPY.certification[entry.certification_status]}
    variant="outlined"
  />
);

const OutcomeMarker = ({ outcome, index }: { outcome: AiLadderRankedOutcome; index: number }) => {
  const isWin = outcome === 'win';
  const label = formatOutcomeLabel(index, outcome);
  return (
    <Box
      component="li"
      aria-label={label}
      sx={{
        alignItems: 'center',
        bgcolor: (theme) => alpha(isWin ? theme.palette.success.main : theme.palette.error.main, 0.12),
        border: '1px solid',
        borderColor: isWin ? 'success.main' : 'error.main',
        borderRadius: 2,
        color: isWin ? 'success.main' : 'error.main',
        display: 'flex',
        gap: 0.5,
        justifyContent: 'center',
        minHeight: 36,
        minWidth: 48,
        px: 1,
      }}
    >
      {isWin ? <CheckCircleRoundedIcon fontSize="small" /> : <CloseRoundedIcon fontSize="small" />}
      <Typography component="span" variant="body2" fontWeight={700}>
        {AI_LADDER_COPY.outcome[outcome]}
      </Typography>
    </Box>
  );
};

const NetScoreMeter = ({ score }: { score: number }) => {
  const fillWidth = (Math.abs(score) / 3) * 50;
  const fillLeft = score < 0 ? 50 - fillWidth : 50;

  return (
    <Stack spacing={0.75}>
      <Typography fontWeight={700}>{formatNetScore(score)}</Typography>
      <Box
        role="meter"
        aria-label={AI_LADDER_COPY.netScoreMeterLabel}
        aria-valuemin={-3}
        aria-valuemax={3}
        aria-valuenow={score}
        aria-valuetext={formatNetScoreValueText(score)}
        sx={{
          bgcolor: 'action.disabledBackground',
          borderRadius: 1,
          height: 12,
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        <Box
          aria-hidden="true"
          sx={{
            bgcolor: score < 0 ? 'error.main' : 'success.main',
            height: '100%',
            left: `${fillLeft}%`,
            position: 'absolute',
            width: `${fillWidth}%`,
          }}
        />
        <Box
          aria-hidden="true"
          sx={{ bgcolor: 'text.primary', height: '100%', left: '50%', opacity: 0.8, position: 'absolute', width: 2 }}
        />
      </Box>
      <Stack direction="row" justifyContent="space-between">
        <Typography variant="caption" color="error.main" fontWeight={700}>
          {AI_LADDER_COPY.demotionThreshold}
        </Typography>
        <Typography variant="caption" color="success.main" fontWeight={700}>
          {AI_LADDER_COPY.promotionThreshold}
        </Typography>
      </Stack>
    </Stack>
  );
};

const CardFrame = ({ children, compact = false }: { children: React.ReactNode; compact?: boolean }) => (
  <Card
    component="section"
    aria-labelledby="ai-ladder-card-title"
    sx={{
      bgcolor: 'background.paper',
      border: '1px solid',
      borderColor: 'divider',
      borderRadius: 3,
      overflow: 'hidden',
    }}
  >
    <CardContent sx={{ p: compact ? 1.25 : { xs: 2, sm: 3 }, '&:last-child': { pb: compact ? 1.25 : { xs: 2, sm: 3 } } }}>
      <Typography id="ai-ladder-card-title" component="h2" variant={compact ? 'body1' : 'h5'} fontWeight={800} gutterBottom>
        {AI_LADDER_COPY.title}
      </Typography>
      {children}
    </CardContent>
  </Card>
);

const AiLadderStatusCard = ({ status, onPrimaryAction, onRetry, compact = false }: AiLadderStatusCardProps) => {
  // See AiLadderSetupOpponent: the copy getters read i18n at render, and this is what
  // makes "render again" happen when the language changes.
  useTranslation();

  if (status.view_state === 'loading') {
    return (
      <CardFrame compact={compact}>
        <Stack role="status" aria-live="polite" spacing={1.5}>
          <Typography color="text.secondary">{AI_LADDER_COPY.loading}</Typography>
          <Skeleton variant="rounded" height={44} />
          <Skeleton variant="rounded" height={44} width="68%" />
        </Stack>
      </CardFrame>
    );
  }

  if (status.view_state === 'error') {
    return (
      <CardFrame compact={compact}>
        <Alert severity="error" role="alert" sx={{ mb: 2 }}>
          {status.message || AI_LADDER_COPY.loadError}
        </Alert>
        <Button variant="outlined" onClick={onRetry} disabled={!onRetry} sx={{ minHeight: 44 }}>
          {AI_LADDER_COPY.retry}
        </Button>
      </CardFrame>
    );
  }

  const placementState = status.placement_state;
  const isPlacement = placementState.phase === 'placement';
  const activeEntry = placementState.phase === 'placement' ? status.current_opponent : placementState.rung;
  const unavailable =
    !activeEntry || activeEntry.certification_status !== 'certified' || activeEntry.availability === 'unavailable';
  const actionLabel = status.pending_settlement
    ? AI_LADDER_COPY.pendingSettlementCta
    : unavailable
      ? AI_LADDER_COPY.unavailableCta
      : isPlacement
        ? AI_LADDER_COPY.continuePlacementCta
        : AI_LADDER_COPY.startRankedCta;

  return (
    <CardFrame compact={compact}>
      <Stack spacing={compact ? 1 : 2.5}>
        {placementState.phase === 'placement' ? (
          <Stack spacing={1}>
            <Stack direction="row" alignItems="baseline" justifyContent="space-between" gap={2}>
              <Typography fontWeight={700}>
                {formatPlacementProgress(
                  placementState.completed_games,
                  placementState.total_games,
                )}
              </Typography>
              {status.current_opponent && (
                <Typography color="text.secondary">
                  {AI_LADDER_COPY.currentOpponentPrefix}
                  {status.current_opponent.rank_name}
                </Typography>
              )}
            </Stack>
            <LinearProgress
              variant="determinate"
              value={(placementState.completed_games / placementState.total_games) * 100}
              aria-label={formatPlacementProgressLabel(
                placementState.completed_games,
                placementState.total_games,
              )}
              aria-valuemin={0}
              aria-valuemax={placementState.total_games}
              aria-valuenow={placementState.completed_games}
              sx={{ borderRadius: 1, height: 8 }}
            />
          </Stack>
        ) : (
          <Stack direction="row" alignItems="baseline" gap={2}>
            <Typography variant="h6" fontWeight={800}>
              {AI_LADDER_COPY.currentRankPrefix}
              {placementState.rung.rank_name}
            </Typography>
          </Stack>
        )}

        {activeEntry && (
          <Stack direction="row" useFlexGap flexWrap="wrap" gap={1}>
            <CertificationChip entry={activeEntry} />
            <RouteChip entry={activeEntry} />
          </Stack>
        )}

        <Box>
          <NetScoreMeter score={status.net_score} />
          <Typography fontWeight={700} sx={{ mt: 2, mb: 0.5 }}>
            {AI_LADDER_COPY.recentResultsHeading}
          </Typography>
          <Typography color="text.secondary" variant="body2" sx={{ mb: 1 }}>
            {AI_LADDER_COPY.recentResultsNote}
          </Typography>
          {status.recent_ranked_results.length > 0 ? (
            <Box
              component="ul"
              aria-label={AI_LADDER_COPY.recentResults}
              sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, listStyle: 'none', m: 0, p: 0 }}
            >
              {status.recent_ranked_results.slice(-5).map((outcome, index) => (
                <OutcomeMarker key={`${outcome}-${index}`} outcome={outcome} index={index} />
              ))}
            </Box>
          ) : (
            <Typography color="text.secondary" variant="body2">
              {AI_LADDER_COPY.noRecentResults}
            </Typography>
          )}
        </Box>

        {status.pending_settlement && (
          <Stack direction="row" role="status" aria-live="polite" alignItems="center" gap={1} color="warning.main">
            <HourglassTopRoundedIcon fontSize="small" />
            <Typography fontWeight={700}>{AI_LADDER_COPY.pendingSettlement}</Typography>
          </Stack>
        )}

        {unavailable && !status.pending_settlement && (
          <Stack direction="row" alignItems="center" gap={1} color="warning.main">
            <WarningAmberRoundedIcon fontSize="small" />
            <Typography fontWeight={700}>{AI_LADDER_COPY.unavailable}</Typography>
          </Stack>
        )}

        {!compact && <Button
          variant="contained"
          onClick={onPrimaryAction}
          disabled={status.pending_settlement || unavailable || !onPrimaryAction}
          sx={{ alignSelf: { xs: 'stretch', sm: 'flex-start' }, minHeight: 44 }}
        >
          {actionLabel}
        </Button>}
      </Stack>
    </CardFrame>
  );
};

export default AiLadderStatusCard;
