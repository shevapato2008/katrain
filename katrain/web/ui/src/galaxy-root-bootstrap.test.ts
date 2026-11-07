import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import type { IndexHtmlTransformContext, Plugin } from 'vite';
import { describe, expect, it, vi } from 'vitest';
import viteConfig from '../vite.config';

const html = readFileSync('index.html', 'utf8');
const prefetchScript = html.match(/<script>\s*([\s\S]*?)<\/script>/)?.[1];
if (!prefetchScript) throw new Error('Missing inline library prefetch script');

function runPrefetch(path: string, language: string | null = 'en') {
  const fetch = vi.fn().mockResolvedValue({ ok: true });
  const window: { __kifuListRequest?: { path: string; response: Promise<unknown> } } = {};
  runInNewContext(prefetchScript!, {
    location: new URL(path, 'https://example.test'),
    URLSearchParams,
    localStorage: { getItem: () => language },
    fetch,
    window,
  });
  return { fetch, window };
}

async function buildPlugin(name: string, kiosk = false) {
  vi.stubEnv('VITE_KIOSK_2D_ONLY', String(kiosk));
  try {
    const config = await viteConfig({ command: 'build', mode: 'production' });
    const plugin = config.plugins?.flat().find(value => value && typeof value === 'object'
      && 'name' in value && value.name === name) as Plugin | undefined;
    expect(plugin, `build plugin ${name}`).toBeDefined();
    return plugin!;
  } finally {
    vi.unstubAllEnvs();
  }
}

async function generatedPreloadScript() {
  const plugin = await buildPlugin('library-module-preload');
  const hook = plugin.transformIndexHtml!;
  const handler = typeof hook === 'function' ? hook : hook.handler;
  const chunk = (fileName: string, facadeModuleId: string | null, imports: string[]) => ({
    type: 'chunk', fileName, facadeModuleId, imports,
  });
  const result = await handler(html, {
    path: '/index.html', filename: '/index.html',
    bundle: {
      'assets/GalaxyApp.js': chunk('assets/GalaxyApp.js', '/src/GalaxyApp.tsx', ['assets/shared.js']),
      'assets/KioskApp.js': chunk('assets/KioskApp.js', '/src/kiosk/KioskApp.tsx', ['assets/shared.js']),
      'assets/shared.js': chunk('assets/shared.js', null, []),
    },
  } as unknown as IndexHtmlTransformContext);
  if (!Array.isArray(result) || typeof result[0]?.children !== 'string') {
    throw new Error('Missing generated module-preload script');
  }
  return result[0].children;
}

function runPreload(script: string, path: string) {
  const links: Array<{ rel?: string; href?: string }> = [];
  runInNewContext(script, {
    location: new URL(path, 'https://example.test'),
    document: {
      createElement: () => ({}),
      head: { appendChild: (link: typeof links[number]) => links.push(link) },
    },
  });
  return links;
}

describe('root Galaxy library bootstrap', () => {
  it.each(['/kifu', '/kifu/', '/kiosk/kifu', '/kiosk/kifu/'])(
    'prefetches one bounded list at %s and preserves search, page and language', path => {
      const { fetch, window } = runPrefetch(`${path}?q=Lee+Changho&page=3&page_size=999`);
      const expectedPath = '/api/v1/kifu/albums?q=Lee+Changho&page=3&page_size=20&lang=en';
      expect(fetch).toHaveBeenCalledExactlyOnceWith(expectedPath, { priority: 'high' });
      expect(window.__kifuListRequest?.path).toBe(expectedPath);
      expect(window.__kifuListRequest?.response).toBeInstanceOf(Promise);
    },
  );

  it('uses the bounded first page and Chinese when no preferences are stored', () => {
    const { fetch } = runPrefetch('/kifu', null);
    expect(fetch).toHaveBeenCalledExactlyOnceWith('/api/v1/kifu/albums?page=1&page_size=20&lang=cn', { priority: 'high' });
  });

  it.each(['/', '/galaxy/kifu', '/galaxy/kifu/', '/kifu/7/replay', '/kifu/7/report', '/kiosk/kifu/7', '/api/v1/kifu/albums'])(
    'does not prefetch a library for %s', path => {
      const { fetch, window } = runPrefetch(path);
      expect(fetch).not.toHaveBeenCalled();
      expect(window.__kifuListRequest).toBeUndefined();
    },
  );

  it.each([
    ['/kifu', 'GalaxyApp'], ['/kifu/?q=Lee&page=3', 'GalaxyApp'],
    ['/kiosk/kifu', 'KioskApp'], ['/kiosk/kifu/?q=Lee', 'KioskApp'],
  ])('preloads the actual %s surface and its shared dependencies', async (path, app) => {
    const links = runPreload(await generatedPreloadScript(), path);
    expect(links).toEqual([
      { rel: 'modulepreload', href: `/assets/${app}.js` },
      { rel: 'modulepreload', href: '/assets/shared.js' },
    ]);
  });

  it.each(['/', '/galaxy/kifu', '/galaxy/kifu/', '/kifu/7/report', '/kiosk/kifu/7', '/api/v1/kifu/albums'])(
    'does not inject library modules for %s', async path => {
      expect(runPreload(await generatedPreloadScript(), path)).toEqual([]);
    },
  );
});

describe('kiosk Galaxy module boundary', () => {
  it.each([
    [{ '/repo/src/kiosk/pages/GamePage.tsx': { renderedLength: 10 }, '/repo/src/api/kifuApi.ts': { renderedLength: 5 } }, []],
    [{ '/repo/src/GalaxyApp.tsx': { renderedLength: 10 }, '/repo/src/galaxy/pages/PlayMenu.tsx': { renderedLength: 5 } }, ['src/GalaxyApp.tsx', 'src/galaxy/pages/PlayMenu.tsx']],
    [{ '/repo/src/GalaxyApp.tsx': { renderedLength: 0 } }, []],
  ])('reports actual emitted Galaxy modules even in a shared-named chunk', async (modules, galaxyModules) => {
    const plugin = await buildPlugin('kiosk-galaxy-module-boundary', true);
    const hook = plugin.generateBundle!;
    const handler = typeof hook === 'function' ? hook : hook.handler;
    const emitFile = vi.fn();
    await handler.call({ emitFile } as never, {} as never, {
      'assets/shared.js': { type: 'chunk', modules },
    } as never, false);
    expect(emitFile).toHaveBeenCalledExactlyOnceWith({
      type: 'asset', fileName: 'kiosk-module-boundary.json', source: JSON.stringify({ galaxyModules }),
    });
  });
});
