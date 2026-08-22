import { Box } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../../hooks/useTranslation';
import { KioskPagebar } from '../shell/KioskPagebar';
import GeometryCalibrationWorkspace from '../components/vision/GeometryCalibrationWorkspace';

const VisionSetupPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  return (
    <Box sx={{ width: '100%', height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column', gap: 1.5, bgcolor: 'background.default' }}>
      {/* 原来这一屏**连标题都没有**,只有一个裸「返回」。标题不是新文案:
          它就是设置页里通到这儿的那个按钮自己的名字。 */}
      <KioskPagebar
        title={t('Recalibrate board', '重新标定棋盘')}
        backLabel={t('Back', '返回')}
        onBack={() => navigate(-1)}
      />
      <Box sx={{ flex: 1, minHeight: 0 }}>
        <GeometryCalibrationWorkspace mode="settings" />
      </Box>
    </Box>
  );
};

export default VisionSetupPage;
