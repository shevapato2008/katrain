import { Routes, Route, Navigate } from 'react-router-dom';
import MainLayout from './galaxy/components/layout/MainLayout';
import Dashboard from './galaxy/pages/Dashboard';
import { Box, Typography } from '@mui/material';

const PlaceholderPage = ({ title }: { title: string }) => (
    <Box sx={{ p: 4 }}><Typography variant="h4">{title}</Typography></Box>
);

const GalaxyApp = () => {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="play" element={<PlaceholderPage title="Play Menu" />} />
        <Route path="play/ai" element={<PlaceholderPage title="Human vs AI" />} />
        <Route path="play/human" element={<PlaceholderPage title="Human vs Human" />} />
        <Route path="research" element={<PlaceholderPage title="Research" />} />
        <Route path="*" element={<Navigate to="/galaxy" replace />} />
      </Route>
    </Routes>
  );
};

export default GalaxyApp;
