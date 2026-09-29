/* eslint-disable react-refresh/only-export-components -- shared coordinate helpers are also used by AmbiguousMoveCard */
import { Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, Typography } from '@mui/material';
import { useTranslation } from '../../../hooks/useTranslation';

type Pos = [number, number, number]; // [row, col, color] 1=黑 2=白

// vision 网格 (row0=顶) ↔ GTP 标签 / KaTrain (x,y)（AmbiguousMoveCard 亦复用）
export const rcToGtpLabel = (row: number, col: number, boardSize: number): string => {
  const colLabel = String.fromCharCode(65 + (col >= 8 ? col + 1 : col)); // skip I
  return `${colLabel}${boardSize - row}`;
};
export const rcToXy = (row: number, col: number, boardSize: number): { x: number; y: number } => ({
  x: col,
  y: boardSize - 1 - row,
});

interface Props {
  open: boolean;
  positions: Pos[]; // 多余/错色的物理子
  missing: Pos[]; // 该在盘上却缺失的子
  boardSize: number;
  playerToMove: string | null; // 'B' | 'W'
  onAdoptObserved: (x: number, y: number) => void; // 采纳观测（单子且轮到该色时）
  onRestored: () => void; // 恢复完成 → visionResetSync
  onNotStone: (row: number, col: number) => void;
}

const colorName = (c: number) => (c === 1 ? '黑' : '白');

const BoardMismatchDialog = ({ open, positions, missing, boardSize, playerToMove, onAdoptObserved, onRestored, onNotStone }: Props) => {
  const { t } = useTranslation();
  const adoptable =
    positions.length === 1 && missing.length === 0 && playerToMove != null &&
    ((playerToMove === 'B' && positions[0][2] === 1) || (playerToMove === 'W' && positions[0][2] === 2));
  return (
    <Dialog open={open} maxWidth="xs" fullWidth className="kiosk-game-side-dialog">
      <DialogTitle>{t('Board mismatch', '盘面与对局不一致')}</DialogTitle>
      <DialogContent>
        <Typography variant="body2">{t('game:mismatch_check_point', '请看左侧紫圈标出的交叉点，再核对实体棋盘。')}</Typography>
        {positions.length === 1 && missing.length === 0 ? (
          <Box className="kiosk-attention-point-row">
            <strong>{rcToGtpLabel(positions[0][0], positions[0][1], boardSize)}</strong>
            <span>{t('game:camera_sees_stone', '相机识别到')}{colorName(positions[0][2])}{t('game:stone_suffix', '子')}<small>{t('game:no_move_at_point', '当前棋谱在此处没有落子')}</small></span>
          </Box>
        ) : (
          <Box className="kiosk-attention-point-list">
            {positions.map(([r, c, clr]) => <span key={`e${r}-${c}`}>{t('game:extra_stone', '多出')} {colorName(clr)} {rcToGtpLabel(r, c, boardSize)}</span>)}
            {missing.map(([r, c, clr]) => <span key={`m${r}-${c}`}>{t('game:missing_stone', '缺少')} {colorName(clr)} {rcToGtpLabel(r, c, boardSize)}</span>)}
          </Box>
        )}
        <Typography variant="caption" sx={{ display: 'block', mt: 1, color: '#d9b0f5' }}>
          {t('game:mismatch_led', '实体盘对应位置闪紫灯。')}
        </Typography>
        <Typography variant="caption" sx={{ display: 'block', mt: 1, color: 'text.secondary' }}>
          {positions.length === 1 && missing.length === 0
            ? t('game:mismatch_not_stone_hint', '这里没有新棋子时，点“不是落子”；若确实落子，请调整棋子后等待自动识别。')
            : t('game:mismatch_restore_hint', '按紫圈位置调整实体棋盘，识别恢复后会自动继续。')}
        </Typography>
        {adoptable && (
          <Button size="small" sx={{ mt: 0.5, px: 0 }} onClick={() => { const { x, y } = rcToXy(positions[0][0], positions[0][1], boardSize); onAdoptObserved(x, y); }}>
            {t('Accept as my move', '确实落在这里？采纳为我的落子')}
          </Button>
        )}
      </DialogContent>
      <DialogActions sx={{ flexWrap: 'nowrap' }}>
        {positions.length === 1 && missing.length === 0 && (
          <Button variant="contained" sx={{ flex: 1, bgcolor: '#b66cf2', color: '#201329', '&:hover': { bgcolor: '#c486f1' } }}
            onClick={() => onNotStone(positions[0][0], positions[0][1])}>{t('Not a move', '不是落子')}</Button>
        )}
        <Button onClick={onRestored} variant="outlined" sx={{ flex: 1 }}>{t('Board restored', '已按提示调整')}</Button>
      </DialogActions>
    </Dialog>
  );
};

export default BoardMismatchDialog;
