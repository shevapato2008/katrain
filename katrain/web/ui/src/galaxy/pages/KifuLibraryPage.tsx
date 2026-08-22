/**
 * KifuLibraryPage —— 棋谱库
 *
 * 版式：统一的 `BoardPageShell`（spec §2.2/§2.3）。
 *
 * 迁版式前是**左右相反**的：左边 520px 写死宽度的列表、右边棋盘，棋盘下方另有一条
 * 自己的操作条。冻结稿 V2 把它对调过来 —— 棋盘在左，搜索 / 卡片列表 / 分页整块搬进
 * 右栏；这是本轮六个棋盘页里唯一构图整体翻转的一页，也是唯一有信息损失风险的一页
 * （520 宽的卡片要压进 320）。
 *
 * 另外原来给 `LiveBoard` 没传 `minimumCanvasSize`，于是吃了它 400px 的硬下限
 * （`LiveBoard.tsx:325-326`）；在 shell 那个 `aspectRatio: 1/1` 的定尺格里，
 * 400 下限在窄档必然把棋盘顶出容器。这里和已迁的三页一样传 0/0。
 */

import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Box,
  Typography,
  TextField,
  Pagination,
  InputAdornment,
  Skeleton,
  Fade,
  Card,
  CardActionArea,
  Button,
  Chip,
  CircularProgress,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import ScienceIcon from '@mui/icons-material/Science';
import { KifuAPI } from '../../api/kifuApi';
import type { KifuAlbumSummary, KifuAlbumDetail } from '../../types/kifu';
import { useTranslation } from '../../hooks/useTranslation';
import { translateResult } from '../../utils/resultTranslation';
import { sgfToMoves } from '../../utils/sgfSerializer';
import LiveBoard from '../../components/live/LiveBoard';
import PlaybackBar from '../../components/live/PlaybackBar';
import BoardPageShell from '../components/board/BoardPageShell';
import ModulePlate from '../components/layout/ModulePlate';
import { useBoardCoordinates } from '../components/board/useBoardCoordinates';

/* 右栏窄档（320 / 340）下的卡片压缩。整块列表从 520 搬进 320，卡片必须自己收 ——
   用具名容器查询，不用视口媒体查询：判据是「卡片实际拿到多少宽」，而右栏宽度是
   由 shell 的 `containerName: 'board-rail'` 决定的，跟视口不是一回事（左栏折叠、
   竖屏下沉都会改它）。同一手法见 `PlaybackBar.tsx` 的 NARROW。 */
const RAIL_NARROW = '@container board-rail (max-width: 340px)';

const PAGE_SIZE = 20;
const ROW_STAGGER = 25;

/* ── Result badge (inline) ── */
function ResultBadge({ result, rules, t }: { result: string | null; rules?: string | null; t: (key: string, fallback?: string) => string }) {
  const raw = result || '?';
  const isBlack = raw.startsWith('B') || raw.startsWith('黑');
  const label = translateResult(result, t, rules);

  return (
    <Typography
      component="span"
      sx={{
        display: 'inline-block',
        fontSize: '0.65rem',
        [RAIL_NARROW]: { fontSize: '0.6rem', px: 0.5 },
        fontWeight: 700,
        lineHeight: 1,
        px: 0.7,
        py: 0.3,
        borderRadius: '4px',
        fontFamily: (t) => `"IBM Plex Mono", monospace, ${t.typography.fontFamily}`,
        bgcolor: isBlack ? 'rgba(10,10,10,0.9)' : 'rgba(255,255,255,0.1)',
        color: isBlack ? '#ccc' : '#f5f3f0',
        border: '1px solid',
        borderColor: isBlack ? 'rgba(255,255,255,0.1)' : 'rgba(255,255,255,0.12)',
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </Typography>
  );
}

/* ── Skeleton placeholder cards ── */
function SkeletonCards({ count }: { count: number }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      {Array.from({ length: count }).map((_, i) => (
        <Box
          key={i}
          sx={{
            p: 1.5,
            borderRadius: '8px',
            bgcolor: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.06)',
          }}
        >
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
            <Skeleton variant="text" width={200} sx={{ bgcolor: 'rgba(255,255,255,0.04)', fontSize: '0.75rem' }} />
            <Skeleton variant="text" width={60} sx={{ bgcolor: 'rgba(255,255,255,0.04)', fontSize: '0.75rem' }} />
          </Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
            <Skeleton variant="text" width={100} sx={{ bgcolor: 'rgba(255,255,255,0.05)', fontSize: '0.9rem' }} />
            <Skeleton variant="text" width={100} sx={{ bgcolor: 'rgba(255,255,255,0.05)', fontSize: '0.9rem' }} />
          </Box>
        </Box>
      ))}
    </Box>
  );
}

/* ── Single game record card (matches live MatchCard compact style) ── */
function GameRecordCard({
  album,
  onClick,
  tMovesUnit,
  t,
  selected,
}: {
  album: KifuAlbumSummary;
  onClick: () => void;
  tMovesUnit: string;
  t: (key: string, fallback?: string) => string;
  selected?: boolean;
}) {
  const r = album.result || '';
  const blackWins = r.startsWith('B') || r.startsWith('黑');

  return (
    <Card
      sx={{
        bgcolor: selected ? 'rgba(76, 175, 80, 0.12)' : 'rgba(255,255,255,0.05)',
        border: selected ? 2 : 1,
        borderColor: selected ? 'primary.main' : 'rgba(255,255,255,0.1)',
        borderRadius: '8px',
        '&:hover': {
          borderColor: selected ? 'primary.main' : 'rgba(255,255,255,0.2)',
          bgcolor: selected ? 'rgba(76, 175, 80, 0.15)' : 'rgba(255,255,255,0.07)',
        },
      }}
    >
      <CardActionArea onClick={onClick} sx={{ p: 1.5, [RAIL_NARROW]: { p: 1 } }}>
        {/* Row 1: Event + Date + Moves */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5, [RAIL_NARROW]: { gap: 0.6 } }}>
          {/* 赛事名是这一行里唯一可以被挤的：它 `flex:1`，日期和手数 `flexShrink:0`。
              但**不能只截一行** —— 列表从 520 搬进 320 之后实测（1024×768）20 张里有
              11 张的赛事名超出，最长一条 298px 只显示得下 165px，丢掉的正好是
              「苏泊尔杭州-山西元工弘弈」这半截队名，也就是围甲局的辨识信息。
              冻结稿的注解点名要查的就是这一处。改成最多两行：2 × 165 = 330 > 298，
              最长的那条也装得下，只有真的长的那几张卡会高出一行。 */}
          <Typography variant="caption" color="text.secondary" sx={{
            flex: 1, minWidth: 0,
            display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
            overflow: 'hidden', wordBreak: 'break-word',
            [RAIL_NARROW]: { fontSize: '0.68rem' },
          }}>
            {album.event || ''}
            {album.round_name && (
              <Typography component="span" sx={{ opacity: 0.6, fontSize: '0.7rem', ml: 0.5, [RAIL_NARROW]: { fontSize: '0.64rem' } }}>
                {album.round_name}
              </Typography>
            )}
          </Typography>
          {album.date_played && (
            <Typography variant="caption" color="text.secondary" sx={{ flexShrink: 0, fontSize: '0.7rem', opacity: 0.7, [RAIL_NARROW]: { fontSize: '0.64rem' } }}>
              {album.date_played}
            </Typography>
          )}
          <Typography variant="caption" color="text.secondary" sx={{ flexShrink: 0, [RAIL_NARROW]: { fontSize: '0.64rem' } }}>
            {album.move_count} {tMovesUnit}
          </Typography>
        </Box>

        {/* Row 2: Black player  [result]  vs  White player */}
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: 0 }}>
            <Box sx={{
              width: 16, height: 16, borderRadius: '50%', flexShrink: 0, mr: 0.7,
              [RAIL_NARROW]: { width: 12, height: 12, mr: 0.5 },
              bgcolor: '#1a1a1a',
              border: '1px solid rgba(255,255,255,0.18)',
              boxShadow: 'inset 0 -0.5px 1px rgba(255,255,255,0.1)',
            }} />
            <Typography
              variant="body2"
              noWrap
              sx={{ fontWeight: blackWins ? 'bold' : 'normal', [RAIL_NARROW]: { fontSize: '0.8rem' } }}
            >
              {album.player_black}
            </Typography>
            {album.black_rank && (
              <Typography component="span" sx={{ color: 'text.secondary', fontSize: '0.68rem', ml: 0.5, flexShrink: 0 }}>
                {album.black_rank}
              </Typography>
            )}
          </Box>

          <Box sx={{ px: 1, flexShrink: 0, [RAIL_NARROW]: { px: 0.5 } }}>
            <ResultBadge result={album.result} rules={album.rules} t={t} />
          </Box>

          <Box sx={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: 0, justifyContent: 'flex-end' }}>
            {album.white_rank && (
              <Typography component="span" sx={{ color: 'text.secondary', fontSize: '0.68rem', mr: 0.5, flexShrink: 0 }}>
                {album.white_rank}
              </Typography>
            )}
            <Typography
              variant="body2"
              noWrap
              sx={{ fontWeight: !blackWins ? 'bold' : 'normal', [RAIL_NARROW]: { fontSize: '0.8rem' } }}
            >
              {album.player_white}
            </Typography>
            <Box sx={{
              width: 16, height: 16, borderRadius: '50%', flexShrink: 0, ml: 0.7,
              [RAIL_NARROW]: { width: 12, height: 12, ml: 0.5 },
              bgcolor: '#e8e4df',
              border: '1px solid rgba(0,0,0,0.25)',
              boxShadow: 'inset 0 0.5px 1px rgba(0,0,0,0.06)',
            }} />
          </Box>
        </Box>
      </CardActionArea>
    </Card>
  );
}

/* ── Main page ── */
export default function KifuLibraryPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();

  const page = Number(searchParams.get('page')) || 1;
  const query = searchParams.get('q') || '';

  const [items, setItems] = useState<KifuAlbumSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [searchInput, setSearchInput] = useState(query);

  // Board preview state
  const [selectedAlbum, setSelectedAlbum] = useState<KifuAlbumSummary | null>(null);
  const [previewMoves, setPreviewMoves] = useState<string[]>([]);
  const [previewColors, setPreviewColors] = useState<('B' | 'W')[]>([]);
  const [previewCurrentMove, setPreviewCurrentMove] = useState(0);
  const [previewBoardSize, setPreviewBoardSize] = useState(19);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [boardEdge, setBoardEdge] = useState(0);
  const coordinates = useBoardCoordinates(boardEdge);

  useEffect(() => {
    setSearchInput(query);
  }, [query]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await KifuAPI.getAlbums({ q: query || undefined, page, page_size: PAGE_SIZE });
      setItems(data.items);
      setTotal(data.total);
    } catch (err) {
      console.error('Failed to fetch kifu albums:', err);
    } finally {
      setLoading(false);
    }
  }, [query, page]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSearch = () => {
    const params: Record<string, string> = {};
    if (searchInput) params.q = searchInput;
    setSearchParams(params, { replace: false });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch();
  };

  const handlePageChange = (_: unknown, newPage: number) => {
    const params: Record<string, string> = {};
    if (query) params.q = query;
    if (newPage > 1) params.page = String(newPage);
    setSearchParams(params, { replace: false });
  };

  // Load SGF for board preview when a card is clicked
  const handleCardClick = useCallback(async (album: KifuAlbumSummary) => {
    setSelectedAlbum(album);
    setPreviewLoading(true);
    try {
      const detail: KifuAlbumDetail = await KifuAPI.getAlbum(album.id);
      if (detail.sgf_content) {
        const parsed = sgfToMoves(detail.sgf_content);
        setPreviewMoves(parsed.moves);
        setPreviewColors(parsed.stoneColors);
        setPreviewCurrentMove(parsed.moves.length); // Show final position
        setPreviewBoardSize(parsed.metadata.boardSize || album.board_size || 19);
      }
    } catch (err) {
      console.error('Failed to load kifu preview:', err);
    } finally {
      setPreviewLoading(false);
    }
  }, []);

  const handleOpenInResearch = useCallback(() => {
    if (selectedAlbum) {
      navigate(`/galaxy/research?kifu_id=${selectedAlbum.id}`);
    }
  }, [selectedAlbum, navigate]);

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const movesUnit = t('kifu:moves_unit', '手');

  const hasPreview = selectedAlbum !== null && !previewLoading && previewMoves.length > 0;

  /* 模块牌副标题：选中棋谱后是对局双方 + 手数，没选中时是记录总数。
     列表还在加载时给一条骨架，避免标题行先塌一次再撑开。 */
  const plateSubtitle = loading && !selectedAlbum
    ? <Skeleton width={140} />
    : selectedAlbum
      ? `${selectedAlbum.player_black} vs ${selectedAlbum.player_white} · ${selectedAlbum.move_count} ${movesUnit}`
      : `${total.toLocaleString()} ${t('kifu:records', 'records')}${query ? ` · "${query}"` : ''}`;

  /* 胜负 chip 进模块牌最右 —— spec §2.4「状态放最右」，和已批准的直播样板
     （`LiveMatchPage.tsx:130-140` 的直播中/已结束 chip）同一个槽。
     §2.4 禁的是把 eyebrow / 面包屑 / 长副标题 / 状态说明和一堆 chip **堆**进页头，
     不是禁这一个状态位。 */
  const plateStatus = selectedAlbum?.result
    ? (
      <Chip
        size="small"
        variant="outlined"
        label={translateResult(selectedAlbum.result, t, selectedAlbum.rules)}
      />
    )
    : undefined;

  return (
    <BoardPageShell
      onBoardSizeChange={setBoardEdge}
      board={hasPreview ? (
        <LiveBoard
          moves={previewMoves}
          stoneColors={previewColors}
          currentMove={previewCurrentMove}
          boardSize={previewBoardSize}
          /* 迁版式前这里写死 `showCoordinates={true}`。改成走共享的自动档：
             spec §3.2「棋盘边长低于 500px 时坐标默认关闭」。本页冻结稿里没有坐标
             开关（右栏塞的是列表，没有显示开关那一段），所以只取 `visible`，
             不挂 toggle —— 有开关的那几页才需要开关。 */
          showCoordinates={coordinates.visible}
          minimumCanvasSize={0}
          minContainerHeight={0}
        />
      ) : previewLoading ? (
        <CircularProgress data-testid="kifu-preview-spinner" />
      ) : (
        <Typography variant="body2" color="text.secondary" sx={{ opacity: 0.5, textAlign: 'center', px: 2 }}>
          {/* 冻结稿写的是「从右边选一局棋谱预览」。这里保留原来那句不带方位的说法 ——
              <900px 竖屏下列表在棋盘**下方**，「从右边」就是假的。 */}
          {t('kifu:select_to_preview', '选择一局棋谱预览')}
        </Typography>
      )}
      modulePlate={(
        <ModulePlate
          title={t('kifu:library', '棋谱库')}
          subtitle={plateSubtitle}
          status={plateStatus}
          /* 棋谱库是一级导航页，没有上一级 —— 同研究页（`ResearchPage.tsx:501`）。 */
          backTo="/galaxy/kifu"
          showBack={false}
        />
      )}
      railBody={(
        <>
          <Box sx={{ p: 2, pb: 1.5 }}>
            <TextField
              fullWidth
              size="small"
              placeholder={t('kifu:search_placeholder', 'Search by player, event, date...')}
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={handleKeyDown}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon sx={{ color: 'text.secondary', fontSize: 20, opacity: 0.6 }} />
                  </InputAdornment>
                ),
              }}
              sx={{
                '& .MuiOutlinedInput-root': {
                  bgcolor: 'rgba(255,255,255,0.025)',
                  borderRadius: '10px',
                  fontSize: '0.88rem',
                  transition: 'all 200ms ease',
                  '& fieldset': { borderColor: 'rgba(255,255,255,0.05)' },
                  '&:hover': {
                    bgcolor: 'rgba(255,255,255,0.04)',
                    '& fieldset': { borderColor: 'rgba(255,255,255,0.08)' },
                  },
                  '&.Mui-focused': {
                    bgcolor: 'rgba(255,255,255,0.045)',
                    '& fieldset': { borderColor: 'rgba(74,107,92,0.4)' },
                  },
                },
              }}
            />
            {/* 记录数与页码。选中棋谱后模块牌的副标题会换成对局双方，所以这一行
                是「一共多少局、看到第几页」唯一常驻的地方（冻结稿同址）。 */}
            {!loading && (
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ display: 'block', mt: 1, fontSize: '0.72rem', opacity: 0.7 }}
              >
                {total.toLocaleString()} {t('kifu:records', 'records')}
                {totalPages > 1 && ` · ${t('kifu:page_x_of_y', '第 {page} / {total} 页')
                  .replace('{page}', String(page))
                  .replace('{total}', String(totalPages))}`}
              </Typography>
            )}
          </Box>

          <Box sx={{ px: 1.5, pb: 1 }}>
            {loading ? (
              <SkeletonCards count={8} />
            ) : items.length === 0 ? (
              <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', pt: 6, pb: 6, gap: 1 }}>
                <Typography variant="h6" sx={{ color: 'text.secondary', fontWeight: 500 }}>
                  {t('kifu:no_results', 'No records found')}
                </Typography>
                {query && (
                  <Typography variant="body2" sx={{ color: 'text.secondary', opacity: 0.5 }}>
                    "{query}"
                  </Typography>
                )}
              </Box>
            ) : (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {items.map((album, index) => (
                  <Fade key={album.id} in timeout={200 + index * ROW_STAGGER}>
                    <Box>
                      <GameRecordCard
                        album={album}
                        onClick={() => handleCardClick(album)}
                        tMovesUnit={movesUnit}
                        t={t}
                        selected={selectedAlbum?.id === album.id}
                      />
                    </Box>
                  </Fade>
                ))}
              </Box>
            )}
          </Box>

          {totalPages > 1 && (
            <Box sx={{ display: 'flex', justifyContent: 'center', px: 1, pb: 2 }}>
              {/* 分页保持 MUI 默认密度，**不收 `siblingCount`**。
                  收了确实每档都是一行，但第 1 页会从 `1 2 3 4 5 … 1254` 掉成
                  `1 2 3 … 1254` —— 少两个直达页码，账本上就是丢了两个控件。
                  实测默认密度在 320 栏里放得下：第 1 页 270px / 309px 可用；
                  翻到第 600 页那种四位数居中的情况会**折成两行**（高 28 → 56），
                  但它在中段里，滚到底完整可见（承重实测 R6 量过）。
                  两行不好看，但比够不着页码轻。 */}
              <Pagination
                count={totalPages}
                page={page}
                onChange={handlePageChange}
                color="primary"
                shape="rounded"
                size="small"
              />
            </Box>
          )}
        </>
      )}
      actions={(
        <>
          {/* 播放条用共享的 `PlaybackBar` —— 冻结稿这里画的是一排光秃秃的走子键，
              但那是稿子对同一件东西的低保真画法（它标的图标 SkipPrevious /
              NavigateBefore 连实际用的都不是）。直播页和复盘页的动作区都是这一件，
              本轮的题目就是统一；顺带把这一页第五份手写播放控件也收掉了。
              它自带 `@container board-rail (max-width:340px)` 的窄档收缩。 */}
          {hasPreview && (
            <PlaybackBar
              currentMove={previewCurrentMove}
              totalMoves={previewMoves.length}
              onMoveChange={setPreviewCurrentMove}
            />
          )}
          <Box sx={{ p: 2, pt: hasPreview ? 1 : 2 }}>
            <Button
              fullWidth
              variant="contained"
              startIcon={<ScienceIcon />}
              disabled={!selectedAlbum}
              onClick={handleOpenInResearch}
              sx={{ textTransform: 'none', minHeight: 40, borderRadius: '8px' }}
            >
              {t('kifu:open_in_research', '在研究中打开')}
            </Button>
          </Box>
        </>
      )}
    />
  );
}
