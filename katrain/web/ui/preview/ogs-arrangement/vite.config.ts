import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

// Build only this TEST artifact. Its index is separate from the application's
// authenticated production index and never replaces the deployed static UI.
export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  envDir: fileURLToPath(new URL('../..', import.meta.url)),
  plugins: [react()],
  publicDir: false,
  define: { __KIOSK_2D_ONLY__: 'true' },
  build: { outDir: 'dist', emptyOutDir: true },
});
