import { Box, Typography, Card, CardContent, Skeleton, Link } from '@mui/material';
import { useEffect, useState } from 'react';
import { LiveAPI } from '../../api/live';
import type { UpcomingMatch } from '../../types/live';
import CalendarTodayIcon from '@mui/icons-material/CalendarToday';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';

interface UpcomingListProps {
  limit?: number;
}

export default function UpcomingList({ limit = 20 }: UpcomingListProps) {
  const [upcoming, setUpcoming] = useState<UpcomingMatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchUpcoming = async () => {
      try {
        setLoading(true);
        const response = await LiveAPI.getUpcoming(limit);
        setUpcoming(response.matches);
        setError(null);
      } catch (err) {
        setError('Failed to load upcoming events');
        console.error('Failed to fetch upcoming:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchUpcoming();
    // Refresh every 30 minutes
    const interval = setInterval(fetchUpcoming, 30 * 60 * 1000);
    return () => clearInterval(interval);
  }, [limit]);

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffDays = Math.ceil((date.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));

    const dateFormatted = date.toLocaleDateString('zh-CN', {
      month: 'short',
      day: 'numeric',
      weekday: 'short',
    });

    if (diffDays === 0) {
      return { date: dateFormatted, label: '今天', color: 'success.main' };
    } else if (diffDays === 1) {
      return { date: dateFormatted, label: '明天', color: 'warning.main' };
    } else if (diffDays <= 7) {
      return { date: dateFormatted, label: `${diffDays}天后`, color: 'info.main' };
    }
    return { date: dateFormatted, label: null, color: 'text.secondary' };
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} variant="rounded" height={80} />
        ))}
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ textAlign: 'center', py: 4 }}>
        <Typography color="error">{error}</Typography>
      </Box>
    );
  }

  if (upcoming.length === 0) {
    return (
      <Box sx={{ textAlign: 'center', py: 4 }}>
        <CalendarTodayIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 1 }} />
        <Typography color="text.secondary">
          暂无即将进行的赛事
        </Typography>
        <Typography variant="caption" color="text.disabled">
          数据来源：日本棋院、野狐围棋
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      {upcoming.map((event) => {
        const { date, label, color } = formatDate(event.scheduled_time);
        return (
          <Card
            key={event.id}
            variant="outlined"
            sx={{
              bgcolor: 'background.paper',
              '&:hover': { bgcolor: 'action.hover' },
            }}
          >
            <CardContent sx={{ py: 1.5, px: 2, '&:last-child': { pb: 1.5 } }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography
                    variant="body2"
                    fontWeight="medium"
                    noWrap
                    title={event.tournament}
                  >
                    {event.tournament}
                  </Typography>
                  {event.round_name && (
                    <Typography variant="caption" color="text.secondary" noWrap>
                      {event.round_name}
                    </Typography>
                  )}
                  {event.player_black && event.player_white && (
                    <Typography variant="caption" color="text.secondary" display="block">
                      {event.player_black} vs {event.player_white}
                    </Typography>
                  )}
                </Box>
                <Box sx={{ textAlign: 'right', ml: 1, flexShrink: 0 }}>
                  <Typography variant="caption" color={color} fontWeight="medium">
                    {label && <span>{label} </span>}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" display="block">
                    {date}
                  </Typography>
                </Box>
              </Box>
              {event.source_url && (
                <Link
                  href={event.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  sx={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 0.5,
                    fontSize: '0.7rem',
                    mt: 0.5,
                    color: 'text.disabled',
                    textDecoration: 'none',
                    '&:hover': { color: 'primary.main' },
                  }}
                >
                  <OpenInNewIcon sx={{ fontSize: 12 }} />
                  官方信息
                </Link>
              )}
            </CardContent>
          </Card>
        );
      })}
    </Box>
  );
}
