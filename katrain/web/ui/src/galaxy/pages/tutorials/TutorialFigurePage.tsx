import { useEffect, useState, useMemo, useCallback } from 'react';
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
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import { TutorialAPI } from '../../api/tutorialApi';
import SGFBoard from '../../components/tutorials/SGFBoard';
import BoardEditToolbar from '../../components/tutorials/BoardEditToolbar';
import RecognitionDebugPanel from '../../components/tutorials/RecognitionDebugPanel';
import AudioPlayer from '../../components/tutorials/AudioPlayer';
import { useBoardEditor } from '../../hooks/useBoardEditor';
import { useAuth } from '../../context/AuthContext';
import type { TutorialSectionDetail, BoardPayload } from '../../../types/tutorial';

export default function TutorialFigurePage() {
  const { sectionId } = useParams<{ sectionId: string }>();
  const navigate = useNavigate();
  const { token } = useAuth();
  const [section, setSection] = useState<TutorialSectionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentFigureIndex, setCurrentFigureIndex] = useState(0);
  const [moveStep, setMoveStep] = useState<number | null>(null);

  const currentFigure = section?.figures[currentFigureIndex] ?? null;

  const handleServerSave = useCallback(async (payload: BoardPayload) => {
    if (!currentFigure) return;
    try {
      const updated = await TutorialAPI.saveBoardPayload(
        currentFigure.id, payload, token ?? undefined, currentFigure.updated_at ?? undefined
      );
      setSection(prev => {
        if (!prev) return prev;
        const figures = [...prev.figures];
        figures[currentFigureIndex] = { ...figures[currentFigureIndex], board_payload: updated.board_payload, updated_at: updated.updated_at };
        return { ...prev, figures };
      });
    } catch (err) {
      alert(err instanceof Error ? err.message : '保存失败，请重试');
    }
  }, [currentFigure, currentFigureIndex, token]);

  const editor = useBoardEditor(currentFigure?.board_payload ?? null, handleServerSave);

  // Sync editor payload when figure changes
  useEffect(() => {
    if (currentFigure?.board_payload) {
      editor.setPayloadFromServer(currentFigure.board_payload);
    }
  }, [currentFigureIndex, currentFigure?.id]);

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

  // Compute max move number from the displayed payload
  const displayPayload = editor.isEditing ? editor.payload : (currentFigure?.board_payload ?? null);
  const maxMoveNumber = useMemo(() => {
    if (!displayPayload?.labels) return 0;
    let max = 0;
    for (const val of Object.values(displayPayload.labels)) {
      const n = parseInt(val, 10);
      if (!isNaN(n) && n > max) max = n;
    }
    return max;
  }, [displayPayload]);

  // Reset move step when figure changes
  useEffect(() => {
    setMoveStep(maxMoveNumber > 0 ? maxMoveNumber : null);
  }, [currentFigureIndex, maxMoveNumber]);

  const isVerified = currentFigure?.recognition_debug?.human_verified === true;

  const handleVerify = useCallback(async () => {
    if (!currentFigure) return;
    try {
      const updated = await TutorialAPI.verifyFigure(currentFigure.id, token ?? undefined);
      setSection(prev => {
        if (!prev) return prev;
        const figures = [...prev.figures];
        figures[currentFigureIndex] = { ...figures[currentFigureIndex], recognition_debug: updated.recognition_debug };
        return { ...prev, figures };
      });
    } catch (err) {
      alert(err instanceof Error ? err.message : '审核失败');
    }
  }, [currentFigure, currentFigureIndex, token]);

  const handlePrev = () => setCurrentFigureIndex(i => Math.max(0, i - 1));
  const handleNext = () => {
    if (!section) return;
    setCurrentFigureIndex(i => Math.min(section.figures.length - 1, i + 1));
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

      {/* Figure navigation */}
      <Box display="flex" alignItems="center" gap={1} mb={2}>
        <IconButton onClick={handlePrev} disabled={currentFigureIndex === 0 || editor.isEditing} aria-label="上一图">
          <NavigateBeforeIcon />
        </IconButton>
        <Typography variant="body2">
          {currentFigure?.figure_label} ({currentFigureIndex + 1} / {section.figures.length})
        </Typography>
        <IconButton onClick={handleNext} disabled={currentFigureIndex === section.figures.length - 1 || editor.isEditing} aria-label="下一图">
          <NavigateNextIcon />
        </IconButton>
      </Box>

      {/* Three-column layout */}
      <Box sx={{
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', md: 'repeat(3, 1fr)' },
        gap: 2,
        maxHeight: 'calc(100vh - 140px)',
      }}>
        {/* Column 1: page screenshot + book text */}
        <Box sx={{ overflowY: 'auto', maxHeight: 'calc(100vh - 140px)', pr: 1 }}>
          <Typography variant="subtitle2" color="text.secondary" gutterBottom>原书内容</Typography>
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

        {/* Column 2: board + controls + debug panel */}
        <Box sx={{ overflowY: 'auto', maxHeight: 'calc(100vh - 140px)', pr: 1 }}>
          <Typography variant="subtitle2" color="text.secondary" gutterBottom>棋盘识别</Typography>
          {displayPayload ? (
            <>
              <SGFBoard
                payload={editor.isEditing ? editor.payload : displayPayload}
                maxMoveStep={editor.isEditing ? undefined : (moveStep ?? undefined)}
                showFullBoard={editor.isEditing}
                onClick={editor.isEditing ? editor.handleClick : undefined}
              />

              {/* Edit toolbar */}
              {editor.isEditing && (
                <BoardEditToolbar
                  activeTool={editor.activeTool}
                  stoneMode={editor.stoneMode}
                  numbering={editor.numbering}
                  nextMoveNumber={editor.nextMoveNumber}
                  selectedShape={editor.selectedShape}
                  canUndo={editor.canUndo}
                  onToolChange={editor.setActiveTool}
                  onStoneModeChange={editor.setStoneMode}
                  onNumberingChange={editor.setNumbering}
                  onNextMoveNumberChange={editor.setNextMoveNumber}
                  onShapeChange={editor.setSelectedShape}
                  onUndo={editor.undo}
                  onSave={editor.save}
                  onCancel={editor.cancelEdit}
                />
              )}

              {/* Move-step slider (read-only mode only) */}
              {maxMoveNumber > 0 && !editor.isEditing && (
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

              {/* Edit + Verify buttons (read-only mode) */}
              {!editor.isEditing && (
                <Box mt={1} display="flex" gap={1}>
                  <Button size="small" variant="outlined" startIcon={<EditIcon />} onClick={editor.enterEdit} aria-label="编辑">
                    编辑
                  </Button>
                  <Button
                    size="small"
                    variant={isVerified ? "contained" : "outlined"}
                    color={isVerified ? "success" : "inherit"}
                    startIcon={isVerified ? <CheckCircleIcon /> : <CheckCircleOutlineIcon />}
                    onClick={handleVerify}
                    disabled={isVerified}
                    aria-label="确认审核"
                  >
                    {isVerified ? "已审核" : "确认审核"}
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
                onClick={async () => {
                  const emptyPayload: BoardPayload = {
                    size: 19, stones: { B: [], W: [] },
                    labels: {}, letters: {}, shapes: {}, highlights: [],
                  };
                  await handleServerSave(emptyPayload);
                }}
              >
                初始化空棋盘
              </Button>
            </Box>
          )}

          {/* Recognition debug panel */}
          {currentFigure?.recognition_debug && (
            <RecognitionDebugPanel debug={currentFigure.recognition_debug} />
          )}
        </Box>

        {/* Column 3: narration + audio */}
        <Box sx={{ overflowY: 'auto', maxHeight: 'calc(100vh - 140px)', pr: 1 }}>
          <Typography variant="subtitle2" color="text.secondary" gutterBottom>语音讲解</Typography>
          {currentFigure?.narration ? (
            <>
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', mb: 2, lineHeight: 1.8 }}>
                {currentFigure.narration}
              </Typography>
              <AudioPlayer
                src={currentFigure.audio_asset ? TutorialAPI.assetUrl(currentFigure.audio_asset) : null}
              />
            </>
          ) : (
            <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
              暂无讲解文本。运行 generate_voice.py 生成。
            </Typography>
          )}
        </Box>
      </Box>
    </Box>
  );
}
