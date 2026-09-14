import { defineConfig, devices } from '@playwright/test';
import { existsSync } from 'node:fs';

const projectPython = existsSync('../../../.venv/bin/python') ? '.venv/bin/python' : 'python3';

// 同上:设了 KATRAIN_PW_E2E_PORT 就用独立端口且不复用(端口被占即失败);不设与原来一字不差(:8002,非 CI 复用)。
const e2ePortEnv = process.env.KATRAIN_PW_E2E_PORT;
const e2ePort = Number(e2ePortEnv ?? 8002);

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'line',
  use: {
    baseURL: `http://127.0.0.1:${e2ePort}`,
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: `cd ../../.. && ${projectPython} -m katrain --ui=web --port ${e2ePort}`,
    url: `http://127.0.0.1:${e2ePort}/health`,
    reuseExistingServer: e2ePortEnv ? false : !process.env.CI,
    stdout: 'pipe',
    stderr: 'pipe',
    timeout: 120 * 1000,
  },
});
