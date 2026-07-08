import { Box, Typography } from '@mui/material';
import { useGeometry } from '../../context/GeometryContext';
import { useTranslation } from '../../../hooks/useTranslation';

export default function PhysicalBoardStatus() {
  const { status } = useGeometry();
  const { t } = useTranslation();
  const { camera_ready, led_ready, geometry_ready } = status.capabilities;

  const rows = [
    { key: 'camera', label: t('Camera', '摄像头'), ok: camera_ready },
    { key: 'led', label: 'LED', ok: led_ready },
    { key: 'calib', label: t('Calibration', '几何标定'), ok: geometry_ready },
  ];

  return (
    <Box>
      <Typography
        variant="body2"
        sx={{ color: status.session_calibrated ? 'warning.main' : 'text.secondary', mb: 1 }}
      >
        {status.session_calibrated ? t('Geometry locked', '几何已锁定') : t('Not calibrated', '待校准')}
      </Typography>
      {rows.map((row) => (
        <Box
          key={row.key}
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            py: 0.75,
          }}
        >
          <Typography variant="body1" sx={{ color: 'text.primary' }}>
            {row.label}
          </Typography>
          <Box
            sx={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              bgcolor: row.ok ? 'primary.main' : 'text.disabled',
            }}
          />
        </Box>
      ))}
    </Box>
  );
}
