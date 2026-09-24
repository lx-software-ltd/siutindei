import { test, expect } from './fixtures/test-fixtures';

test.describe('Cognito Users Panel', () => {
  test('views attributes and updates roles', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=cognito-users');
    await expect(adminPage.getByRole('table', { name: 'Users' })).toBeVisible();

    await expect(
      adminPage
        .getByRole('table')
        .getByText('manager@example.com', { exact: true })
        .first()
    ).toBeVisible();

    await adminPage.getByRole('row', { name: /manager@example.com/ }).first().click();
    await expect(adminPage.getByLabel('Raw Attributes')).toBeVisible();
    await adminPage.getByRole('row', { name: /manager@example.com/ }).first().click();
    await expect(adminPage.getByLabel('Raw Attributes')).toHaveCount(0);

    await adminPage.getByTitle('Make Admin').first().click();
    await expect(adminPage.getByTitle('Remove Admin').first()).toBeVisible();

    await adminPage.getByRole('button', { name: 'More actions' }).first().click();
    await adminPage.getByRole('menuitem', { name: 'Delete User' }).click();
    await adminPage
      .getByRole('dialog')
      .getByRole('button', { name: 'Delete User' })
      .click();
    await expect(adminPage.getByRole('dialog')).not.toBeVisible();
    await expect(
      adminPage.getByRole('row', { name: /manager@example.com Manager User/ })
    ).toHaveCount(0);
  });
});
