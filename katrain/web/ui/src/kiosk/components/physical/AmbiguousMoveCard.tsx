import { Button, Card, CardActions, CardContent, Typography } from '@mui/material';
import { useTranslation } from '../../../hooks/useTranslation';
import { rcToGtpLabel, rcToXy } from './BoardMismatchDialog';

interface Props {
  row: number;
  col: number;
  boardSize: number;
  onConfirm: (x: number, y: number) => void; // 确认 → API.playMove
  onIgnore: () => void;
}

const AmbiguousMoveCard = ({ row, col, boardSize, onConfirm, onIgnore }: Props) => {
  const { t } = useTranslation();
  return (
    <Card sx={{ position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)', zIndex: 120, minWidth: 280 }}>
      <CardContent>
        <Typography>
          {t('Possible move detected at', '检测到疑似落子于')} {rcToGtpLabel(row, col, boardSize)}
        </Typography>
      </CardContent>
      <CardActions>
        <Button variant="contained" onClick={() => { const { x, y } = rcToXy(row, col, boardSize); onConfirm(x, y); }}>
          {t('Confirm', '确认落子')}
        </Button>
        <Button onClick={onIgnore}>{t('Ignore', '忽略')}</Button>
      </CardActions>
    </Card>
  );
};

export default AmbiguousMoveCard;
