import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { KifuAPI } from '../../api/kifuApi';
import type { KifuAlbumDetail } from '../../types/kifu';
import { useKifuAnalysis } from '../../features/kifu/useKifuAnalysis';
import { kifuDefaultRulesSource, kifuEventRules, kifuRulesLabel } from '../../features/kifu/kifuRules';
import { kifuAnalysisParametersValid, kifuAnalysisStatus } from '../../features/kifu/kifuAnalysisStatus';
import { gradedMoves, isBad } from '../../features/analysis/moveGrade';
import type { WinratePoint } from '../../features/report/reportStats';
import { sgfToMoves } from '../../utils/sgfSerializer';
import { translateResult } from '../../utils/resultTranslation';
import { useSound } from '../../hooks/useSound';
import { useReplayStoneSound } from '../../hooks/useReplayStoneSound';
import { useTranslation } from '../../hooks/useTranslation';
import LiveBoard, { type AiMoveMarker } from '../../components/live/LiveBoard';
import { reportPlayerToMove } from '../../utils/reportPlayer';
import PhysicalBoardButton from '../components/PhysicalBoardButton';
import { ReportAnalysisRail } from '../components/report/ReportAnalysisRail';
import KioskReportPlayback from '../components/report/KioskReportPlayback';
import { colsFor, rowsFor } from '../shell/goBoard';
import { KioskPagebar } from '../shell/KioskPagebar';
import { Icon } from '../shell/icons';

/** Professional archive report, sharing the personal report's board, AI, grade and chart components. */
export default function KifuReportDetailPage() {
  const { kifuId } = useParams<{ kifuId: string }>();
  const id = kifuId && /^\d+$/.test(kifuId) ? Number(kifuId) : null;
  const navigate = useNavigate();
  const { t, lang } = useTranslation();
  const [loaded, setLoaded] = useState<{ id: number; lang: string; album: KifuAlbumDetail } | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [selectedPosition, setSelectedPosition] = useState<{ id: number; move: number } | null>(null);
  const [showCoordinates, setShowCoordinates] = useState(true);
  const [reload, setReload] = useState(0);
  const [variation, setVariation] = useState<{ id: number | null; position: number; move: string } | null>(null);
  const [showAiMarkers, setShowAiMarkers] = useState(true);
  const [showMoveNumbers, setShowMoveNumbers] = useState(true);
  const [showTerritory, setShowTerritory] = useState(false);
  const [tryMoveMode, setTryMoveMode] = useState(false);
  const [tryMoves, setTryMoves] = useState<string[]>([]);
  const { play: playSound } = useSound();
  const handleTryMove = (move: string) => {
    setTryMoves((previous) => [...previous, move]);
    playSound('stone');
  };
  const { detail, analysisByMove, error: analysisError } = useKifuAnalysis(id);
  const analysisParameters = detail && kifuAnalysisParametersValid(detail) ? detail.analysis_parameters : null;
  const defaultRulesSource = kifuDefaultRulesSource(analysisParameters, t);
  const frontier = Math.max(0, ...Object.keys(analysisByMove).map(Number));
  const cursor = selectedPosition?.id === id ? selectedPosition.move : frontier;
  const selectMove = (move: number) => {
    if (id !== null) setSelectedPosition({ id, move });
    setTryMoves([]);
    setVariation(null);
  };

  useEffect(() => {
    if (id === null) return;
    let cancelled = false;
    KifuAPI.getAlbum(id, lang).then((album) => {
      if (!cancelled) { setLoaded({ id, lang, album }); setLoadError(false); }
    }).catch(() => { if (!cancelled) setLoadError(true); });
    return () => { cancelled = true; };
  }, [id, lang, reload]);

  const album = loaded?.id === id && loaded.lang === lang ? loaded.album : null;
  const eventRules = kifuEventRules(analysisParameters, album?.rules);
  const parsed = useMemo(() => {
    try { return album?.sgf_content ? sgfToMoves(album.sgf_content) : null; } catch { return null; }
  }, [album]);
  const boardSize = parsed?.metadata.boardSize || album?.board_size || 19;
  const totalMoves = parsed ? Math.max(0, parsed.moves.length - (parsed.setupCount ?? 0)) : 0;
  const at = Math.min(cursor, totalMoves);
  const boardCursor = at + (parsed?.setupCount ?? 0);
  useReplayStoneSound({ identity: id, cursor: at, move: parsed?.moves[boardCursor - 1],
    ready: !!parsed && !!detail, boardSize, selected: selectedPosition?.id === id });
  const playerToMove = reportPlayerToMove(parsed?.stoneColors, boardCursor, parsed?.setupCount);
  const currentAnalysis = analysisByMove[at] ?? null;
  const markers = useMemo((): AiMoveMarker[] | null => {
    if (!showAiMarkers || !currentAnalysis?.top_moves?.length) return null;
    return currentAnalysis.top_moves.slice(0, 5).map((move, rank) => ({
      move: move.move, rank: rank + 1, visits: move.visits,
      winrate: playerToMove === 'B' ? move.winrate ?? 0 : 1 - (move.winrate ?? 0), score_lead: playerToMove === 'B' ? move.score_lead ?? 0 : -(move.score_lead ?? 0),
    }));
  }, [currentAnalysis, showAiMarkers, playerToMove]);
  const grades = useMemo(() => gradedMoves(analysisByMove), [analysisByMove]);
  const points = useMemo((): WinratePoint[] => (detail?.moves ?? []).filter((row) => row.winrate != null && analysisByMove[row.move_number]).map((row) => ({
    moveNumber: row.move_number, winrate: row.winrate!,
    player: row.actual_player === 'B' || row.actual_player === 'W' ? row.actual_player : null,
    bad: grades.some((grade) => grade.move_number === row.move_number && isBad(grade)),
  })), [detail, grades, analysisByMove]);
  const leadPoints = useMemo(() => (detail?.moves ?? []).filter((row) => row.score_lead != null && analysisByMove[row.move_number]).map((row) => ({
    moveNumber: row.move_number, scoreLead: row.score_lead!,
  })), [detail, analysisByMove]);
  const activeMove = variation?.id === id && variation.position === at
    && currentAnalysis?.top_moves.some((move) => move.move === variation.move) ? variation.move : null;
  const pvMoves = currentAnalysis?.top_moves.find((move) => move.move === activeMove)?.pv ?? null;
  useEffect(() => { setTryMoveMode(false); setTryMoves([]); setVariation(null); }, [id]);
  useEffect(() => { setTryMoves([]); setVariation(null); }, [at]);
  const retryLoad = () => setReload((value) => value + 1);
  const status = kifuAnalysisStatus(detail, analysisError, t);
  const title = album ? album.display_event ?? album.event ?? t('kifu:report_title', '职业棋局报告') : t('kifu:report_title', '职业棋局报告');

  return (
    <div className="kiosk-layout-a report-analysis-layout" data-testid="kifu-report-detail-page">
      <div className="kiosk-board" data-coordinates={showCoordinates} data-testid="kifu-report-detail-board">
        <div className="kiosk-board__ruler kiosk-board__ruler--top">
          {colsFor(boardSize).map((col) => <span key={col}>{col}</span>)}
        </div>
        <div className="kiosk-board__ruler kiosk-board__ruler--left">
          {rowsFor(boardSize).map((row) => <span key={row}>{row}</span>)}
        </div>
        <div className="kiosk-board__play">
          {parsed && <LiveBoard
            moves={parsed.moves} stoneColors={parsed.stoneColors}
            currentMove={boardCursor} boardSize={boardSize} nextColor={playerToMove}
            showCoordinates={false} minimumCanvasSize={0} minContainerHeight={0}
            aiMarkers={markers} showAiMarkers={showAiMarkers} pvMoves={pvMoves}
            onIntersectionClick={(x, y) => {
              if (activeMove) { setVariation(null); return; }
              if (!showAiMarkers) return;
              const move = `${'ABCDEFGHJKLMNOPQRSTUVWXYZ'[x]}${y + 1}`;
              if (currentAnalysis?.top_moves.some((candidate) => candidate.move === move)) {
                setVariation({ id, position: at, move });
              }
            }}
            aiMarkerLimit={5}
            showMoveNumbers={showMoveNumbers} showTerritory={showTerritory}
            ownership={showTerritory ? currentAnalysis?.ownership ?? null : null}
            tryMoves={tryMoveMode ? tryMoves : undefined}
            onTryMove={tryMoveMode ? handleTryMove : undefined}
          />}
        </div>
        <div className="kiosk-board__ruler kiosk-board__ruler--right">
          {rowsFor(boardSize).map((row) => <span key={row}>{row}</span>)}
        </div>
        <div className="kiosk-board__ruler kiosk-board__ruler--bottom">
          {colsFor(boardSize).map((col) => <span key={col}>{col}</span>)}
        </div>
      </div>

      {!album || !parsed ? (
        <div className="kiosk-rail" data-testid="kifu-report-detail-shell">
          <KioskPagebar backLabel={t('kifu:back_kifu', '棋谱')} onBack={() => navigate('/kiosk/kifu')} title={title} />
          <div className="empty" data-testid="kifu-report-loading">
            <h4>{loadError || id === null ? t('kifu:report_load_failed', '职业棋局暂时无法读取') : album ? t('report:no_sgf', '没有可用于复盘展示的 SGF 数据。') : t('kifu:report_loading', '正在读取职业棋局报告')}</h4>
            {(loadError || album) && <button type="button" className="kiosk-btn" onClick={retryLoad}>{t('report:retry_load', '重试加载')}</button>}
          </div>
        </div>
      ) : (
        <ReportAnalysisRail
          key={id} testId="kifu-report" shellTestId="kifu-report-detail-shell"
          players={[album.display_player_black ?? album.player_black, album.display_player_white ?? album.player_white]}
          pagebar={(<KioskPagebar
            backLabel={t('kifu:back_kifu', '棋谱')} onBack={() => navigate('/kiosk/kifu')} title={title}
            sub={`${album.date_played ?? ''} · ${at} / ${totalMoves} ${t('kifu:moves_unit', '手')}`}
          />)}
          analysis={currentAnalysis} analysisByMove={analysisByMove}
          playerToMove={playerToMove} actualMove={parsed.moves[boardCursor]}
          currentMove={at} totalMoves={totalMoves} points={points} lead={leadPoints}
          onMoveClick={selectMove} activeMove={activeMove}
          onCandidateClick={(move) => {
            setTryMoveMode(false); setTryMoves([]);
            setVariation(activeMove === move ? null : { id, position: at, move });
          }}
          status={(<div className="report-analysis-rail__status" data-testid="kifu-report-head">
            <span>{status}</span>
            <span>{detail?.requested_visits != null ? `${detail.requested_visits} visits · ${album.move_count} ${t('kifu:moves_unit', '手')}` : '—'}</span>
          </div>)}
          statusVisible={detail?.status !== 'completed' || !kifuAnalysisParametersValid(detail) || detail.moves.length === 0 || analysisError}
          metadata={(<div className="report-analysis-rail__status" data-testid="kifu-report-metadata">
            <span>{album.result ? translateResult(album.result, t, analysisParameters?.rules ?? album.rules) : '—'}</span>
            <span>{kifuRulesLabel(eventRules, t, analysisParameters)}</span><span>{t('report:komi_label', '贴目')} {analysisParameters?.komi ?? album.komi ?? '—'}</span>
          </div>)}
          details={[
            [t('review:black', '黑'), [album.display_player_black ?? album.player_black, album.display_black_rank ?? album.black_rank].filter(Boolean).join(' · ')],
            [t('review:white', '白'), [album.display_player_white ?? album.player_white, album.display_white_rank ?? album.white_rank].filter(Boolean).join(' · ')],
            [t('report:event', '赛事'), [album.display_event ?? album.event, album.display_round_name ?? album.round_name].filter(Boolean).join(' · ')],
            [t('report:date', '日期'), album.date_played],
            [t('report:result', '结果'), album.result],
            [t('report:rules', '规则'), kifuRulesLabel(eventRules, t, analysisParameters)],
            [t('report:sgf_rules', 'SGF 规则'), defaultRulesSource ? null : album.rules],
            [t('report:sgf_komi', 'SGF 贴目'), album.komi],
            [analysisParameters?.verified === true ? t('report:analysis_rules', '分析规则（已核验）') : t('report:analysis_rules_unverified', '分析规则'), analysisParameters ? kifuRulesLabel(analysisParameters.rules, t, analysisParameters) : '—'],
            [t('report:komi_label', '贴目'), analysisParameters?.komi],
            ...(defaultRulesSource ? [[t('kifu:rules_source', '规则来源'), defaultRulesSource] as const] : []),
            [t('report:status', '状态'), status],
            [t('report:source', '来源'), album.sources?.join(' · ') || album.source],
          ]}
          detailActions={<button type="button" onClick={() => navigate(`/kiosk/kifu/${id}/replay`)}>{t('kifu:view_kifu', '查看棋谱')}</button>}
          actions={(<>
            <button type="button" aria-pressed={tryMoveMode} onClick={() => { setTryMoveMode((value) => !value); setTryMoves([]); setVariation(null); }}><Icon name="hand-pointing" />{t('report:try', '试下')}</button>
            <button type="button" aria-pressed={showTerritory} disabled={!currentAnalysis?.ownership} onClick={() => setShowTerritory((value) => !value)}><Icon name="map-trifold" />{t('report:territory', '领地')}</button>
            <button type="button" aria-pressed={showAiMarkers} onClick={() => setShowAiMarkers((value) => !value)}><Icon name="lightbulb" />{t('Advice', '支招')}</button>
            <PhysicalBoardButton source={`kifu_${album.id}`} name={title} sgf={album.sgf_content} boardSize={boardSize} />
          </>)}
          toggles={(<>
            <button type="button" aria-pressed={showMoveNumbers} onClick={() => setShowMoveNumbers((value) => !value)}><Icon name="list-numbers" />{t('report:move_numbers', '手数')}</button>
            <button type="button" aria-pressed={showCoordinates} onClick={() => setShowCoordinates((value) => !value)}><Icon name="grid-nine" />{t('Coordinates', '坐标')}</button>

          </>)}
          notices={(<>
            {analysisError && <p className="rverr" role="status">{t('kifu:analysis_read_error', '分析状态暂时无法读取')}<button type="button" onClick={() => navigate(0)}>{t('report:retry_load', '重试加载')}</button></p>}
            {(detail?.status === 'failed' || detail?.status === 'rules_unresolved') && <p className="rverr" role="status">{detail.parameter_error?.message || detail.error_message || status}</p>}
            {tryMoveMode && tryMoves.length > 0 && <p className="rverr" role="status" data-testid="kifu-report-try">{tryMoves.join(' → ')}</p>}
            {activeMove && <p className="rverr" role="status" data-testid="kifu-report-variation">{t('report:variation_preview', '变化预览 · 点击棋盘关闭')}<button type="button" onClick={() => setVariation(null)}>{t('report:clear_variation', '清除变化')}</button></p>}
          </>)}
          navigation={<KioskReportPlayback testId="kifu-report-movenav" currentMove={at} totalMoves={totalMoves} onMoveChange={selectMove} />}
        />
      )}
    </div>
  );
}
