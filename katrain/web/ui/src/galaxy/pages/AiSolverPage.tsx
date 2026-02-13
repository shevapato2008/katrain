import { useState, useMemo, useCallback } from 'react';
import { Box } from '@mui/material';
import AiSolverBoard from '../components/ai-solver/AiSolverBoard';
import AiSolverSidebar from '../components/ai-solver/AiSolverSidebar';
import { useAiSolverBoard } from '../hooks/useAiSolverBoard';
import type { AiMoveMarker } from '../components/live/LiveBoard';

const AiSolverPage = () => {
  const board = useAiSolverBoard();
  const [hoveredPV, setHoveredPV] = useState<string[] | null>(null);

  // Parse analysis result into AiMoveMarker array (top 5 moves)
  const parsedMarkers = useMemo((): AiMoveMarker[] | null => {
    if (!board.analysisResult) return null;
    const turnResult = board.analysisResult?.turnInfos?.[0] ?? board.analysisResult;
    const moveInfos = turnResult?.moveInfos;
    if (!moveInfos || !Array.isArray(moveInfos)) return null;

    return moveInfos.slice(0, 5).map((mi: any, idx: number) => ({
      move: mi.move,
      rank: idx + 1,
      visits: mi.visits,
      winrate: mi.winrate,
      score_lead: mi.scoreLead ?? 0,
    }));
  }, [board.analysisResult]);

  // Build PV text from the best move's principal variation
  const pvText = useMemo((): string | null => {
    if (!board.analysisResult) return null;
    const turnResult = board.analysisResult?.turnInfos?.[0] ?? board.analysisResult;
    const moveInfos = turnResult?.moveInfos;
    if (!moveInfos || !Array.isArray(moveInfos) || moveInfos.length === 0) return null;

    const bestPV = moveInfos[0].pv;
    if (!bestPV || !Array.isArray(bestPV) || bestPV.length === 0) return null;

    return bestPV.map((m: string, i: number) => `${i + 1}. ${m}`).join('  ');
  }, [board.analysisResult]);

  // Get the best move's PV for board display
  const bestPVMoves = useMemo((): string[] | null => {
    if (hoveredPV) return hoveredPV;
    if (!board.analysisResult) return null;
    const turnResult = board.analysisResult?.turnInfos?.[0] ?? board.analysisResult;
    const moveInfos = turnResult?.moveInfos;
    if (!moveInfos || !Array.isArray(moveInfos) || moveInfos.length === 0) return null;
    return moveInfos[0].pv ?? null;
  }, [board.analysisResult, hoveredPV]);

  const handleRegionChange = useCallback((region: { x1: number; y1: number; x2: number; y2: number }) => {
    board.setRegion(region);
  }, [board]);

  return (
    <Box sx={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Board area */}
      <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', bgcolor: '#0f0f0f' }}>
        <Box sx={{ flexGrow: 1, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
          <AiSolverBoard
            stones={board.stones}
            boardSize={board.boardSize}
            activeTool={board.activeTool}
            region={board.region}
            effectiveRegion={board.getEffectiveRegion()}
            onIntersectionClick={board.handleIntersectionClick}
            onRegionChange={handleRegionChange}
            aiMarkers={parsedMarkers}
            pvMoves={bestPVMoves}
            showAiMarkers={!!parsedMarkers && !hoveredPV}
          />
        </Box>
      </Box>

      {/* Sidebar */}
      <AiSolverSidebar
        board={board}
        onRegionClear={board.clearRegion}
        parsedMarkers={parsedMarkers}
        pvText={pvText}
        onHoverPV={setHoveredPV}
      />
    </Box>
  );
};

export default AiSolverPage;
