import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider, CssBaseline } from '@mui/material';
import { zenTheme } from './theme';
import ZenModeApp from './ZenModeApp';
import GalaxyApp from './GalaxyApp';

const AppRouter = () => {
  return (
    <ThemeProvider theme={zenTheme}>
      <CssBaseline />
      <BrowserRouter>
        <Routes>
          <Route path="/galaxy/*" element={<GalaxyApp />} />
          <Route path="/*" element={<ZenModeApp />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
};

export default AppRouter;
