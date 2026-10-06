import { test, expect } from './fixtures/test-fixtures';

test.describe('Data quality', () => {
  test('admin can preview and merge a duplicate group', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');
    await adminPage.getByRole('button', { name: 'Data quality', exact: true }).click();
    await expect(adminPage.getByRole('table', { name: 'Duplicate organizations' })).toBeVisible();
    await adminPage.getByRole('cell', { name: 'Harbour Club · Harbour Club Limited' }).click();
    await expect(adminPage.getByRole('button', { name: 'Merge' })).toBeEnabled();
    await adminPage.getByRole('button', { name: 'Merge' }).click();
    await expect(
      adminPage.getByText('No duplicate organizations match these filters.')
    ).toBeVisible();
  });

  test('admin can scan and apply a name fix', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=data-quality&tab=names');
    await adminPage.getByRole('button', { name: 'Scan names' }).click();
    await expect(adminPage.getByText('Created 1, updated 0, skipped 0.')).toBeVisible();
    await adminPage.getByRole('cell', { name: 'HARBOUR CLUB', exact: true }).click();
    await adminPage.getByRole('button', { name: 'Apply', exact: true }).click();
    await expect(adminPage.getByText('Name updated.')).toBeVisible();
  });

  test('admin can merge from the organizations table', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');
    await adminPage.getByRole('button', { name: 'Merge into…' }).first().click();
    await adminPage.getByLabel('Find organization').fill('Harbour');
    await adminPage.getByRole('button', { name: 'Find' }).click();
    await adminPage.getByRole('button', { name: 'Harbour Club Limited' }).click();
    const dialog = adminPage.getByRole('dialog', { name: 'Merge organization' });
    await expect(dialog.getByRole('button', { name: 'Merge', exact: true })).toBeEnabled();
    await dialog.getByRole('button', { name: 'Merge', exact: true }).click();
    await expect(adminPage.getByRole('dialog', { name: 'Merge organization' })).toHaveCount(0);
  });
});
