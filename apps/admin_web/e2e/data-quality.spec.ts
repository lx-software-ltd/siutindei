import { formatDateTime } from '../src/lib/date-utils';

import { test, expect } from './fixtures/test-fixtures';

test.describe('Data quality', () => {
  test('admin can preview and merge a duplicate group', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');
    await adminPage.getByRole('button', { name: 'Data quality', exact: true }).click();
    await expect(adminPage.getByRole('table', { name: 'Data quality · Duplicates' })).toBeVisible();
    await expect(adminPage.getByText(/Groups share a name/)).toHaveCount(0);
    await expect(adminPage.getByText(/to the survivor/)).toHaveCount(0);
    await adminPage.getByRole('cell', { name: 'Harbour Club · Harbour Club Limited' }).click();
    await expect(adminPage.getByText('desk@example.com')).toBeVisible();
    await expect(adminPage.getByRole('button', { name: 'Merge' })).toBeEnabled();
    await adminPage.getByRole('button', { name: 'Merge' }).click();
    await adminPage.getByRole('button', { name: 'Merge organizations', exact: true }).click();
    await expect(
      adminPage.getByText('No duplicate organizations match these filters.')
    ).toBeVisible();
  });

  test('admin can scan and apply a name fix', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=data-quality&tab=names');
    await expect(adminPage.getByRole('table', { name: 'Data quality · Names' })).toBeVisible();
    await expect(adminPage.getByTestId('admin-filter-bar').getByLabel('Name')).toHaveCount(0);
    const nameKpis = adminPage.getByTestId('admin-kpi-card');
    await expect(nameKpis).toHaveCount(1);
    await expect(nameKpis).toContainText(['Pending']);
    await expect(adminPage.getByText(/\d+ pending/)).toHaveCount(0);
    await adminPage.getByRole('button', { name: 'Sweep pending' }).click();
    await expect(
      adminPage.getByText('Created 1, updated 0, skipped 0, cleared 0.')
    ).toBeVisible();
    await adminPage.getByRole('cell', { name: 'HARBOUR CLUB', exact: true }).click();
    const actionBar = adminPage.getByTestId('admin-editor-panel').locator('.border-t');
    await expect(actionBar.getByRole('button', { name: 'Apply', exact: true })).toBeVisible();
    await expect(actionBar.getByRole('button', { name: 'Dismiss' })).toBeVisible();
    await actionBar.getByRole('button', { name: 'Apply', exact: true }).click();
    await expect(adminPage.getByText('Name updated.')).toBeVisible();
  });

  test('admin can select every matching name from the header checkbox', async ({
    adminPage,
  }) => {
    await adminPage.goto('/admin/dashboard?section=data-quality&tab=names');
    await adminPage.getByRole('button', { name: 'Sweep pending' }).click();
    await adminPage.getByRole('checkbox', { name: 'Select visible rows' }).click();
    await adminPage.getByRole('checkbox', { name: 'Select all matching rows' }).click();
    await expect(
      adminPage.getByText(/All matching records are selected/)
    ).toBeVisible();
    await adminPage.getByRole('button', { name: 'Apply selected' }).click();
    await expect(adminPage.getByText('Updated 1. 0 failed.')).toBeVisible();
  });

  test('admin can sweep names and filter by rule', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=data-quality&tab=names');
    await expect(adminPage.getByLabel('Rule')).toHaveValue('');
    await adminPage.getByLabel('Rule').selectOption('title_case');
    await expect(adminPage.getByRole('button', { name: 'Sweep pending' })).toBeVisible();
    await adminPage.getByRole('button', { name: 'Sweep all orgs' }).click();
    await expect(
      adminPage.getByText('Created 0, updated 1, skipped 0, cleared 1.')
    ).toBeVisible();
  });

  test('admin sees which sweep includes an approved organization', async ({
    adminPage,
  }) => {
    await adminPage.goto(
      '/admin/dashboard?section=data-quality&tab=locations&organization=org-1'
    );
    await expect(
      adminPage.getByText(
        'Sweep pending only includes organizations still in review.'
      )
    ).toBeVisible();
  });

  test('admin can sweep and apply a location fix', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=data-quality&tab=locations');
    await expect(adminPage.getByRole('table', { name: 'Data quality · Locations' })).toBeVisible();
    const locationKpis = adminPage.getByTestId('admin-kpi-card');
    await expect(locationKpis).toHaveCount(1);
    await expect(locationKpis).toContainText(['Pending']);
    await expect(adminPage.getByText(/pending\./)).toHaveCount(0);
    await adminPage.getByRole('button', { name: 'Sweep pending' }).click();
    await expect(
      adminPage.getByText(
        'Created 1, updated 0, skipped 0, cleared 0, linked 0, queued 0.'
      )
    ).toBeVisible();
    await adminPage.getByRole('cell', { name: 'Swim Class', exact: true }).click();
    await expect(adminPage.getByText('Name matches the district')).toBeVisible();
    await adminPage.getByRole('button', { name: 'Apply', exact: true }).click();
    await expect(adminPage.getByText('Location updated.')).toBeVisible();
  });

  test('admin can link one model candidate from the row', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=data-quality&tab=locations');
    await adminPage.getByRole('button', { name: 'Sweep pending' }).click();
    await adminPage.getByRole('cell', { name: 'Art Class', exact: true }).click();
    await expect(adminPage.getByText('Model named more than one venue')).toBeVisible();
    await adminPage.getByRole('button', { name: 'Link 8 Harbour Road' }).click();
    await expect(adminPage.getByText('Location updated.')).toBeVisible();
    await expect(adminPage.getByRole('cell', { name: 'Art Class', exact: true })).toHaveCount(0);
  });

  test('admin can tick one location without selecting the rest', async ({
    adminPage,
  }) => {
    await adminPage.goto('/admin/dashboard?section=data-quality&tab=locations');
    await adminPage.getByRole('button', { name: 'Sweep pending' }).click();
    const rows = adminPage.getByRole('checkbox', { name: 'Select row' });
    await expect(rows).toHaveCount(2);
    await rows.first().check();
    await expect(rows.first()).toBeChecked();
    await expect(rows.nth(1)).not.toBeChecked();
    await expect(
      adminPage.getByText(/All matching records are selected/)
    ).toHaveCount(0);
    await adminPage.getByRole('button', { name: 'Apply selected' }).click();
    await expect(
      adminPage.getByRole('cell', { name: 'Swim Class', exact: true })
    ).toHaveCount(0);
    await expect(
      adminPage.getByRole('cell', { name: 'Art Class', exact: true })
    ).toBeVisible();
  });

  test('admin can select every matching location from the header checkbox', async ({
    adminPage,
  }) => {
    await adminPage.goto('/admin/dashboard?section=data-quality&tab=locations');
    await adminPage.getByRole('button', { name: 'Sweep pending' }).click();
    await adminPage.getByRole('checkbox', { name: 'Select visible rows' }).click();
    await adminPage.getByRole('checkbox', { name: 'Select all matching rows' }).click();
    await expect(
      adminPage.getByText(/All matching records are selected/)
    ).toBeVisible();
    await adminPage.getByRole('button', { name: 'Apply selected' }).click();
    await expect(adminPage.getByText('Updated 1. 0 failed.')).toBeVisible();
  });

  test('admin can queue a pin lookup from the locations tab', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=data-quality&tab=locations');
    await expect(adminPage.getByRole('button', { name: 'Look up with Google' })).toBeDisabled();
    await expect(adminPage.getByRole('button', { name: 'Export CSV' })).toHaveCount(0);
    await adminPage.getByRole('button', { name: 'Look up pins' }).click();
    await expect(adminPage.getByText('Queued 0 pin lookups.')).toBeVisible();
  });

  test('admin can edit name rule word lists', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=data-quality&tab=names');
    const exceptions = adminPage.getByLabel('Words to leave in capitals');
    const suffixes = adminPage.getByLabel('Bracket suffixes to remove');
    await expect(exceptions).toHaveValue('YMCA');
    await exceptions.click();
    await exceptions.press('End');
    await exceptions.pressSequentially(' YWCA');
    await expect(exceptions).toHaveValue('YMCA YWCA');
    await suffixes.click();
    await suffixes.press('End');
    await suffixes.pressSequentially(' edb');
    await expect(suffixes).toHaveValue('lcsd edb');
    await adminPage.getByRole('button', { name: 'Save rules' }).click();
    await expect(adminPage.getByText('Name rules saved.')).toBeVisible();
    await expect(exceptions).toHaveValue('YMCA YWCA');
    await expect(suffixes).toHaveValue('lcsd edb');
  });

  test('admin can forget a deleted organization', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=data-quality&tab=deleted');
    await expect(adminPage.getByRole('table', { name: 'Data quality · Deleted' })).toBeVisible();
    await expect(
      adminPage.getByRole('table', { name: 'Data quality · Deleted' }).getByRole('columnheader')
    ).toHaveText(['Expand', 'Name', 'Place id', 'Source', 'Deleted', 'Source id']);
    await adminPage.getByRole('cell', { name: 'Harbour Club', exact: true }).click();
    await expect(adminPage.getByText('Old Harbour')).toBeVisible();
    await expect(adminPage.getByText('admin-sub')).toBeVisible();
    await adminPage.getByRole('button', { name: 'Forget' }).click();
    await expect(adminPage.getByText(/same file/)).toBeVisible();
    await adminPage.getByRole('button', { name: 'Allow import' }).click();
    await expect(
      adminPage.getByText('No deleted organizations are blocking import.')
    ).toBeVisible();
  });

  test('admin starts a run for one organization by name', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=data-quality&tab=runs');
    await expect(adminPage.getByRole('table', { name: 'Data quality · Runs' })).toBeVisible();
    await adminPage.getByLabel('Scope').selectOption('organization');
    await expect(adminPage.getByLabel('Organization id')).toHaveCount(0);
    const organization = adminPage.getByLabel('Organization');
    await expect(adminPage.getByRole('button', { name: 'Run checks' })).toBeDisabled();
    const search = adminPage.waitForRequest(
      (request) =>
        request.url().includes('/user/organizations') &&
        request.url().includes('q=Test')
    );
    await organization.fill('Test');
    await search;
    await adminPage.getByRole('option', { name: 'Test Organization 1' }).click();
    await expect(organization).toHaveValue('Test Organization 1');
    const posted = adminPage.waitForRequest(
      (request) =>
        request.method() === 'POST' &&
        new URL(request.url()).pathname.endsWith('/admin/data-quality/runs')
    );
    await adminPage.getByRole('button', { name: 'Run checks' }).click();
    const body = (await posted).postDataJSON() as {
      scope: { kind: string; org_id?: string };
    };
    expect(body.scope).toMatchObject({
      kind: 'organization',
      org_id: 'org-1',
    });
  });

  test('admin starts a run for one import by its create time', async ({
    adminPage,
  }) => {
    await adminPage.goto('/admin/dashboard?section=data-quality&tab=runs');
    const listed = adminPage.waitForRequest(
      (request) =>
        request.method() === 'GET' &&
        request.url().includes('/admin/imports') &&
        request.url().includes('limit=20')
    );
    await adminPage.getByLabel('Scope').selectOption('import');
    await listed;
    await expect(adminPage.getByLabel('Import id')).toHaveCount(0);
    const importSelect = adminPage.getByLabel('Import');
    await expect(importSelect.locator('option[value="job-1"]')).toHaveText(
      formatDateTime('2024-02-01T00:00:00Z')
    );
    await expect(importSelect.locator('option')).toHaveCount(6);
    await importSelect.selectOption('job-1');
    const posted = adminPage.waitForRequest(
      (request) =>
        request.method() === 'POST' &&
        new URL(request.url()).pathname.endsWith('/admin/data-quality/runs')
    );
    await adminPage.getByRole('button', { name: 'Run checks' }).click();
    const body = (await posted).postDataJSON() as {
      scope: { kind: string; import_job_id?: string };
    };
    expect(body.scope).toMatchObject({
      kind: 'import',
      import_job_id: 'job-1',
    });
  });

  test('admin can merge from the organization workspace', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=organizations&org=org-1');
    await adminPage.getByRole('button', { name: 'Merge into…' }).click();
    await adminPage.getByLabel('Find organization').fill('Harbour');
    await adminPage.getByRole('button', { name: 'Find' }).click();
    await adminPage.getByRole('button', { name: 'Harbour Club Limited' }).click();
    const dialog = adminPage.getByRole('dialog', { name: 'Merge organization' });
    await expect(dialog.getByRole('button', { name: 'Merge', exact: true })).toBeEnabled();
    await dialog.getByRole('button', { name: 'Merge', exact: true }).click();
    await adminPage.getByRole('button', { name: 'Merge organizations', exact: true }).click();
    await expect(adminPage.getByRole('dialog', { name: 'Merge organization' })).toHaveCount(0);
  });
});
