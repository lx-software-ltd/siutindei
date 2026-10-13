import { test, expect } from './fixtures/test-fixtures';

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

    const filterBox = await filters.boundingBox();
    const actionBox = await actions.boundingBox();
    expect(filterBox).toBeTruthy();
    expect(actionBox).toBeTruthy();
    expect(actionBox!.y).toBeGreaterThan(filterBox!.y);
    expect(Math.abs(actionBox!.x - filterBox!.x)).toBeLessThan(32);

    await adminPage.screenshot({
      path: '/opt/cursor/artifacts/table-card-catalog.png',
      fullPage: true,
    });
  });

  test('activities put search and New activity on the left, on two rows', async ({
    adminPage,
  }) => {
    await adminPage.goto('/admin/dashboard?section=activities&org=org-1');
    const card = adminPage.getByTestId('admin-record-table');
    const filters = card.getByTestId('admin-filter-bar');
    const actions = card.getByTestId('admin-record-table-actions');
    const create = actions.getByRole('button', { name: 'New activity' });

    await expect(card).toBeVisible();
    await expect(filters).toBeVisible();
    await expect(create).toBeVisible();

    const filterBox = await filters.boundingBox();
    const actionBox = await actions.boundingBox();
    const createBox = await create.boundingBox();
    expect(actionBox!.y).toBeGreaterThan(filterBox!.y);
    expect(Math.abs(createBox!.x - filterBox!.x)).toBeLessThan(32);

    await adminPage.screenshot({
      path: '/opt/cursor/artifacts/table-card-activities.png',
      fullPage: true,
    });
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

    await adminPage.screenshot({
      path: '/opt/cursor/artifacts/table-card-categories.png',
      fullPage: true,
    });
  });

  test('names keep sweep buttons on the actions row and the count above the card', async ({
    adminPage,
  }) => {
    await adminPage.goto('/admin/dashboard?section=data-quality&tab=names');
    const card = adminPage.getByTestId('admin-record-table');
    const filters = card.getByTestId('admin-filter-bar');
    const actions = card.getByTestId('admin-record-table-actions');
    const sweep = actions.getByRole('button', { name: 'Sweep pending' });
    const summary = adminPage.locator('p.text-sm.text-slate-700').filter({
      hasText: /pending/i,
    });

    await expect(filters).toBeVisible();
    await expect(sweep).toBeVisible();
    await expect(summary).toBeVisible();
    await expect(card.locator('p.text-sm.text-slate-700').filter({ hasText: /pending/i })).toHaveCount(0);

    const filterBox = await filters.boundingBox();
    const actionBox = await actions.boundingBox();
    expect(actionBox!.y).toBeGreaterThan(filterBox!.y);

    await adminPage.screenshot({
      path: '/opt/cursor/artifacts/table-card-names.png',
      fullPage: true,
    });
  });
});
