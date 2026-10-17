import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  publicDir: false,
  base: './',
  build: {
    outDir: fileURLToPath(new URL('../../../../../output/shell-stones-20261017/photo-model/site', import.meta.url)),
    emptyOutDir: true,
    chunkSizeWarningLimit: 700,
  },
});
