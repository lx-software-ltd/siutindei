import { expect, test } from './fixtures/test-fixtures';

test.use({ viewport: { width: 390, height: 844 } });

test.describe('Listing captions on a phone', () => {
  test('Users repeats name, roles, and times under the email', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=cognito-users');
    const table = adminPage.getByRole('table', { name: 'Users' });
    await expect(table).toBeVisible();
    await expect(table.getByRole('columnheader', { name: 'Roles' })).toBeHidden();
    await expect(table.getByRole('columnheader', { name: 'Last Login' })).toBeHidden();

    const row = table.getByRole('row', { name: /manager@example.com/ }).first();
    const secondary = row.locator('span.md\\:hidden');
    await expect(secondary.filter({ hasText: 'Manager User' })).toBeVisible();
    await expect(secondary.getByText('Manager', { exact: true })).toBeVisible();
    await row.screenshot({ path: '/opt/cursor/artifacts/users-phone-captions.png' });

    await row.getByRole('button', { name: /Expand/ }).click();
    await expect(adminPage.getByRole('region', { name: /manager@example.com/ })).toBeVisible();
  });

  test('Catalog repeats email, phone, and manager under the name', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=catalog');
    const table = adminPage.getByRole('table', { name: 'Catalog' });
    await expect(table).toBeVisible();
    await expect(table.getByRole('columnheader', { name: 'Phone' })).toBeHidden();
    await expect(table.getByRole('columnheader', { name: 'Contact' })).toHaveCount(0);

    const row = table.getByRole('row', { name: /Test Organization 1/ }).first();
    const secondary = row.locator('span.md\\:hidden');
    await expect(secondary.filter({ hasText: 'contact@org-one.test' })).toBeVisible();
    await expect(secondary.filter({ hasText: '12345678' })).toBeVisible();
    await expect(secondary.filter({ hasText: 'manager-user-id-456' })).toBeVisible();
    await expect(row.getByText('No phone')).toHaveCount(0);
    await expect(row.getByText('No manager')).toHaveCount(0);
    await row.screenshot({ path: '/opt/cursor/artifacts/catalog-phone-captions.png' });
  });

  test('API keys repeat status and prefix, and a missing expiry is an em dash', async ({
    adminPage,
  }) => {
    await adminPage.goto('/admin/dashboard?section=api-keys');
    const table = adminPage.getByRole('table', { name: 'API keys' });
    await expect(table).toBeVisible();
    await expect(table.getByRole('columnheader', { name: 'Status' })).toBeHidden();
    await expect(table.getByRole('columnheader', { name: 'Prefix' })).toBeHidden();
    await expect(table.getByText('Never')).toHaveCount(0);

    const partner = table.getByRole('row', { name: /Partner read key/ });
    await expect(partner.locator('span.md\\:hidden').filter({ hasText: 'Full access' })).toBeVisible();
    await expect(partner.locator('span.md\\:hidden').getByText('active', { exact: true })).toBeVisible();
    await expect(partner.locator('span.lg\\:hidden').filter({ hasText: 'stk_readkey1' })).toBeVisible();
    await expect(partner.locator('span.lg\\:hidden').filter({ hasText: '—' })).toBeVisible();
    await partner.screenshot({ path: '/opt/cursor/artifacts/api-keys-phone-captions.png' });

    const revoked = table.getByRole('row', { name: /Old revoked key/ });
    await expect(revoked.locator('span.md\\:hidden').getByText('revoked', { exact: true })).toBeVisible();
  });

  test('Feedback repeats stars and the submitted time under the organization', async ({
    adminPage,
  }) => {
    await adminPage.goto('/admin/dashboard?section=feedback');
    const table = adminPage.getByRole('table', { name: 'Feedback', exact: true });
    await expect(table).toBeVisible();
    await expect(table.getByRole('columnheader', { name: 'Stars' })).toBeHidden();
    await expect(table.getByRole('columnheader', { name: 'Submitted' })).toBeHidden();

    const row = table.getByRole('row', { name: /Test Organization 1/ }).first();
    await expect(row.locator('span.md\\:hidden').filter({ hasText: '4' })).toBeVisible();
    await expect(row.locator('span.lg\\:hidden').filter({ hasText: 'user@example.com' })).toBeVisible();
    await row.screenshot({ path: '/opt/cursor/artifacts/feedback-phone-captions.png' });

    await row.click();
    await expect(adminPage.getByLabel('Description')).toBeVisible();
  });

  test('Deleted repeats place id and source id under the name', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=data-quality&tab=deleted');
    const table = adminPage.getByRole('table', { name: 'Data quality · Deleted' });
    await expect(table).toBeVisible();
    await expect(table.getByRole('columnheader', { name: 'Place id' })).toBeHidden();
    await expect(table.getByRole('columnheader', { name: 'Source id' })).toBeHidden();
    await expect(table.getByRole('columnheader', { name: 'Operations' })).toHaveCount(0);

    const row = table.getByRole('row', { name: /Harbour Club/ }).first();
    await expect(row.locator('span.md\\:hidden').filter({ hasText: 'ChIJdeleted-club' })).toBeVisible();
    await expect(row.locator('span.lg\\:hidden').filter({ hasText: 'catalog-harbour' })).toBeVisible();
    await row.screenshot({ path: '/opt/cursor/artifacts/deleted-phone-captions.png' });

    await row.click();
    await expect(adminPage.getByText('Old Harbour')).toBeVisible();
  });

  test('Tickets repeats the id and an empty reviewed time, and keeps district in the editor', async ({
    adminPage,
  }) => {
    await adminPage.goto('/admin/dashboard?section=tickets');
    const table = adminPage.getByRole('table', { name: 'Tickets' });
    await expect(table).toBeVisible();
    await expect(table.getByRole('columnheader', { name: 'Ticket ID' })).toBeHidden();
    await expect(table.getByRole('columnheader', { name: 'Reviewed' })).toBeHidden();

    const row = table.getByRole('row', { name: /T00001/ });
    await expect(row.locator('span.md\\:hidden').filter({ hasText: 'T00001' })).toBeVisible();
    await expect(row.locator('span.md\\:hidden').filter({ hasText: 'pending@example.com' })).toBeVisible();
    await expect(row.locator('span.lg\\:hidden').filter({ hasText: '—' })).toBeVisible();
    await expect(row.getByText('District')).toHaveCount(0);
    await row.screenshot({ path: '/opt/cursor/artifacts/tickets-phone-captions.png' });

    await row.click();
    const detail = adminPage.getByRole('region', { name: /T00001/ });
    await expect(detail.getByText('Ticket ID', { exact: true })).toBeVisible();
    await expect(detail.getByText('T00001', { exact: true })).toBeVisible();
  });
});
