import { test, expect } from './fixtures/test-fixtures';

test.describe('Table card slots', () => {
  test('catalog keeps shared filters outside and actions inside, right-aligned', async ({
    adminPage,
  }) => {
    await adminPage.goto('/admin/dashboard?section=catalog');
    const card = adminPage.getByTestId('admin-record-table');
    const filters = adminPage.getByTestId('admin-filter-bar');
    const actions = adminPage.getByTestId('admin-record-table-actions');
    const create = adminPage.getByRole('button', { name: 'New organization', exact: true });

    await expect(adminPage.getByRole('table', { name: 'Catalog' })).toBeVisible();
    await expect(filters).toBeVisible();
    await expect(actions).toBeVisible();
    await expect(card.getByTestId('admin-record-table-actions')).toBeVisible();
    await expect(card.getByTestId('admin-filter-bar')).toHaveCount(0);
    await expect(actions.getByRole('button', { name: 'New organization', exact: true })).toBeVisible();
    await expect(actions.getByRole('button', { name: 'Approve' })).toBeVisible();

    const filterBox = await filters.boundingBox();
    const actionBox = await actions.boundingBox();
    const createBox = await create.boundingBox();
    expect(filterBox).toBeTruthy();
    expect(actionBox).toBeTruthy();
    expect(createBox).toBeTruthy();
    expect(actionBox!.y).toBeGreaterThan(filterBox!.y);
    expect(createBox!.x).toBeGreaterThan(filterBox!.x);

    await adminPage.screenshot({
      path: '/opt/cursor/artifacts/table-card-catalog.png',
      fullPage: true,
    });
  });

  test('activities put search left and New activity on a new right-aligned row', async ({
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
    expect(createBox!.x).toBeGreaterThan(filterBox!.x);

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
