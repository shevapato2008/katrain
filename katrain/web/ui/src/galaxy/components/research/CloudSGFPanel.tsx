/**
 * GameLibraryModal: A modal dialog for browsing and loading games from:
 * - Personal game library (user_games API, requires auth)
 * - Public tournament kifu albums (kifu API, no auth needed)
 */
import { useState, useEffect, useCallback } from 'react';
import {
  Dialog, DialogTitle, DialogContent, Box, Typography,
  List, ListItem, ListItemButton, ListItemText,
  TextField, IconButton, Pagination, Divider,
  CircularProgress, Chip,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import SearchIcon from '@mui/icons-material/Search';
import FolderIcon from '@mui/icons-material/Folder';
import PublicIcon from '@mui/icons-material/Public';
import { useAuth } from '../../context/AuthContext';
import { UserGamesAPI, type UserGameSummary } from '../../api/userGamesApi';
import { KifuAPI } from '../../api/kifuApi';
import { useTranslation } from '../../../hooks/useTranslation';

type Category = 'my_games' | 'my_positions' | 'public_kifu';

interface GameLibraryModalProps {
  open: boolean;
  onClose: () => void;
  onLoadGame: (sgf: string) => void;
}

const CATEGORY_KEYS: { key: Category; labelKey: string; labelFallback: string; icon: React.ReactNode }[] = [
  { key: 'my_games', labelKey: 'research:my_games', labelFallback: '我的棋谱', icon: <FolderIcon sx={{ fontSize: 18 }} /> },
  { key: 'my_positions', labelKey: 'research:my_positions', labelFallback: '我的盘面', icon: <FolderIcon sx={{ fontSize: 18 }} /> },
  { key: 'public_kifu', labelKey: 'research:tournament_games', labelFallback: '大赛棋谱', icon: <PublicIcon sx={{ fontSize: 18 }} /> },
];

const PAGE_SIZE = 15;

export default function GameLibraryModal({ open, onClose, onLoadGame }: GameLibraryModalProps) {
  const { token } = useAuth();
  const { t } = useTranslation();
  const [category, setCategory] = useState<Category>('my_games');
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);

  // Data
  const [items, setItems] = useState<GameListItem[]>([]);
  const [total, setTotal] = useState(0);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  // Fetch data when category, page, or search changes
  useEffect(() => {
    if (!open) return;
    fetchData();
  }, [open, category, page]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      if (category === 'public_kifu') {
        const resp = await KifuAPI.getAlbums({ q: searchQuery || undefined, page, page_size: PAGE_SIZE });
        setItems(resp.items.map((item: any) => ({
          id: String(item.id),
          title: item.title || `${item.player_black || '?'} vs ${item.player_white || '?'}`,
          playerBlack: item.player_black || '',
          playerWhite: item.player_white || '',
          result: item.result || '',
          moveCount: item.move_count || 0,
          date: item.game_date || item.event_date || '',
          source: 'public_kifu' as const,
          sgfContent: item.sgf_content,
        })));
        setTotal(resp.total);
      } else if (token) {
        const catFilter = category === 'my_positions' ? 'position' : 'game';
        const resp = await UserGamesAPI.list(token, {
          page,
          page_size: PAGE_SIZE,
          category: catFilter,
          q: searchQuery || undefined,
        });
        setItems(resp.items.map((item: UserGameSummary) => ({
          id: item.id,
          title: item.title || `${item.player_black || '?'} vs ${item.player_white || '?'}`,
          playerBlack: item.player_black || '',
          playerWhite: item.player_white || '',
          result: item.result || '',
          moveCount: item.move_count,
          date: item.game_date || item.created_at || '',
          source: category,
        })));
        setTotal(resp.total);
      } else {
        setItems([]);
        setTotal(0);
      }
    } catch (err) {
      console.error('Failed to fetch games:', err);
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [category, page, searchQuery, token]);

  const handleSearch = () => {
    setPage(1);
    fetchData();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch();
  };

  const handleSelectGame = async (item: GameListItem) => {
    try {
      let sgf: string | undefined;
      if (item.source === 'public_kifu') {
        // Public kifu: fetch full detail to get SGF
        if (item.sgfContent) {
          sgf = item.sgfContent;
        } else {
          const detail = await KifuAPI.getAlbum(Number(item.id));
          sgf = detail.sgf_content;
        }
      } else if (token) {
        // Personal game: fetch detail to get SGF
        const detail = await UserGamesAPI.get(token, item.id);
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

  const handleCategoryChange = (cat: Category) => {
    setCategory(cat);
    setPage(1);
    setSearchQuery('');
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
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
        <Typography variant="h6" sx={{ fontSize: '1rem', fontWeight: 600 }}>{t('research:game_library', '棋谱库')}</Typography>
        <IconButton size="small" onClick={onClose}>
          <CloseIcon fontSize="small" />
        </IconButton>
      </DialogTitle>
      <Divider />
      <DialogContent sx={{ p: 0, display: 'flex', overflow: 'hidden' }}>
        {/* Left sidebar: categories */}
        <Box sx={{
          width: 160,
          flexShrink: 0,
          borderRight: '1px solid',
          borderColor: 'divider',
          display: 'flex',
          flexDirection: 'column',
        }}>
          <List dense sx={{ py: 0 }}>
            {CATEGORY_KEYS.map((cat) => (
              <ListItem key={cat.key} disablePadding>
                <ListItemButton
                  selected={category === cat.key}
                  onClick={() => handleCategoryChange(cat.key)}
                  disabled={cat.key !== 'public_kifu' && !token}
                  sx={{
                    py: 1.5,
                    '&.Mui-selected': {
                      bgcolor: 'rgba(74, 107, 92, 0.15)',
                      borderRight: '2px solid',
                      borderColor: 'primary.main',
                    },
                  }}
                >
                  <Box sx={{ mr: 1, display: 'flex', alignItems: 'center', color: 'text.secondary' }}>
                    {cat.icon}
                  </Box>
                  <ListItemText
                    primary={t(cat.labelKey, cat.labelFallback)}
                    primaryTypographyProps={{ fontSize: '0.85rem' }}
                  />
                </ListItemButton>
              </ListItem>
            ))}
          </List>
          {!token && (
            <Box sx={{ p: 1.5 }}>
              <Typography variant="caption" color="text.secondary">
                {t('research:login_to_view', '登录后可查看个人棋谱')}
              </Typography>
            </Box>
          )}
        </Box>

        {/* Right: search + list */}
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
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
          <Box sx={{ flex: 1, overflow: 'auto' }}>
            {loading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                <CircularProgress size={32} />
              </Box>
            ) : items.length === 0 ? (
              <Box sx={{ p: 3, textAlign: 'center' }}>
                <Typography variant="body2" color="text.secondary">
                  {!token && category !== 'public_kifu' ? t('research:please_login', '请先登录') : t('research:no_games', '暂无棋谱')}
                </Typography>
              </Box>
            ) : (
              <List dense sx={{ py: 0 }}>
                {items.map((item) => (
                  <ListItem key={item.id} disablePadding>
                    <ListItemButton onClick={() => handleSelectGame(item)} sx={{ py: 1 }}>
                      <ListItemText
                        primary={
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.85rem' }}>
                              {item.title}
                            </Typography>
                            {item.result && (
                              <Chip label={item.result} size="small" sx={{ height: 20, fontSize: '0.7rem' }} />
                            )}
                          </Box>
                        }
                        secondary={
                          <Typography variant="caption" color="text.secondary">
                            {item.moveCount > 0 ? t('research:n_moves', '{n}手').replace('{n}', String(item.moveCount)) : ''}
                            {item.date ? ` | ${item.date.slice(0, 10)}` : ''}
                          </Typography>
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
        </Box>
      </DialogContent>
    </Dialog>
  );
}

interface GameListItem {
  id: string;
  title: string;
  playerBlack: string;
  playerWhite: string;
  result: string;
  moveCount: number;
  date: string;
  source: Category | 'public_kifu';
  sgfContent?: string;
}
