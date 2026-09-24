import { test, expect } from './fixtures/test-fixtures';

test.describe('API Keys Panel', () => {
  test('lists issued keys with status and organization', async ({
    adminPage,
  }) => {
    await adminPage.goto('/admin/dashboard?section=api-keys');

    await expect(adminPage.getByRole('table', { name: 'API keys' })).toBeVisible();

    const table = adminPage.getByRole('table');
    await expect(table).toContainText('Partner read key');
    await expect(table).toContainText('stk_readkey1');
    await expect(table).toContainText('Full access');
    await expect(table).toContainText('Org One CRUD key');
    await expect(table).toContainText('Test Organization 1');
    await expect(table).toContainText('Old revoked key');
    await expect(table.getByText('revoked', { exact: true })).toBeVisible();
  });

  test('creates a key and shows the plaintext once', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=api-keys');

    await adminPage.getByRole('button', { name: 'New API key' }).click();
    await adminPage.getByLabel('Name').fill('New Partner Key');
    await adminPage.getByLabel('Scope').selectOption('crud');
    await adminPage
      .getByLabel('Organization')
      .selectOption({ label: 'Test Organization 1' });

    await adminPage.getByRole('button', { name: 'Create Key' }).click();

    await expect(adminPage.getByText('API key created')).toBeVisible();
    await expect(adminPage.getByTestId('created-api-key')).toHaveText(
      'stk_newkey12345-plaintext-shown-once'
    );

    // The new key appears in the table.
    await expect(adminPage.getByRole('table')).toContainText(
      'New Partner Key'
    );

    // Dismissing hides the plaintext permanently.
    await adminPage.getByRole('button', { name: 'Dismiss' }).click();
    await expect(adminPage.getByTestId('created-api-key')).not.toBeVisible();
  });

  test('validates the create form', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=api-keys');

    await adminPage.getByRole('button', { name: 'New API key' }).click();
    await adminPage.getByRole('button', { name: 'Create Key' }).click();
    await expect(adminPage.getByText('Name is required.')).toBeVisible();

    await adminPage.getByLabel('Name').fill('Expiring key');
    await adminPage
      .getByLabel('Expiry (optional)')
      .fill('2020-01-01T00:00');
    await adminPage.getByRole('button', { name: 'Create Key' }).click();
    await expect(
      adminPage.getByText('Expiry date must be in the future.')
    ).toBeVisible();
  });

  test('revokes a key after confirmation', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=api-keys');

    const table = adminPage.getByRole('table');
    await expect(table).toContainText('Partner read key');

    await adminPage.getByTitle('Revoke key').first().click();

    const dialog = adminPage.getByRole('dialog');
    await expect(dialog.getByText('Revoke API key?')).toBeVisible();
    await dialog.getByRole('button', { name: 'Revoke Key' }).click();

    await expect(table.getByRole('cell', { name: /revoked/i }).first()).toBeVisible();
  });

  test('lists keys without a search field', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=api-keys');

    const table = adminPage.getByRole('table');
    await expect(table).toContainText('Partner read key');
    await expect(table).toContainText('Org One CRUD key');
    await expect(adminPage.getByPlaceholder('Search keys...')).toHaveCount(0);
  });
});
