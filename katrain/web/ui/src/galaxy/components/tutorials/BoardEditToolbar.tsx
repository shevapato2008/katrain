import Box from '@mui/material/Box';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import ToggleButton from '@mui/material/ToggleButton';
import IconButton from '@mui/material/IconButton';
import Button from '@mui/material/Button';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import Tooltip from '@mui/material/Tooltip';
import UndoIcon from '@mui/icons-material/Undo';
import SaveIcon from '@mui/icons-material/Save';
import CloseIcon from '@mui/icons-material/Close';
import { useState } from 'react';
import type { EditTool, StoneEditMode, ShapeType } from '../../types/tutorial';

interface BoardEditToolbarProps {
  activeTool: EditTool;
  stoneMode: StoneEditMode;
  numbering: boolean;
  selectedShape: ShapeType;
  canUndo: boolean;
  onToolChange: (tool: EditTool) => void;
  onStoneModeChange: (mode: StoneEditMode) => void;
  onNumberingChange: (v: boolean) => void;
  onShapeChange: (s: ShapeType) => void;
  onUndo: () => void;
  onSave: () => void;
  onCancel: () => void;
}

export default function BoardEditToolbar({
  activeTool, stoneMode, numbering, selectedShape, canUndo,
  onToolChange, onStoneModeChange, onNumberingChange, onShapeChange,
  onUndo, onSave, onCancel,
}: BoardEditToolbarProps) {
  const [shapeAnchor, setShapeAnchor] = useState<null | HTMLElement>(null);

  return (
    <Box display="flex" flexWrap="wrap" gap={1} alignItems="center" py={1}>
      {/* Tool selection */}
      <ToggleButtonGroup
        value={activeTool}
        exclusive
        onChange={(_, val) => val && onToolChange(val)}
        size="small"
      >
        <ToggleButton value="stone">
          <Tooltip title="摆子"><span>●</span></Tooltip>
        </ToggleButton>
        <ToggleButton value="letter">
          <Tooltip title="字母"><span>ABC</span></Tooltip>
        </ToggleButton>
        <ToggleButton value="shape" onClick={e => { onToolChange('shape'); setShapeAnchor(e.currentTarget); }}>
          <Tooltip title="图形"><span>△</span></Tooltip>
        </ToggleButton>
        <ToggleButton value="eraser">
          <Tooltip title="橡皮擦"><span>✕</span></Tooltip>
        </ToggleButton>
      </ToggleButtonGroup>

      {/* Shape dropdown */}
      <Menu anchorEl={shapeAnchor} open={Boolean(shapeAnchor)} onClose={() => setShapeAnchor(null)}>
        <MenuItem selected={selectedShape === 'triangle'} onClick={() => { onShapeChange('triangle'); setShapeAnchor(null); }}>△ 三角形</MenuItem>
        <MenuItem selected={selectedShape === 'square'} onClick={() => { onShapeChange('square'); setShapeAnchor(null); }}>□ 正方形</MenuItem>
        <MenuItem selected={selectedShape === 'circle'} onClick={() => { onShapeChange('circle'); setShapeAnchor(null); }}>○ 圆形</MenuItem>
      </Menu>

      {/* Stone mode (only when stone tool active) */}
      {activeTool === 'stone' && (
        <>
          <ToggleButtonGroup
            value={stoneMode}
            exclusive
            onChange={(_, val) => val && onStoneModeChange(val)}
            size="small"
          >
            <ToggleButton value="black"><Tooltip title="黑子"><span>●</span></Tooltip></ToggleButton>
            <ToggleButton value="white"><Tooltip title="白子"><span>○</span></Tooltip></ToggleButton>
            <ToggleButton value="alternate"><Tooltip title="交替"><span>◐</span></Tooltip></ToggleButton>
          </ToggleButtonGroup>

          <ToggleButton
            value="numbering"
            selected={numbering}
            onChange={() => onNumberingChange(!numbering)}
            size="small"
          >
            <Tooltip title="编号"><span>123</span></Tooltip>
          </ToggleButton>
        </>
      )}

      <Box sx={{ flexGrow: 1 }} />

      {/* Actions */}
      <Tooltip title="撤销">
        <span>
          <IconButton size="small" onClick={onUndo} disabled={!canUndo}><UndoIcon /></IconButton>
        </span>
      </Tooltip>
      <Button size="small" variant="contained" startIcon={<SaveIcon />} onClick={onSave} aria-label="保存">
        保存
      </Button>
      <Button size="small" variant="outlined" startIcon={<CloseIcon />} onClick={onCancel} aria-label="取消">
        取消
      </Button>
    </Box>
  );
}
