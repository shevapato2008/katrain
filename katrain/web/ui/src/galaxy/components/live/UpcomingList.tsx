import { Box, Typography, Card, CardContent, Skeleton, Link } from '@mui/material';
import { useEffect, useState } from 'react';
import { LiveAPI } from '../../../api/live';
import type { UpcomingMatch } from '../../../types/live';
import CalendarTodayIcon from '@mui/icons-material/CalendarToday';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { i18n } from '../../../i18n';
import { useTranslation } from '../../../hooks/useTranslation';

interface UpcomingListProps {
  limit?: number;
}

export default function UpcomingList({ limit = 20 }: UpcomingListProps) {
  const { t, lang } = useTranslation();
  const [upcoming, setUpcoming] = useState<UpcomingMatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchUpcoming = async () => {
      try {
        setLoading(true);
        const response = await LiveAPI.getUpcoming(limit, lang);
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
  }, [limit, lang]);

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffDays = Math.ceil((date.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));

    const locale = lang === 'en' ? 'en-US' : 'zh-CN';
    const dateFormatted = date.toLocaleDateString(locale, {
      month: 'short',
      day: 'numeric',
      weekday: 'short',
    });

    if (diffDays === 0) {
      return { date: dateFormatted, label: t('live:today'), color: 'success.main' };
    } else if (diffDays === 1) {
      return { date: dateFormatted, label: t('live:tomorrow'), color: 'warning.main' };
    } else if (diffDays <= 7) {
      const label = t('live:in_days').replace('{0}', String(diffDays));
      return { date: dateFormatted, label, color: 'info.main' };
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
          {t('live:no_upcoming')}
        </Typography>
        <Typography variant="caption" color="text.disabled">
          {t('live:data_source')}
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
                    title={i18n.translateTournament(event.tournament)}
                  >
                    {i18n.translateTournament(event.tournament)}
                  </Typography>
                  {event.round_name && (
                    <Typography variant="caption" color="text.secondary" noWrap>
                      {i18n.translateRound(event.round_name)}
                    </Typography>
                  )}
                  {event.player_black && event.player_white && (
                    <Typography variant="caption" color="text.secondary" display="block">
                      {i18n.translatePlayer(event.player_black)} vs {i18n.translatePlayer(event.player_white)}
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
                  {t('live:official_info')}
                </Link>
              )}
            </CardContent>
          </Card>
        );
      })}
    </Box>
  );
}
