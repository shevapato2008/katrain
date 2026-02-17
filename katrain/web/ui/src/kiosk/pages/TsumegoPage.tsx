import { useState } from 'react';
import { Box, Typography, ButtonBase, Chip } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { mockTsumegoProblems } from '../data/mocks';

const levels = ['入门', '初级', '中级', '高级'];

const TsumegoPage = () => {
  const navigate = useNavigate();
  const [filter, setFilter] = useState('全部');
  const filtered = filter === '全部' ? mockTsumegoProblems : mockTsumegoProblems.filter((p) => p.level === filter);

  return (
    <Box sx={{ display: 'flex', height: '100%' }}>
      <Box sx={{ height: '100%', aspectRatio: '1', bgcolor: 'background.paper', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRight: '1px solid', borderColor: 'divider', flexShrink: 0 }}>
        <Typography variant="body2" sx={{ color: 'text.secondary', opacity: 0.3 }}>题目预览</Typography>
      </Box>
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Box sx={{ display: 'flex', gap: 1, p: 2, pb: 1, flexShrink: 0 }}>
          {['全部', ...levels].map((l) => (
            <Chip key={l} label={l} onClick={() => setFilter(l)} variant={filter === l ? 'filled' : 'outlined'} color={filter === l ? 'primary' : 'default'} sx={{ minHeight: 40, fontSize: '0.9rem' }} />
          ))}
        </Box>
        <Box sx={{ flex: 1, overflow: 'auto', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))', gap: 1, p: 2, pt: 1, alignContent: 'start' }}>
          {filtered.map((p) => (
            <ButtonBase key={p.id} onClick={() => navigate(`/kiosk/tsumego/problem/${p.id}`)} sx={{ minHeight: 56, borderRadius: 2, bgcolor: p.solved ? 'primary.dark' : 'background.paper', border: '1px solid', borderColor: p.solved ? 'primary.main' : 'divider', '&:active': { transform: 'scale(0.96)' } }}>
              <Typography variant="body2" sx={{ fontWeight: 500 }}>{p.label}</Typography>
            </ButtonBase>
          ))}
        </Box>
      </Box>
    </Box>
  );
};

export default TsumegoPage;
