import { test, expect } from './fixtures/test-fixtures';

test.describe('Media Panel', () => {
  test('adds, reorders, removes, and saves media', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=media&org=org-1');
    await expect(
      adminPage.getByRole('heading', { name: 'Test Organization 1' })
    ).toBeVisible();
    await expect(adminPage.getByRole('heading', { name: 'Media' })).toBeVisible();
    await expect(adminPage.getByRole('button', { name: 'History' })).toHaveCount(0);
    const mediaHeading = adminPage.getByRole('heading', { name: 'Media' });
    const versionControl = adminPage.getByRole('button', { name: 'Version 2 · Latest' });
    const headingBox = await mediaHeading.boundingBox();
    const versionBox = await versionControl.boundingBox();
    const cardBox = await mediaHeading.locator('xpath=ancestor::section[1]').boundingBox();
    expect(headingBox).toBeTruthy();
    expect(versionBox).toBeTruthy();
    expect(cardBox).toBeTruthy();
    expect(versionBox!.x).toBeGreaterThan(headingBox!.x + headingBox!.width);
    expect(cardBox!.x + cardBox!.width - (versionBox!.x + versionBox!.width)).toBeLessThan(48);
    await versionControl.click();
    await adminPage.getByRole('menuitem', { name: /Version 1/ }).click();
    await expect(adminPage.getByText('Viewing version 1 of 2 · read-only')).toBeVisible();
    await expect(adminPage.locator('img[src="https://example.com/original.jpg"]')).toBeVisible();
    await expect(adminPage.locator('#media-url')).toHaveCount(0);
    await expect(adminPage.getByRole('button', { name: 'Save media' })).toHaveCount(0);
    await adminPage.getByRole('button', { name: 'Back to latest' }).first().click();

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
