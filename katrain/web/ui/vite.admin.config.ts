import { resolve } from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  publicDir: false,
  server: {
    host: '127.0.0.1',
    port: 5174,
    strictPort: true,
    proxy: {
      '/api/admin': { target: 'http://127.0.0.1:8010', changeOrigin: true },
      '/api/v1/tutorials': { target: 'http://127.0.0.1:8010', changeOrigin: true },
    },
  },
  build: {
    outDir: '../static-admin',
    emptyOutDir: true,
    rollupOptions: { input: resolve(import.meta.dirname, 'admin.html') },
  },
})
