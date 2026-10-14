import { test, expect } from './fixtures/test-fixtures';

test.describe('Media Panel', () => {
  test('adds, reorders, removes, and saves media', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=media&org=org-1');
    await expect(
      adminPage.getByRole('heading', { name: 'Test Organization 1' })
    ).toBeVisible();
    await expect(adminPage.getByRole('heading', { name: 'Media' })).toBeVisible();
    await expect(adminPage.getByRole('button', { name: 'History' })).toHaveCount(0);
    const version = adminPage.getByLabel('Version');
    await expect(version).toHaveValue('2');
    await version.selectOption('1');
    await expect(adminPage.getByText('Read-only')).toBeVisible();
    await expect(adminPage.getByText('https://example.com/original.jpg')).toBeVisible();
    await expect(adminPage.locator('#media-url')).toHaveCount(0);
    await expect(adminPage.getByRole('button', { name: 'Save media' })).toHaveCount(0);
    await version.selectOption('2');

    const mediaInput = adminPage.locator('#media-url');
    await mediaInput.fill('https://example.com/media-one.jpg');
    await adminPage.getByTitle('Add URL').click();

    await mediaInput.fill('https://example.com/media-two.jpg');
    await adminPage.getByTitle('Add URL').click();

    await expect(adminPage.getByRole('button', { name: 'Remove' })).toHaveCount(2);

    await adminPage.getByRole('button', { name: 'Down' }).first().click();
    await adminPage.getByRole('button', { name: 'Remove' }).first().click();
    await expect(adminPage.getByRole('button', { name: 'Remove' })).toHaveCount(1);

    await adminPage.getByRole('button', { name: 'Save media' }).click();
    await expect(adminPage.getByText('Media saved successfully.')).toBeVisible();
  });
});
