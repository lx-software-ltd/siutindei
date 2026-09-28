import { test, expect } from './fixtures/test-fixtures';

test.describe('Category suggestions', () => {
  test('admin can open suggestions and decide', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');
    await adminPage.getByRole('button', { name: 'Categories', exact: true }).click();
    await adminPage
      .getByRole('button', { name: 'Category Suggestions', exact: true })
      .click();
    await expect(adminPage.locator('#suggestion-status-filter')).toHaveCount(0);

    await expect(adminPage.getByText('Capture unknown categories on import')).toBeVisible();
    await expect(adminPage.getByText('Pottery').first()).toBeVisible();

    await adminPage.getByRole('cell', { name: 'Pottery' }).click();
    await expect(adminPage.getByText('Hands-on indoor class')).toBeVisible();
    await adminPage.getByRole('button', { name: 'Reject' }).click();
    await expect(adminPage.getByText('Status: approved')).toBeVisible();
  });
});
