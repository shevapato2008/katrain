import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  publicDir: false,
  base: './',
  server: { host: '127.0.0.1', port: 4179, strictPort: true },
  build: {
    outDir: fileURLToPath(new URL('../../../../../output/shell-stones-20261017/site', import.meta.url)),
    emptyOutDir: true,
    chunkSizeWarningLimit: 650,
  },
});
