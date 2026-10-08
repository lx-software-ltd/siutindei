import { test, expect } from './fixtures/test-fixtures';

test.describe('Data quality', () => {
  test('admin can preview and merge a duplicate group', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');
    await adminPage.getByRole('button', { name: 'Data quality', exact: true }).click();
    await expect(adminPage.getByRole('table', { name: 'Duplicate organizations' })).toBeVisible();
    await adminPage.getByRole('cell', { name: 'Harbour Club · Harbour Club Limited' }).click();
    await expect(adminPage.getByText('desk@example.com')).toBeVisible();
    await expect(adminPage.getByRole('button', { name: 'Merge' })).toBeEnabled();
    await adminPage.getByRole('button', { name: 'Merge' }).click();
    await adminPage.getByRole('button', { name: 'Merge organizations', exact: true }).click();
    await expect(
      adminPage.getByText('No duplicate organizations match these filters.')
    ).toBeVisible();
  });

  test('admin can scan and apply a name fix', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=data-quality&tab=names');
    await adminPage.getByRole('button', { name: 'Scan names' }).click();
    await expect(
      adminPage.getByText('Created 1, updated 0, skipped 0, cleared 0.')
    ).toBeVisible();
    await adminPage.getByRole('cell', { name: 'HARBOUR CLUB', exact: true }).click();
    await adminPage.getByRole('button', { name: 'Apply', exact: true }).click();
    await expect(adminPage.getByText('Name updated.')).toBeVisible();
  });

  test('admin can sweep names and filter by rule', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=data-quality&tab=names');
    await expect(adminPage.getByLabel('Rule')).toHaveValue('');
    await adminPage.getByLabel('Rule').selectOption('title_case');
    await expect(adminPage.getByLabel('Sweep')).toHaveValue('pending_review');
    await adminPage.getByLabel('Sweep').selectOption('all');
    await adminPage.getByRole('button', { name: 'Sweep scan' }).click();
    await expect(
      adminPage.getByText('Created 0, updated 1, skipped 0, cleared 1.')
    ).toBeVisible();
  });

  test('admin can edit name rule word lists', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=data-quality&tab=names');
    const exceptions = adminPage.getByLabel('Words to leave in capitals');
    const suffixes = adminPage.getByLabel('Bracket suffixes to remove');
    await expect(exceptions).toHaveValue('YMCA');
    await exceptions.click();
    await exceptions.press('End');
    await exceptions.pressSequentially(' YWCA');
    await expect(exceptions).toHaveValue('YMCA YWCA');
    await suffixes.click();
    await suffixes.press('End');
    await suffixes.pressSequentially(' edb');
    await expect(suffixes).toHaveValue('lcsd edb');
    await adminPage.getByRole('button', { name: 'Save rules' }).click();
    await expect(adminPage.getByText('Name rules saved.')).toBeVisible();
    await expect(exceptions).toHaveValue('YMCA YWCA');
    await expect(suffixes).toHaveValue('lcsd edb');
  });

  test('admin can merge from the organization workspace', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=organizations&org=org-1');
    await adminPage.getByRole('button', { name: 'Merge into…' }).click();
    await adminPage.getByLabel('Find organization').fill('Harbour');
    await adminPage.getByRole('button', { name: 'Find' }).click();
    await adminPage.getByRole('button', { name: 'Harbour Club Limited' }).click();
    const dialog = adminPage.getByRole('dialog', { name: 'Merge organization' });
    await expect(dialog.getByRole('button', { name: 'Merge', exact: true })).toBeEnabled();
    await dialog.getByRole('button', { name: 'Merge', exact: true }).click();
    await adminPage.getByRole('button', { name: 'Merge organizations', exact: true }).click();
    await expect(adminPage.getByRole('dialog', { name: 'Merge organization' })).toHaveCount(0);
  });
});
