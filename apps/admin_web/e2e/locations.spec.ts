import { test, expect } from './fixtures/test-fixtures';

test.describe('Locations Panel', () => {
  test('searches and deletes a location', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=locations&org=org-1');
    await expect(
      adminPage.getByRole('heading', { name: 'Test Organization 1' })
    ).toBeVisible();
    await expect(adminPage.getByRole('table', { name: 'Locations' })).toBeVisible();
    await expect(adminPage.getByRole('columnheader', { name: 'Version' })).toHaveCount(0);
    await expect(adminPage.getByRole('cell', { name: 'v1' })).toHaveCount(0);
    await adminPage.getByRole('row', { name: /123 Test Street/ }).first().click();
    await expect(adminPage.getByLabel('Version')).toHaveValue('1');
    await expect(adminPage.getByRole('button', { name: 'History' })).toHaveCount(0);

    await expect(adminPage.locator('label', { hasText: /^Search$/ })).toHaveCount(0);
    await adminPage.getByPlaceholder('Name or address', { exact: true }).fill('Test Street');
    await expect(adminPage.getByRole('table')).toContainText('123 Test Street');

    await adminPage.getByRole('button', { name: 'Delete' }).first().click();
    await adminPage
      .getByRole('alertdialog')
      .getByRole('button', { name: 'Delete' })
      .click();
    await expect(adminPage.getByRole('alertdialog')).not.toBeVisible();
  });
});
