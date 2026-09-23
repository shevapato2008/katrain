import { defineConfig, devices } from '@playwright/test';

// 并行开发的 worktree 各起各的 vite(2026-09 本机同时有 10+ 个 katrain worktree)。
// 设了 KATRAIN_PW_VISUAL_PORT:用这个端口、`--strictPort`、不复用 —— 端口被占就失败,保证测的是**本 worktree** 的源码。
// 不设:与原来一字不差(:5173,复用已在跑的服务)。
const visualPortEnv = process.env.KATRAIN_PW_VISUAL_PORT;
const visualPort = Number(visualPortEnv ?? 5173);

export default defineConfig({
  testDir: './tests',
  reporter: 'line',
  use: {
    baseURL: `http://127.0.0.1:${visualPort}`,
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `npm run dev -- --host 127.0.0.1 --port ${visualPort}${visualPortEnv ? ' --strictPort' : ''}`,
    url: `http://127.0.0.1:${visualPort}/galaxy/play`,
    reuseExistingServer: !visualPortEnv,
    timeout: 120_000,
  },
});
