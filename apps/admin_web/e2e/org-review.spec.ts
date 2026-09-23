import { test, expect } from './fixtures/test-fixtures';

test.describe('Organization review queue', () => {
  test('shows missing details and bulk-approves a pending organization', async ({
    adminPage,
  }) => {
    await adminPage.goto('/admin/dashboard?section=imports&tab=review');
    await expect(
      adminPage.getByRole('heading', { name: 'Review queue' })
    ).toBeVisible();
    await expect(
      adminPage.getByRole('cell', { name: 'Test Organization 1' })
    ).toBeVisible();
    await expect(
      adminPage.getByRole('cell', { name: 'No locations' })
    ).toBeVisible();

    await adminPage.getByRole('checkbox', { name: 'Select row' }).first().check();
    await adminPage.getByRole('checkbox', {
      name: 'Release even when details are missing',
    }).check();
    await adminPage.getByRole('button', { name: 'Approve' }).click();
    await expect(adminPage.getByText(/Updated 1/)).toBeVisible();
  });

  test('lists import history', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=imports&tab=history');
    await expect(
      adminPage.getByRole('heading', { name: 'Import history' })
    ).toBeVisible();
    await expect(
      adminPage.getByRole('cell', { name: 'admin/imports/catalog.json' })
    ).toBeVisible();
  });
});
