import { test, expect } from './fixtures/test-fixtures';

test.describe('Categories Panel', () => {
  test.beforeEach(async ({ adminPage }) => {
  await adminPage.goto('/admin/dashboard');
    await adminPage.getByRole('button', { name: 'Categories' }).click();
  });

  test('should display the category form', async ({ adminPage }) => {
    await adminPage.getByRole('button', { name: 'New category' }).click();

    await expect(adminPage.getByLabel('Name')).toBeVisible();
    await expect(
      adminPage
        .getByRole('button', { name: 'Select English (en)' })
        .first()
    ).toBeVisible();
    await expect(
      adminPage
        .getByRole('button', { name: 'Select Chinese (zh)' })
        .first()
    ).toBeVisible();
    await expect(
      adminPage
        .getByRole('button', { name: 'Select Cantonese (yue)' })
        .first()
    ).toBeVisible();
    await expect(adminPage.getByLabel('Parent')).toBeVisible();
    await expect(adminPage.getByLabel('Display Order')).toBeVisible();
    await expect(adminPage.getByRole('button', { name: 'Create' })).toBeVisible();
  });

  test('should display existing categories list', async ({ adminPage }) => {
    await expect(adminPage.getByRole('table', { name: 'Categories' })).toBeVisible();
    await expect(adminPage.getByPlaceholder('Search categories...')).toHaveCount(0);
    await expect(
      adminPage.getByRole('button', { name: 'Suggestions', exact: true })
    ).toBeVisible();

    await expect(adminPage.getByRole('columnheader', { name: 'Path' })).toBeVisible();
    await expect(
      adminPage.getByRole('columnheader', { name: 'Display Order' })
    ).toBeVisible();
    await expect(
      adminPage.getByRole('columnheader', { name: 'Operations' })
    ).toBeVisible();

    await expect(adminPage.getByText('Sport / Water Sports')).toBeVisible();

    const rows = adminPage
      .getByRole('table', { name: 'Categories' })
      .locator('tr[data-testid^="admin-row-"]:not([data-testid$="-detail"])');
    await expect(rows).toHaveCount(8);
    await expect(rows.nth(0)).toHaveAttribute('data-testid', 'admin-row-cat-sport');
    await expect(rows.nth(1)).toHaveAttribute('data-testid', 'admin-row-cat-water');
    await expect(rows.nth(2)).toHaveAttribute('data-testid', 'admin-row-cat-team');
    await expect(rows.nth(3)).toHaveAttribute('data-testid', 'admin-row-cat-arts');
    await expect(rows.nth(4)).toHaveAttribute('data-testid', 'admin-row-cat-paint');
    await expect(rows.nth(5)).toHaveAttribute('data-testid', 'admin-row-cat-places');
    await expect(rows.nth(6)).toHaveAttribute('data-testid', 'admin-row-cat-schools');
    await expect(rows.nth(7)).toHaveAttribute('data-testid', 'admin-row-cat-primary');
    await expect(
      adminPage.getByRole('columnheader', { name: 'Public' })
    ).toBeVisible();
    await expect(rows.nth(6)).toContainText('Hidden from public');
    await expect(rows.nth(7)).toContainText('Hidden by a parent');
  });

  test('locks a fixed root but lets an admin hide it', async ({ adminPage }) => {
    await adminPage.getByTestId('admin-row-cat-schools').click();
    await expect(adminPage.getByLabel('Parent')).toBeDisabled();
    const hidden = adminPage.getByLabel(/Hidden from public/);
    await expect(hidden).toBeEnabled();
    await expect(hidden).toBeChecked();
    await expect(adminPage.getByLabel('Show in the home wizard')).toBeDisabled();
  });

  test('should create a new category', async ({ adminPage }) => {
    await adminPage.getByRole('button', { name: 'New category' }).click();
    await adminPage.getByLabel('Name').fill('Outdoor');
    await adminPage.getByLabel('Parent').selectOption({ label: 'Sport' });
    await adminPage.getByLabel('Display Order').fill('3');

    await adminPage.getByRole('button', { name: 'Create' }).click();

    await expect(adminPage.getByText('Outdoor')).toBeVisible();
  });
});
