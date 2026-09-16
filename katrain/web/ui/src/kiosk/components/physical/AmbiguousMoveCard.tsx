import { Button, Card, CardActions, CardContent, Typography } from '@mui/material';
import { useTranslation } from '../../../hooks/useTranslation';
import { rcToGtpLabel, rcToXy } from './BoardMismatchDialog';

interface Props {
  row: number;
  col: number;
  boardSize: number;
  /** 这一手是谁的:1=黑 2=白。说不出颜色就别说 —— 只念点位。 */
  color?: number | null;
  /**
   * 这个格子在两帧里**都没有任何检测框支撑**(worker 那边 peak conf 恰好 0.00)。
   * 含义是确定的:子没落在交叉点上,被挤到了邻格,或者压在了已有的子上。
   * 这不是「看不清」,是「没放正」—— 两种情况该说的话完全不一样。
   */
  unbacked?: boolean;
  onConfirm: (x: number, y: number) => void; // 确认 → API.playMove
  onIgnore: () => void;
}

const AmbiguousMoveCard = ({ row, col, boardSize, color, unbacked, onConfirm, onIgnore }: Props) => {
  const { t } = useTranslation();
  const point = rcToGtpLabel(row, col, boardSize);
  const who = color === 1 ? t('review:black', '黑') : color === 2 ? t('review:white', '白') : '';

  return (
    <Card sx={{ position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)', zIndex: 120, minWidth: 280, maxWidth: 420 }}>
      <CardContent sx={{ pb: 1 }}>
        {unbacked ? (
          <>
            <Typography sx={{ fontWeight: 600 }}>
              {who
                ? `${who}${t('vision:offcenter_at', ' 子没放正')}`
                : t('vision:offcenter_plain', '这颗子没放正')}
            </Typography>
            {/* 说清楚**该做什么**,而不只是报告出了什么事。位置要给 —— 满盘时
                「有颗子没放正」等于让用户自己去找。 */}
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {t('vision:offcenter_hint', '请把它挪到')} {point} {t('vision:offcenter_hint_tail', '的交叉点上,会自动识别')}
            </Typography>
          </>
        ) : (
          <Typography>
            {t('Possible move detected at', '检测到疑似落子于')} {point}
          </Typography>
        )}
      </CardContent>
      <CardActions>
        {/* 摆偏那一档里「确认落子」仍然留着:用户可能就是想下在那儿,懒得挪子。
            但它不再是唯一的出口,也不再是那句唯一的话。 */}
        <Button variant="contained" onClick={() => { const { x, y } = rcToXy(row, col, boardSize); onConfirm(x, y); }}>
          {unbacked ? `${t('vision:play_here_anyway', '就下在')} ${point}` : t('Confirm', '确认落子')}
        </Button>
        <Button onClick={onIgnore}>
          {unbacked ? t('vision:offcenter_dismiss', '我挪一下') : t('Ignore', '忽略')}
        </Button>
      </CardActions>
    </Card>
  );
};

export default AmbiguousMoveCard;
