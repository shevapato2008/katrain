import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  plugins: [react()],
  publicDir: false,
  define: { __KIOSK_2D_ONLY__: 'false' },
  build: {
    outDir: '../tutorial-media-static',
    emptyOutDir: true,
    rolldownOptions: { input: fileURLToPath(new URL('./tutorial-media.html', import.meta.url)) },
  },
});
