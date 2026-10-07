import { test, expect } from './fixtures/test-fixtures';

test.describe('Organization review queue', () => {
  test('shows missing details and bulk-approves a pending organization', async ({
    adminPage,
  }) => {
    await adminPage.goto('/admin/dashboard?section=imports&tab=review');
    await expect(
      adminPage.getByRole('heading', { name: 'Catalog' })
    ).toBeVisible();
    await expect(
      adminPage.getByRole('cell', { name: 'Test Organization 1', exact: true })
    ).toBeVisible();
    await expect(
      adminPage.getByRole('cell', { name: 'No locations' })
    ).toBeVisible();

    await adminPage.getByRole('checkbox', { name: 'Select row' }).first().check();
    await adminPage.getByRole('checkbox', {
      name: 'Release even when details are missing',
    }).check();
    await adminPage.getByRole('button', { name: 'Approve' }).click();
    await expect(adminPage.getByText(/Updated 1/)).toBeVisible();
  });

  test('lists import history', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=imports&tab=history');
    await expect(
      adminPage.getByRole('heading', { name: 'Import history' })
    ).toBeVisible();
    await expect(
      adminPage.getByRole('cell', { name: 'admin/imports/catalog.json' })
    ).toBeVisible();
    await expect(
      adminPage.getByRole('cell', { name: 'admin/imports/dry-run.json' })
    ).toBeVisible();
    await expect(adminPage.getByRole('button', { name: 'View orgs' })).toHaveCount(
      1
    );
  });

  test('filters the queue when the name is submitted', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=catalog');
    const requestPromise = adminPage.waitForRequest(
      (request) =>
        request.url().includes('/admin/org-review') &&
        request.url().includes('q=Studio')
    );
    await adminPage.getByLabel('Name').fill('Studio');
    await adminPage.getByLabel('Name').press('Enter');
    await requestPromise;
  });

  test('applies a bulk property and opens the fix link', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=catalog');
    await adminPage.getByRole('checkbox', { name: 'Select row' }).first().check();
    await adminPage.getByRole('button', { name: 'Apply properties' }).click();
    await adminPage.getByRole('checkbox', { name: 'Email' }).check();
    await adminPage.getByRole('textbox', { name: 'Email' }).fill('studio@example.com');
    await adminPage.getByRole('button', { name: 'Apply to selected' }).click();
    await expect(adminPage.getByText(/Updated 1/)).toBeVisible();

    await adminPage.getByRole('cell', { name: 'Test Organization 1', exact: true }).click();
    await adminPage.getByRole('button', { name: 'Fix' }).first().click();
    await expect(adminPage).toHaveURL(/section=locations/);
    await expect(adminPage).toHaveURL(/location=loc-1/);
    await expect(adminPage).toHaveURL(/org=org-1/);
  });

  test('releases one organization from readiness and opens its category check', async ({
    adminPage,
  }) => {
    await adminPage.goto('/admin/dashboard?section=organizations&org=org-1');
    await expect(adminPage.getByRole('heading', { name: 'Readiness' })).toBeVisible();
    await expect(adminPage.getByRole('button', { name: 'Reject' })).toBeVisible();
    await expect(adminPage.getByRole('button', { name: 'Reopen' })).toBeVisible();
    await adminPage.getByRole('checkbox', { name: /Approve anyway/ }).check();
    await adminPage.getByRole('button', { name: 'Approve', exact: true }).click();
    await expect(
      adminPage.getByText(
        'Organization approved. Public search can stay cached for up to 5 minutes.'
      )
    ).toBeVisible();
    await adminPage.getByRole('button', { name: 'Reject' }).click();
    await expect(adminPage.getByText('Organization rejected.')).toBeVisible();
    await adminPage.getByRole('button', { name: 'Reopen' }).click();
    await expect(adminPage.getByText('Organization reopened.')).toBeVisible();

    await adminPage
      .getByRole('listitem')
      .filter({ hasText: 'Category check is waiting' })
      .getByRole('button', { name: 'Fix' })
      .click();
    await expect(adminPage).toHaveURL(/section=data-quality/);
    await expect(adminPage).toHaveURL(/tab=checks/);
    await expect(adminPage).toHaveURL(/organization=org-1/);
    await expect(adminPage.locator('#check-org-filter')).toHaveValue('org-1');
  });
});
