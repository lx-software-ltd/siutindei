import { test, expect } from './fixtures/test-fixtures';

test.describe('Feedback Panel', () => {
  test('views feedback entries and opens edit form from row', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=feedback');
    await expect(
      adminPage.getByRole('table', { name: 'Organization feedback' })
    ).toBeVisible();

    await expect(
      adminPage.getByRole('cell', { name: 'Test Organization' }).first()
    ).toBeVisible();

    await adminPage.getByRole('row', { name: /Test Organization/ }).first().click();
    await expect(
      adminPage.getByRole('button', { name: /Set rating to 5 stars/ })
    ).toBeVisible();
    await expect(adminPage.getByLabel('Description')).toBeVisible();
  });
});
