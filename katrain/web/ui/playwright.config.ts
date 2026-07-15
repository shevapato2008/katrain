import { defineConfig, devices } from '@playwright/test';
import { existsSync } from 'node:fs';

const projectPython = existsSync('../../../.venv/bin/python') ? '.venv/bin/python' : 'python3';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'line',
  use: {
    baseURL: 'http://127.0.0.1:8002',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: `cd ../../.. && ${projectPython} -m katrain --ui=web --port 8002`,
    url: 'http://127.0.0.1:8002/health',
    reuseExistingServer: !process.env.CI,
    stdout: 'pipe',
    stderr: 'pipe',
    timeout: 120 * 1000,
  },
});
