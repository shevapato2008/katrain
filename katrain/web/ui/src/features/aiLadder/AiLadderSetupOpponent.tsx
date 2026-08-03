import CloudOutlinedIcon from '@mui/icons-material/CloudOutlined';
import ComputerOutlinedIcon from '@mui/icons-material/ComputerOutlined';
import HourglassTopRoundedIcon from '@mui/icons-material/HourglassTopRounded';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import { Alert, Box, Button, Chip, LinearProgress, Skeleton, Stack, Typography } from '@mui/material';
import { AI_LADDER_COPY, formatPlacementProgress, formatPlacementProgressLabel } from './copy';
import type { AiLadderCatalogEntry, AiLadderStatus } from './types';

interface AiLadderSetupOpponentProps {
  status: AiLadderStatus;
  onRetry?: () => void;
}

const StatusChips = ({ entry }: { entry: AiLadderCatalogEntry }) => {
  const RouteIcon = entry.route === 'local' ? ComputerOutlinedIcon : CloudOutlinedIcon;
  return (
    <Stack direction="row" useFlexGap flexWrap="wrap" gap={1}>
      <Chip
        size="small"
        color={entry.certification_status === 'certified' ? 'success' : 'warning'}
        label={AI_LADDER_COPY.certification[entry.certification_status]}
        variant="outlined"
      />
      <Chip
        size="small"
        icon={<RouteIcon />}
        label={AI_LADDER_COPY.route[entry.route]}
        variant="outlined"
      />
    </Stack>
  );
};

const Frame = ({ children }: { children: React.ReactNode }) => (
  <Box
    component="section"
    aria-labelledby="ai-ladder-setup-opponent-title"
    sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2, mt: 2, p: 2 }}
  >
    <Typography id="ai-ladder-setup-opponent-title" component="h2" variant="h6" fontWeight={800} gutterBottom>
      {AI_LADDER_COPY.setupTitle}
    </Typography>
    {children}
  </Box>
);

const AiLadderSetupOpponent = ({ status, onRetry }: AiLadderSetupOpponentProps) => {
  if (status.view_state === 'loading') {
    return (
      <Frame>
        <Stack role="status" aria-live="polite" spacing={1}>
          <Typography color="text.secondary" variant="body2">
            {AI_LADDER_COPY.loading}
          </Typography>
          <Skeleton variant="rounded" height={36} />
        </Stack>
      </Frame>
    );
  }

  if (status.view_state === 'error') {
    return (
      <Frame>
        <Alert severity="error" role="alert" sx={{ mb: 1.5 }}>
          {AI_LADDER_COPY.loadError}
        </Alert>
        <Button variant="outlined" onClick={onRetry} disabled={!onRetry} sx={{ minHeight: 44 }}>
          {AI_LADDER_COPY.retry}
        </Button>
      </Frame>
    );
  }

  const placementState = status.placement_state;
  const activeEntry = placementState.phase === 'placement' ? status.current_opponent : placementState.rung;
  const unavailable =
    !activeEntry || activeEntry.certification_status !== 'certified' || activeEntry.availability === 'unavailable';

  return (
    <Frame>
      <Stack spacing={1.5}>
        {placementState.phase === 'placement' ? (
          <>
            <Typography fontWeight={700}>
              {AI_LADDER_COPY.placementOpponentPrefix}
              {status.current_opponent?.rank_name ?? '—'}
            </Typography>
            <Box>
              <Typography color="text.secondary" variant="body2" gutterBottom>
                {formatPlacementProgress(placementState.completed_games, placementState.total_games)}
              </Typography>
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
            </Box>
          </>
        ) : (
          <Typography fontWeight={700}>
            {AI_LADDER_COPY.rankedOpponentPrefix}
            {placementState.rung.rank_name}
          </Typography>
        )}

        {activeEntry && <StatusChips entry={activeEntry} />}

        {status.pending_settlement && (
          <Stack direction="row" role="status" aria-live="polite" alignItems="center" gap={1} color="warning.main">
            <HourglassTopRoundedIcon fontSize="small" />
            <Typography variant="body2" fontWeight={700}>{AI_LADDER_COPY.pendingSettlement}</Typography>
          </Stack>
        )}

        {unavailable && !status.pending_settlement && (
          <Stack direction="row" alignItems="center" gap={1} color="warning.main">
            <WarningAmberRoundedIcon fontSize="small" />
            <Typography variant="body2" fontWeight={700}>{AI_LADDER_COPY.unavailable}</Typography>
          </Stack>
        )}
      </Stack>
    </Frame>
  );
};

export default AiLadderSetupOpponent;
