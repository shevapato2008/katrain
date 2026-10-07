import { useEffect, useState } from 'react';
import { useTranslation } from '../../../hooks/useTranslation';
import { Icon } from '../../shell/icons';

interface Props {
  testId: string;
  currentMove: number;
  totalMoves: number;
  onMoveChange: (move: number) => void;
}

export default function KioskReportPlayback({ testId, currentMove, totalMoves, onMoveChange }: Props) {
  const { t } = useTranslation();
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    if (!playing) return;
    if (currentMove >= totalMoves) { setPlaying(false); return; }
    const timer = window.setTimeout(() => onMoveChange(currentMove + 1), 1000);
    return () => window.clearTimeout(timer);
  }, [playing, currentMove, totalMoves, onMoveChange]);

  const go = (move: number) => { setPlaying(false); onMoveChange(move); };
  return <div className="kiosk-movenav report-playback" data-testid={testId}>
    <button type="button" aria-label={t('kifu:to_start', '回到开局')} disabled={currentMove === 0} onClick={() => go(0)}><Icon name="caret-double-left" /></button>
    <button type="button" aria-label={t('kifu:prev_move', '上一手')} disabled={currentMove === 0} onClick={() => go(currentMove - 1)}><Icon name="caret-left" /></button>
    <button type="button" aria-label={playing ? t('live:pause', '暂停') : t('live:play', '播放')} onClick={() => { if (currentMove >= totalMoves) onMoveChange(0); setPlaying(!playing); }}>{playing ? 'Ⅱ' : '▶'}</button>
    <button type="button" aria-label={t('kifu:next_move', '下一手')} disabled={currentMove >= totalMoves} onClick={() => go(currentMove + 1)}><Icon name="caret-right" /></button>
    <button type="button" aria-label={t('kifu:to_end', '跳到最后')} disabled={currentMove >= totalMoves} onClick={() => go(totalMoves)}><Icon name="caret-double-right" /></button>
    <input type="range" aria-label={t('live:move_slider', '手数进度')} min={0} max={totalMoves} value={currentMove} onChange={(event) => go(Number(event.target.value))} />
    <output>{currentMove}/{totalMoves} {t('kifu:moves_unit', '手')}</output>
  </div>;
}
