/**
 * TsumegoProblemControls —— 死活题页右栏的三段内容
 *
 * 统一版式（spec §2.3）把右栏切成模块牌 / 中段（唯一可滚）/ 显示开关 / 动作区，
 * 所以这个文件导出三块，由 `TsumegoProblemPage` 分别塞进 `BoardPageShell`：
 *
 *   default 导出        中段：面包屑（由页面传进来）、本题状态、四个工具格按钮
 *   TsumegoDisplayControls  显示开关：坐标
 *   TsumegoProblemActions   动作区：上一题 / 下一题
 *
 * 工具格四个键（提示 / 试下 / 撤销 / 重置）以前是一个 outlined Button 加三个圆形
 * IconButton；按 Fan 的裁定，除「离开对局」这类和滑轨类以外的按钮一律做成对局室
 * 右栏那种带标签的方格键，所以这里改用共享的 `ToolGridButton`。
 */

import type { ReactNode } from 'react';
import { Box, Typography, Button, Divider, Switch } from '@mui/material';
import UndoIcon from '@mui/icons-material/Undo';
import RefreshIcon from '@mui/icons-material/Refresh';
import LightbulbIcon from '@mui/icons-material/Lightbulb';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import TimerIcon from '@mui/icons-material/Timer';
import TouchAppIcon from '@mui/icons-material/TouchApp';
import ToolGridButton from '../board/ToolGridButton';
import { useTranslation } from '../../../hooks/useTranslation';

// mm:ss
const formatTime = (seconds: number): string => {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
};

const StoneDot = ({ color, size }: { color: 'B' | 'W'; size: number }) => (
  <Box
    sx={{
      width: size,
      height: size,
      borderRadius: '50%',
      flex: 'none',
      bgcolor: color === 'B' ? '#1a1a1a' : '#f5f5f5',
      border: '1px solid',
      borderColor: color === 'B' ? '#333' : '#ccc',
    }}
  />
);

interface TsumegoProblemControlsProps {
  /** 面包屑由页面渲染后传进来 —— 导航是页面的事，这里只负责摆位置。 */
  breadcrumb?: ReactNode;
  hint?: string;
  showHint: boolean;
  isSolved: boolean;
  isFailed: boolean;
  isTryMode: boolean;
  elapsedTime: number;
  attempts: number;
  nextPlayer: 'B' | 'W';
  canUndo: boolean;
  onUndo: () => void;
  onReset: () => void;
  onToggleHint: () => void;
  onEnterTryMode: () => void;
  onExitTryMode: () => void;
}

const TsumegoProblemControls = ({
  breadcrumb,
  hint,
  showHint,
  isSolved,
  isFailed,
  isTryMode,
  elapsedTime,
  attempts,
  nextPlayer,
  canUndo,
  onUndo,
  onReset,
  onToggleHint,
  onEnterTryMode,
  onExitTryMode,
}: TsumegoProblemControlsProps) => {
  const { t } = useTranslation();
  const toPlay = nextPlayer === 'B' ? t('tsumego:blackToPlay') : t('tsumego:whiteToPlay');

  return (
    <Box>
      {breadcrumb != null && (
        <>
          <Box sx={{ px: 2, py: 1.5 }}>{breadcrumb}</Box>
          <Divider />
        </>
      )}

      {/* 本题：状态 + 计时 + 尝试次数 */}
      <Box sx={{ px: 2, py: 1.5 }}>
        <Typography
          variant="caption"
          sx={{ display: 'block', mb: 1, letterSpacing: '.1em', textTransform: 'uppercase', color: 'text.disabled' }}
        >
          {t('tsumego:this_problem', '本题')}
        </Typography>
        {isSolved ? (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, color: '#4caf50' }}>
            <CheckCircleIcon />
            <Typography variant="h6" sx={{ fontWeight: 'bold' }}>{t('tsumego:solved')}</Typography>
          </Box>
        ) : isFailed ? (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, color: '#e16b5c' }}>
            <CancelIcon />
            <Typography variant="h6" sx={{ fontWeight: 'bold' }}>{t('tsumego:incorrect')}</Typography>
          </Box>
        ) : (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <StoneDot color={nextPlayer} size={20} />
            <Typography variant="body1">{toPlay}</Typography>
          </Box>
        )}

        {/* 判错之后仍然要看得见轮谁走 —— 迁版式前就是这样，保留 */}
        {isFailed && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
            <StoneDot color={nextPlayer} size={16} />
            <Typography variant="body2" color="text.secondary">{toPlay}</Typography>
          </Box>
        )}

        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 1.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: 'text.secondary' }}>
            <TimerIcon fontSize="small" />
            <Typography variant="body2">{formatTime(elapsedTime)}</Typography>
          </Box>
          {/* 冻结稿里这一格在 0 次时也在，行结构不随数据跳动 */}
          <Typography variant="body2" color="text.secondary">
            {t('tsumego:attempts')}: {attempts}
          </Typography>
        </Box>
      </Box>

      <Divider />

      {/* 工具格 */}
      <Box sx={{ px: 2, py: 1.5 }}>
        {/* 四列一行 —— 冻结稿的 `tgrid` 默认 4 列、gap 6px，与研究页工具格同一档 */}
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '6px' }}>
          <ToolGridButton
            icon={<LightbulbIcon />}
            label={t('tsumego:hint', '提示')}
            ariaLabel={showHint ? t('tsumego:hideHint') : t('tsumego:showHint')}
            toggle
            active={showHint}
            onClick={onToggleHint}
          />
          <ToolGridButton
            icon={<TouchAppIcon />}
            label={t('tsumego:tryMode', '试下')}
            ariaLabel={t('tsumego:tryModeDesc')}
            toggle
            active={isTryMode}
            disabled={isSolved}
            onClick={isTryMode ? onExitTryMode : onEnterTryMode}
          />
          <ToolGridButton
            icon={<UndoIcon />}
            label={t('tsumego:undo')}
            ariaLabel={`${t('tsumego:undo')} (U)`}
            disabled={!canUndo || isSolved}
            onClick={onUndo}
          />
          <ToolGridButton
            icon={<RefreshIcon />}
            label={t('tsumego:reset')}
            ariaLabel={`${t('tsumego:reset')} (R)`}
            onClick={onReset}
          />
        </Box>

        {/* 后端 hint 字段是 String(16)，多数题只存了「黑先」；真正的提示是棋盘上那个绿点，
            所以「提示」这个键不再依赖这个字段存在与否，有字才多显示这一条。 */}
        {showHint && hint && (
          <Typography
            variant="body2"
            sx={{
              mt: 1.5,
              p: 1.5,
              bgcolor: 'rgba(232, 150, 57, 0.1)',
              borderRadius: 1,
              borderLeft: '3px solid #e89639',
            }}
          >
            {hint}
          </Typography>
        )}

        {isTryMode && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5, lineHeight: 1.7 }}>
            {t('tsumego:tryModeDesc')}
          </Typography>
        )}
      </Box>
    </Box>
  );
};

export function TsumegoDisplayControls({
  showCoordinates,
  onToggleCoordinates,
}: {
  showCoordinates: boolean;
  onToggleCoordinates: () => void;
}) {
  const { t } = useTranslation();
  return (
    <>
      <Divider />
      <Box sx={{ px: 2, py: 0.5, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="body2" color="text.secondary">{t('Coordinates', '坐标')}</Typography>
        <Switch
          size="small"
          checked={showCoordinates}
          onChange={onToggleCoordinates}
          /* MUI v7：`inputProps` 到不了里面那个 input（实测 aria-label 为 null），
             可及名要走 `slotProps.input`。 */
          slotProps={{ input: { 'aria-label': t('Coordinates', '坐标') } }}
        />
      </Box>
    </>
  );
}

export function TsumegoProblemActions({
  isSolved,
  hasPrevious,
  hasNext,
  onPrevious,
  onNext,
}: {
  isSolved: boolean;
  hasPrevious: boolean;
  hasNext: boolean;
  onPrevious: () => void;
  onNext: () => void;
}) {
  const { t } = useTranslation();
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, px: 2, py: 1.5 }}>
      <Button
        fullWidth
        variant="outlined"
        size="small"
        startIcon={<NavigateBeforeIcon />}
        onClick={onPrevious}
        disabled={!hasPrevious}
        sx={{ textTransform: 'none' }}
      >
        {t('tsumego:previousProblem')}
      </Button>
      <Button
        fullWidth
        variant={isSolved ? 'contained' : 'outlined'}
        size="small"
        endIcon={<NavigateNextIcon />}
        onClick={onNext}
        disabled={!hasNext}
        color={isSolved ? 'success' : 'primary'}
        sx={{ textTransform: 'none' }}
      >
        {t('tsumego:nextProblem')}
      </Button>
    </Box>
  );
}

export default TsumegoProblemControls;
