import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { ESLint } from 'eslint'
import { loadConfigFromFile } from 'vite'
import { describe, expect, it } from 'vitest'

const uiRoot = resolve(import.meta.dirname, '../..')
const atRoot = (name: string) => resolve(uiRoot, name)

describe('independent admin entry', () => {
  it('builds the admin HTML separately and proxies only admin and tutorial reads to its local server', async () => {
    const configPath = atRoot('vite.admin.config.ts')
    expect(existsSync(configPath)).toBe(true)

    const loaded = await loadConfigFromFile({ command: 'build', mode: 'production' }, configPath)
    expect(loaded).not.toBeNull()
    const config = loaded!.config
    expect(config.build?.outDir).toBe('../static-admin')
    expect(config.build?.rollupOptions?.input).toBe(atRoot('admin.html'))
    expect(config.publicDir).toBe(false)
    expect(config.server?.host).toBe('127.0.0.1')
    expect(config.server?.port).toBe(5174)
    expect(config.server?.proxy).toEqual({
      '/api/admin': { target: 'http://127.0.0.1:8010', changeOrigin: true },
      '/api/v1/tutorials': { target: 'http://127.0.0.1:8010', changeOrigin: true },
    })
  })

  it('loads AdminApp from its own HTML and React entry', () => {
    const htmlPath = atRoot('admin.html')
    const entryPath = atRoot('src/admin/main.tsx')
    expect(existsSync(htmlPath)).toBe(true)
    expect(existsSync(entryPath)).toBe(true)
    expect(readFileSync(htmlPath, 'utf8')).toContain('/src/admin/main.tsx')
    expect(readFileSync(htmlPath, 'utf8')).not.toContain('/src/main.tsx')
    expect(readFileSync(entryPath, 'utf8')).toContain("import AdminApp from './AdminApp'")
  })
})

describe('admin import boundary', () => {
  const eslint = new ESLint({ cwd: uiRoot })

  async function restrictedImports(file: string, source: string) {
    const [result] = await eslint.lintText(source, { filePath: atRoot(file) })
    return result.messages.filter((message) => message.ruleId === 'no-restricted-imports')
  }

  it.each([
    ['src/admin/BoundaryProbe.ts', '../kiosk/pages/LobbyPage'],
    ['src/admin/BoundaryProbe.ts', '../galaxy/pages/GameRoomPage'],
    ['src/admin/BoundaryProbe.ts', '../pages/VideoRecorderPage'],
    ['src/kiosk/BoundaryProbe.ts', '../admin/AdminApp'],
    ['src/galaxy/BoundaryProbe.ts', '../admin/AdminApp'],
    ['src/components/BoundaryProbe.ts', '../admin/AdminApp'],
    ['src/AppRouter.tsx', './admin/AdminApp'],
  ])('rejects %s importing %s', async (file, target) => {
    expect(await restrictedImports(file, `import thing from '${target}'\nvoid thing`)).toHaveLength(1)
  })
})
