import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../../hooks/useTranslation';
import GeometryCalibrationScreen from '../components/vision/GeometryCalibrationScreen';

/**
 * 屏 26 棋盘标定 `/kiosk/vision/setup`。入口是设置屏那颗「重新标定棋盘」。
 *
 * 这一层现在只剩四个字面量 —— 页控条、摄像头画面、四步、按钮全部住在
 * `GeometryCalibrationScreen` 里,和 `PhysicalBoardGuard` 那一路**共用同一段代码**。
 * 两条路唯一的差别就是这四个字:guard 是从做题/摆谱里被拦下的,写「← 设置」是对来路撒谎。
 */
const VisionSetupPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  return (
    <GeometryCalibrationScreen
      backLabel={t('vision:back_settings', '设置')}
      onBack={() => navigate(-1)}
      title={t('vision:calibrate_title', '棋盘标定')}
      sub={t('vision:calibrate_sub', '先把棋盘清空 · 四角 + 九星共 13 个定位点')}
    />
  );
};

export default VisionSetupPage;
