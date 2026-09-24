import { test, expect } from './fixtures/test-fixtures';

test.describe('Locations Panel', () => {
  test('searches and deletes a location', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=locations');
    await expect(adminPage.getByRole('table', { name: 'Locations' })).toBeVisible();

    await adminPage.getByPlaceholder('Search locations...').fill('Test Street');
    await expect(adminPage.getByRole('table')).toContainText('123 Test Street');

    await adminPage.getByRole('button', { name: 'Delete' }).first().click();
    await adminPage
      .getByRole('dialog')
      .getByRole('button', { name: 'Delete' })
      .click();
    await expect(adminPage.getByRole('dialog')).not.toBeVisible();
  });
});
