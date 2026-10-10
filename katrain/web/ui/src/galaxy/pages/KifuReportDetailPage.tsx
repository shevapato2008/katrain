import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Alert, Box, CircularProgress, Typography } from '@mui/material';

import { KifuAPI } from '../../api/kifuApi';
import type { KifuAlbumDetail } from '../../types/kifu';
import { useKifuAnalysis } from '../../features/kifu/useKifuAnalysis';
import { kifuAnalysisParametersValid, kifuAnalysisStatus } from '../../features/kifu/kifuAnalysisStatus';
import { sgfToMoves } from '../../utils/sgfSerializer';
import { reportPlayerToMove } from '../../utils/reportPlayer';
import { useSound } from '../../hooks/useSound';
import { useReplayStoneSound } from '../../hooks/useReplayStoneSound';
import { useTranslation } from '../../hooks/useTranslation';
import LiveBoard, { type AiMoveMarker } from '../../components/live/LiveBoard';
import AiAnalysis from '../../components/live/AiAnalysis';
import PlaybackBar from '../../components/live/PlaybackBar';
import TrendChart from '../../components/live/TrendChart';
import BoardPageShell from '../components/board/BoardPageShell';
import ReportMetaPanel from '../components/report/ReportMetaPanel';
import ReportAnalysisLayout from '../components/report/ReportAnalysisLayout';
import { useBoardCoordinates } from '../components/board/useBoardCoordinates';
import LiveMatchDisplayControls from './live/LiveMatchDisplayControls';
import ReplayBoard3D from '../components/board/ReplayBoard3D';

const BACK_TO = '/galaxy/kifu';

export default function KifuReportDetailPage({ replayOnly = false }: { replayOnly?: boolean }) {
  const { albumId } = useParams<{ albumId: string }>();
  const id = albumId && /^\d+$/.test(albumId) ? Number(albumId) : null;
  const { t, lang } = useTranslation();
  const [loaded, setLoaded] = useState<{ id: number; lang: string; album: KifuAlbumDetail } | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [selectedPosition, setSelectedPosition] = useState<{ id: number; move: number } | null>(null);
  const [boardEdge, setBoardEdge] = useState(0);
  const [showAiMarkers, setShowAiMarkers] = useState(true);
  const [showMoveNumbers, setShowMoveNumbers] = useState(false);
  const [view3d, setView3d] = useState(false);
  const [showTerritory, setShowTerritory] = useState(false);
  const [tryMoveMode, setTryMoveMode] = useState(false);
  const [tryMoves, setTryMoves] = useState<string[]>([]);
  const { play: playSound } = useSound();
  const handleTryMove = (move: string) => {
    setTryMoves((previous) => [...previous, move]);
    playSound('stone');
  };
  const [pvMoves, setPvMoves] = useState<string[] | null>(null);
  const coordinates = useBoardCoordinates(boardEdge);
  const { detail, analysisByMove, error: analysisError } = useKifuAnalysis(replayOnly ? null : id);
  const analysisParameters = detail && kifuAnalysisParametersValid(detail) ? detail.analysis_parameters : null;
  const frontier = Math.max(0, ...Object.keys(analysisByMove).map(Number));
  const currentMove = selectedPosition?.id === id ? selectedPosition.move : replayOnly && loaded?.id === id ? loaded.album.move_count : frontier;
  const setCurrentMove = (move: number) => { if (id !== null) setSelectedPosition({ id, move }); };

  useEffect(() => {
    if (id === null) return;
    let cancelled = false;
    KifuAPI.getAlbum(id, lang).then((album) => {
      if (!cancelled) { setLoaded({ id, lang, album }); setLoadError(false); }
    }).catch(() => { if (!cancelled) setLoadError(true); });
    return () => { cancelled = true; };
  }, [id, lang]);

  const album = loaded?.id === id && loaded.lang === lang ? loaded.album : null;
  const parsed = useMemo(() => album?.sgf_content ? sgfToMoves(album.sgf_content) : null, [album]);
  const totalMoves = parsed ? Math.max(0, parsed.moves.length - (parsed.setupCount ?? 0)) : 0;
  const at = Math.min(currentMove, totalMoves);
  const boardCursor = at + (parsed?.setupCount ?? 0);
  useReplayStoneSound({ identity: id, cursor: at, move: parsed?.moves[boardCursor - 1],
    ready: !!parsed && (replayOnly || !!detail), boardSize: parsed?.metadata.boardSize || album?.board_size || 19, selected: selectedPosition?.id === id });
  const playerToMove = reportPlayerToMove(parsed?.stoneColors, boardCursor, parsed?.setupCount);
  const analysis = analysisByMove[at] ?? null;
  const markers = useMemo((): AiMoveMarker[] | null => {
    if (!analysis?.top_moves?.length || !showAiMarkers) return null;
    return analysis.top_moves.slice(0, 5).map((move, rank) => ({
      move: move.move, rank: rank + 1, visits: move.visits,
      winrate: playerToMove === 'B' ? move.winrate ?? 0 : 1 - (move.winrate ?? 0), score_lead: playerToMove === 'B' ? move.score_lead ?? 0 : -(move.score_lead ?? 0),
    }));
  }, [analysis, showAiMarkers, playerToMove]);
  const status = kifuAnalysisStatus(detail, analysisError, t);

  return (
    <BoardPageShell
      fixedRail
      onBoardSizeChange={setBoardEdge}
      board={parsed ? (
        view3d ? <ReplayBoard3D moves={parsed.moves} stoneColors={parsed.stoneColors} currentMove={boardCursor} boardSize={parsed.metadata.boardSize || album?.board_size || 19} handicapCount={parsed.setupCount ?? 0} showCoordinates={coordinates.visible} showMoveNumbers={showMoveNumbers} showAiMarkers={showAiMarkers} aiMarkers={markers} showTerritory={showTerritory} ownership={showTerritory ? analysis?.ownership ?? null : null} tryMoves={tryMoveMode ? tryMoves : undefined} onTryMove={tryMoveMode ? handleTryMove : undefined} /> : <LiveBoard
          moves={parsed.moves} stoneColors={parsed.stoneColors}
          currentMove={boardCursor} boardSize={parsed.metadata.boardSize || album?.board_size || 19}
          nextColor={playerToMove}
          pvMoves={pvMoves} aiMarkers={markers} showAiMarkers={showAiMarkers}
          aiMarkerLimit={5}
          showMoveNumbers={showMoveNumbers} showTerritory={showTerritory}
          showCoordinates={coordinates.visible} ownership={showTerritory ? analysis?.ownership ?? null : null}
          tryMoves={tryMoveMode ? tryMoves : undefined}
          onTryMove={tryMoveMode ? handleTryMove : undefined}
          minimumCanvasSize={0} minContainerHeight={0}
        />
      ) : loadError || id === null ? <Alert severity="error">{t('kifu:report_load_failed', '职业棋局暂时无法读取')}</Alert> : <CircularProgress />}
      modulePlate={null}
      railBody={album ? (
        <ReportAnalysisLayout
          identity={<ReportMetaPanel
            professional
            statusLabel={replayOnly ? undefined : status}
            analysisParameters={analysisParameters}
            backTo={BACK_TO}
            game={{
              game_date: album.date_played, source: 'kifu_library', event: album.display_event ?? album.event,
              title: null, round_name: album.display_round_name ?? album.round_name,
              result: album.result, rules: album.rules,
              player_black: album.display_player_black ?? album.player_black,
              player_white: album.display_player_white ?? album.player_white,
              black_rank: album.display_black_rank ?? album.black_rank,
              white_rank: album.display_white_rank ?? album.white_rank, komi: album.komi,
            }}
            task={replayOnly ? null : { status: detail?.status ?? 'loading', report_type: 'deep', requested_visits: detail?.requested_visits }}
            currentMove={at} currentAnalysis={analysis}
          />}
          recommendations={replayOnly ? <Typography sx={{ p: 1 }}>{t('kifu:replay', '逐手回放')} · {totalMoves} {t('kifu:moves_unit', '手')}</Typography> : <>
            {detail?.status !== 'completed' && <Box sx={{ px: 1, py: 0.5 }}><Typography sx={{ fontSize: 18 }}>{status}</Typography>{(detail?.status === 'failed' || detail?.status === 'rules_unresolved') && <Alert severity="error">{detail.parameter_error?.message || detail.error_message || status}</Alert>}</Box>}
            {analysis ? <AiAnalysis currentMove={at} analysis={analysisByMove} onMoveHover={setPvMoves} topN={5} reportMode playerToMove={playerToMove} actualMove={parsed?.moves[boardCursor]} /> : <Alert severity="info">{detail?.status === 'running' ? t('kifu:report_no_position', '当前局面暂无分析结果') : status}</Alert>}
          </>}
          controls={<LiveMatchDisplayControls
            reportMode
            tryMoveMode={tryMoveMode} showTerritory={showTerritory} showMoveNumbers={showMoveNumbers}
            showAiMarkers={showAiMarkers} showCoordinates={coordinates.visible}
            view3d={view3d}
            ownershipAvailable={analysis?.ownership != null} tryMoves={tryMoves}
            onTryMoveToggle={() => { setTryMoveMode((value) => !value); setTryMoves([]); }}
            onTerritoryToggle={() => setShowTerritory((value) => !value)}
            onMoveNumbersToggle={() => setShowMoveNumbers((value) => !value)}
            onAiMarkersToggle={() => setShowAiMarkers((value) => !value)}
            onCoordinatesToggle={coordinates.toggle} on3dToggle={() => setView3d((value) => !value)} onClearTryMoves={() => setTryMoves([])}
          />}
          analysis={replayOnly || !Object.keys(analysisByMove).length ? null : <TrendChart reportMode analysis={analysisByMove} totalMoves={detail?.status === 'completed' ? totalMoves : Math.max(...Object.keys(analysisByMove).map(Number), 0)} currentMove={at} onMoveClick={setCurrentMove} />}
          navigation={<PlaybackBar inline currentMove={at} totalMoves={totalMoves} onMoveChange={setCurrentMove} />}
        />
      ) : null}
      actions={null}
    />
  );
}
