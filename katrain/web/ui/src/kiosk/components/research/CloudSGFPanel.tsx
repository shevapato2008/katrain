/**
 * GameLibraryModal: A modal dialog for browsing and loading games from the
 * public tournament kifu album library (kifu API, no auth needed).
 *
 * Kiosk simplification: the galaxy original also offered a personal game
 * library gated behind auth (`useAuth` + `UserGamesAPI`). The kiosk build has
 * no login flow, so this down-port keeps only the public `KifuAPI` list.
 */
import { useState, useEffect, useCallback } from 'react';
import {
  Dialog, DialogTitle, DialogContent, DialogActions, Box, Typography,
  List, ListItem, ListItemButton, ListItemText,
  TextField, IconButton, Button, Pagination, Divider,
  CircularProgress, Chip,
} from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import CloseIcon from '@mui/icons-material/Close';
import SearchIcon from '@mui/icons-material/Search';
import { KifuAPI } from '../../../api/kifuApi';
import type { KifuAlbumSummary } from '../../../types/kifu';
import { useTranslation } from '../../../hooks/useTranslation';

interface GameLibraryModalProps {
  open: boolean;
  onClose: () => void;
  onLoadGame: (sgf: string) => void;
}

const PAGE_SIZE = 15;

export default function GameLibraryModal({ open, onClose, onLoadGame }: GameLibraryModalProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);

  // Data
  const [items, setItems] = useState<GameListItem[]>([]);
  const [total, setTotal] = useState(0);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  // Fetch data when the modal opens or the page changes
  useEffect(() => {
    if (!open) return;
    fetchData();
  }, [open, page]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await KifuAPI.getAlbums({ q: searchQuery || undefined, page, page_size: PAGE_SIZE });
      setItems(resp.items.map((item: KifuAlbumSummary) => ({
        id: String(item.id),
        title: item.event
          ? `${item.event}${item.round_name ? ' · ' + item.round_name : ''}`
          : `${item.player_black || '?'} vs ${item.player_white || '?'}`,
        playerBlack: item.player_black || '',
        playerWhite: item.player_white || '',
        blackRank: item.black_rank || '',
        whiteRank: item.white_rank || '',
        result: item.result || '',
        moveCount: item.move_count || 0,
        date: item.date_played || '',
      })));
      setTotal(resp.total);
    } catch (err) {
      console.error('Failed to fetch games:', err);
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, searchQuery]);

  const handleSearch = () => {
    setPage(1);
    fetchData();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch();
  };

  const handleSelectGame = async (item: GameListItem) => {
    try {
      let sgf: string | undefined = item.sgfContent;
      if (!sgf) {
        const detail = await KifuAPI.getAlbum(Number(item.id));
        sgf = detail.sgf_content;
      }
      if (sgf) {
        onLoadGame(sgf);
        onClose();
      }
    } catch (err) {
      console.error('Failed to load game:', err);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          height: '70vh',
          maxHeight: 600,
          bgcolor: 'background.paper',
        },
      }}
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', py: 1.5 }}>
        <Typography
          variant="h6"
          sx={{ fontFamily: "'Newsreader','Noto Serif SC',serif", fontWeight: 500, fontSize: '1.15rem' }}
        >
          {t('research:game_library', '从棋谱库打开')}
        </Typography>
        <IconButton size="small" onClick={onClose}>
          <CloseIcon fontSize="small" />
        </IconButton>
      </DialogTitle>
      <Divider />
      <DialogContent sx={{ p: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Search bar */}
        <Box sx={{ p: 1.5, display: 'flex', gap: 1 }}>
          <TextField
            size="small"
            fullWidth
            placeholder={t('research:search_placeholder', '搜索棋手、赛事...')}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            sx={{ '& .MuiInputBase-root': { fontSize: '0.875rem' } }}
          />
          <IconButton size="small" onClick={handleSearch}>
            <SearchIcon />
          </IconButton>
        </Box>

        <Divider />

        {/* List */}
        <Box sx={{ flex: 1, overflow: 'auto', p: 1.5 }}>
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
              <CircularProgress size={32} />
            </Box>
          ) : items.length === 0 ? (
            <Box sx={{ p: 3, textAlign: 'center' }}>
              <Typography variant="body2" color="text.secondary">
                {t('research:no_games', '暂无棋谱')}
              </Typography>
            </Box>
          ) : (
            <List dense sx={{ py: 0, display: 'flex', flexDirection: 'column', gap: 1 }}>
              {items.map((item) => (
                <ListItem key={item.id} disablePadding>
                  <ListItemButton
                    onClick={() => handleSelectGame(item)}
                    sx={{
                      py: 1,
                      px: 1.5,
                      borderRadius: '11px',
                      border: '1px solid',
                      borderColor: 'divider',
                      bgcolor: 'var(--raise2)',
                      '&:hover': { borderColor: '#3a4d45', bgcolor: 'var(--raise2)' },
                    }}
                  >
                    <ListItemText
                      secondaryTypographyProps={{ component: 'div' }}
                      primary={
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                          <Typography variant="caption" color="text.secondary" noWrap sx={{ maxWidth: '60%' }}>
                            {item.title}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {item.date ? item.date.slice(0, 10) : ''}
                            {item.moveCount > 0
                              ? ` · ${t('research:n_moves', '{n}手').replace('{n}', String(item.moveCount))}`
                              : ''}
                          </Typography>
                        </Box>
                      }
                      secondary={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Box
                            sx={{
                              width: 12, height: 12, borderRadius: '50%', flexShrink: 0,
                              background: 'radial-gradient(circle at 35% 30%, #4a4a4a, #0a0a0a)',
                              border: '1px solid #000',
                            }}
                          />
                          <Typography component="span" variant="body2" sx={{ fontWeight: 600, fontSize: '0.85rem' }}>
                            {item.playerBlack || '?'}
                          </Typography>
                          {item.blackRank && (
                            <Typography component="span" variant="caption" color="text.secondary">
                              {item.blackRank}
                            </Typography>
                          )}
                          {item.result && (
                            <Chip
                              label={item.result}
                              size="small"
                              sx={{
                                height: 20,
                                fontSize: '0.7rem',
                                fontWeight: 700,
                                color: 'primary.main',
                                bgcolor: alpha(theme.palette.primary.main, 0.14),
                              }}
                            />
                          )}
                          <Typography component="span" variant="body2" color="text.secondary" sx={{ fontSize: '0.85rem' }}>
                            {item.playerWhite || '?'}
                          </Typography>
                          {item.whiteRank && (
                            <Typography component="span" variant="caption" color="text.secondary">
                              {item.whiteRank}
                            </Typography>
                          )}
                          <Box
                            sx={{
                              width: 12, height: 12, borderRadius: '50%', flexShrink: 0,
                              background: 'radial-gradient(circle at 35% 30%, #fff, #cabfa9)',
                              border: '1px solid #8a8272',
                            }}
                          />
                        </Box>
                      }
                    />
                  </ListItemButton>
                </ListItem>
              ))}
            </List>
          )}
        </Box>

        {/* Pagination */}
        {totalPages > 1 && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 1, borderTop: '1px solid', borderColor: 'divider' }}>
            <Pagination
              count={totalPages}
              page={page}
              onChange={(_, p) => setPage(p)}
              size="small"
            />
          </Box>
        )}
      </DialogContent>
      <Divider />
      <DialogActions sx={{ px: 2, py: 1.5 }}>
        <Button onClick={onClose} color="inherit" size="small">
          {t('research:cancel', '取消')}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

interface GameListItem {
  id: string;
  title: string;
  playerBlack: string;
  playerWhite: string;
  blackRank: string;
  whiteRank: string;
  result: string;
  moveCount: number;
  date: string;
  sgfContent?: string;
}
