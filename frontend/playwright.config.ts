import { defineConfig, devices } from '@playwright/test';

process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ||= 'browser-client.apps.example.test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: 'line',
  use: {
    baseURL: 'http://127.0.0.1:3100',
    trace: 'retain-on-failure',
  },
  webServer: {
    command: `npm run build && node -e "const fs=require('node:fs'); fs.cpSync('.next/static','.next/standalone/.next/static',{recursive:true}); fs.cpSync('public','.next/standalone/public',{recursive:true})" && node -e "process.env.HOSTNAME='127.0.0.1'; process.env.PORT='3100'; require('./.next/standalone/server.js')"`,
    url: 'http://127.0.0.1:3100',
    reuseExistingServer: false,
    timeout: 180_000,
  },
  projects: [
    { name: 'chromium-desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox-desktop', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit-desktop', use: { ...devices['Desktop Safari'] } },
    { name: 'chromium-360', use: { ...devices['Desktop Chrome'], viewport: { width: 360, height: 800 } } },
    { name: 'webkit-390', use: { ...devices['iPhone 13'] } },
    { name: 'chromium-768', use: { ...devices['Desktop Chrome'], viewport: { width: 768, height: 1024 } } },
  ],
});
