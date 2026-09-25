import { test, expect } from './fixtures/test-fixtures';

test.describe('Audit Logs Panel', () => {
  test('filters logs and opens detail modal', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=audit-logs');
    await expect(adminPage.getByRole('table', { name: 'Audit logs' })).toBeVisible();
    await expect(adminPage.getByText(/Showing \d+ entries/)).toHaveCount(0);

    await expect(
      adminPage.getByRole('cell', { name: 'organizations' }).first()
    ).toBeVisible();
    await expect(adminPage.locator('label', { hasText: /^Action$/ })).toHaveCount(0);
    await expect(adminPage.locator('label', { hasText: /^Table$/ })).toHaveCount(0);
    await expect(adminPage.locator('label', { hasText: /^Time range$/ })).toHaveCount(0);
    await expect(adminPage.locator('label', { hasText: /^Actor$/ })).toHaveCount(0);

    await adminPage.getByLabel('Action').selectOption('UPDATE');
    await expect(adminPage.getByRole('table')).toContainText('UPDATE');

    await adminPage.getByRole('row').nth(1).click();
    await expect(adminPage.getByLabel('Record ID')).toBeVisible();
    await adminPage.getByRole('row').nth(1).click();
    await expect(adminPage.getByLabel('Record ID')).toHaveCount(0);
  });
});
