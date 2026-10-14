import { test, expect } from './fixtures/test-fixtures';

test.describe('Category suggestions', () => {
  test('admin can open suggestions and decide', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');
    await adminPage.getByRole('button', { name: 'Categories', exact: true }).click();
    await adminPage
      .getByRole('button', { name: 'Suggestions', exact: true })
      .click();
    await expect(
      adminPage.getByRole('table', { name: 'Categories · Suggestions' })
    ).toBeVisible();
    const kpiCards = adminPage.getByTestId('admin-kpi-card');
    await expect(kpiCards).toHaveCount(3);
    await expect(kpiCards).toContainText([
      'Pending',
      'Activities need category',
      'Spending per month',
    ]);
    await expect(kpiCards.nth(0)).toContainText('1');
    await expect(kpiCards.nth(1)).toContainText('2');
    await expect(kpiCards.nth(2)).toContainText('$0.0100');
    await expect(adminPage.getByText(/pending\./)).toHaveCount(0);
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
    await adminPage.getByRole('button', { name: 'Data quality', exact: true }).click();
    await adminPage
      .getByRole('group', { name: 'Data quality' })
      .getByRole('button', { name: 'Categories', exact: true })
      .click();
    await expect(
      adminPage.getByRole('table', { name: 'Data quality · Categories' })
    ).toBeVisible();
    const checkKpis = adminPage.getByTestId('admin-kpi-card');
    await expect(checkKpis).toHaveCount(2);
    await expect(checkKpis).toContainText(['Waiting', 'Auto-assigned']);
    await expect(checkKpis.nth(0)).toContainText('1');
    await expect(checkKpis.nth(1)).toContainText('0');
    await expect(adminPage.getByText(/waiting\./)).toHaveCount(0);
    await expect(adminPage.locator('#check-status-filter')).toHaveValue('pending');
    await expect(adminPage.getByText('Clay club')).toBeVisible();
    await expect(adminPage.getByRole('columnheader', { name: 'Organization' })).toHaveCount(0);
    await expect(adminPage.getByRole('columnheader', { name: 'Current' })).toHaveCount(0);
    await expect(adminPage.getByRole('columnheader', { name: 'Proposed' })).toBeVisible();
    await expect(adminPage.getByRole('cell', { name: 'Harbor Arts', exact: true })).toHaveCount(0);
    await expect(adminPage.getByRole('cell', { name: 'Sport', exact: true })).toHaveCount(0);
    await expect(adminPage.getByRole('cell', { name: 'Ceramics', exact: true })).toBeVisible();
    await expect(adminPage.getByRole('cell', { name: '62%' })).toBeVisible();
    const apply = adminPage.getByRole('button', { name: 'Apply' });
    const applyIcon = await apply.locator('svg').boundingBox();
    expect(applyIcon?.width).toBeGreaterThan(8);
    expect(applyIcon?.height).toBeGreaterThan(8);
    await expect(adminPage.getByRole('button', { name: 'Sweep pending' })).toBeVisible();
    await adminPage.getByRole('button', { name: 'Sweep all orgs' }).click();
    await expect(adminPage.getByText(/Scan 2 activities in 1 model call/)).toBeVisible();
    await expect(adminPage.getByLabel('Ignore the current category')).toBeVisible();
    await adminPage.getByRole('button', { name: 'Start scan' }).click();
    const sweepKpi = adminPage.getByTestId('admin-kpi-card').filter({ hasText: 'Sweep' });
    await expect(sweepKpi).toContainText('1 of 1');
    await expect(adminPage.getByText('1 of 1 batches.')).toHaveCount(0);
    await adminPage.getByRole('cell', { name: 'Clay club', exact: true }).click();
    await expect(adminPage.getByText('Indoor craft, not sport')).toBeVisible();
    await adminPage.getByRole('button', { name: 'Apply', exact: true }).click();
    await expect(
      adminPage.getByTestId('admin-row-rev-1').getByRole('cell', { name: 'applied', exact: true })
    ).toBeVisible();
  });

  test('admin can apply every matching pending check', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');
    await adminPage.getByRole('button', { name: 'Data quality', exact: true }).click();
    await adminPage
      .getByRole('group', { name: 'Data quality' })
      .getByRole('button', { name: 'Categories', exact: true })
      .click();
    await adminPage.getByRole('checkbox', { name: 'Select visible rows' }).click();
    await adminPage.getByRole('checkbox', { name: 'Select all matching rows' }).click();
    await expect(
      adminPage.getByText(/All matching records are selected/)
    ).toBeVisible();
    await adminPage.getByRole('button', { name: 'Apply matching' }).click();
    await expect(
      adminPage.getByText('Apply every pending reassignment')
    ).toBeVisible();
    await adminPage.getByRole('button', { name: 'Apply pending' }).click();
    await expect(
      adminPage.getByTestId('admin-row-rev-1').getByRole('cell', { name: 'applied', exact: true })
    ).toBeVisible();
  });
});

test('legacy category checks link opens data quality', async ({ adminPage }) => {
  await adminPage.goto(
    '/admin/dashboard?section=activity-categories&categoryView=checks'
  );
  await expect(adminPage).toHaveURL(/section=data-quality/);
  await expect(adminPage).toHaveURL(/tab=checks/);
  await expect(adminPage).not.toHaveURL(/categoryView=/);
  await expect(
    adminPage
      .getByRole('group', { name: 'Data quality' })
      .getByRole('button', { name: 'Categories', exact: true })
  ).toBeVisible();
});
