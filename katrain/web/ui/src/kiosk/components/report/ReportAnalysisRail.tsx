import { useRef, useState, type ReactNode } from 'react';
import Modal from '@mui/material/Modal';

import type { MoveAnalysis } from '../../../types/live';
import type { WinratePoint } from '../../../features/report/reportStats';
import { useTranslation } from '../../../hooks/useTranslation';
import MoveGradePanel from './MoveGradePanel';
import { ReviewWinratePlot, type LeadPoint } from './ReviewWinratePlot';

interface Props {
  testId: string;
  shellTestId?: string;
  pagebar: ReactNode;
  players: readonly [string, string];
  status: ReactNode;
  details: readonly (readonly [string, ReactNode])[];
  analysis: MoveAnalysis | null;
  analysisByMove: Record<number, MoveAnalysis>;
  playerToMove: 'B' | 'W';
  actualMove?: string;
  currentMove: number;
  totalMoves: number;
  points: readonly WinratePoint[];
  lead: readonly LeadPoint[];
  onMoveClick: (move: number) => void;
  onCandidateClick: (move: string) => void;
  activeMove: string | null;
  actions: ReactNode;
  toggles: ReactNode;
  navigation: ReactNode;
  notices?: ReactNode;
}

/** Fixed five-row report rail; full-game analysis stays in a bounded, scrollable modal. */
export function ReportAnalysisRail(props: Props) {
  const { t } = useTranslation();
  const [panel, setPanel] = useState<'analysis' | 'details' | null>(null);
  const railRef = useRef<HTMLDivElement>(null);
  const candidates = props.analysis?.top_moves ?? [];
  const playedMove = props.actualMove ?? props.analysisByMove[props.currentMove + 1]?.move;
  const playedCandidate = playedMove ? candidates.find((candidate) => candidate.move === playedMove) : undefined;
  const playedOutsideTopFive = playedMove && !candidates.slice(0, 5).some((candidate) => candidate.move === playedMove);
  const weight = (move: typeof candidates[number]) => Number.isFinite(move.psv) && move.psv >= 0 ? move.psv : 0;
  const psvTotal = candidates.reduce((sum, move) => sum + weight(move), 0);
  const visitsTotal = candidates.reduce((sum, move) => sum + Math.max(0, move.visits || 0), 0);
  const percentage = (value: number | null | undefined) => value == null ? '—' : `${(value * 100).toFixed(1)}%`;
  const leadLabel = (value: number | null | undefined) => value == null ? '—' : `${value >= 0 ? '+' : '−'}${Math.abs(value).toFixed(1)}`;
  const black = t('review:black', '黑');
  const white = t('review:white', '白');
  const analysisLabel = t('grade:fold_title', '着手评价 · 七档');
  const detailsLabel = t('report:game_details', '对局详情');
  const close = () => setPanel(null);

  return (
    <div ref={railRef} className="kiosk-rail report-analysis-rail" data-testid={props.shellTestId ?? `${props.testId}-shell`}>
      {props.pagebar}
      <div className="report-analysis-rail__head">
        <div className="report-analysis-rail__scores" data-testid={`${props.testId}-scores`}>
          <div className="report-analysis-rail__players"><strong title={props.players[0]}>● {props.players[0]}</strong><b>{props.analysis ? Math.abs(props.analysis.score_lead) < .05 ? t('report:even_position', '形势均衡') : `${props.analysis.score_lead > 0 ? black : white}${t('report:leads', '领先')} ${Math.abs(props.analysis.score_lead).toFixed(1)} ${t('report:points_unit', '目')}` : '—'}</b><strong title={props.players[1]}>{props.players[1]} ○</strong></div>
          <div className="report-analysis-rail__win"><span>{black} {percentage(props.analysis?.winrate)}</span><i><em style={{ width: `${props.analysis ? Math.max(0, Math.min(100, props.analysis.winrate * 100)) : 50}%` }} /></i><span>{white} {percentage(props.analysis ? 1 - props.analysis.winrate : null)}</span></div>
        </div>
        {props.status}
      </div>
      {props.notices}
      <section className="report-analysis-rail__candidates" data-testid={`${props.testId}-ai`}>
        <div className="report-analysis-rail__columns">
          <span>{props.playerToMove === 'B' ? black : white} · {t('live:suggested_move', '着点')}</span>
          <span>{t('live:recommendation', '推荐度')}</span>
          <span>{t('live:lead_pts', '领先')}</span>
          <span>{t('live:winrate', '胜率')}</span>
        </div>
        {Array.from({ length: 5 }, (_, index) => {
          const move = candidates[index];
          const share = move && (psvTotal > 0 ? weight(move) / psvTotal : visitsTotal > 0 ? Math.max(0, move.visits || 0) / visitsTotal : null);
          const score = move?.score_lead == null ? null : props.playerToMove === 'B' ? move.score_lead : -move.score_lead;
          const winrate = move?.winrate == null ? null : props.playerToMove === 'B' ? move.winrate : 1 - move.winrate;
          return (
            <button
              key={index} type="button" className="report-analysis-rail__candidate"
              data-testid={move ? 'ai-recommend-row' : 'ai-recommend-empty-row'}
              disabled={!move} aria-pressed={!!move && props.activeMove === move.move}
              onClick={() => move && props.onCandidateClick(move.move)}
            >
              <span>{index + 1} · {move?.move ?? '—'}</span>
              <span>{share == null ? '—' : `${(share * 100).toFixed(0)}%`}</span>
              <span className={score != null && score < 0 ? 'neg' : ''}>{leadLabel(score)}</span>
              <span>{percentage(winrate)}</span>
            </button>
          );
        })}
      </section>
      <div className="report-analysis-rail__actions" data-testid={`${props.testId}-actions`}>
        {props.actions}
        <button type="button" aria-label={analysisLabel} onClick={() => setPanel('analysis')} data-testid={`${props.testId}-grade`}>
          {t('report:analysis', '分析')}
        </button>
        <button type="button" onClick={() => setPanel('details')}>{detailsLabel}</button>
      </div>
      {props.toggles}
      {props.navigation}
      <Modal open={panel !== null} onClose={close} disablePortal disableScrollLock container={() => railRef.current!} className="report-analysis-modal">
        <div className="report-analysis-modal__box" role="dialog" aria-modal="true" aria-label={panel === 'analysis' ? analysisLabel : detailsLabel}>
          <div className="report-analysis-modal__head">
            <h3>{panel === 'analysis' ? analysisLabel : detailsLabel}</h3>
            <button type="button" onClick={close}>{t('Close', '关闭')}</button>
          </div>
          <div className="report-analysis-modal__body">
            {panel === 'analysis' ? (
              <MoveGradePanel
                analysis={props.analysisByMove} totalMoves={props.totalMoves} onMoveClick={props.onMoveClick}
                trend={<div className="evalpad"><ReviewWinratePlot
                  points={props.points} lead={props.lead}
                  empty={props.points.length < 2 ? t('review:plot_thin', '报告里还没有算出来的手') : ''}
                  axisTop={`${black} 100`} axisMid="50" axisBottom={`${white} 100`}
                  label={t('review:plot_pick_label', '逐手胜率，点一下跳到那一手')}
                  cursor={props.currentMove} onPick={props.onMoveClick}
                /></div>}
              />
            ) : (
              <dl className="report-analysis-modal__details">
                {props.details.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value == null || value === '' ? '—' : value}</dd></div>)}
                {playedOutsideTopFive && <div><dt>{t('report:actual_move', '实战着点')}</dt><dd>{playedMove} · {playedCandidate ? t('report:outside_top_five', '未进入前五推荐') : t('report:unevaluated_move', '未进入候选，暂无评估')}</dd></div>}
              </dl>
            )}
          </div>
        </div>
      </Modal>
    </div>
  );
}
