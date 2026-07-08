import { Box, Typography, TextField, Select, MenuItem, FormControl, InputLabel, Button, Divider, Stack } from '@mui/material';
import ScienceIcon from '@mui/icons-material/Science';
import ResearchToolbar, { type PlaceMode, type EditMode } from './ResearchToolbar';
import { useTranslation } from '../../../hooks/useTranslation';

interface ResearchSetupPanelProps {
  playerBlack: string;
  playerWhite: string;
  onPlayerBlackChange: (name: string) => void;
  onPlayerWhiteChange: (name: string) => void;
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
  showHints: boolean;
  onToggleHints: () => void;
  showTerritory: boolean;
  onToggleTerritory: () => void;
  isAnalysisPending?: boolean;
  onClear: () => void;
  onOpen?: () => void;
  onSave?: () => void;
  onCopyToClipboard?: () => void;
  onOpenFromCloud?: () => void;
  onStartAnalysis: () => void;
}

export default function ResearchSetupPanel({
  playerBlack,
  playerWhite,
  onPlayerBlackChange,
  onPlayerWhiteChange,
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
  showHints,
  onToggleHints,
  showTerritory,
  onToggleTerritory,
  isAnalysisPending,
  onClear,
  onOpen,
  onSave,
  onCopyToClipboard,
  onOpenFromCloud,
  onStartAnalysis,
}: ResearchSetupPanelProps) {
  const { t } = useTranslation();
  const inputSx = {
    '& .MuiInputBase-root': { fontSize: '0.9rem' },
    '& .MuiInputLabel-root': { fontSize: '0.9rem' },
    '& .MuiMenuItem-root': { fontSize: '0.9rem' },
  };

  const menuItemSx = { fontSize: '0.9rem' };

  return (
    <Box sx={{
      width: 340,
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      bgcolor: 'background.paper',
      borderLeft: '1px solid',
      borderColor: 'divider',
    }}>
      <Box sx={{ flexGrow: 1, overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
        {/* Player Info */}
        <Box sx={{ p: 2 }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1, display: 'block', fontWeight: 600, letterSpacing: 0.5 }}>
            {t('research:game_info', '对局信息')}
          </Typography>
          <Stack spacing={1.5}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Box sx={{ width: 14, height: 14, borderRadius: '50%', bgcolor: '#1a1a1a', border: '1px solid rgba(255,255,255,0.2)', flexShrink: 0 }} />
              <TextField
                size="small"
                fullWidth
                placeholder={t('research:black', '黑方')}
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
                placeholder={t('research:white', '白方')}
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
            {t('research:rules_settings', '规则设置')}
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5 }}>
            {/* Rules */}
            <FormControl size="small" fullWidth sx={inputSx}>
              <InputLabel>{t('research:rules', '规则')}</InputLabel>
              <Select
                value={rules}
                label={t('research:rules', '规则')}
                onChange={(e) => onRulesChange(e.target.value)}
              >
                <MenuItem value="chinese" sx={menuItemSx}>{t('research:rules_chinese', '中国规则')}</MenuItem>
                <MenuItem value="japanese" sx={menuItemSx}>{t('research:rules_japanese', '日本规则')}</MenuItem>
                <MenuItem value="korean" sx={menuItemSx}>{t('research:rules_korean', '韩国规则')}</MenuItem>
              </Select>
            </FormControl>

            {/* Komi */}
            <TextField
              size="small"
              fullWidth
              label={t('research:komi_label', '贴目')}
              type="number"
              value={komi}
              onChange={(e) => onKomiChange(Number(e.target.value))}
              inputProps={{ step: 0.5 }}
              sx={inputSx}
            />

            {/* Handicap */}
            <FormControl size="small" fullWidth sx={inputSx}>
              <InputLabel>{t('research:handicap_label', '让子')}</InputLabel>
              <Select
                value={handicap}
                label={t('research:handicap_label', '让子')}
                onChange={(e) => onHandicapChange(Number(e.target.value))}
              >
                {[0, 2, 3, 4, 5, 6, 7, 8, 9].map(h => (
                  <MenuItem key={h} value={h} sx={menuItemSx}>{h === 0 ? t('research:none', '无') : t('research:n_stones', '{n}子').replace('{n}', String(h))}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>
        </Box>

        <Divider />

        {/* Toolbar */}
        <Box sx={{ p: 2 }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1, display: 'block', fontWeight: 600, letterSpacing: 0.5 }}>
            {t('research:edit_tools', '编辑工具')}
          </Typography>
          <ResearchToolbar
            isAnalyzing={true}
            showMoveNumbers={showMoveNumbers}
            onToggleMoveNumbers={onToggleMoveNumbers}
            onPass={onPass}
            editMode={editMode}
            onEditModeChange={onEditModeChange}
            placeMode={placeMode}
            onPlaceModeChange={onPlaceModeChange}
            showHints={showHints}
            onToggleHints={onToggleHints}
            showTerritory={showTerritory}
            onToggleTerritory={onToggleTerritory}
            isAnalysisPending={isAnalysisPending}
            onClear={onClear}
            onOpen={onOpen}
            onSave={onSave}
            onCopyToClipboard={onCopyToClipboard}
            onOpenFromCloud={onOpenFromCloud}
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
            bgcolor: 'primary.main',
            color: '#0d1a13',
            fontWeight: 700,
            fontSize: '1rem',
            py: 1.5,
            '&:hover': { bgcolor: 'primary.dark' },
          }}
        >
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', lineHeight: 1.3 }}>
            <Box component="span">{t('research:start_research', '开始研究')}</Box>
            <Box component="span" sx={{ fontWeight: 500, fontSize: '0.72rem', opacity: 0.72 }}>
              {t('research:start_research_subtitle', '全局扫描 · 500 visits/手')}
            </Box>
          </Box>
        </Button>
      </Box>
    </Box>
  );
}
