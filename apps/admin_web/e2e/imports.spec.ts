import { test, expect } from './fixtures/test-fixtures';

test.describe('Imports Panel', () => {
  test('redirects to imports section and runs import', async ({ adminPage }) => {
    await adminPage.goto('/admin/imports');
    await expect(adminPage).toHaveURL(/section=imports/);
    await expect(adminPage.getByRole('heading', { name: 'Imports' })).toBeVisible();
    await expect(adminPage.getByRole('heading', { name: 'Exports' })).toBeVisible();

    const jsonFile = {
      name: 'import.json',
      mimeType: 'application/json',
      buffer: Buffer.from(JSON.stringify({ organizations: [] })),
    };

    await adminPage.setInputFiles('#admin-import-file', jsonFile);
    await adminPage
      .getByRole('checkbox', { name: 'Skip records that already exist' })
      .uncheck();
    const requestPromise = adminPage.waitForRequest(
      (request) =>
        request.method() === 'POST' &&
        request.url().includes('/admin/imports') &&
        !request.url().includes('/presign')
    );
    await adminPage.getByRole('button', { name: 'Upload & Import' }).click();
    const request = await requestPromise;
    expect(request.postDataJSON()).toMatchObject({ allow_updates: true });

    const upload = adminPage.getByRole('button', { name: 'Upload & Import' });
    const summary = adminPage.getByText('Summary', { exact: true });
    await expect(summary).toBeVisible();
    const uploadBox = await upload.boundingBox();
    const summaryBox = await summary.boundingBox();
    expect(uploadBox).toBeTruthy();
    expect(summaryBox).toBeTruthy();
    expect(summaryBox!.y).toBeGreaterThan(uploadBox!.y);
    await expect(adminPage.getByText(/^Organizations:/)).toBeVisible();
    await expect(
      adminPage.getByText(/Existing organizations, venues, and activities stay/)
    ).toHaveCount(0);
    await expect(adminPage.getByLabel('Organization name (optional)')).toBeVisible();
  });

  test('saves which data quality checks run on import', async ({
    adminPage,
  }) => {
    await adminPage.goto('/admin/dashboard?section=imports&tab=settings');
    await expect(
      adminPage.getByRole('heading', { name: 'Settings', exact: true })
    ).toBeVisible();
    const duplicates = adminPage.getByLabel('Duplicates');
    await expect(duplicates).toHaveValue('off');
    await duplicates.selectOption('report');
    const requestPromise = adminPage.waitForRequest(
      (request) =>
        request.method() === 'PUT' && request.url().includes('/admin/import-settings')
    );
    await adminPage.getByRole('button', { name: 'Save settings' }).click();
    const request = await requestPromise;
    expect(request.postDataJSON()).toMatchObject({
      duplicates: 'report',
      name_cleanup: 'apply',
      unknown_categories: 'capture',
      locations: 'off',
      categories: 'off',
      skip_deleted_organizations: true,
    });
    await expect(
      adminPage.getByText(/after an enrichment apply/)
    ).toBeVisible();
    await expect(adminPage.getByText('Settings saved.')).toBeVisible();
  });

  test('sends allow_updates false when skip existing is checked', async ({
    adminPage,
  }) => {
    await adminPage.goto('/admin/imports');
    const jsonFile = {
      name: 'import.json',
      mimeType: 'application/json',
      buffer: Buffer.from(JSON.stringify({ organizations: [] })),
    };
    await adminPage.setInputFiles('#admin-import-file', jsonFile);
    await expect(
      adminPage.getByRole('checkbox', { name: 'Skip records that already exist' })
    ).toBeChecked();
    const requestPromise = adminPage.waitForRequest(
      (request) =>
        request.method() === 'POST' &&
        request.url().includes('/admin/imports') &&
        !request.url().includes('/presign')
    );
    await adminPage.getByRole('button', { name: 'Upload & Import' }).click();
    const request = await requestPromise;
    expect(request.postDataJSON()).toMatchObject({ allow_updates: false });
    const upload = adminPage.getByRole('button', { name: 'Upload & Import' });
    const summary = adminPage.getByText('Summary', { exact: true });
    await expect(summary).toBeVisible();
    const uploadBox = await upload.boundingBox();
    const summaryBox = await summary.boundingBox();
    expect(uploadBox).toBeTruthy();
    expect(summaryBox).toBeTruthy();
    expect(summaryBox!.y).toBeGreaterThan(uploadBox!.y);
  });
});
