import { Box, Typography, CircularProgress, Alert, Tabs, Tab } from '@mui/material';
import { useState } from 'react';
import MatchCard from './MatchCard';
import type { MatchSummary } from '../../../types/live';

interface MatchListProps {
  matches: MatchSummary[];
  loading?: boolean;
  error?: Error | null;
  compact?: boolean;
  title?: string;
  showTabs?: boolean;
  selectedId?: string;  // Currently selected match ID
  onSelect?: (match: MatchSummary) => void;  // Callback when a match is selected
}

export default function MatchList({
  matches,
  loading = false,
  error = null,
  compact = false,
  title,
  showTabs = false,
  selectedId,
  onSelect,
}: MatchListProps) {
  const [tab, setTab] = useState(0);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ m: 2 }}>
        加载失败: {error.message}
      </Alert>
    );
  }

  // Split matches by status
  const liveMatches = matches.filter((m) => m.status === 'live');
  const finishedMatches = matches.filter((m) => m.status === 'finished');

  const displayMatches = showTabs
    ? tab === 0
      ? liveMatches
      : finishedMatches
    : matches;

  return (
    <Box>
      {title && (
        <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
          {title}
        </Typography>
      )}

      {showTabs && (
        <Tabs
          value={tab}
          onChange={(_, v) => setTab(v)}
          sx={{ mb: 2, borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab label={`正在直播 (${liveMatches.length})`} />
          <Tab label={`历史直播 (${finishedMatches.length})`} />
        </Tabs>
      )}

      {displayMatches.length === 0 ? (
        <Box sx={{ textAlign: 'center', py: 4, color: 'text.secondary' }}>
          <Typography>暂无比赛</Typography>
        </Box>
      ) : (
        <Box>
          {displayMatches.map((match) => (
            <MatchCard
              key={match.id}
              match={match}
              compact={compact}
              selected={selectedId === match.id}
              onSelect={onSelect}
            />
          ))}
        </Box>
      )}
    </Box>
  );
}
