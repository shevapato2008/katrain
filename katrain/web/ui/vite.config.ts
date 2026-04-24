/// <reference types="vitest" />
import { defineConfig } from 'vitest/config'
import { loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const kioskMode = env.VITE_KIOSK_2D_ONLY === 'true'

  return {
    plugins: [react()],
    define: {
      __KIOSK_2D_ONLY__: JSON.stringify(kioskMode),
    },
    server: {
      proxy: {
        '/api': { target: 'http://127.0.0.1:8001', changeOrigin: true },
        '/ws':  { target: 'ws://127.0.0.1:8001', ws: true },
        '/assets': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      }
    },
    build: {
      outDir: kioskMode ? '../static-kiosk-2d' : '../static',
      emptyOutDir: true,
      rollupOptions: kioskMode ? {
        external: ['three', '@react-three/fiber', '@react-three/drei'],
      } : undefined,
    },
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: './src/test/setup.ts',
      exclude: ['tests/**', 'node_modules/**'],
    },
  }
})
