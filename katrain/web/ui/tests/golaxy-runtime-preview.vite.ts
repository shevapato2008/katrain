// Preview-only dev server. Production uses vite.config.ts.
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
const repo = resolve(process.cwd(), '../../..');
const assets = { '/assets/img/logo-white.png': 'img/logo-white.png', '/assets/img/board.png': 'img/board.png' };
export default defineConfig({ plugins: [react(), { name: 'preview-assets', configureServer(server) {
 server.middlewares.use(async (req,res,next) => {
  const asset = assets[req.url as keyof typeof assets];
  if (!asset) return next();
  res.setHeader('Content-Type','image/png');
  res.end(await readFile(resolve(repo,'katrain',asset)));
 });
}}], define: { __KIOSK_2D_ONLY__: 'false' }, server: { fs: { allow:[repo] } } });
