import { test, expect } from './fixtures/test-fixtures';

test.describe('Category suggestions', () => {
  test('admin can open suggestions and decide', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');
    await adminPage.getByRole('button', { name: 'Categories', exact: true }).click();
    await adminPage
      .getByRole('button', { name: 'Category Suggestions', exact: true })
      .click();
    await expect(adminPage.locator('#suggestion-status-filter')).toHaveCount(0);

    await expect(adminPage.getByText('Capture unknown categories on import')).toBeVisible();
    await expect(adminPage.getByText('Pottery').first()).toBeVisible();

    await adminPage.getByRole('cell', { name: 'Pottery' }).click();
    await expect(adminPage.getByText('Hands-on indoor class')).toBeVisible();
    await adminPage.getByRole('button', { name: 'Reject' }).click();
    await expect(adminPage.getByText('Status: approved')).toBeVisible();
  });

  test('admin can scan pending organizations and apply a check', async ({
    adminPage,
  }) => {
    await adminPage.goto('/admin/dashboard');
    await adminPage.getByRole('button', { name: 'Categories', exact: true }).click();
    await adminPage.getByRole('button', { name: 'Category Checks', exact: true }).click();
    await expect(adminPage.getByText('Clay club')).toBeVisible();
    const apply = adminPage.getByRole('button', { name: 'Apply' });
    const applyIcon = await apply.locator('svg').boundingBox();
    expect(applyIcon?.width).toBeGreaterThan(8);
    expect(applyIcon?.height).toBeGreaterThan(8);
    await adminPage.getByRole('button', { name: 'Verify categories' }).click();
    await expect(adminPage.getByText('Scan 2 activities in 1 model call.')).toBeVisible();
    await adminPage.getByRole('button', { name: 'Start scan' }).click();
    await expect(adminPage.getByText('1 of 1 batches.')).toBeVisible();
    await adminPage.getByRole('cell', { name: 'Clay club', exact: true }).click();
    await expect(adminPage.getByText('Indoor craft, not sport')).toBeVisible();
    await adminPage.getByRole('button', { name: 'Apply' }).click();
    await expect(
      adminPage.getByTestId('admin-row-rev-1').getByText('applied', { exact: true })
    ).toBeVisible();
  });
});
