import { Box, Button } from '@mui/material';
import { ArrowBack } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import GeometryCalibrationWorkspace from '../components/vision/GeometryCalibrationWorkspace';

const VisionSetupPage = () => {
  const navigate = useNavigate();
  return (
    <Box sx={{ width: '100%', height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column', gap: 1.5, p: 2, bgcolor: 'background.default' }}>
      <Box>
        <Button variant="text" color="inherit" startIcon={<ArrowBack />} onClick={() => navigate(-1)} sx={{ color: 'text.secondary' }}>返回</Button>
      </Box>
      <Box sx={{ flex: 1, minHeight: 0 }}>
        <GeometryCalibrationWorkspace mode="settings" />
      </Box>
    </Box>
  );
};

export default VisionSetupPage;
