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

    await expect(adminPage.getByRole('columnheader', { name: 'Path' })).toBeVisible();
    await expect(
      adminPage.getByRole('columnheader', { name: 'Display Order' })
    ).toBeVisible();
    await expect(
      adminPage.getByRole('columnheader', { name: 'Operations' })
    ).toBeVisible();

    await expect(adminPage.getByText('Sport / Water Sports')).toBeVisible();
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
