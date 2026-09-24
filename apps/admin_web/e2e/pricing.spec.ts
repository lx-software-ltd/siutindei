import { test, expect } from './fixtures/test-fixtures';

test.describe('Pricing Panel', () => {
  test('creates a pricing entry', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=pricing');
    await expect(adminPage.getByRole('table', { name: 'Pricing' })).toBeVisible();
    await adminPage.getByRole('button', { name: 'New pricing' }).click();

    await adminPage.locator('#pricing-location').selectOption('loc-1');
    await adminPage.locator('#pricing-activity').selectOption('activity-1');
    await adminPage.locator('#pricing-currency').selectOption('HKD');
    await adminPage.locator('#pricing-amount').fill('250');

    await adminPage.getByRole('button', { name: 'Create' }).click();
    await expect(adminPage.getByRole('table')).toContainText('HKD 250.00');
    await expect(adminPage.getByRole('table')).toContainText('Per class');
  });
});
