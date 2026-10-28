import path from 'node:path';

import type { Page } from '@playwright/test';

import { test, expect } from './fixtures/test-fixtures';

async function saveTableCardShot(page: Page, name: string) {
  const dir = process.env.ADMIN_E2E_SCREENSHOT_DIR;
  if (!dir) {
    return;
  }
  await page.screenshot({
    path: path.join(dir, `${name}.png`),
    fullPage: true,
  });
}

test.describe('Table card slots', () => {
  test('catalog keeps filters and left-aligned actions inside the table card', async ({
    adminPage,
  }) => {
    await adminPage.goto('/admin/dashboard?section=catalog');
    const card = adminPage.getByTestId('admin-record-table');
    const filters = card.getByTestId('admin-filter-bar');
    const actions = card.getByTestId('admin-record-table-actions');
    const create = actions.getByRole('button', { name: 'New organization', exact: true });

    await expect(adminPage.getByRole('table', { name: 'Catalog' })).toBeVisible();
    await expect(filters).toBeVisible();
    await expect(create).toBeVisible();
    await expect(actions.getByRole('button', { name: 'Approve' })).toBeVisible();
    await expect(adminPage.getByTestId('admin-filter-bar')).toHaveCount(1);

    const apply = actions.getByRole('button', { name: 'Apply properties' });
    const release = actions.getByRole('button', {
      name: 'Release even when details are missing',
    });
    const approve = actions.getByRole('button', { name: 'Approve' });
    await expect(apply).toBeVisible();
    await expect(release).toBeVisible();
    await expect(card.getByRole('button', { name: 'Clear import filter' })).toHaveCount(
      0
    );
    const applyBox = await apply.boundingBox();
    const releaseBox = await release.boundingBox();
    const createBox = await create.boundingBox();
    const approveBox = await approve.boundingBox();
    expect(applyBox).toBeTruthy();
    expect(releaseBox).toBeTruthy();
    expect(createBox).toBeTruthy();
    expect(approveBox).toBeTruthy();
    expect(releaseBox!.x).toBeGreaterThan(applyBox!.x);
    expect(Math.abs(createBox!.height - approveBox!.height)).toBeLessThan(2);

    const filterBox = await filters.boundingBox();
    const actionBox = await actions.boundingBox();
    expect(filterBox).toBeTruthy();
    expect(actionBox).toBeTruthy();
    expect(actionBox!.y).toBeGreaterThan(filterBox!.y);
    expect(Math.abs(actionBox!.x - filterBox!.x)).toBeLessThan(32);

    await saveTableCardShot(adminPage, 'table-card-catalog');
  });

  test('catalog import scope sits above the table card', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=catalog&job=job-1');
    const card = adminPage.getByTestId('admin-record-table');
    const note = adminPage.getByText('Filtered to this import.');
    const showAll = adminPage.getByRole('button', { name: 'Show all' });

    await expect(note).toBeVisible();
    await expect(showAll).toBeVisible();
    await expect(card.getByText('Filtered to this import.')).toHaveCount(0);
    await expect(card.getByRole('button', { name: 'Show all' })).toHaveCount(0);
    await expect(card.getByRole('button', { name: 'Clear import filter' })).toHaveCount(
      0
    );

    await showAll.click();
    await expect(note).toHaveCount(0);
    await expect(adminPage).not.toHaveURL(/[?&]job=/);
  });

  test('activities omit the filter bar and keep New activity on the actions row', async ({
    adminPage,
  }) => {
    await adminPage.goto('/admin/dashboard?section=activities&org=org-1');
    const card = adminPage.getByTestId('admin-record-table');
    const actions = card.getByTestId('admin-record-table-actions');

    await expect(card).toBeVisible();
    await expect(adminPage.getByTestId('admin-filter-bar')).toHaveCount(0);
    await expect(actions.getByRole('button', { name: 'New activity' })).toBeVisible();

    await saveTableCardShot(adminPage, 'table-card-activities');
  });

  test('categories omit the empty filter bar and keep Create on the actions row', async ({
    adminPage,
  }) => {
    await adminPage.goto('/admin/dashboard?section=activity-categories');
    const card = adminPage.getByTestId('admin-record-table');
    const actions = card.getByTestId('admin-record-table-actions');

    await expect(card).toBeVisible();
    await expect(adminPage.getByTestId('admin-filter-bar')).toHaveCount(0);
    await expect(actions.getByRole('button', { name: 'New category' })).toBeVisible();

    await saveTableCardShot(adminPage, 'table-card-categories');
  });

  test('names keep sweep buttons on the actions row and the count above the card', async ({
    adminPage,
  }) => {
    await adminPage.goto('/admin/dashboard?section=data-quality&tab=names');
    const card = adminPage.getByTestId('admin-record-table');
    const filters = card.getByTestId('admin-filter-bar');
    const actions = card.getByTestId('admin-record-table-actions');
    const sweep = actions.getByRole('button', { name: 'Sweep pending' });
    const kpiCards = adminPage.getByTestId('admin-kpi-card');

    await expect(filters).toBeVisible();
    await expect(filters.getByLabel('Name')).toHaveCount(0);
    await expect(filters.getByLabel('Record')).toBeVisible();
    await expect(sweep).toBeVisible();
    await expect(kpiCards).toHaveCount(1);
    await expect(kpiCards).toContainText(['Pending']);
    await expect(card.getByTestId('admin-kpi-card')).toHaveCount(0);
    await expect(adminPage.locator('p.text-sm.text-ink-700').filter({ hasText: /pending/i })).toHaveCount(0);

    const filterBox = await filters.boundingBox();
    const actionBox = await actions.boundingBox();
    expect(actionBox!.y).toBeGreaterThan(filterBox!.y);

    await saveTableCardShot(adminPage, 'table-card-names');
  });

  test('category checks keep sweep on the actions row and org scope above the card', async ({
    adminPage,
  }) => {
    await adminPage.goto(
      '/admin/dashboard?section=data-quality&tab=checks&organization=org-1'
    );
    const card = adminPage.getByTestId('admin-record-table');
    const actions = card.getByTestId('admin-record-table-actions');
    const note = adminPage.getByText(
      'Filtered to the organization from the review queue.'
    );

    await expect(actions.getByRole('button', { name: 'Apply matching' })).toBeVisible();
    await expect(actions.getByRole('button', { name: 'Dismiss matching' })).toBeVisible();
    await expect(note).toBeVisible();
    await expect(card.getByText('Filtered to the organization from the review queue.')).toHaveCount(
      0
    );
    await expect(card.getByLabel('Organization')).toHaveCount(0);

    await saveTableCardShot(adminPage, 'table-card-category-checks');
  });

  test('catalog map shows the same filters above the map card', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=catalog&view=map');
    const filters = adminPage.getByTestId('admin-filter-bar');

    await expect(adminPage.getByTestId('admin-record-table')).toHaveCount(0);
    await expect(filters).toBeVisible();
    await expect(filters.getByLabel('Review')).toBeVisible();
    await expect(filters.getByRole('textbox', { name: 'Name', exact: true })).toBeVisible();
  });
});
