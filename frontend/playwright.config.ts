import { defineConfig } from '@playwright/test'

const frontendPort = process.env.E2E_FRONTEND_PORT ?? '4173'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  reporter: 'list',
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    trace: 'on-first-retry',
  },
  webServer: {
    command: `npm run dev -- --host 127.0.0.1 --port ${frontendPort}`,
    port: Number(frontendPort),
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
