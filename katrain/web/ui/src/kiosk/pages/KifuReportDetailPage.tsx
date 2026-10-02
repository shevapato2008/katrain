import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { KifuAPI } from '../../api/kifuApi';
import type { KifuAlbumDetail } from '../../types/kifu';
import { useKifuAnalysis } from '../../features/kifu/useKifuAnalysis';
import { kifuAnalysisStatus } from '../../features/kifu/kifuAnalysisStatus';
import { gradedMoves, isBad, isBrilliant } from '../../features/analysis/moveGrade';
import type { WinratePoint } from '../../features/report/reportStats';
import { sgfToMoves } from '../../utils/sgfSerializer';
import { useTranslation } from '../../hooks/useTranslation';
import LiveBoard, { type AiMoveMarker } from '../../components/live/LiveBoard';
import { AiRecommendRows } from '../components/report/AiRecommendRows';
import MoveGradePanel from '../components/report/MoveGradePanel';
import { ReviewWinratePlot } from '../components/report/ReviewWinratePlot';
import { colsFor, rowsFor } from '../shell/goBoard';
import { KioskFold } from '../shell/KioskFold';
import { KioskPagebar } from '../shell/KioskPagebar';
import { Icon } from '../shell/icons';
import { interpolate } from '../utils/interpolate';

/** Professional archive report, sharing the personal report's board, AI, grade and chart components. */
export default function KifuReportDetailPage() {
  const { kifuId } = useParams<{ kifuId: string }>();
  const id = kifuId && /^\d+$/.test(kifuId) ? Number(kifuId) : null;
  const navigate = useNavigate();
  const { t, lang } = useTranslation();
  const [loaded, setLoaded] = useState<{ id: number; lang: string; album: KifuAlbumDetail } | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [selectedPosition, setSelectedPosition] = useState<{ id: number; move: number } | null>(null);
  const [openFold, setOpenFold] = useState<'ai' | 'grade'>('ai');
  const [showAiMarkers, setShowAiMarkers] = useState(true);
  const [showMoveNumbers, setShowMoveNumbers] = useState(true);
  const [showTerritory, setShowTerritory] = useState(false);
  const [tryMoveMode, setTryMoveMode] = useState(false);
  const [tryMoves, setTryMoves] = useState<string[]>([]);
  const { detail, analysisByMove, error: analysisError } = useKifuAnalysis(id);
  const frontier = Math.max(0, ...Object.keys(analysisByMove).map(Number));
  const cursor = selectedPosition?.id === id ? selectedPosition.move : frontier;
  const selectMove = (move: number) => {
    if (id !== null) setSelectedPosition({ id, move });
    setTryMoves([]);
  };

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
  const boardSize = parsed?.metadata.boardSize || album?.board_size || 19;
  const totalMoves = parsed ? Math.max(0, parsed.moves.length - (parsed.setupCount ?? 0)) : 0;
  const at = Math.min(cursor, totalMoves);
  const currentAnalysis = analysisByMove[at] ?? null;
  const markers = useMemo((): AiMoveMarker[] | null => {
    if (!showAiMarkers || !currentAnalysis?.top_moves?.length) return null;
    return currentAnalysis.top_moves.slice(0, 3).map((move, rank) => ({
      move: move.move, rank: rank + 1, visits: move.visits,
      winrate: move.winrate ?? 0, score_lead: move.score_lead ?? 0,
    }));
  }, [currentAnalysis, showAiMarkers]);
  const aiRows = useMemo(() => {
    const candidates = currentAnalysis?.top_moves ?? [];
    const total = candidates.reduce((sum, move) => sum + move.visits, 0);
    return candidates.slice(0, 10).map((move) => ({
      move: move.move, share: total ? move.visits / total * 100 : 0,
      scoreLead: move.score_lead ?? 0, winrate: move.winrate ?? 0,
    }));
  }, [currentAnalysis]);
  const grades = useMemo(() => gradedMoves(analysisByMove), [analysisByMove]);
  const gradeSummary = interpolate(t('grade:summary', '妙 {a} · 坏 {b}'), {
    a: grades.filter(isBrilliant).length, b: grades.filter(isBad).length,
  });
  const points = useMemo((): WinratePoint[] => (detail?.moves ?? []).filter((row) => row.winrate != null).map((row) => ({
    moveNumber: row.move_number, winrate: row.winrate!,
    player: row.actual_player === 'B' || row.actual_player === 'W' ? row.actual_player : null,
    bad: grades.some((grade) => grade.move_number === row.move_number && isBad(grade)),
  })), [detail, grades]);
  const leadPoints = useMemo(() => (detail?.moves ?? []).filter((row) => row.score_lead != null).map((row) => ({
    moveNumber: row.move_number, scoreLead: row.score_lead!,
  })), [detail]);
  const status = kifuAnalysisStatus(detail, analysisError, t);
  const title = album ? `${album.display_player_black ?? album.player_black} ${t('kifu:versus', '对')} ${album.display_player_white ?? album.player_white}` : t('kifu:report_title', '职业棋局报告');

  return (
    <div className="kiosk-layout-a" data-testid="kifu-report-detail-page">
      <div className="kiosk-board" data-testid="kifu-report-detail-board">
        <div className="kiosk-board__ruler kiosk-board__ruler--top">
          {colsFor(boardSize).map((col) => <span key={col}>{col}</span>)}
        </div>
        <div className="kiosk-board__ruler kiosk-board__ruler--left">
          {rowsFor(boardSize).map((row) => <span key={row}>{row}</span>)}
        </div>
        <div className="kiosk-board__play">
          {parsed && <LiveBoard
            moves={parsed.moves} stoneColors={parsed.stoneColors}
            currentMove={at + (parsed.setupCount ?? 0)} boardSize={boardSize}
            showCoordinates={false} minimumCanvasSize={0} minContainerHeight={0}
            aiMarkers={markers} showAiMarkers={showAiMarkers}
            showMoveNumbers={showMoveNumbers} showTerritory={showTerritory}
            ownership={showTerritory ? currentAnalysis?.ownership ?? null : null}
            tryMoves={tryMoveMode ? tryMoves : undefined}
            onTryMove={tryMoveMode ? (move) => setTryMoves((previous) => [...previous, move]) : undefined}
          />}
        </div>
        <div className="kiosk-board__ruler kiosk-board__ruler--right">
          {rowsFor(boardSize).map((row) => <span key={row}>{row}</span>)}
        </div>
        <div className="kiosk-board__ruler kiosk-board__ruler--bottom">
          {colsFor(boardSize).map((col) => <span key={col}>{col}</span>)}
        </div>
      </div>

      <div className="kiosk-rail" data-testid="kifu-report-detail-shell">
        <KioskPagebar
          backLabel={t('kifu:back_kifu', '棋谱')} onBack={() => navigate('/kiosk/kifu')}
          title={title} sub={album ? `${album.display_event ?? album.event ?? t('kifu:professional_game', '职业棋局')} · ${at} / ${totalMoves} ${t('kifu:moves_unit', '手')}` : undefined}
        />
        {!album ? (
          <div className="empty" data-testid="kifu-report-loading">
            <h4>{loadError || id === null ? t('kifu:report_load_failed', '职业棋局暂时无法读取') : t('kifu:report_loading', '正在读取职业棋局报告')}</h4>
          </div>
        ) : (
          <>
            <div className="rhead" data-testid="kifu-report-head">
              <div>
                <h4>{status} · {t('report:deep', '深度报告')}</h4>
                <p>{detail?.status === 'running'
                  ? interpolate(t('kifu:report_progress', '已分析 {done} / {total} 手'), { done: detail.analyzed_moves, total: detail.total_moves })
                  : interpolate(t('kifu:report_visits', '每局面 2000 visits · {total} 手'), { total: album.move_count })}</p>
              </div>
              <div className="end">
                <button type="button" className="kiosk-btn kiosk-btn--pill" onClick={() => navigate(`/kiosk/kifu/${id}/replay`)}>
                  {t('kifu:view_kifu', '查看棋谱')}
                </button>
              </div>
            </div>
            {detail?.status === 'failed' && <p className="rverr" role="status">{detail.error_message || t('kifu:analysis_failed', '分析未完成')}</p>}

            <KioskFold
              fold="ai" grow={openFold === 'ai'} open={openFold === 'ai'}
              onToggle={() => setOpenFold(openFold === 'ai' ? 'grade' : 'ai')}
              scrollbar bodyClassName="aitab" testId="kifu-report-ai"
              title={interpolate(t('research:ai_after_move', 'AI 推荐 · 第 {n} 手之后'), { n: at })}
              value={currentAnalysis ? `${t('review:black', '黑')} ${(currentAnalysis.winrate * 100).toFixed(1)}%` : status}
            >
              {currentAnalysis ? <AiRecommendRows rows={aiRows} /> : <span>{t('kifu:report_no_position', '当前局面暂无分析结果')}</span>}
            </KioskFold>

            <KioskFold
              fold="grade" grow={openFold === 'grade'} open={openFold === 'grade'}
              onToggle={() => setOpenFold(openFold === 'grade' ? 'ai' : 'grade')}
              testId="kifu-report-grade" title={t('grade:fold_title', '着手评价 · 七档')} value={gradeSummary}
            >
              <MoveGradePanel
                analysis={analysisByMove} totalMoves={totalMoves} onMoveClick={selectMove}
                trend={(
                  <>
                    <p className="tline">
                      <span className="wr">{t('review:black_winrate', '黑胜率')} <b>{currentAnalysis ? `${(currentAnalysis.winrate * 100).toFixed(1)}%` : '—'}</b></span>
                      <span className="sl">{t('review:black_lead', '黑领先')} <b>{currentAnalysis ? `${currentAnalysis.score_lead >= 0 ? '+' : '−'}${Math.abs(currentAnalysis.score_lead).toFixed(1)} ${t('report:points_unit', '目')}` : '—'}</b></span>
                    </p>
                    <div className="evalpad">
                      <ReviewWinratePlot
                        points={points} lead={leadPoints} empty={points.length < 2 ? t('review:plot_thin', '报告里还没有算出来的手') : ''}
                        axisTop={`${t('review:black', '黑')} 100`} axisMid="50" axisBottom={`${t('review:white', '白')} 100`}
                        label={t('review:plot_pick_label', '逐手胜率，点一下跳到那一手')} cursor={at} onPick={selectMove}
                      />
                    </div>
                  </>
                )}
              />
            </KioskFold>

            <div className="gtoggles gtoggles--icon" role="group" aria-label={t('review:toggles', '显示')}>
              <button type="button" aria-pressed={tryMoveMode} onClick={() => { setTryMoveMode((value) => !value); setTryMoves([]); }}>
                <Icon name="hand-pointing" />{t('report:try', '试下')}
              </button>
              <button type="button" aria-pressed={showTerritory} disabled={!currentAnalysis?.ownership} onClick={() => setShowTerritory((value) => !value)}>
                <Icon name="map-trifold" />{t('report:territory', '领地')}
              </button>
              <button type="button" aria-pressed={showMoveNumbers} onClick={() => setShowMoveNumbers((value) => !value)}>
                <Icon name="list-numbers" />{t('report:move_numbers', '手数')}
              </button>
              <button type="button" aria-pressed={showAiMarkers} onClick={() => setShowAiMarkers((value) => !value)}>
                <Icon name="lightbulb" />{t('Advice', '支招')}
              </button>
            </div>
            <div className="kiosk-movenav" data-testid="kifu-report-movenav">
              <button type="button" aria-label={t('kifu:to_start', '回到开局')} disabled={at === 0} onClick={() => selectMove(0)}><Icon name="caret-double-left" /></button>
              <button type="button" aria-label={t('kifu:prev_move', '上一手')} disabled={at === 0} onClick={() => selectMove(at - 1)}><Icon name="caret-left" /></button>
              <button type="button" aria-label={t('kifu:next_move', '下一手')} disabled={at >= totalMoves} onClick={() => selectMove(at + 1)}><Icon name="caret-right" /></button>
              <button type="button" aria-label={t('kifu:to_end', '跳到最后')} disabled={at >= totalMoves} onClick={() => selectMove(totalMoves)}><Icon name="caret-double-right" /></button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
