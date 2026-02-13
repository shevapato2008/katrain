import { Box, Typography, Tooltip, keyframes } from '@mui/material';
import DeleteForeverIcon from '@mui/icons-material/DeleteForever';
import CropFreeIcon from '@mui/icons-material/CropFree';
import LayersClearIcon from '@mui/icons-material/LayersClear';
import type { AiSolverTool } from '../../hooks/useAiSolverBoard';

const blink = keyframes`
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
`;

const ICON_SIZE = 22;

function BlackStoneIcon({ size = 18 }: { size?: number }) {
  return (
    <Box sx={{
      width: size, height: size, borderRadius: '50%',
      bgcolor: '#1a1a1a', border: '1.5px solid rgba(255,255,255,0.2)',
      boxSizing: 'border-box', boxShadow: 'inset 0 -1px 2px rgba(255,255,255,0.1)',
    }} />
  );
}

function WhiteStoneIcon({ size = 18 }: { size?: number }) {
  return (
    <Box sx={{
      width: size, height: size, borderRadius: '50%',
      bgcolor: '#fff', border: '1.5px solid rgba(0,0,0,0.3)',
      boxSizing: 'border-box', boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.08)',
    }} />
  );
}

function AlternateIcon({ size = 18 }: { size?: number }) {
  const stoneSize = size * 0.8;
  const overlap = stoneSize * 0.35;
  const totalWidth = stoneSize * 2 - overlap;
  return (
    <Box sx={{ width: totalWidth, height: stoneSize, position: 'relative', display: 'flex', alignItems: 'center' }}>
      <Box sx={{
        width: stoneSize, height: stoneSize, borderRadius: '50%',
        bgcolor: '#1a1a1a', position: 'absolute', left: 0, zIndex: 1,
        border: '1.5px solid rgba(255,255,255,0.2)', boxSizing: 'border-box',
        boxShadow: 'inset 0 -1px 2px rgba(255,255,255,0.1)',
      }} />
      <Box sx={{
        width: stoneSize, height: stoneSize, borderRadius: '50%',
        bgcolor: '#fff', position: 'absolute', left: stoneSize - overlap, zIndex: 2,
        border: '1.5px solid rgba(0,0,0,0.3)', boxSizing: 'border-box',
        boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.08)',
      }} />
    </Box>
  );
}

interface AiSolverToolbarProps {
  activeTool: AiSolverTool;
  onToolChange: (tool: AiSolverTool) => void;
  onClear: () => void;
}

export default function AiSolverToolbar({ activeTool, onToolChange, onClear }: AiSolverToolbarProps) {
  const handleToolClick = (tool: AiSolverTool) => {
    onToolChange(activeTool === tool ? null : tool);
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)' }}>
        <ToolButton
          icon={<BlackStoneIcon size={18} />}
          label="摆黑"
          active={activeTool === 'placeBlack'}
          onClick={() => handleToolClick('placeBlack')}
        />
        <ToolButton
          icon={<WhiteStoneIcon size={18} />}
          label="摆白"
          active={activeTool === 'placeWhite'}
          onClick={() => handleToolClick('placeWhite')}
        />
        <ToolButton
          icon={<AlternateIcon size={20} />}
          label="交替"
          active={activeTool === 'alternate'}
          onClick={() => handleToolClick('alternate')}
        />
        <ToolButton
          icon={<DeleteForeverIcon sx={{ fontSize: ICON_SIZE }} />}
          label="删除"
          active={activeTool === 'delete'}
          onClick={() => handleToolClick('delete')}
          isDestructive
        />
      </Box>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)' }}>
        <ToolButton
          icon={<CropFreeIcon sx={{ fontSize: ICON_SIZE }} />}
          label="画框"
          active={activeTool === 'drawRect'}
          onClick={() => handleToolClick('drawRect')}
        />
        <Box /> {/* reserved */}
        <Box /> {/* reserved */}
        <ToolButton
          icon={<LayersClearIcon sx={{ fontSize: ICON_SIZE }} />}
          label="清空"
          active={false}
          onClick={onClear}
        />
      </Box>
    </Box>
  );
}

function ToolButton({ icon, label, active, onClick, disabled, loading, isDestructive }: {
  icon: React.ReactNode;
  label: string;
  active: boolean;
  onClick: (e: React.MouseEvent) => void;
  disabled?: boolean;
  loading?: boolean;
  isDestructive?: boolean;
}) {
  return (
    <Tooltip title={disabled ? '' : label}>
      <Box
        onClick={(e) => !disabled && onClick(e)}
        sx={{
          py: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: disabled ? 'default' : 'pointer',
          bgcolor: active && !disabled
            ? (isDestructive ? 'rgba(211, 47, 47, 0.15)' : 'rgba(74, 107, 92, 0.2)')
            : 'rgba(255,255,255,0.04)',
          color: active && !disabled
            ? (isDestructive ? 'error.main' : 'primary.light')
            : (isDestructive ? 'error.main' : 'text.primary'),
          opacity: disabled ? 0.3 : 1,
          border: '1px solid',
          borderColor: active && !disabled
            ? (isDestructive ? 'error.main' : 'primary.main')
            : 'rgba(255,255,255,0.06)',
          animation: loading ? `${blink} 1s ease-in-out infinite` : 'none',
          transition: 'all 0.15s ease',
          '&:hover': {
            bgcolor: disabled
              ? 'rgba(255,255,255,0.04)'
              : (active
                ? (isDestructive ? 'rgba(211, 47, 47, 0.25)' : 'rgba(74, 107, 92, 0.3)')
                : 'rgba(255,255,255,0.08)'),
          },
        }}
      >
        {icon}
        <Typography variant="caption" sx={{ mt: 0.5, fontSize: '0.8rem', lineHeight: 1.2 }}>
          {label}
        </Typography>
      </Box>
    </Tooltip>
  );
}
