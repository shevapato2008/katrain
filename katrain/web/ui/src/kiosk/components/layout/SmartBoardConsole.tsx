import { Box, ButtonBase, Typography } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import LiveBoard from '../../../components/live/LiveBoard';
import { useOptionalVision } from '../../context/VisionContext';
import { useOptionalGeometry } from '../../context/GeometryContext';

export interface SmartBoardConsoleProps {
  moves?: string[];
  currentMove?: number;
}

/** Resolve board-pose sync state to a status color (migrated from StatusBar.tsx) */
// @ts-expect-error TS6133 — kept for future use / migration reference
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const syncStateColor = (syncState: string): string => {
  switch (syncState) {
    case 'synced':
      return 'success.main';
    case 'calibrating':
    case 'setup':
      return 'warning.main';
    case 'mismatch':
    case 'lost':
      return 'error.main';
    default:
      return 'grey.500';
  }
};

/** Resolve geometry calibration phase to a status color (migrated from StatusBar.tsx) */
const geometryPhaseColor = (phase: string): string =>
  phase === 'ready' ? 'success.main' : phase === 'degraded' || phase === 'failed' ? 'error.main' : 'warning.main';

interface StatusCellProps {
  label: string;
  value: string;
  dotColor: string;
  valueColor?: string;
  onClick: () => void;
}

/** One 摄像头/标定/LED status cell — colored dot + label + value, click opens vision setup */
const StatusCell = ({ label, value, dotColor, valueColor = 'text.primary', onClick }: StatusCellProps) => (
  <ButtonBase
    onClick={onClick}
    aria-label={`${label}状态`}
    sx={{
      flex: 1,
      flexDirection: 'column',
      alignItems: 'flex-start',
      justifyContent: 'flex-start',
      bgcolor: 'background.paper',
      border: '1px solid',
      borderColor: 'divider',
      borderRadius: '11px',
      px: 1.25,
      py: 1.125,
      textAlign: 'left',
    }}
  >
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
      <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: dotColor, flexShrink: 0 }} />
      <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: 11 }}>
        {label}
      </Typography>
    </Box>
    <Typography sx={{ fontSize: 13, fontWeight: 600, color: valueColor, mt: 0.375 }}>{value}</Typography>
  </ButtonBase>
);

/**
 * SmartBoardConsole — persistent left-side console on /kiosk/play: a read-only
 * live board preview + 摄像头/标定/LED status cells. STATIC preview stub: no
 * recognized-board feed exists yet, so the board renders whatever `moves`/
 * `currentMove` the caller passes (empty by default) with a visible
 * "no live feed" label so it is never mistaken for recognized-board data.
 */
const SmartBoardConsole = ({ moves, currentMove }: SmartBoardConsoleProps) => {
  const navigate = useNavigate();
  const vision = useOptionalVision();
  const geometry = useOptionalGeometry();

  const cameraConnected = vision?.visionStatus.cameraConnected ?? false;
  const ledConnected = vision?.visionStatus.ledConnected ?? false;
  const geometryPhase = geometry?.status.phase ?? 'required';

  const goToVisionSetup = () => navigate('/kiosk/vision/setup');

  const geometryValue =
    geometryPhase === 'ready' ? '已标定' : geometryPhase === 'degraded' || geometryPhase === 'failed' ? '异常' : '需校准';

  return (
    <Box
      sx={{
        width: 322,
        flexShrink: 0,
        m: 2.5,
        p: 1.875,
        bgcolor: 'background.paper',
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: '18px',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* title row — artifact .console .ch */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.375 }}>
        <Typography sx={{ fontSize: 13, fontWeight: 700, letterSpacing: '1.5px', color: 'text.primary' }}>
          智能棋盘
        </Typography>
        <Typography
          sx={{
            fontFamily: "'Newsreader','Noto Serif SC',serif",
            fontStyle: 'italic',
            fontSize: 12,
            color: 'text.secondary',
          }}
        >
          Live board
        </Typography>
      </Box>

      {/* read-only board preview */}
      <Box
        sx={{
          position: 'relative',
          width: '100%',
          aspectRatio: '1',
          borderRadius: '10px',
          overflow: 'hidden',
          boxShadow: '0 8px 24px -12px rgba(0,0,0,0.6)',
        }}
      >
        {/* TODO: feed recognized board state when available — no recognized-board feed exists yet.
            minContainerHeight={0}: this preview is only ~292px square, so the default 400px floor
            would overflow and clip the board (see LiveBoard). Let it scale down to fit. */}
        <LiveBoard moves={moves ?? []} currentMove={currentMove ?? 0} boardSize={19} showCoordinates={false} minContainerHeight={0} />
        <Box
          sx={{
            position: 'absolute',
            left: 0,
            right: 0,
            bottom: 6,
            display: 'flex',
            justifyContent: 'center',
            pointerEvents: 'none',
          }}
        >
          <Typography
            variant="caption"
            sx={{
              color: 'text.disabled',
              bgcolor: 'rgba(0,0,0,0.45)',
              px: 1,
              py: 0.25,
              borderRadius: '6px',
              fontSize: 10.5,
            }}
          >
            实时预览暂不可用 · no live feed
          </Typography>
        </Box>
      </Box>

      {/* status cells — 摄像头 / 标定 / LED */}
      <Box sx={{ display: 'flex', gap: 1, mt: 1.625 }}>
        <StatusCell
          label="摄像头"
          value={cameraConnected ? '已连接' : '未连接'}
          dotColor={cameraConnected ? 'primary.main' : 'error.main'}
          onClick={goToVisionSetup}
        />
        <StatusCell
          label="标定"
          value={geometryValue}
          dotColor={geometryPhaseColor(geometryPhase)}
          onClick={goToVisionSetup}
        />
        <StatusCell
          label="LED"
          value={ledConnected ? '已连接' : '未连接'}
          dotColor={ledConnected ? 'primary.main' : 'warning.main'}
          onClick={goToVisionSetup}
        />
      </Box>
    </Box>
  );
};

export default SmartBoardConsole;
