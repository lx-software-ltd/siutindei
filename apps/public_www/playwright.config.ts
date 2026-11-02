import { defineConfig, devices } from '@playwright/test';

const PORT = 3100;
const BASE_URL = `http://localhost:${PORT}`;

/**
 * Public website smoke tests. Search reads the staging fixture
 * (`public/fixtures/activity_search_staging.json`, synced by
 * `scripts/codegen/sync-activity-search-staging-fixture.sh public-www`),
 * so no API is needed.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: `npm run dev -- -p ${PORT}`,
    url: `${BASE_URL}/en/`,
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
    env: {
      NEXT_PUBLIC_SITE_ORIGIN: BASE_URL,
      NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED: 'true',
    },
  },
});
