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
    await adminPage
      .getByRole('button', { name: 'Release even when details are missing' })
      .click();
    await adminPage.getByRole('button', { name: 'Approve' }).click();
    await expect(adminPage.getByText(/Updated 1/)).toBeVisible();
  });

  test('lists import history', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=imports&tab=history');
    await expect(
      adminPage.getByRole('heading', { name: 'Imports · History' })
    ).toBeVisible();
    await expect(
      adminPage.getByRole('table', { name: 'Imports · History' })
    ).toBeVisible();
    await expect(
      adminPage.getByRole('columnheader', { name: 'File' })
    ).toHaveCount(0);
    await expect(
      adminPage.getByRole('columnheader', { name: 'When' })
    ).toBeVisible();
    const when = await adminPage.evaluate(() => {
      const date = new Date('2024-02-01T00:00:00Z');
      const monthDay = date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      });
      const hours24 = date.getHours();
      const period = hours24 >= 12 ? 'PM' : 'AM';
      const hours12 = hours24 % 12 || 12;
      const pad = (value: number) => String(value).padStart(2, '0');
      return `${monthDay}, ${pad(hours12)}:${pad(date.getMinutes())} ${period}`;
    });
    await expect(adminPage.getByTestId('admin-row-job-1')).toContainText(when);
    await expect(
      adminPage.getByTestId('admin-row-job-1').getByRole('link')
    ).toHaveCount(0);
    await expect(
      adminPage.getByText('admin/imports/catalog.json')
    ).toHaveCount(0);
    await expect(
      adminPage.getByText('admin/imports/dry-run.json')
    ).toHaveCount(0);
    await expect(adminPage.getByText('admin/imports/expired.json')).toHaveCount(
      0
    );
    await expect(
      adminPage.getByRole('cell', { name: 'Live execution', exact: true })
    ).toBeVisible();
    await expect(
      adminPage.getByRole('cell', { name: 'Live execution · skip existing' })
    ).toBeVisible();
    await expect(adminPage.getByRole('cell', { name: 'Dry run' })).toHaveCount(2);
    await expect(adminPage.getByText('completed', { exact: true })).toHaveCount(0);
    await expect(adminPage.getByRole('button', { name: 'View orgs' })).toHaveCount(
      2
    );
  });

  test('opens the stored import file from history', async ({ adminPage }) => {
    await adminPage.context().route('https://imports.example/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: '{"organizations":[]}',
      });
    });
    await adminPage.goto('/admin/dashboard?section=imports&tab=history');
    await expect(adminPage.getByTestId('admin-row-job-1')).toHaveAttribute(
      'data-expanded',
      'false'
    );
    await expect(
      adminPage.getByTestId('admin-row-job-1').getByRole('link')
    ).toHaveCount(0);

    await adminPage.getByRole('cell', { name: 'created 1, updated 0' }).click();
    const fileLink = adminPage
      .getByTestId('admin-row-job-1-detail')
      .getByRole('link', { name: 'admin/imports/catalog.json' });
    await expect(fileLink).toHaveAttribute(
      'href',
      'https://imports.example/admin/imports/catalog.json'
    );
    const popupPromise = adminPage.waitForEvent('popup');
    await fileLink.click();
    const popup = await popupPromise;
    await expect(popup).toHaveURL(
      'https://imports.example/admin/imports/catalog.json'
    );
    await expect(adminPage.getByTestId('admin-row-job-1')).toHaveAttribute(
      'data-expanded',
      'true'
    );
  });

  test('retries a skip-existing import with the stored flag', async ({
    adminPage,
  }) => {
    await adminPage.goto('/admin/dashboard?section=imports&tab=history');
    await adminPage.getByRole('button', { name: 'Retry failed' }).click();
    const requestPromise = adminPage.waitForRequest(
      (request) =>
        request.method() === 'POST' &&
        request.url().includes('/admin/imports') &&
        !request.url().includes('/presign')
    );
    await adminPage
      .getByRole('alertdialog')
      .getByRole('button', { name: 'Retry failed' })
      .click();
    const request = await requestPromise;
    expect(request.postDataJSON()).toMatchObject({
      object_key: 'admin/imports/skip.json',
      retry_failed: true,
      allow_updates: false,
    });
  });

  test('filters the queue to rows unchanged since import', async ({
    adminPage,
  }) => {
    await adminPage.goto('/admin/dashboard?section=catalog');
    const requestPromise = adminPage.waitForRequest(
      (request) =>
        request.url().includes('/admin/org-review') &&
        request.url().includes('changed=unchanged')
    );
    await adminPage.locator('#review-changed-filter').selectOption('unchanged');
    await requestPromise;
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
    await adminPage
      .getByRole('listitem')
      .filter({ hasText: 'Location is missing a map pin' })
      .getByRole('button', { name: 'Fix' })
      .click();
    await expect(adminPage).toHaveURL(/section=data-quality/);
    await expect(adminPage).toHaveURL(/tab=locations/);
    await expect(adminPage).toHaveURL(/organization=org-1/);
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
    await expect(
      adminPage.getByText('Filtered to the organization from the review queue.')
    ).toBeVisible();
    await expect(adminPage.locator('#check-org-filter')).toHaveCount(0);
  });
});
