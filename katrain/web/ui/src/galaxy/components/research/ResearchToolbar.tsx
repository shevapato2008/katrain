import { Box, Typography, Tooltip, keyframes, Menu, MenuItem, ListItemIcon, ListItemText, Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions, Button } from '@mui/material';
import { useState } from 'react';
import FormatListNumberedIcon from '@mui/icons-material/FormatListNumbered';
import PanToolAltIcon from '@mui/icons-material/PanToolAlt';
import OpenWithIcon from '@mui/icons-material/OpenWith';
import DeleteForeverIcon from '@mui/icons-material/DeleteForever';
import TipsAndUpdatesIcon from '@mui/icons-material/TipsAndUpdates';
import MapIcon from '@mui/icons-material/Map';
import LayersClearIcon from '@mui/icons-material/LayersClear';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import SaveIcon from '@mui/icons-material/Save';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import CloudDownloadIcon from '@mui/icons-material/CloudDownload';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';

const blink = keyframes`
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
`;

export type PlaceMode = 'alternate' | 'black' | 'white' | null;
export type EditMode = 'place' | 'move' | 'delete' | null;

interface ResearchToolbarProps {
  isAnalyzing: boolean;
  showMoveNumbers: boolean;
  onToggleMoveNumbers: () => void;
  onPass: () => void;
  editMode: EditMode;
  onEditModeChange: (mode: EditMode) => void;
  placeMode: PlaceMode;
  onPlaceModeChange: (mode: PlaceMode) => void;
  showHints: boolean;
  onToggleHints: () => void;
  showTerritory: boolean;
  onToggleTerritory: () => void;
  onClear: () => void;
  onOpen?: () => void;
  onSave?: () => void;
  onCopyToClipboard?: () => void;
  onSaveToCloud?: () => void;
  onOpenFromCloud?: () => void;
  isAnalysisPending?: boolean;
}

const ICON_SIZE = 22;

// Custom icon: pure black filled stone
function BlackStoneIcon({ size = 18 }: { size?: number }) {
  return (
    <Box sx={{
      width: size,
      height: size,
      borderRadius: '50%',
      bgcolor: '#1a1a1a',
      border: '1.5px solid rgba(255,255,255,0.2)',
      boxSizing: 'border-box',
      boxShadow: 'inset 0 -1px 2px rgba(255,255,255,0.1)',
    }} />
  );
}

// Custom icon: pure white filled stone
function WhiteStoneIcon({ size = 18 }: { size?: number }) {
  return (
    <Box sx={{
      width: size,
      height: size,
      borderRadius: '50%',
      bgcolor: '#fff',
      border: '1.5px solid rgba(0,0,0,0.3)',
      boxSizing: 'border-box',
      boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.08)',
    }} />
  );
}

// Custom icon: black + white stones side by side (alternating mode)
function AlternateIcon({ size = 18 }: { size?: number }) {
  const stoneSize = size * 0.8;
  const overlap = stoneSize * 0.35;
  const totalWidth = stoneSize * 2 - overlap;
  return (
    <Box sx={{ width: totalWidth, height: stoneSize, position: 'relative', display: 'flex', alignItems: 'center' }}>
      {/* Black stone (left) */}
      <Box sx={{
        width: stoneSize,
        height: stoneSize,
        borderRadius: '50%',
        bgcolor: '#1a1a1a',
        position: 'absolute',
        left: 0,
        zIndex: 1,
        border: '1.5px solid rgba(255,255,255,0.2)',
        boxSizing: 'border-box',
        boxShadow: 'inset 0 -1px 2px rgba(255,255,255,0.1)',
      }} />
      {/* White stone (right, overlapping) */}
      <Box sx={{
        width: stoneSize,
        height: stoneSize,
        borderRadius: '50%',
        bgcolor: '#fff',
        position: 'absolute',
        left: stoneSize - overlap,
        zIndex: 2,
        border: '1.5px solid rgba(0,0,0,0.3)',
        boxSizing: 'border-box',
        boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.08)',
      }} />
    </Box>
  );
}

export default function ResearchToolbar({
  isAnalyzing,
  showMoveNumbers,
  onToggleMoveNumbers,
  onPass,
  editMode,
  onEditModeChange,
  placeMode,
  onPlaceModeChange,
  showHints,
  onToggleHints,
  showTerritory,
  onToggleTerritory,
  onClear,
  onOpen,
  onSave,
  onCopyToClipboard,
  onSaveToCloud,
  onOpenFromCloud,
  isAnalysisPending = false,
}: ResearchToolbarProps) {
  const [openAnchor, setOpenAnchor] = useState<null | HTMLElement>(null);
  const [saveAnchor, setSaveAnchor] = useState<null | HTMLElement>(null);
  const [passConfirmOpen, setPassConfirmOpen] = useState(false);

  // Selecting a placeMode deselects editMode, and vice versa
  const handlePlaceMode = (mode: PlaceMode) => {
    if (placeMode === mode) {
      // Toggle off: deselect
      onPlaceModeChange(null);
    } else {
      onPlaceModeChange(mode);
      if (editMode) onEditModeChange(null); // clear edit mode
    }
  };

  const handleEditMode = (mode: EditMode) => {
    if (editMode === mode) {
      onEditModeChange(null);
    } else {
      onEditModeChange(mode);
      if (placeMode) onPlaceModeChange(null); // clear place mode
    }
  };

  const handlePassConfirm = () => {
    setPassConfirmOpen(false);
    onPass();
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
      {/* Row 1: Edit tools — 4 per row, no gap */}
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)' }}>
        <ToolButton
          icon={<FormatListNumberedIcon sx={{ fontSize: ICON_SIZE }} />}
          label="手数"
          active={showMoveNumbers}
          onClick={onToggleMoveNumbers}
        />
        <ToolButton
          icon={<PanToolAltIcon sx={{ fontSize: ICON_SIZE }} />}
          label="停一手"
          active={false}
          onClick={() => setPassConfirmOpen(true)}
        />
        <ToolButton
          icon={<OpenWithIcon sx={{ fontSize: ICON_SIZE }} />}
          label="移动"
          active={editMode === 'move'}
          onClick={() => handleEditMode('move')}
        />
        <ToolButton
          icon={<DeleteForeverIcon sx={{ fontSize: ICON_SIZE }} />}
          label="删除"
          active={editMode === 'delete'}
          onClick={() => handleEditMode('delete')}
          isDestructive
        />
        <ToolButton
          icon={<BlackStoneIcon size={18} />}
          label="摆黑"
          active={placeMode === 'black'}
          onClick={() => handlePlaceMode('black')}
        />
        <ToolButton
          icon={<WhiteStoneIcon size={18} />}
          label="摆白"
          active={placeMode === 'white'}
          onClick={() => handlePlaceMode('white')}
        />
        <ToolButton
          icon={<AlternateIcon size={20} />}
          label="交替"
          active={placeMode === 'alternate'}
          onClick={() => handlePlaceMode('alternate')}
        />
        <ToolButton
          icon={<LayersClearIcon sx={{ fontSize: ICON_SIZE }} />}
          label="清空"
          active={false}
          onClick={onClear}
        />
      </Box>

      {/* Row 2: Analysis + File tools — 4 per row, no gap */}
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)' }}>
        <ToolButton
          icon={<TipsAndUpdatesIcon sx={{ fontSize: ICON_SIZE }} />}
          label="提示"
          active={showHints}
          onClick={onToggleHints}
          disabled={!isAnalyzing}
          loading={isAnalysisPending && showHints}
        />
        <ToolButton
          icon={<MapIcon sx={{ fontSize: ICON_SIZE }} />}
          label="领地"
          active={showTerritory}
          onClick={onToggleTerritory}
          disabled={!isAnalyzing}
        />
        <ToolButton
          icon={<FolderOpenIcon sx={{ fontSize: ICON_SIZE }} />}
          label="打开"
          active={false}
          onClick={(e) => setOpenAnchor(e.currentTarget as HTMLElement)}
        />
        <ToolButton
          icon={<SaveIcon sx={{ fontSize: ICON_SIZE }} />}
          label="保存"
          active={false}
          onClick={(e) => setSaveAnchor(e.currentTarget as HTMLElement)}
        />
      </Box>

      {/* Open dropdown menu */}
      <Menu
        anchorEl={openAnchor}
        open={Boolean(openAnchor)}
        onClose={() => setOpenAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        transformOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <MenuItem sx={{ fontSize: '0.875rem' }} onClick={() => { onOpen?.(); setOpenAnchor(null); }}>
          <ListItemIcon><UploadFileIcon sx={{ fontSize: 18 }} /></ListItemIcon>
          <ListItemText primaryTypographyProps={{ fontSize: '0.875rem' }}>打开本地 SGF</ListItemText>
        </MenuItem>
        <MenuItem sx={{ fontSize: '0.875rem' }} onClick={() => { onOpenFromCloud?.(); setOpenAnchor(null); }}>
          <ListItemIcon><CloudDownloadIcon sx={{ fontSize: 18 }} /></ListItemIcon>
          <ListItemText primaryTypographyProps={{ fontSize: '0.875rem' }}>从棋谱库导入</ListItemText>
        </MenuItem>
      </Menu>

      {/* Save dropdown menu */}
      <Menu
        anchorEl={saveAnchor}
        open={Boolean(saveAnchor)}
        onClose={() => setSaveAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        transformOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <MenuItem sx={{ fontSize: '0.875rem' }} onClick={() => { onSave?.(); setSaveAnchor(null); }}>
          <ListItemIcon><SaveIcon sx={{ fontSize: 18 }} /></ListItemIcon>
          <ListItemText primaryTypographyProps={{ fontSize: '0.875rem' }}>保存 SGF</ListItemText>
        </MenuItem>
        <MenuItem sx={{ fontSize: '0.875rem' }} onClick={() => { onSaveToCloud?.(); setSaveAnchor(null); }}>
          <ListItemIcon><CloudUploadIcon sx={{ fontSize: 18 }} /></ListItemIcon>
          <ListItemText primaryTypographyProps={{ fontSize: '0.875rem' }}>保存到棋谱库</ListItemText>
        </MenuItem>
        <MenuItem sx={{ fontSize: '0.875rem' }} onClick={() => { onCopyToClipboard?.(); setSaveAnchor(null); }}>
          <ListItemIcon><ContentCopyIcon sx={{ fontSize: 18 }} /></ListItemIcon>
          <ListItemText primaryTypographyProps={{ fontSize: '0.875rem' }}>复制 SGF 到剪贴板</ListItemText>
        </MenuItem>
      </Menu>

      {/* Pass confirmation dialog */}
      <Dialog open={passConfirmOpen} onClose={() => setPassConfirmOpen(false)}>
        <DialogTitle>停一手</DialogTitle>
        <DialogContent>
          <DialogContentText>确认在当前位置插入一个 Pass（停一手）？</DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPassConfirmOpen(false)} color="inherit" size="small">取消</Button>
          <Button onClick={handlePassConfirm} variant="contained" size="small" autoFocus>确认</Button>
        </DialogActions>
      </Dialog>
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
