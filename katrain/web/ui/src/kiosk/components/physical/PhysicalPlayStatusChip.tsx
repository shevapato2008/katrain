import { useEffect, useRef, useState } from 'react';
import { Chip } from '@mui/material';
import { HourglassTop } from '@mui/icons-material';
import { useTranslation } from '../../../hooks/useTranslation';
import type { VisionSyncEvent } from '../../hooks/useVisionSync';

interface Props {
  latestEvent: VisionSyncEvent | null;
  currentNodeId: number | null; // gameState.current_node_id — advance hides the chip
}

/** '确认中…' (PRD §3.2/Q3): shown from move_pending until the game state advances or 6s. */
const PhysicalPlayStatusChip = ({ latestEvent, currentNodeId }: Props) => {
  const { t } = useTranslation();
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (latestEvent?.type === 'move_pending') {
      setVisible(true);
      const timer = setTimeout(() => setVisible(false), 6000);
      return () => clearTimeout(timer);
    }
  }, [latestEvent]);
  // Skip the reset on initial mount — effects always fire on mount regardless of
  // deps, and without this guard it immediately clobbers the move_pending show
  // above. Only an actual currentNodeId change (the game state advancing) should hide.
  const isFirstNodeRender = useRef(true);
  useEffect(() => {
    if (isFirstNodeRender.current) {
      isFirstNodeRender.current = false;
      return;
    }
    setVisible(false);
  }, [currentNodeId]);
  if (!visible) return null;
  return (
    <Chip
      icon={<HourglassTop />}
      label={t('Confirming…', '确认中…')}
      color="warning"
      size="small"
      sx={{ position: 'absolute', top: 8, left: '50%', transform: 'translateX(-50%)', zIndex: 50 }}
    />
  );
};

export default PhysicalPlayStatusChip;
