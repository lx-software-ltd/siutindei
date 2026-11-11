import { test, expect } from './fixtures/test-fixtures';

test.describe('Audit Logs Panel', () => {
  test('filters logs and opens detail modal', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=audit-logs');
    await expect(adminPage.getByRole('table', { name: 'Audit logs' })).toBeVisible();
    await expect(adminPage.getByText(/Showing \d+ entries/)).toHaveCount(0);

    await expect(
      adminPage.getByRole('cell', { name: 'organizations' }).first()
    ).toBeVisible();
    await expect(adminPage.locator('label', { hasText: /^Action$/ })).toHaveCount(0);
    await expect(adminPage.locator('label', { hasText: /^Table$/ })).toHaveCount(0);
    await expect(adminPage.locator('label', { hasText: /^Time range$/ })).toHaveCount(0);
    await expect(adminPage.locator('label', { hasText: /^Actor$/ })).toHaveCount(0);
    await expect(adminPage.getByRole('columnheader', { name: 'Actor' })).toBeVisible();
    const userRow = adminPage.getByTestId('admin-row-audit-1');
    await expect(userRow.getByRole('cell', { name: 'admin@example.com' })).toBeVisible();
    await expect(userRow.getByRole('img', { name: 'Email' })).toBeVisible();
    const systemRow = adminPage.getByTestId('admin-row-audit-2');
    await expect(systemRow.getByRole('cell', { name: 'system' })).toBeVisible();
    await expect(systemRow.getByRole('img', { name: 'GitHub' })).toHaveCount(0);
    const jobRow = adminPage.getByTestId('admin-row-audit-4');
    await expect(jobRow.getByRole('cell', { name: 'category check' })).toBeVisible();
    await expect(jobRow.getByRole('img', { name: 'User' })).toHaveCount(0);
    const keyRow = adminPage.getByTestId('admin-row-audit-3');
    await expect(keyRow.getByRole('cell', { name: 'Partner read key' })).toBeVisible();
    await expect(keyRow.getByRole('img', { name: 'API key' })).toBeVisible();
    await expect(adminPage.getByText('admin-user-id-123')).toHaveCount(0);
    await expect(adminPage.getByText('api-key:api-key-1')).toHaveCount(0);
    await expect(adminPage.getByText('category-scan:run-1')).toHaveCount(0);
    await expect(adminPage.getByRole('columnheader', { name: 'Timestamp' })).toBeVisible();
    await expect(adminPage.getByRole('columnheader', { name: /Timestamp GMT/ })).toHaveCount(0);
    await expect(adminPage.getByRole('columnheader', { name: 'User Email' })).toHaveCount(0);
    const filterBar = adminPage.getByTestId('admin-filter-bar');
    const filterSelects = filterBar.locator('select');
    await expect(filterSelects).toHaveCount(3);
    await expect(filterSelects.nth(0)).toHaveAttribute('aria-label', 'Table');
    await expect(filterSelects.nth(1)).toHaveAttribute('aria-label', 'Action');
    await expect(filterSelects.nth(2)).toHaveAttribute('aria-label', 'Time range');
    await expect(adminPage.getByLabel('Actor')).toHaveCount(0);
    await expect(adminPage.getByPlaceholder('Actor email')).toHaveCount(0);

    await expect(adminPage.getByLabel('Table')).toHaveValue('all');
    await expect(adminPage.getByLabel('Table').locator('option')).toHaveText([
      'All tables',
      'activities',
      'activity_categories',
      'activity_locations',
      'activity_pricing',
      'activity_schedule',
      'api_keys',
      'category_suggestion_settings',
      'category_suggestions',
      'cognito_user',
      'feedback_labels',
      'import_settings',
      'locations',
      'organization_duplicate_dismissals',
      'organization_feedback',
      'organization_merges',
      'organizations',
      'tickets',
    ]);
    await expect(adminPage.getByLabel('Action')).toHaveValue('all');
    await expect(adminPage.getByLabel('Action').locator('option')).toHaveText([
      'All actions',
      'insert',
      'update',
      'delete',
    ]);
    await expect(adminPage.getByRole('cell', { name: 'update', exact: true })).toBeVisible();
    await expect(adminPage.getByRole('cell', { name: 'insert', exact: true })).toBeVisible();
    await expect(adminPage.getByText('UPDATE', { exact: true })).toHaveCount(0);
    await expect(adminPage.getByText('INSERT', { exact: true })).toHaveCount(0);
    await expect(adminPage.getByText('Insert', { exact: true })).toHaveCount(0);
    await expect(adminPage.getByText('Update', { exact: true })).toHaveCount(0);
    await expect(adminPage.getByText('Delete', { exact: true })).toHaveCount(0);

    await adminPage.getByLabel('Action').selectOption('update');
    await expect(adminPage.getByRole('table')).toContainText('update');

    await adminPage.getByRole('row').nth(1).click();
    await expect(adminPage.getByText('Record ID', { exact: true })).toBeVisible();
    await expect(
      adminPage.getByTestId('admin-row-audit-1-detail').getByRole('img', { name: 'Email' })
    ).toBeVisible();
    await expect(adminPage.getByLabel('Old values JSON')).toBeVisible();
    await expect(
      adminPage.getByLabel('Old values JSON').locator('[data-audit-changed="true"]').first()
    ).toBeVisible();
    await expect(
      adminPage.getByLabel('New values JSON').locator('[data-audit-changed="true"]').first()
    ).toBeVisible();
    await adminPage.getByRole('row').nth(1).click();
    await expect(adminPage.getByText('Record ID', { exact: true })).toHaveCount(0);

    await adminPage.getByTestId('admin-row-audit-2').click();
    const sourceValue = adminPage.locator('dt', { hasText: /^Source$/ }).locator('xpath=..').locator('dd');
    await expect(sourceValue).toHaveText('—');
    const requestIdValue = adminPage
      .locator('dt', { hasText: /^Request ID$/ })
      .locator('xpath=..')
      .locator('dd');
    await expect(requestIdValue).toHaveText('—');
    await expect(adminPage.getByTestId('admin-row-audit-2-detail')).toContainText('system');
    await expect(
      adminPage.getByTestId('admin-row-audit-2-detail').getByRole('img', { name: 'GitHub' })
    ).toHaveCount(0);

    await keyRow.click();
    const keyDetail = adminPage.getByTestId('admin-row-audit-3-detail');
    const actorValue = keyDetail
      .locator('dt', { hasText: /^Actor$/ })
      .locator('xpath=..')
      .locator('dd');
    await expect(actorValue).toContainText('Partner read key');
    await expect(keyDetail.getByRole('img', { name: 'API key' })).toBeVisible();

    await jobRow.click();
    const jobDetail = adminPage.getByTestId('admin-row-audit-4-detail');
    await expect(jobDetail).toContainText('category check');
    await expect(jobDetail.getByText('category-scan:run-1')).toHaveCount(0);
  });
});
