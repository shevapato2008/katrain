import Box from '@mui/material/Box';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import UndoIcon from '@mui/icons-material/Undo';
import DeleteSweepIcon from '@mui/icons-material/DeleteSweep';
import { useState } from 'react';
import ToolGridButton from '../board/ToolGridButton';
import type { EditTool, StoneEditMode, ShapeType } from '../../../types/tutorial';
import { toolGridSx } from '../../../components/railStyles';

/* ── Stone icon components (matching ResearchToolbar style) ── */

function BlackStoneIcon({ size = 16 }: { size?: number }) {
  return (
    <Box sx={{
      width: size, height: size, borderRadius: '50%',
      bgcolor: '#1a1a1a', border: '1.5px solid rgba(255,255,255,0.2)',
      boxSizing: 'border-box', boxShadow: 'inset 0 -1px 2px rgba(255,255,255,0.1)',
    }} />
  );
}

function WhiteStoneIcon({ size = 16 }: { size?: number }) {
  return (
    <Box sx={{
      width: size, height: size, borderRadius: '50%',
      bgcolor: '#fff', border: '1.5px solid rgba(0,0,0,0.3)',
      boxSizing: 'border-box', boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.08)',
    }} />
  );
}

function AlternateIcon({ size = 16 }: { size?: number }) {
  const s = size * 0.8;
  const overlap = s * 0.35;
  return (
    <Box sx={{ width: s * 2 - overlap, height: s, position: 'relative' }}>
      <Box sx={{
        width: s, height: s, borderRadius: '50%', bgcolor: '#1a1a1a',
        position: 'absolute', left: 0, zIndex: 1,
        border: '1.5px solid rgba(255,255,255,0.2)', boxSizing: 'border-box',
      }} />
      <Box sx={{
        width: s, height: s, borderRadius: '50%', bgcolor: '#fff',
        position: 'absolute', left: s - overlap, zIndex: 2,
        border: '1.5px solid rgba(0,0,0,0.3)', boxSizing: 'border-box',
      }} />
    </Box>
  );
}

/* ── Main toolbar ── */

interface BoardEditToolbarProps {
  activeTool: EditTool;
  nextLetter: string;
  onNextLetterChange: (l: string) => void;
  stoneMode: StoneEditMode;
  numbering: boolean;
  nextMoveNumber: number;
  selectedShape: ShapeType;
  canUndo: boolean;
  onToolChange: (tool: EditTool) => void;
  onStoneModeChange: (mode: StoneEditMode) => void;
  onNumberingChange: (v: boolean) => void;
  onNextMoveNumberChange: (n: number) => void;
  onShapeChange: (s: ShapeType) => void;
  onUndo: () => void;
  onClearAll: () => void;
}

/**
 * 变化图的棋盘编辑工具条。
 *
 * 2026-08-22 迁统一版式：从「一条横向 flex、按需换行」改成右栏里的**四列工具格**，
 * 用的是全站共享的 `ToolGridButton`（Fan 的裁定：除破坏性整行按钮和滑轨外，
 * 其他按钮一律按对局室工具格的方式设计）。这同时收掉了本文件自己那份 `ToolButton`
 * —— 它是工具格按钮的第四份实现。
 *
 * **保存 / 取消不在这里了**：它们是这一屏的主动作，归右栏动作区
 * （`BoardPageShell` 的 `board-rail-actions`，不跟着滚）。编辑长图时它们原来会跟着
 * 工具条一起滚出视口。
 */
export default function BoardEditToolbar({
  activeTool, stoneMode, numbering, nextMoveNumber, nextLetter, selectedShape, canUndo,
  onToolChange, onStoneModeChange, onNumberingChange, onNextMoveNumberChange, onNextLetterChange, onShapeChange,
  onUndo, onClearAll,
}: BoardEditToolbarProps) {
  /* 图形菜单锚在被点的那个格子上。锚点存 state 而不是 ref —— 渲染期读 `ref.current`
     既是 React 的规则违例（refs 不参与渲染），也会让菜单第一次打开时锚不到东西。 */
  const [shapeAnchor, setShapeAnchor] = useState<HTMLElement | null>(null);

  const glyph = (text: string, size: number) => (
    <Typography component="span" sx={{ fontSize: size, fontWeight: 700, lineHeight: 1 }}>{text}</Typography>
  );

  return (
    <Box>
      <Box sx={toolGridSx}>
        <ToolGridButton
          icon={<BlackStoneIcon />} label="摆黑" toggle
          active={activeTool === 'stone' && stoneMode === 'black'}
          onClick={() => { onToolChange('stone'); onStoneModeChange('black'); }}
        />
        <ToolGridButton
          icon={<WhiteStoneIcon />} label="摆白" toggle
          active={activeTool === 'stone' && stoneMode === 'white'}
          onClick={() => { onToolChange('stone'); onStoneModeChange('white'); }}
        />
        <ToolGridButton
          icon={<AlternateIcon />} label="交替" toggle
          active={activeTool === 'stone' && stoneMode === 'alternate'}
          onClick={() => { onToolChange('stone'); onStoneModeChange('alternate'); }}
        />
        <ToolGridButton
          icon={glyph('123', 12)} label="编号" toggle
          active={numbering}
          onClick={() => onNumberingChange(!numbering)}
          /* 编号只对落子工具有意义；不是落子工具时说明理由，而不是留一个按下去没反应的键。 */
          disabled={activeTool !== 'stone'}
          tooltip={activeTool === 'stone' ? undefined : '先选摆黑 / 摆白 / 交替'}
        />
        <ToolGridButton
          icon={glyph('A', 13)} label="大写" toggle
          active={activeTool === 'letter_upper'}
          onClick={() => onToolChange('letter_upper')}
        />
        <ToolGridButton
          icon={glyph('a', 13)} label="小写" toggle
          active={activeTool === 'letter_lower'}
          onClick={() => onToolChange('letter_lower')}
        />
        <ToolGridButton
          icon={glyph('✕', 14)} label="橡皮" toggle
          active={activeTool === 'eraser'}
          onClick={() => onToolChange('eraser')}
        />
        <ToolGridButton
          icon={glyph('△', 14)} label="图形" toggle
          active={activeTool === 'shape'}
          onClick={(e) => { onToolChange('shape'); setShapeAnchor(e.currentTarget); }}
        />
        <ToolGridButton
          icon={<UndoIcon />} label="撤销"
          onClick={onUndo}
          disabled={!canUndo}
          tooltip={canUndo ? undefined : '还没有可撤销的改动'}
        />
        <ToolGridButton
          icon={<DeleteSweepIcon />} label="一键清空"
          onClick={onClearAll}
          isDestructive
        />
      </Box>

      {/* 两个跟着工具走的输入框：只在对应工具生效时出现，不留死输入 */}
      {activeTool === 'stone' && numbering && (
        <TextField
          size="small"
          type="number"
          label="下一手编号"
          value={nextMoveNumber}
          onChange={e => {
            const n = parseInt(e.target.value, 10);
            if (!isNaN(n) && n > 0) onNextMoveNumberChange(n);
          }}
          sx={{ mt: 1.25, width: 132 }}
          slotProps={{ htmlInput: { min: 1 } }}
        />
      )}
      {(activeTool === 'letter_upper' || activeTool === 'letter_lower') && (
        <TextField
          size="small"
          label="下一个字母"
          value={nextLetter}
          onChange={(e) => onNextLetterChange(e.target.value)}
          sx={{ mt: 1.25, width: 132 }}
        />
      )}

      {/* Shape submenu */}
      <Menu anchorEl={shapeAnchor} open={Boolean(shapeAnchor)} onClose={() => setShapeAnchor(null)}>
        <MenuItem selected={selectedShape === 'triangle'} onClick={() => { onShapeChange('triangle'); setShapeAnchor(null); }}>△ 三角形</MenuItem>
        <MenuItem selected={selectedShape === 'square'} onClick={() => { onShapeChange('square'); setShapeAnchor(null); }}>□ 正方形</MenuItem>
        <MenuItem selected={selectedShape === 'circle'} onClick={() => { onShapeChange('circle'); setShapeAnchor(null); }}>○ 圆形</MenuItem>
        <MenuItem selected={selectedShape === 'cross'} onClick={() => { onShapeChange('cross'); setShapeAnchor(null); }}>✕ 叉形</MenuItem>
      </Menu>
    </Box>
  );
}
