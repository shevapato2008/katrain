/// <reference types="vitest" />
import { defineConfig } from 'vitest/config'
// loadEnv is not re-exported by vitest/config, so import directly from vite
import { loadEnv, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'

// Kiosk-only: media is served from a hotlink-protected gateway that 403s any
// non-origin Referer. The kiosk runs on the board origin (not the media domain),
// and <video>/<audio> don't honor a referrerpolicy attribute, so strip the
// Referer document-wide for the kiosk build via a head meta tag. Galaxy (served
// from the media's own domain) keeps its default referrer behavior.
const kioskNoReferrerMeta: Plugin = {
  name: 'kiosk-no-referrer-meta',
  transformIndexHtml() {
    return [{ tag: 'meta', attrs: { name: 'referrer', content: 'no-referrer' }, injectTo: 'head' }]
  },
}

// Discover this surface's static dependencies in the HTML response, avoiding
// the index -> lazy app -> shared widgets waterfall on a cold library.
const libraryModulePreload: Plugin = {
  name: 'library-module-preload',
  transformIndexHtml: {
    order: 'post',
    handler(_html, context) {
      if (!context.bundle) return;
      const bundle = context.bundle;
      const surfaces: Record<string, string[]> = {};
      for (const [surface, module] of [['galaxy', '/GalaxyApp.tsx'], ['kiosk', '/kiosk/KioskApp.tsx']]) {
        const app = Object.values(bundle).find(chunk => chunk.type === 'chunk' && chunk.facadeModuleId?.endsWith(module));
        if (!app || app.type !== 'chunk') continue;
        const files = new Set<string>();
        const visit = (file: string) => {
          if (files.has(file)) return;
          const chunk = bundle[file];
          if (!chunk || chunk.type !== 'chunk') return;
          files.add(file);
          chunk.imports.forEach(visit);
        };
        visit(app.fileName);
        surfaces[surface] = [...files];
      }
      return [{ tag: 'script', injectTo: 'head-prepend', children:
        `var kifuModules=${JSON.stringify(surfaces)};var kifuSurface=location.pathname.match(/^\\/(galaxy|kiosk)\\/kifu\\/?$/);if(kifuSurface){(kifuModules[kifuSurface[1]]||[]).forEach(function(file){var link=document.createElement('link');link.rel='modulepreload';link.href='/'+file;document.head.appendChild(link);});}`,
      }];
    },
  },
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  const kioskMode = env.VITE_KIOSK_2D_ONLY === 'true'

  return {
    plugins: [react(), libraryModulePreload, ...(kioskMode ? [kioskNoReferrerMeta] : [])],
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
      rolldownOptions: {
        ...(kioskMode ? { external: ['three', '@react-three/fiber', '@react-three/drei'] } : {}),
        output: {
          codeSplitting: {
            groups: [{
              name: 'ui-core',
              test: /\/node_modules\/(?:@mui\/|@emotion\/|react(?:-dom|-router(?:-dom)?|-transition-group)?\/)/,
            }],
          },
        },
      },
      // Kiosk (SBC) build EXCLUDES three.js. The 3D Go board was removed from the kiosk on
      // 2026-07-13 to free ~321MB of Mali GPU memory that was contending with KataGo's OpenCL
      // on the shared RK3562 GPU. Marking three external makes any accidental kiosk import fail
      // loudly at build time; the full/galaxy build keeps 3D and bundles them normally.
    },
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: './src/test/setup.ts',
      exclude: ['tests/**', 'node_modules/**'],
    },
  }
})
