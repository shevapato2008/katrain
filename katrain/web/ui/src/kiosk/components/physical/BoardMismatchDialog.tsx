import { Button, Dialog, DialogActions, DialogContent, DialogTitle, List, ListItem, Typography } from '@mui/material';
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
  onDismiss: () => void;
}

const colorName = (c: number) => (c === 1 ? '黑' : '白');

const BoardMismatchDialog = ({ open, positions, missing, boardSize, playerToMove, onAdoptObserved, onRestored, onDismiss }: Props) => {
  const { t } = useTranslation();
  const adoptable =
    positions.length === 1 && missing.length === 0 && playerToMove != null &&
    ((playerToMove === 'B' && positions[0][2] === 1) || (playerToMove === 'W' && positions[0][2] === 2));
  return (
    <Dialog open={open} maxWidth="xs" fullWidth>
      <DialogTitle>{t('Board mismatch', '盘面与对局不一致')}</DialogTitle>
      <DialogContent>
        {positions.length > 0 && (
          <>
            <Typography variant="subtitle2" color="error">{t('Remove these stones', '请拿走（蓝灯处）')}</Typography>
            <List dense>
              {positions.map(([r, c, clr]) => (
                <ListItem key={`e${r}-${c}`}>{`${colorName(clr)} ${rcToGtpLabel(r, c, boardSize)}`}</ListItem>
              ))}
            </List>
          </>
        )}
        {missing.length > 0 && (
          <>
            <Typography variant="subtitle2" color="warning.main">{t('Place these stones', '请摆上（红/绿灯处）')}</Typography>
            <List dense>
              {missing.map(([r, c, clr]) => (
                <ListItem key={`m${r}-${c}`}>{`${colorName(clr)} ${rcToGtpLabel(r, c, boardSize)}`}</ListItem>
              ))}
            </List>
          </>
        )}
      </DialogContent>
      <DialogActions>
        {adoptable && (
          <Button onClick={() => { const { x, y } = rcToXy(positions[0][0], positions[0][1], boardSize); onAdoptObserved(x, y); }}>
            {t('Accept as my move', '采纳为我的落子')}
          </Button>
        )}
        <Button onClick={onRestored} variant="contained">{t('Board restored', '已按指示恢复')}</Button>
        <Button onClick={onDismiss}>{t('Ignore', '忽略')}</Button>
      </DialogActions>
    </Dialog>
  );
};

export default BoardMismatchDialog;
