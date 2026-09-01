import { useEffect, useState, useMemo, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import CircularProgress from '@mui/material/CircularProgress';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import IconButton from '@mui/material/IconButton';
import Slider from '@mui/material/Slider';
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import EditIcon from '@mui/icons-material/Edit';
import RecordVoiceOverIcon from '@mui/icons-material/RecordVoiceOver';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import RuleIcon from '@mui/icons-material/Rule';
import Chip from '@mui/material/Chip';
import useMediaQuery from '@mui/material/useMediaQuery';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import CloseIcon from '@mui/icons-material/Close';
import SaveIcon from '@mui/icons-material/Save';
import { TutorialAPI } from '../../api/tutorialApi';
import BoardPageShell from '../../components/board/BoardPageShell';
import ModulePlate from '../../components/layout/ModulePlate';
import ToolGridButton from '../../components/board/ToolGridButton';
import SGFBoard from '../../components/tutorials/SGFBoard';
import BoardEditToolbar from '../../components/tutorials/BoardEditToolbar';
import RecognitionDebugPanel from '../../components/tutorials/RecognitionDebugPanel';
import AudioPlayer from '../../components/tutorials/AudioPlayer';
import { useBoardEditor } from '../../hooks/useBoardEditor';
import { useAuth } from '../../../context/AuthContext';
import type { TutorialSectionDetail, TutorialFigure, BoardPayload } from '../../../types/tutorial';

export default function TutorialFigurePage() {
  const { sectionId } = useParams<{ sectionId: string }>();
  const { token } = useAuth();
  const [section, setSection] = useState<TutorialSectionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentFigureIndex, setCurrentFigureIndex] = useState(0);
  const [moveStep, setMoveStep] = useState<number | null>(null);
  const [isEditingNarration, setIsEditingNarration] = useState(false);
  const [editedNarration, setEditedNarration] = useState('');
  const [isGeneratingAudio, setIsGeneratingAudio] = useState(false);
  /* 原书页对照层。审图的人必须让原书页图和识别出的棋盘**并排**才能核对，
     所以它不进右栏，而是做成 stage 里的一层，占左侧 34%，可一键收起把整块还给棋盘。
     竖屏放不下并排（410 的 stage 让出 34% 只剩 270 的棋盘），那一档改成降到右栏第一节。 */
  const [compareOpen, setCompareOpen] = useState(true);
  const isWide = useMediaQuery('(min-width:900px)');
  const showCompare = isWide && compareOpen;

  const currentFigure = section?.figures[currentFigureIndex] ?? null;

  const updateCurrentFigure = useCallback((updater: (figure: TutorialFigure) => TutorialFigure) => {
    setSection(prev => {
      if (!prev || !prev.figures[currentFigureIndex]) return prev;
      const figures = [...prev.figures];
      figures[currentFigureIndex] = updater(figures[currentFigureIndex]);
      return { ...prev, figures };
    });
  }, [currentFigureIndex]);

  const handleServerSave = useCallback(async (payload: BoardPayload) => {
    if (!currentFigure) return;
    try {
      const updated = await TutorialAPI.saveBoardPayload(
        currentFigure.id, payload, token ?? undefined, currentFigure.updated_at ?? undefined
      );
      updateCurrentFigure(figure => ({
        ...figure,
        board_payload: updated.board_payload,
        updated_at: updated.updated_at,
      }));
    } catch (err) {
      alert(err instanceof Error ? err.message : '保存失败，请重试');
    }
  }, [currentFigure, token, updateCurrentFigure]);

  const editor = useBoardEditor(currentFigure?.board_payload ?? null, handleServerSave);

  // Sync editor payload when figure changes
  useEffect(() => {
    if (currentFigure?.board_payload) {
      editor.setPayloadFromServer(currentFigure.board_payload);
    }
  }, [currentFigureIndex, currentFigure?.id]);

  useEffect(() => {
    setEditedNarration(currentFigure?.narration ?? '');
    setIsEditingNarration(false);
    setIsGeneratingAudio(false);
  }, [currentFigure?.id, currentFigure?.narration]);

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

  const handleLogicCheck = useCallback(() => {
    if (!displayPayload) return;
    const { labels, stones } = displayPayload;
    if (!labels || Object.keys(labels).length === 0) {
      alert('没有编号数据');
      return;
    }

    // Build set of B/W coords for quick lookup
    const blackSet = new Set(stones.B.map(([c, r]) => `${c},${r}`));
    const whiteSet = new Set(stones.W.map(([c, r]) => `${c},${r}`));

    // Collect numeric labels with their color
    const moves: { num: number; color: 'B' | 'W' | null; coord: string }[] = [];
    for (const [coord, val] of Object.entries(labels)) {
      const n = parseInt(val, 10);
      if (isNaN(n)) continue;
      const color = blackSet.has(coord) ? 'B' as const : whiteSet.has(coord) ? 'W' as const : null;
      moves.push({ num: n, color, coord });
    }

    if (moves.length === 0) {
      alert('没有数字编号');
      return;
    }

    const errors: string[] = [];

    // Check duplicates
    const numCounts = new Map<number, number>();
    for (const m of moves) {
      numCounts.set(m.num, (numCounts.get(m.num) ?? 0) + 1);
    }
    const duplicates = [...numCounts.entries()].filter(([, c]) => c > 1).map(([n]) => n);
    if (duplicates.length > 0) {
      errors.push(`重复编号: ${duplicates.join(', ')}`);
    }

    // Sort by number
    moves.sort((a, b) => a.num - b.num);

    // Check consecutive
    const minNum = moves[0].num;
    const gaps: number[] = [];
    for (let i = 0; i < moves.length; i++) {
      if (moves[i].num !== minNum + i) {
        // Find actual gap
        const expected = minNum + i;
        if (!moves.some(m => m.num === expected)) {
          gaps.push(expected);
        }
      }
    }
    // More robust: check full range
    const maxNum = moves[moves.length - 1].num;
    const existingNums = new Set(moves.map(m => m.num));
    const missingNums: number[] = [];
    for (let n = minNum; n <= maxNum; n++) {
      if (!existingNums.has(n)) missingNums.push(n);
    }
    if (missingNums.length > 0) {
      errors.push(`缺少编号: ${missingNums.join(', ')}`);
    }

    // Check color exists for each numbered stone
    const noColor = moves.filter(m => m.color === null);
    if (noColor.length > 0) {
      errors.push(`编号 ${noColor.map(m => m.num).join(', ')} 没有对应棋子`);
    }

    // Check alternating colors (only for stones that have color)
    const colored = moves.filter(m => m.color !== null);
    if (colored.length >= 2) {
      const badPairs: string[] = [];
      for (let i = 1; i < colored.length; i++) {
        if (colored[i].color === colored[i - 1].color) {
          badPairs.push(`${colored[i - 1].num}(${colored[i - 1].color === 'B' ? '黑' : '白'})→${colored[i].num}(${colored[i].color === 'B' ? '黑' : '白'})`);
        }
      }
      if (badPairs.length > 0) {
        errors.push(`颜色未交替: ${badPairs.join(', ')}`);
      }
    }

    if (errors.length === 0) {
      alert(`✓ 逻辑检查通过 (${moves.length}手, ${minNum}-${maxNum})`);
    } else {
      alert(`✗ 逻辑检查发现问题:\n\n${errors.join('\n')}`);
    }
  }, [displayPayload]);

  const handleVerify = useCallback(async () => {
    if (!currentFigure) return;
    try {
      const updated = await TutorialAPI.verifyFigure(currentFigure.id, token ?? undefined);
      updateCurrentFigure(figure => ({
        ...figure,
        recognition_debug: updated.recognition_debug,
      }));
    } catch (err) {
      alert(err instanceof Error ? err.message : '审核失败');
    }
  }, [currentFigure, token, updateCurrentFigure]);

  const handleGenerateAudio = useCallback(async () => {
    if (!currentFigure) return;
    setIsGeneratingAudio(true);
    try {
      const updated = await TutorialAPI.generateFigureAudio(
        currentFigure.id,
        editedNarration,
        token ?? undefined,
      );
      updateCurrentFigure(() => updated);
      setIsEditingNarration(false);
    } catch (err) {
      alert(err instanceof Error ? err.message : '生成语音失败');
    } finally {
      setIsGeneratingAudio(false);
    }
  }, [currentFigure, editedNarration, token, updateCurrentFigure]);

  const handleSaveNarration = useCallback(async () => {
    if (!currentFigure) return;
    try {
      const updated = await TutorialAPI.saveNarration(
        currentFigure.id,
        editedNarration,
        currentFigure.audio_asset ?? null,
        token ?? undefined,
      );
      updateCurrentFigure(() => updated);
      setIsEditingNarration(false);
    } catch (err) {
      alert(err instanceof Error ? err.message : '保存讲解失败');
    }
  }, [currentFigure, editedNarration, token, updateCurrentFigure]);

  const handlePrev = () => setCurrentFigureIndex(i => Math.max(0, i - 1));
  const handleNext = () => {
    if (!section) return;
    setCurrentFigureIndex(i => Math.min(section.figures.length - 1, i + 1));
  };

  if (loading) return <Box display="flex" justifyContent="center" p={4}><CircularProgress /></Box>;
  if (error) return <Box p={3}><Alert severity="error">{error} <Button onClick={load}>重试</Button></Alert></Box>;
  if (!section) return <Box p={3}><Typography>小节不存在</Typography></Box>;
  if (section.figures.length === 0) return <Box p={3}><Typography>该小节暂无变化图</Typography></Box>;

  const SECTION = { py: 2, borderBottom: '1px solid', borderColor: 'divider' } as const;
  const hasBoard = Boolean(displayPayload);

  const pageImage = currentFigure?.page_image_path ? (
    <Box
      component="img"
      src={TutorialAPI.assetUrl(currentFigure.page_image_path)}
      alt={`原书第 ${currentFigure.page} 页`}
      sx={{ width: '100%', display: 'block', borderRadius: 1, border: '1px solid', borderColor: 'divider' }}
    />
  ) : (
    <Typography variant="caption" color="text.secondary">该图没有原书页截图</Typography>
  );

  const boardNode = (
    <Box sx={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}>
      {showCompare ? (
        <Box
          data-testid="source-pane"
          sx={{
            position: 'absolute', left: 0, top: 0, bottom: 0, width: '34%', minWidth: 180, zIndex: 5,
            bgcolor: 'background.paper', borderRight: '1px solid', borderColor: 'divider',
            display: 'flex', flexDirection: 'column',
          }}
        >
          <Box sx={{ flex: 'none', display: 'flex', alignItems: 'center', justifyContent: 'space-between', px: 1.25, py: 0.75, borderBottom: '1px solid', borderColor: 'divider' }}>
            <Typography variant="caption" color="text.secondary">原书页</Typography>
            <IconButton size="small" aria-label="收起原书页" onClick={() => setCompareOpen(false)}>
              <ChevronLeftIcon fontSize="small" />
            </IconButton>
          </Box>
          {/* 这一层自己滚 —— 原书页是竖长的扫描图（实测版心 ~1500×2200），
              34% 宽下装不进一屏。它不在右栏的滚动段里，两条滚动条互不干扰。 */}
          <Box sx={{ flex: 1, minHeight: 0, overflowY: 'auto', p: 1.25 }}>
            {pageImage}
            {currentFigure?.book_text && (
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1, whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>
                {currentFigure.book_text}
              </Typography>
            )}
          </Box>
        </Box>
      ) : isWide && (
        <IconButton
          size="small"
          aria-label="展开原书页"
          onClick={() => setCompareOpen(true)}
          sx={{ position: 'absolute', left: 8, top: 8, zIndex: 6, bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider' }}
        >
          <ChevronRightIcon fontSize="small" />
        </IconButton>
      )}
      <Box sx={{ position: 'absolute', inset: 0, left: showCompare ? '34%' : 0, display: 'grid', placeItems: 'center', p: 1, minWidth: 0, minHeight: 0 }}>
        {hasBoard ? (
          <SGFBoard
            payload={editor.isEditing ? editor.payload : displayPayload!}
            maxMoveStep={editor.isEditing ? undefined : (moveStep ?? undefined)}
            showFullBoard={editor.isEditing}
            onClick={editor.isEditing ? editor.handleClick : undefined}
            /* 变化图只截棋盘一角，SGFBoard 按 viewport 出图，**不一定是方的**
               （第 3 节实测 379×703）。所以两个方向都要限，光给 maxWidth 会让竖长的图
               在高度上溢出 stage。 */
            style={{ maxWidth: '100%', maxHeight: '100%', width: 'auto', height: 'auto' }}
          />
        ) : (
          <Typography color="text.secondary">暂无棋盘数据</Typography>
        )}
      </Box>
    </Box>
  );

  const initEmptyBoard = async () => {
    await handleServerSave({ size: 19, stones: { B: [], W: [] }, labels: {}, letters: {}, shapes: {}, highlights: [] });
  };

  return (
    <BoardPageShell
      board={boardNode}
      modulePlate={(
        <ModulePlate
          title={`${section.section_number}. ${section.title}`}
          subtitle={`${currentFigure?.figure_label ?? ''} · ${currentFigureIndex + 1} / ${section.figures.length}`}
          status={<Chip size="small" color={editor.isEditing ? 'warning' : 'default'} variant={editor.isEditing ? 'filled' : 'outlined'} label={editor.isEditing ? '编辑中' : '只读'} />}
          backTo={section.chapter_id ? `/galaxy/tutorials/book/${section.chapter_id}` : '/galaxy/tutorials'}
          backLabel="教程"
        />
      )}
      railBody={(
        <>
          {/* 翻图 + 对照层开关 */}
          <Box sx={{ ...SECTION, pt: 1.5 }}>
            <Box display="flex" alignItems="center" justifyContent="space-between">
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
            {isWide && (
              <Box sx={{ display: 'grid', gridTemplateColumns: '1fr', gap: '6px', mt: 1.25 }}>
                <ToolGridButton
                  icon={<MenuBookIcon />}
                  label="对照原书页"
                  toggle
                  active={compareOpen}
                  onClick={() => setCompareOpen(v => !v)}
                />
              </Box>
            )}
          </Box>

          {/* 竖屏没有对照层，原书页降到这里 */}
          {!isWide && (
            <Box sx={SECTION}>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>原书页</Typography>
              {pageImage}
              {currentFigure?.book_text && (
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1, whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>
                  {currentFigure.book_text}
                </Typography>
              )}
            </Box>
          )}

          {currentFigure?.page_context_text && (
            <Box sx={SECTION}>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>原书正文</Typography>
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', color: 'text.secondary', lineHeight: 1.8 }}>
                {currentFigure.page_context_text}
              </Typography>
            </Box>
          )}

          {hasBoard && (
            <Box sx={SECTION}>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                {editor.isEditing ? '编辑棋盘' : '手数'}
              </Typography>
              {editor.isEditing ? (
                <BoardEditToolbar
                  activeTool={editor.activeTool}
                  stoneMode={editor.stoneMode}
                  numbering={editor.numbering}
                  nextMoveNumber={editor.nextMoveNumber}
                  nextLetter={editor.nextLetter}
                  selectedShape={editor.selectedShape}
                  canUndo={editor.canUndo}
                  onToolChange={editor.setActiveTool}
                  onStoneModeChange={editor.setStoneMode}
                  onNumberingChange={editor.setNumbering}
                  onNextMoveNumberChange={editor.setNextMoveNumber}
                  onNextLetterChange={editor.setNextLetter}
                  onShapeChange={editor.setSelectedShape}
                  onUndo={editor.undo}
                  onClearAll={editor.clearAll}
                />
              ) : maxMoveNumber > 0 ? (
                <>
                  <Typography variant="caption" color="text.secondary">当前 {moveStep ?? maxMoveNumber} / {maxMoveNumber}</Typography>
                  {/* 滑轨自己要留出横向余量：滑块拉到最右端时，它和它的水波纹会越过轨道
                      末端约 13px。竖屏下右栏是满宽、滚动段又不裁横向，这点溢出会一路顶到
                      右栏上，实测让整条右栏横向可滚 5px。 */}
                  <Box>
                    <Slider
                      value={moveStep ?? maxMoveNumber}
                      onChange={(_, v) => setMoveStep(v as number)}
                      min={0}
                      max={maxMoveNumber}
                      step={1}
                      size="small"
                      aria-label="手数"
                    />
                  </Box>
                </>
              ) : (
                <Typography variant="body2" color="text.secondary">这张图没有编号手数</Typography>
              )}
            </Box>
          )}

          {/* 语音讲解 */}
          <Box sx={SECTION}>
            <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
              <Typography variant="caption" color="text.secondary">语音讲解</Typography>
              <Button
                size="small"
                variant="outlined"
                startIcon={<EditIcon />}
                onClick={() => setIsEditingNarration(v => !v)}
                aria-label={isEditingNarration ? '收起编辑' : '编辑讲解'}
              >
                {isEditingNarration ? '收起编辑' : '编辑讲解'}
              </Button>
            </Box>

            {isEditingNarration ? (
              <Box>
                <TextField
                  label="讲解文本"
                  multiline
                  fullWidth
                  minRows={5}
                  value={editedNarration}
                  onChange={(e) => setEditedNarration(e.target.value)}
                />
                <Box display="flex" flexDirection="column" gap={1} mt={1.5}>
                  <Button variant="contained" startIcon={<RecordVoiceOverIcon />} onClick={handleGenerateAudio} disabled={isGeneratingAudio} aria-label="生成语音并保存">
                    {isGeneratingAudio ? '生成中...' : '生成语音并保存'}
                  </Button>
                  <Box display="flex" gap={1}>
                    <Button fullWidth variant="outlined" onClick={handleSaveNarration} aria-label="保存文字">保存文字</Button>
                    <Button fullWidth variant="text" onClick={() => { setEditedNarration(currentFigure?.narration ?? ''); setIsEditingNarration(false); }}>取消</Button>
                  </Box>
                </Box>
              </Box>
            ) : currentFigure?.narration ? (
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', mb: 2, lineHeight: 1.8 }}>
                {currentFigure.narration}
              </Typography>
            ) : (
              <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic', mb: 2 }}>
                暂无讲解文本。点击“编辑讲解”后可直接填写并生成语音。
              </Typography>
            )}

            <AudioPlayer src={currentFigure?.audio_asset ? TutorialAPI.assetUrl(currentFigure.audio_asset) : null} />
            {currentFigure?.video_asset && (
              <Box sx={{ mt: 2 }}>
                <video
                  controls
                  preload="none"
                  poster={TutorialAPI.assetUrl(currentFigure.video_asset.replace('.mp4', '.jpg'))}
                  width="100%"
                  style={{ borderRadius: 8, display: 'block' }}
                  src={TutorialAPI.assetUrl(currentFigure.video_asset)}
                  onError={(e) => { (e.target as HTMLVideoElement).style.display = 'none'; }}
                />
                {currentFigure.video_duration_ms && (
                  <Typography variant="caption" color="text.secondary">
                    {Math.floor(currentFigure.video_duration_ms / 60000)}:
                    {String(Math.floor((currentFigure.video_duration_ms % 60000) / 1000)).padStart(2, '0')}
                  </Typography>
                )}
              </Box>
            )}
          </Box>

          {currentFigure?.recognition_debug && (
            <Box sx={{ p: 2 }}>
              <RecognitionDebugPanel debug={currentFigure.recognition_debug} />
            </Box>
          )}
        </>
      )}
      actions={(
        <Box sx={{ py: 1.5, borderTop: '1px solid', borderColor: 'divider' }}>
          {!hasBoard ? (
            <Button fullWidth variant="contained" onClick={initEmptyBoard}>初始化空棋盘</Button>
          ) : editor.isEditing ? (
            <Box display="flex" gap={1}>
              <Button variant="outlined" color="inherit" startIcon={<CloseIcon />} onClick={editor.cancelEdit} aria-label="取消">取消</Button>
              <Button fullWidth variant="contained" startIcon={<SaveIcon />} onClick={editor.save} aria-label="保存">保存</Button>
            </Box>
          ) : (
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1 }}>
              <Button variant="outlined" startIcon={<EditIcon />} onClick={editor.enterEdit} aria-label="编辑">编辑</Button>
              <Button variant="outlined" startIcon={<RuleIcon />} onClick={handleLogicCheck} aria-label="逻辑检查">逻辑检查</Button>
              <Box sx={{ gridColumn: '1 / -1' }}>
                <Button
                  fullWidth
                  variant={isVerified ? 'contained' : 'outlined'}
                  color={isVerified ? 'success' : 'primary'}
                  startIcon={isVerified ? <CheckCircleIcon /> : <CheckCircleOutlineIcon />}
                  onClick={handleVerify}
                  disabled={isVerified}
                  aria-label="确认审核"
                >
                  {isVerified ? '已审核' : '确认审核'}
                </Button>
              </Box>
            </Box>
          )}
        </Box>
      )}
    />
  );
}
