import { useRef, useState, type ReactNode } from 'react';
import Modal from '@mui/material/Modal';

import type { MoveAnalysis } from '../../../types/live';
import type { WinratePoint } from '../../../features/report/reportStats';
import { useTranslation } from '../../../hooks/useTranslation';
import { reportCandidates } from '../../../features/analysis/reportCandidates';
import { Icon } from '../../shell/icons';
import MoveGradePanel from './MoveGradePanel';
import { ReviewWinratePlot, type LeadPoint } from './ReviewWinratePlot';
import './reportRail.css';

interface Props {
  testId: string;
  shellTestId?: string;
  pagebar: ReactNode;
  players: readonly [string, string];
  metadata: ReactNode;
  status: ReactNode;
  statusVisible?: boolean;
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
  detailActions?: ReactNode;
  toggles: ReactNode;
  navigation: ReactNode;
  notices?: ReactNode;
}

/** Both report types share one fixed workspace; only its bounded lists scroll. */
export function ReportAnalysisRail(props: Props) {
  const { t } = useTranslation();
  const [detailsOpen, setDetailsOpen] = useState(false);
  const railRef = useRef<HTMLDivElement>(null);
  const playedMove = props.actualMove ?? props.analysisByMove[props.currentMove + 1]?.move;
  const displayCandidates = reportCandidates(props.analysis?.top_moves ?? [], props.analysis ? playedMove : null);
  const percentage = (value: number | null | undefined) => value == null ? '—' : `${(value * 100).toFixed(1)}%`;
  const leadLabel = (value: number | null | undefined) => value == null ? '—' : `${value >= 0 ? '+' : '−'}${Math.abs(value).toFixed(1)}`;
  const black = t('review:black', '黑');
  const white = t('review:white', '白');
  const detailsLabel = t('report:game_details', '对局详情');
  const close = () => setDetailsOpen(false);

  const recommendation = <section className="report-analysis-rail__candidates" data-testid={`${props.testId}-ai`}>
    <div className="report-analysis-rail__candidate-head"><strong>{t('report:ai_recommendation', 'AI推荐')} · {props.playerToMove === 'B' ? black : white}{t('report:to_play', '方待落子')}</strong>{props.statusVisible && !detailsOpen && props.analysis ? props.status : <span>{t('report:after_move', '第 {n} 手后').replace('{n}', String(props.currentMove))}</span>}</div>
    {props.analysis ? <>
      <div className="report-analysis-rail__columns">
        <span>{t('live:suggested_move', '着点')}</span><span>{t('live:recommendation', '推荐度')}</span>
        <span>{t('report:score_difference', '目差')}</span><span>{t('live:winrate', '胜率')}</span>
      </div>
      <div className="report-analysis-rail__candidate-list" data-testid="report-candidate-list">
        {displayCandidates.map((move, index) => {
          const score = move.score_lead == null ? null : props.playerToMove === 'B' ? move.score_lead : -move.score_lead;
          const winrate = move.winrate == null ? null : props.playerToMove === 'B' ? move.winrate : 1 - move.winrate;
          return <button key={`${index}-${move.move}`} type="button" className="report-analysis-rail__candidate"
            data-actual={move.isActualMove || undefined} data-testid="ai-recommend-row"
            disabled={!move.pv.length} aria-pressed={props.activeMove === move.move}
            onClick={() => props.onCandidateClick(move.move)}>
            <span><i className={`kifu-record__stone kifu-record__stone--${props.playerToMove === 'B' ? 'black' : 'white'}`} aria-hidden="true" />{move.move}{move.isActualMove && <small>{index >= 5 ? t('report:actual_move_short', '实战') : '✓'}</small>}</span>
            <span>{move.percentage == null ? '—' : `${move.percentage.toFixed(0)}%`}</span>
            <span>{leadLabel(score)}</span><span>{percentage(winrate)}</span>
          </button>;
        })}
      </div>
    </> : <div className="report-analysis-rail__empty" role="status">{!detailsOpen && props.status}<span>{t('report:no_position_analysis', '当前局面暂无分析数据')}</span></div>}
  </section>;

  return <div ref={railRef} className="kiosk-rail report-analysis-rail report-rail-v2" data-testid={props.shellTestId ?? `${props.testId}-shell`}>
    <div className="report-analysis-rail__head">
      <div className="report-analysis-rail__pagebar">{props.pagebar}<button type="button" className="report-details-button" aria-label={detailsLabel} onClick={() => setDetailsOpen(true)}><Icon name="info" /></button></div>
      <div className="report-analysis-rail__scores" data-testid={`${props.testId}-scores`}>
        <div className="report-analysis-rail__players"><strong title={props.players[0]}><i className="kifu-record__stone kifu-record__stone--black" aria-label={black} /><span>{props.players[0]}</span></strong><b>{props.analysis ? Math.abs(props.analysis.score_lead) < .05 ? t('report:even_position', '形势均衡') : `${props.analysis.score_lead > 0 ? black : white}${t('report:leads', '领先')} ${Math.abs(props.analysis.score_lead).toFixed(1)} ${t('report:points_unit', '目')}` : t('report:position_number', '第 {n} 手').replace('{n}', String(props.currentMove))}</b><strong title={props.players[1]}><span>{props.players[1]}</span><i className="kifu-record__stone kifu-record__stone--white" aria-label={white} /></strong></div>
        <div className="report-analysis-rail__win"><span>{black} {percentage(props.analysis?.winrate)}</span><i data-empty={!props.analysis || undefined}>{props.analysis && <em style={{ width: `${Math.max(0, Math.min(100, props.analysis.winrate * 100))}%` }} />}</i><span>{white} {percentage(props.analysis ? 1 - props.analysis.winrate : null)}</span></div>
      </div>
      {props.metadata}
    </div>
    <MoveGradePanel analysis={props.analysisByMove} totalMoves={props.totalMoves} onMoveClick={props.onMoveClick}
      recommendation={recommendation}
      trend={<div className="report-trend">
        <div className="tline"><span className="wr">{t('live:black_winrate', '黑方胜率')} <b>{percentage(props.analysis?.winrate)}</b></span><span className="sl">{t('live:black_lead', '黑方领先')} <b>{leadLabel(props.analysis?.score_lead)}</b> {t('live:points_unit', '目')}</span></div>
        <div className="evalpad"><ReviewWinratePlot points={props.points} lead={props.lead}
          empty={props.points.length < 2 ? t('review:plot_thin', '报告里还没有算出来的手') : ''}
          axisTop="100%" axisMid="50%" axisBottom="0%"
          label={t('review:plot_pick_label', '逐手胜率，点一下跳到那一手')}
          cursor={props.currentMove} onPick={props.onMoveClick} totalMoves={props.totalMoves} /></div>
        <div className="report-trend__scale"><div>{[0, .25, .5, .75, 1].map(f => <span key={f}>{Math.round(props.totalMoves * f)}</span>)}</div><span>{t('grade:axis_move_number', '手数')}</span></div>
      </div>} />
    <div className="report-analysis-rail__tools">
      <div className="report-analysis-rail__actions" data-testid={`${props.testId}-actions`}>{props.actions}</div>
      <div className="report-analysis-rail__toggles" role="group" aria-label={t('review:toggles', '显示')} data-testid={`${props.testId}-toggles`}>{props.toggles}</div>
    </div>
    {props.navigation}
    <div className="report-analysis-rail__notices">{props.notices}</div>
    <Modal open={detailsOpen} onClose={close} disablePortal disableScrollLock container={() => railRef.current!} className="report-analysis-modal report-details-modal">
      <div className="report-analysis-modal__box" role="dialog" aria-modal="true" aria-label={detailsLabel}>
        <div className="report-analysis-modal__head"><h3>{detailsLabel}</h3><button type="button" onClick={close} aria-label={t('Close', '关闭')}>×</button></div>
        <div className="report-analysis-modal__body">{props.status}
          <dl className="report-analysis-modal__details">{props.details.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value == null || value === '' ? '—' : value}</dd></div>)}</dl>
          {props.detailActions && <div className="report-analysis-rail__detail-actions" onClick={close}>{props.detailActions}</div>}
        </div>
      </div>
    </Modal>
  </div>;
}
