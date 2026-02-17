import { Box, Typography, ButtonBase, Divider } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { mockKifuList } from '../data/mocks';

const KifuPage = () => {
  const navigate = useNavigate();

  return (
    <Box sx={{ display: 'flex', height: '100%' }}>
      <Box sx={{ height: '100%', aspectRatio: '1', bgcolor: 'background.paper', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRight: '1px solid', borderColor: 'divider', flexShrink: 0 }}>
        <Typography variant="body2" sx={{ color: 'text.secondary', opacity: 0.3 }}>棋谱预览</Typography>
      </Box>
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Box sx={{ p: 2, pb: 1, flexShrink: 0 }}>
          <Typography variant="h5">棋谱</Typography>
        </Box>
        <Divider />
        <Box sx={{ flex: 1, overflow: 'auto' }}>
          {mockKifuList.map((kifu) => (
            <ButtonBase
              key={kifu.id}
              onClick={() => navigate(`/kiosk/kifu/${kifu.id}`)}
              sx={{
                display: 'flex',
                width: '100%',
                justifyContent: 'space-between',
                alignItems: 'center',
                p: 2,
                borderBottom: '1px solid',
                borderColor: 'divider',
                textAlign: 'left',
                '&:active': { bgcolor: 'rgba(92, 181, 122, 0.08)' },
              }}
            >
              <Box>
                <Typography variant="body1" sx={{ fontWeight: 500 }}>
                  {kifu.black} vs {kifu.white}
                </Typography>
                <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                  {kifu.event}
                </Typography>
              </Box>
              <Typography variant="body2" sx={{ fontFamily: "'JetBrains Mono', monospace", color: 'text.secondary' }}>
                {kifu.result}
              </Typography>
            </ButtonBase>
          ))}
        </Box>
      </Box>
    </Box>
  );
};

export default KifuPage;
