import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import PerformanceFixture from './PerformanceFixture';

createRoot(document.getElementById('root')!).render(<StrictMode><PerformanceFixture /></StrictMode>);
