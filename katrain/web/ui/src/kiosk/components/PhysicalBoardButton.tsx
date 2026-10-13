import { useLocation, useNavigate } from 'react-router-dom';
import { cacheSgf } from '../../api/baipuApi';
import { useTranslation } from '../../hooks/useTranslation';
import { backToState } from '../hooks/useBackTo';

interface Props {
  source: string;
  name: string;
  sgf: string | null | undefined;
  boardSize: number;
}

/** Reports enter the existing camera/LED replay session with their complete SGF. */
export default function PhysicalBoardButton({ source, name, sgf, boardSize }: Props) {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const disabled = !sgf || boardSize !== 19;
  return (
    <button
      type="button" className="physical-board-button" disabled={disabled}
      title={disabled ? boardSize !== 19
        ? t('kifu:wrong_size_reason', '这是 {n} 路的谱 —— 实体盘只摆得了 19 路').replace('{n}', String(boardSize))
        : t('kifu:need_sgf', '这一局还没读到谱') : undefined}
      onClick={() => {
        if (disabled || !sgf) return;
        cacheSgf(source, name, sgf);
        navigate(`/kiosk/baipu/session/${encodeURIComponent(source)}`, {
          state: { ...backToState(location), sgf, name, backLabel: t('report:back_report', '报告') },
        });
      }}
    >{t('report:physical_board', '实体棋盘')}</button>
  );
}
