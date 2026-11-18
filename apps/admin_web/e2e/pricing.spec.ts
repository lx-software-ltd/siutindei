import { test, expect } from './fixtures/test-fixtures';

test.describe('Pricing Panel', () => {
  test('creates a pricing entry', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=pricing&org=org-1');
    await expect(adminPage.getByRole('table', { name: 'Pricing' })).toBeVisible();
    await expect(adminPage.getByRole('columnheader', { name: 'Version' })).toHaveCount(0);
    await expect(adminPage.getByRole('cell', { name: 'v1' })).toHaveCount(0);
    await expect(adminPage.getByTestId('admin-filter-bar')).toHaveCount(0);
    await expect(adminPage.getByPlaceholder('Activity, location, or price')).toHaveCount(0);
    await adminPage.getByRole('row', { name: /Harbour Hall/ }).first().click();
    await expect(adminPage.getByText('Organization Version 2')).toBeVisible();
    const editor = adminPage.getByTestId('admin-editor-panel');
    const accessory = editor.getByTestId('admin-editor-accessory');
    const version = accessory.getByRole('button', { name: 'Version 1 · Latest' });
    await expect(version).toBeVisible();
    await expect(adminPage.getByRole('button', { name: 'History' })).toHaveCount(0);
    const editorBox = await editor.boundingBox();
    const versionBox = await version.boundingBox();
    const locationBox = await editor.locator('#pricing-location').boundingBox();
    expect(editorBox).toBeTruthy();
    expect(versionBox).toBeTruthy();
    expect(locationBox).toBeTruthy();
    expect(versionBox!.y).toBeLessThan(locationBox!.y);
    expect(
      Math.abs(versionBox!.x + versionBox!.width - (editorBox!.x + editorBox!.width))
    ).toBeLessThan(32);
    await adminPage.getByRole('button', { name: 'New pricing' }).click();

    const pricingType = adminPage.locator('#pricing-type');
    await expect(pricingType.locator('option')).toHaveText([
      'Per class',
      'Per term',
      'Hourly',
      'Daily',
      'Free',
      'Monthly',
      'Yearly',
    ]);
    await expect(adminPage.locator('#pricing-location')).toContainText(
      'Harbour Hall · 123 Test Street'
    );
    await expect(adminPage.locator('#pricing-location')).toContainText(
      'Harbour Hall · 9 Hill Road'
    );
    await adminPage.locator('#pricing-location').selectOption('loc-1');
    await adminPage.locator('#pricing-activity').selectOption('activity-1');
    await adminPage.locator('#pricing-currency').selectOption('HKD');
    await adminPage.locator('#pricing-amount').fill('250');
    await adminPage.locator('#pricing-amount-max').fill('300');

    await adminPage.getByRole('button', { name: 'Create' }).click();
    await expect(adminPage.getByRole('table')).toContainText('HKD 250.00–300.00');
    await expect(adminPage.getByRole('table')).toContainText('Per class');
  });

  test('stores a free trial on a per-class price and a monthly price', async ({
    adminPage,
  }) => {
    await adminPage.goto('/admin/dashboard?section=pricing&org=org-1');
    await adminPage.getByRole('button', { name: 'New pricing' }).click();

    const trial = adminPage.getByRole('checkbox', {
      name: 'Free trial class offered',
    });
    await expect(trial).toBeVisible();
    await trial.check();
    await adminPage.locator('#pricing-type').selectOption('per_hour');
    await expect(trial).toHaveCount(0);
    await adminPage.locator('#pricing-type').selectOption('per_class');
    await expect(trial).toBeVisible();
    await expect(trial).not.toBeChecked();
    await trial.check();

    await adminPage.locator('#pricing-location').selectOption('loc-1');
    await adminPage.locator('#pricing-activity').selectOption('activity-1');
    await adminPage.locator('#pricing-amount').fill('180');

    const created = adminPage.waitForRequest(
      (request) =>
        request.method() === 'POST' && request.url().includes('/admin/pricing')
    );
    await adminPage.getByRole('button', { name: 'Create' }).click();
    const request = await created;
    expect(request.postDataJSON()).toMatchObject({
      pricing_type: 'per_class',
      free_trial_class_offered: true,
    });
    await expect(trial).toBeChecked();

    const row = adminPage.getByRole('row', { name: /HKD 180\.00/ });
    await row.getByRole('cell').first().click();
    await expect(trial).toHaveCount(0);
    await row.getByRole('cell').first().click();
    await expect(trial).toBeChecked();

    await adminPage.locator('#pricing-type').selectOption('per_month');
    await expect(trial).toBeChecked();
    const updated = adminPage.waitForRequest(
      (request) =>
        request.method() === 'PUT' && request.url().includes('/admin/pricing/')
    );
    await adminPage.getByRole('button', { name: 'Update' }).click();
    expect((await updated).postDataJSON()).toMatchObject({
      pricing_type: 'per_month',
      free_trial_class_offered: true,
    });
    await expect(trial).toBeChecked();
  });
});
