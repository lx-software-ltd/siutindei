import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for Admin Web E2E tests.
 * @see https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  testDir: './e2e',
  /* Run tests in files in parallel */
  fullyParallel: true,
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  /* Opt out of parallel tests on CI. */
  workers: process.env.CI ? 1 : undefined,
  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  reporter: process.env.CI ? 'github' : 'html',
  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    /* Base URL to use in actions like `await page.goto('/')`. */
    baseURL: 'http://localhost:3000',

    /* Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer */
    trace: 'on-first-retry',

    /* Take screenshot on failure */
    screenshot: 'only-on-failure',
  },

  /* Configure projects for major browsers */
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  /*
   * Reuse skips `env` below. A server started with plain `npm run dev`
   * has no mock Cognito config, and every authenticated spec stops on
   * the login screen. Stop that process before running Playwright.
   */
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
    env: {
      NEXT_PUBLIC_API_BASE_URL: 'http://localhost:3000/api/mock',
      NEXT_PUBLIC_COGNITO_DOMAIN: 'mock-cognito.auth.us-east-1.amazoncognito.com',
      NEXT_PUBLIC_COGNITO_CLIENT_ID: 'mock-client-id-12345',
      NEXT_PUBLIC_COGNITO_USER_POOL_ID: 'mock-user-pool-id',
    },
  },
});
