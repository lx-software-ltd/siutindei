import { test, expect } from './fixtures/test-fixtures';

const CHANGE = {
  id: '11111111-1111-4111-8111-111111111111',
  entity_type: 'organization',
  entity_id: 'org-1',
  org_id: 'org-1',
  org_name: 'Harbor Arts',
  record_name: 'Harbor Arts',
  field: 'phone_number',
  base_value: '21234567',
  current_value: '21234567',
  proposed_value: '29876543',
  import_job_id: 'job-1',
  created_at: '2026-10-14T00:00:00+00:00',
  current_user_id: 'admin-sub',
  current_import_job_id: null,
  status: 'pending',
};

test.describe('Import changes', () => {
  test('accepts one change and keeps another', async ({ adminPage }) => {
    let rows = [CHANGE, { ...CHANGE, id: '22222222-2222-4222-8222-222222222222', field: 'website' }];
    await adminPage.route('**/api/mock/**/admin/import-changes**', async (route) => {
      const url = route.request().url();
      const method = route.request().method();
      if (method === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            items: rows,
            next_cursor: null,
            pending_count: rows.length,
          }),
        });
        return;
      }
      if (method === 'POST' && url.includes('/accept-all')) {
        rows = [];
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ applied: 2 }),
        });
        return;
      }
      if (method === 'POST' && url.includes('/accept')) {
        rows = rows.filter((row) => !url.includes(row.id));
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ ...CHANGE, status: 'applied' }),
        });
        return;
      }
      if (method === 'POST' && url.includes('/dismiss')) {
        rows = rows.filter((row) => !url.includes(row.id));
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ ...CHANGE, status: 'dismissed' }),
        });
        return;
      }
      await route.fallback();
    });

    await adminPage.goto(
      '/admin/dashboard?section=data-quality&tab=import-changes&organization=org-1'
    );
    await expect(adminPage.getByRole('columnheader', { name: 'Field' })).toBeVisible();
    await adminPage.getByRole('button', { name: 'Expand Harbor Arts phone_number' }).click();
    const phoneDetail = adminPage.getByRole('region', {
      name: 'Collapse Harbor Arts phone_number',
    });
    await expect(phoneDetail.getByText('21234567').first()).toBeVisible();
    await expect(phoneDetail.getByText('29876543')).toBeVisible();
    await phoneDetail.getByRole('button', { name: 'Accept', exact: true }).click();
    await expect(
      adminPage.getByRole('button', { name: 'Expand Harbor Arts phone_number' })
    ).toHaveCount(0);

    await adminPage.getByRole('button', { name: 'Expand Harbor Arts website' }).click();
    await adminPage.getByRole('button', { name: 'Keep mine' }).click();
    await expect(adminPage.getByText('No import changes are waiting.')).toBeVisible();
  });

  test('settings name the two import policies', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=imports&tab=settings');
    await expect(adminPage.getByLabel('Existing rows')).toHaveValue('merge');
    await expect(adminPage.getByLabel('Approved organizations')).toHaveValue('propose');
    await expect(
      adminPage.getByText('Merge writes a source change when nobody edited that field.')
    ).toBeVisible();
    await expect(
      adminPage.getByText('Approved organizations queue every source change.')
    ).toBeVisible();
  });
});
