import { useLocation } from 'react-router-dom';
import { useTranslation } from '../../hooks/useTranslation';
import GeometryCalibrationScreen from '../components/vision/GeometryCalibrationScreen';
import { readBackTo, useBackTo } from '../hooks/useBackTo';

/**
 * 屏 26 棋盘标定 `/kiosk/vision/setup`。入口是设置屏那颗「重新标定棋盘」。
 *
 * 这一层现在只剩四个字面量 —— 页控条、摄像头画面、四步、按钮全部住在
 * `GeometryCalibrationScreen` 里,和 `PhysicalBoardGuard` 那一路**共用同一段代码**。
 * 两条路唯一的差别就是这四个字:guard 是从做题/摆谱里被拦下的,写「← 设置」是对来路撒谎。
 * 同理,做题屏的「去标定」也进这一页 —— 它写明了返回去哪儿,键上就只写「返回」。
 */
const VisionSetupPage = () => {
  const back = useBackTo('/kiosk/settings');
  const fromSettings = readBackTo(useLocation().state) === null;
  const { t } = useTranslation();
  return (
    <GeometryCalibrationScreen
      backLabel={fromSettings ? t('vision:back_settings', '设置') : t('Back', '返回')}
      onBack={back}
      title={t('vision:calibrate_title', '棋盘标定')}
      sub={t('vision:calibrate_sub', '先把棋盘清空 · 四角 + 九星共 13 个定位点')}
    />
  );
};

export default VisionSetupPage;
