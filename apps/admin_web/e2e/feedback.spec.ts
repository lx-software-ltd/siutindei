import { test, expect } from './fixtures/test-fixtures';

test.describe('Feedback Panel', () => {
  test('views feedback entries and opens edit form from row', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=feedback');
    await expect(
      adminPage.getByRole('table', { name: 'Organization feedback' })
    ).toBeVisible();
    await expect(adminPage.getByPlaceholder('Search feedback...')).toHaveCount(0);

    await expect(
      adminPage.getByRole('cell', { name: 'Test Organization' }).first()
    ).toBeVisible();

    await adminPage.getByRole('row', { name: /Test Organization/ }).first().click();
    await expect(
      adminPage.getByRole('button', { name: /Set rating to 5 stars/ })
    ).toBeVisible();
    await expect(adminPage.getByLabel('Description')).toBeVisible();
  });

  test('feedback labels have no search field', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=feedback-labels');
    await expect(
      adminPage.getByRole('table', { name: 'Feedback labels' })
    ).toBeVisible();
    await expect(adminPage.getByPlaceholder('Search labels...')).toHaveCount(0);
    await expect(
      adminPage.getByRole('button', { name: 'New feedback label' })
    ).toBeVisible();
  });
});
