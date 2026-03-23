import { useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import CircularProgress from '@mui/material/CircularProgress';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import IconButton from '@mui/material/IconButton';
import Slider from '@mui/material/Slider';
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import EditIcon from '@mui/icons-material/Edit';
import { TutorialAPI } from '../../api/tutorialApi';
import SGFBoard from '../../components/tutorials/SGFBoard';
import type { TutorialSectionDetail, TutorialFigure, BoardPayload } from '../../types/tutorial';

export default function TutorialFigurePage() {
  const { sectionId } = useParams<{ sectionId: string }>();
  const navigate = useNavigate();
  const [section, setSection] = useState<TutorialSectionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentFigureIndex, setCurrentFigureIndex] = useState(0);
  const [isEditing, setIsEditing] = useState(false);
  const [moveStep, setMoveStep] = useState<number | null>(null);

  const load = () => {
    if (!sectionId) return;
    setLoading(true);
    setError(null);
    TutorialAPI.getSection(Number(sectionId))
      .then(s => {
        setSection(s);
        setCurrentFigureIndex(0);
      })
      .catch(e => setError(e instanceof Error ? e.message : '加载失败'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [sectionId]);

  const currentFigure: TutorialFigure | null = section?.figures[currentFigureIndex] ?? null;

  // Compute max move number from labels
  const maxMoveNumber = useMemo(() => {
    if (!currentFigure?.board_payload?.labels) return 0;
    let max = 0;
    for (const val of Object.values(currentFigure.board_payload.labels)) {
      const n = parseInt(val, 10);
      if (!isNaN(n) && n > max) max = n;
    }
    return max;
  }, [currentFigure]);

  // Reset move step when figure changes
  useEffect(() => {
    setMoveStep(maxMoveNumber > 0 ? maxMoveNumber : null);
  }, [currentFigureIndex, maxMoveNumber]);

  const handlePrev = () => setCurrentFigureIndex(i => Math.max(0, i - 1));
  const handleNext = () => {
    if (!section) return;
    setCurrentFigureIndex(i => Math.min(section.figures.length - 1, i + 1));
  };

  const handleSave = async (payload: BoardPayload) => {
    if (!currentFigure) return;
    try {
      const updated = await TutorialAPI.saveBoardPayload(currentFigure.id, payload);
      setSection(prev => {
        if (!prev) return prev;
        const figures = [...prev.figures];
        figures[currentFigureIndex] = { ...figures[currentFigureIndex], board_payload: updated.board_payload };
        return { ...prev, figures };
      });
      setIsEditing(false);
    } catch (err) {
      alert(err instanceof Error ? err.message : '保存失败，请重试');
    }
  };

  if (loading) return <Box display="flex" justifyContent="center" p={4}><CircularProgress /></Box>;
  if (error) return <Box p={3}><Alert severity="error">{error} <Button onClick={load}>重试</Button></Alert></Box>;
  if (!section) return <Box p={3}><Typography>小节不存在</Typography></Box>;
  if (section.figures.length === 0) return <Box p={3}><Typography>该小节暂无变化图</Typography></Box>;

  return (
    <Box p={2}>
      <Button size="small" onClick={() => navigate(-1)} sx={{ mb: 1 }}>← 返回</Button>
      <Typography variant="h6" gutterBottom>
        {section.section_number}. {section.title}
      </Typography>

      {/* Figure navigation bar */}
      <Box display="flex" alignItems="center" gap={1} mb={2}>
        <IconButton onClick={handlePrev} disabled={currentFigureIndex === 0} aria-label="上一图">
          <NavigateBeforeIcon />
        </IconButton>
        <Typography variant="body2">
          {currentFigure?.figure_label} ({currentFigureIndex + 1} / {section.figures.length})
        </Typography>
        <IconButton onClick={handleNext} disabled={currentFigureIndex === section.figures.length - 1} aria-label="下一图">
          <NavigateNextIcon />
        </IconButton>
      </Box>

      {/* Two-column layout */}
      <Box display="flex" gap={3} flexWrap="wrap">
        {/* Left panel: page screenshot + book text */}
        <Box sx={{ flex: '1 1 400px', maxWidth: 600 }}>
          {currentFigure?.page_image_path && (
            <Box
              component="img"
              src={TutorialAPI.assetUrl(currentFigure.page_image_path)}
              alt={`page ${currentFigure.page}`}
              sx={{ width: '100%', borderRadius: 1, border: '1px solid #ddd', mb: 2 }}
            />
          )}
          {currentFigure?.book_text && (
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', color: 'text.secondary' }}>
              {currentFigure.book_text}
            </Typography>
          )}
          {currentFigure?.page_context_text && (
            <Typography variant="body2" sx={{ mt: 1, whiteSpace: 'pre-wrap', color: 'text.secondary', fontStyle: 'italic' }}>
              {currentFigure.page_context_text}
            </Typography>
          )}
        </Box>

        {/* Right panel: SGF board + controls */}
        <Box sx={{ flex: '1 1 350px', maxWidth: 500 }}>
          {currentFigure?.board_payload ? (
            <>
              <SGFBoard
                payload={currentFigure.board_payload}
                maxMoveStep={moveStep ?? undefined}
                showFullBoard={isEditing}
              />

              {/* Move-step slider */}
              {maxMoveNumber > 0 && !isEditing && (
                <Box px={1} mt={1}>
                  <Typography variant="caption" color="text.secondary">手数: {moveStep ?? maxMoveNumber}</Typography>
                  <Slider
                    value={moveStep ?? maxMoveNumber}
                    onChange={(_, v) => setMoveStep(v as number)}
                    min={0}
                    max={maxMoveNumber}
                    step={1}
                    size="small"
                  />
                </Box>
              )}

              {/* Edit button */}
              {!isEditing && (
                <Box mt={1}>
                  <Button
                    size="small"
                    variant="outlined"
                    startIcon={<EditIcon />}
                    onClick={() => setIsEditing(true)}
                    aria-label="编辑"
                  >
                    编辑
                  </Button>
                </Box>
              )}

              {/* Edit mode: save/cancel */}
              {isEditing && (
                <Box mt={1} display="flex" gap={1}>
                  <Button
                    size="small"
                    variant="contained"
                    onClick={() => currentFigure.board_payload && handleSave(currentFigure.board_payload)}
                    aria-label="保存"
                  >
                    保存
                  </Button>
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={() => setIsEditing(false)}
                    aria-label="取消"
                  >
                    取消
                  </Button>
                </Box>
              )}
            </>
          ) : (
            <Box p={4} textAlign="center">
              <Typography color="text.secondary">暂无棋盘数据</Typography>
              <Button
                size="small"
                variant="outlined"
                sx={{ mt: 1 }}
                onClick={() => {
                  // Initialize empty board payload
                  const emptyPayload: BoardPayload = {
                    size: 19,
                    stones: { B: [], W: [] },
                    labels: {},
                    letters: {},
                    shapes: {},
                    highlights: [],
                  };
                  handleSave(emptyPayload);
                }}
              >
                初始化空棋盘
              </Button>
            </Box>
          )}

          {/* Narration */}
          {currentFigure?.narration && (
            <Typography variant="body2" sx={{ mt: 2, whiteSpace: 'pre-wrap' }}>
              {currentFigure.narration}
            </Typography>
          )}
        </Box>
      </Box>
    </Box>
  );
}
