import { useLocation, useNavigate } from 'react-router-dom';
import { cacheSgf } from '../../api/baipuApi';
import { useTranslation } from '../../hooks/useTranslation';
import { backToState } from '../hooks/useBackTo';
import { useAuth } from '../../context/AuthContext';
import { kioskActivityStorage } from '../storage/kioskActivityStorage';
import { PhysicalBoardIcon } from '../shell/PhysicalBoardIcon';

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
  const { identityKey, isGuest, isLoading } = useAuth();
  const baipuIdentity = isGuest ? 'guest' : identityKey;
  const disabled = !sgf || boardSize !== 19 || isLoading || !baipuIdentity;
  return (
    <button
      type="button" className="physical-board-button" disabled={disabled}
      title={disabled ? boardSize !== 19
        ? t('kifu:wrong_size_reason', '这是 {n} 路的谱 —— 实体盘只摆得了 19 路').replace('{n}', String(boardSize))
        : t('kifu:need_sgf', '这一局还没读到谱') : undefined}
      onClick={() => {
        if (disabled || !sgf) return;
        cacheSgf(source, name, sgf, kioskActivityStorage(identityKey, isGuest));
        navigate(`/kiosk/baipu/session/${encodeURIComponent(source)}`, {
          state: { ...backToState(location), sgf, name, baipuIdentity, backLabel: t('report:back_report', '报告') },
        });
      }}
    ><PhysicalBoardIcon />{t('report:physical_board_short', '实体盘')}</button>
  );
}
