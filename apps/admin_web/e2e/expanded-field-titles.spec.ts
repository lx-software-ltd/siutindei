import { test, expect } from './fixtures/test-fixtures';

const SEMIBOLD = '600';

test.describe('Expanded field titles', () => {
  test('activity field titles match File warnings weight', async ({
    adminPage,
  }, testInfo) => {
    await adminPage.goto('/admin/dashboard?section=activities&org=org-1');
    await expect(adminPage.getByText('Swimming Class')).toBeVisible();
    await adminPage.getByRole('row', { name: /Swimming Class/ }).first().click();
    await expect(adminPage.getByLabel('Name')).toHaveValue('Swimming Class');

    const nameTitle = adminPage.locator('label[for="activity-name"]');
    await expect(nameTitle).toHaveCSS('font-weight', SEMIBOLD);
    await expect(adminPage.locator('label[for="activity-description"]')).toHaveCSS(
      'font-weight',
      SEMIBOLD
    );

    await adminPage.screenshot({
      path: testInfo.outputPath('expanded-activity-field-titles.png'),
      fullPage: true,
    });
  });

  test('import history field titles are semibold', async ({
    adminPage,
  }, testInfo) => {
    await adminPage.route('**/api/mock/**/admin/imports/job-1', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'job-1',
          object_key: 'admin/imports/catalog.json',
          download_url: 'https://imports.example/admin/imports/catalog.json',
          dry_run: false,
          status: 'completed',
          summary: {
            organizations: { created: 1, updated: 0, failed: 0, skipped: 0 },
            locations: { created: 0, updated: 0, failed: 0, skipped: 0 },
            activities: { created: 0, updated: 0, failed: 0, skipped: 0 },
            pricing: { created: 0, updated: 0, failed: 0, skipped: 0 },
            schedules: { created: 0, updated: 0, failed: 0, skipped: 0 },
            warnings: 0,
            errors: 0,
            captured_categories: 0,
          },
          results: [
            {
              type: 'organizations',
              key: 'Harbor Arts',
              status: 'created',
              warnings: [],
              errors: [],
            },
          ],
          file_warnings: ['Missing column: neighbourhood'],
        }),
      });
    });
    await adminPage.route('**/api/mock/**/admin/imports', async (route) => {
      if (route.request().method() !== 'GET') {
        await route.fallback();
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: [
            {
              id: 'job-1',
              object_key: 'admin/imports/catalog.json',
              download_url: 'https://imports.example/admin/imports/catalog.json',
              dry_run: false,
              status: 'completed',
              summary: {
                organizations: { created: 1, updated: 0, failed: 0, skipped: 0 },
                captured_categories: 0,
              },
              file_warnings: ['Missing column: neighbourhood'],
              result_count: 1,
              created_at: '2024-02-01T00:00:00Z',
              updated_at: '2024-02-01T01:00:00Z',
            },
          ],
          next_cursor: null,
        }),
      });
    });

    await adminPage.goto('/admin/dashboard?section=imports&tab=history');
    await adminPage.getByRole('cell', { name: /created 1, updated 0/ }).click();
    const detail = adminPage.getByTestId('admin-row-job-1-detail');
    await expect(detail.getByText('File warnings')).toHaveCount(0);
    await expect(detail.getByText('Missing column: neighbourhood')).toHaveCount(
      0
    );
    await expect(detail.getByText('Categories captured')).toBeVisible();
    await expect(detail.getByText('—', { exact: true })).toBeVisible();

    for (const title of [
      'First recorded',
      'Last changed',
      'Mode',
      'File',
      'Results',
    ]) {
      await expect(detail.getByText(title, { exact: true })).toHaveCSS(
        'font-weight',
        SEMIBOLD
      );
    }

    await adminPage.screenshot({
      path: testInfo.outputPath('expanded-import-history-field-titles.png'),
      fullPage: true,
    });
  });
});
