import { test, expect } from './fixtures/test-fixtures';

test.describe('Imports Panel', () => {
  test('redirects to imports section and runs import', async ({ adminPage }) => {
    await adminPage.goto('/admin/imports');
    await expect(adminPage).toHaveURL(/section=imports/);
    await expect(adminPage.getByRole('heading', { name: 'Imports' })).toBeVisible();

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

    await expect(adminPage.getByText('Summary')).toBeVisible();
    await expect(adminPage.getByText(/^Organizations:/)).toBeVisible();
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
    await expect(adminPage.getByText('Summary')).toBeVisible();
  });
});
