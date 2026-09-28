import { test, expect } from './fixtures/test-fixtures';

test.describe('Tickets Panel', () => {
  test.beforeEach(async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=tickets');
    await expect(adminPage.getByRole('table', { name: 'Tickets' })).toBeVisible();
  });

  test('lists tickets without type, status, or search filters', async ({ adminPage }) => {
    await expect(
      adminPage.getByRole('cell', { name: 'T00001' }).first()
    ).toBeVisible();
    await expect(adminPage.getByPlaceholder('Search tickets...')).toHaveCount(0);
    await expect(adminPage.locator('#type-filter')).toHaveCount(0);
    await expect(adminPage.locator('#status-filter')).toHaveCount(0);
    await expect(
      adminPage.getByRole('table').getByText('pending@example.com').first()
    ).toBeVisible();
  });

  test('reviews a pending ticket', async ({ adminPage }) => {
    await adminPage.getByRole('row', { name: /T00001/ }).click();
    await expect(adminPage.getByLabel('Ticket ID')).toHaveValue('T00001');
    await expect(adminPage.getByText('Create new')).toBeVisible();

    await adminPage.getByRole('button', { name: 'Approve' }).click();
    await expect(adminPage.getByText('Failed to process ticket')).toHaveCount(0);
    await expect(adminPage.getByText('Please select an organization')).toHaveCount(0);
  });
});
