import { Box, Typography, TextField, Select, MenuItem, FormControl, InputLabel, Button, Divider, Stack } from '@mui/material';
import ScienceIcon from '@mui/icons-material/Science';
import ResearchToolbar, { type PlaceMode, type EditMode } from './ResearchToolbar';

interface ResearchSetupPanelProps {
  playerBlack: string;
  playerWhite: string;
  onPlayerBlackChange: (name: string) => void;
  onPlayerWhiteChange: (name: string) => void;
  boardSize: number;
  onBoardSizeChange: (size: number) => void;
  rules: string;
  onRulesChange: (rules: string) => void;
  komi: number;
  onKomiChange: (komi: number) => void;
  handicap: number;
  onHandicapChange: (handicap: number) => void;
  // Toolbar props
  showMoveNumbers: boolean;
  onToggleMoveNumbers: () => void;
  onPass: () => void;
  editMode: EditMode;
  onEditModeChange: (mode: EditMode) => void;
  placeMode: PlaceMode;
  onPlaceModeChange: (mode: PlaceMode) => void;
  onClear: () => void;
  onOpen?: () => void;
  onSave?: () => void;
  onStartAnalysis: () => void;
}

export default function ResearchSetupPanel({
  playerBlack,
  playerWhite,
  onPlayerBlackChange,
  onPlayerWhiteChange,
  boardSize,
  onBoardSizeChange,
  rules,
  onRulesChange,
  komi,
  onKomiChange,
  handicap,
  onHandicapChange,
  showMoveNumbers,
  onToggleMoveNumbers,
  onPass,
  editMode,
  onEditModeChange,
  placeMode,
  onPlaceModeChange,
  onClear,
  onOpen,
  onSave,
  onStartAnalysis,
}: ResearchSetupPanelProps) {
  const inputSx = {
    '& .MuiInputBase-root': { fontSize: '0.9rem' },
    '& .MuiInputLabel-root': { fontSize: '0.9rem' },
    '& .MuiMenuItem-root': { fontSize: '0.9rem' },
  };

  const menuItemSx = { fontSize: '0.9rem' };

  return (
    <Box sx={{
      width: 500,
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      bgcolor: 'background.paper',
      borderLeft: '1px solid rgba(255,255,255,0.05)',
    }}>
      <Box sx={{ flexGrow: 1, overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
        {/* Player Info */}
        <Box sx={{ p: 2 }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1, display: 'block', fontWeight: 600, letterSpacing: 0.5 }}>
            对局信息
          </Typography>
          <Stack spacing={1.5}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Box sx={{ width: 14, height: 14, borderRadius: '50%', bgcolor: '#1a1a1a', border: '1px solid rgba(255,255,255,0.2)', flexShrink: 0 }} />
              <TextField
                size="small"
                fullWidth
                placeholder="黑方"
                value={playerBlack}
                onChange={(e) => onPlayerBlackChange(e.target.value)}
                sx={inputSx}
              />
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Box sx={{ width: 14, height: 14, borderRadius: '50%', bgcolor: '#f5f5f5', border: '1px solid #666', flexShrink: 0 }} />
              <TextField
                size="small"
                fullWidth
                placeholder="白方"
                value={playerWhite}
                onChange={(e) => onPlayerWhiteChange(e.target.value)}
                sx={inputSx}
              />
            </Box>
          </Stack>
        </Box>

        <Divider />

        {/* Rules Config */}
        <Box sx={{ p: 2 }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5, display: 'block', fontWeight: 600, letterSpacing: 0.5 }}>
            规则设置
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5 }}>
            {/* Board Size */}
            <FormControl size="small" fullWidth sx={inputSx}>
              <InputLabel>棋盘大小</InputLabel>
              <Select
                value={boardSize}
                label="棋盘大小"
                onChange={(e) => onBoardSizeChange(Number(e.target.value))}
              >
                <MenuItem value={9} sx={menuItemSx}>9×9</MenuItem>
                <MenuItem value={13} sx={menuItemSx}>13×13</MenuItem>
                <MenuItem value={19} sx={menuItemSx}>19×19</MenuItem>
              </Select>
            </FormControl>

            {/* Rules */}
            <FormControl size="small" fullWidth sx={inputSx}>
              <InputLabel>规则</InputLabel>
              <Select
                value={rules}
                label="规则"
                onChange={(e) => onRulesChange(e.target.value)}
              >
                <MenuItem value="chinese" sx={menuItemSx}>中国规则</MenuItem>
                <MenuItem value="japanese" sx={menuItemSx}>日本规则</MenuItem>
                <MenuItem value="korean" sx={menuItemSx}>韩国规则</MenuItem>
              </Select>
            </FormControl>

            {/* Komi */}
            <TextField
              size="small"
              fullWidth
              label="贴目"
              type="number"
              value={komi}
              onChange={(e) => onKomiChange(Number(e.target.value))}
              inputProps={{ step: 0.5 }}
              sx={inputSx}
            />

            {/* Handicap */}
            <FormControl size="small" fullWidth sx={inputSx}>
              <InputLabel>让子</InputLabel>
              <Select
                value={handicap}
                label="让子"
                onChange={(e) => onHandicapChange(Number(e.target.value))}
              >
                {[0, 2, 3, 4, 5, 6, 7, 8, 9].map(h => (
                  <MenuItem key={h} value={h} sx={menuItemSx}>{h === 0 ? '无' : `${h}子`}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>
        </Box>

        <Divider />

        {/* Toolbar */}
        <Box sx={{ p: 2 }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1, display: 'block', fontWeight: 600, letterSpacing: 0.5 }}>
            编辑工具
          </Typography>
          <ResearchToolbar
            isAnalyzing={false}
            showMoveNumbers={showMoveNumbers}
            onToggleMoveNumbers={onToggleMoveNumbers}
            onPass={onPass}
            editMode={editMode}
            onEditModeChange={onEditModeChange}
            placeMode={placeMode}
            onPlaceModeChange={onPlaceModeChange}
            showHints={false}
            onToggleHints={() => {}}
            showTerritory={false}
            onToggleTerritory={() => {}}
            onClear={onClear}
            onOpen={onOpen}
            onSave={onSave}
          />
        </Box>
      </Box>

      {/* Start Analysis Button - pinned to bottom */}
      <Box sx={{ p: 2, borderTop: '1px solid rgba(255,255,255,0.05)' }}>
        <Button
          variant="contained"
          fullWidth
          size="large"
          startIcon={<ScienceIcon />}
          onClick={onStartAnalysis}
          sx={{
            bgcolor: 'success.main',
            color: '#fff',
            fontWeight: 700,
            fontSize: '1rem',
            py: 1.5,
            '&:hover': { bgcolor: 'success.dark' },
          }}
        >
          开始研究
        </Button>
      </Box>
    </Box>
  );
}
