import { test, expect } from './fixtures/test-fixtures';

test.describe('Cognito Users Panel', () => {
  test('views details and updates roles', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=cognito-users');
    const table = adminPage.getByRole('table', { name: 'Users' });
    await expect(table).toBeVisible();
    await expect(adminPage.getByPlaceholder('Search users...')).toHaveCount(0);

    await expect(table.getByRole('columnheader')).toHaveText([
      'Expand',
      'Email',
      'Name',
      'Provider',
      'Roles',
      'Created',
      'Last Login',
      'Operations',
    ]);

    const managerRow = table.getByRole('row', { name: /manager@example.com/ }).first();
    await expect(
      managerRow.getByRole('cell', { name: 'manager@example.com', exact: true })
    ).toBeVisible();
    await expect(managerRow.getByRole('img', { name: 'Email' })).toBeVisible();
    await expect(
      managerRow.getByText('Manager', { exact: true }).filter({ visible: true })
    ).toHaveCount(1);
    await expect(
      managerRow.getByText('Admin', { exact: true }).filter({ visible: true })
    ).toHaveCount(0);

    const adminManagerRow = table
      .getByRole('row', { name: /admin-manager@example.com/ })
      .first();
    await expect(
      adminManagerRow.getByText('Admin', { exact: true }).filter({ visible: true })
    ).toHaveCount(1);
    await expect(
      adminManagerRow.getByText('Manager', { exact: true }).filter({ visible: true })
    ).toHaveCount(1);

    await managerRow.click();
    const detail = adminPage.getByTestId('admin-row-manager-user-id-456-detail');
    await expect(detail.getByText('Raw Attributes', { exact: true })).toHaveCount(0);
    await expect(detail.getByText('Groups', { exact: true })).toHaveCount(0);
    await expect(detail.getByText('Groups:', { exact: true })).toHaveCount(0);
    await expect(detail.getByText('Email', { exact: true })).toBeVisible();
    await expect(detail.getByText('Username', { exact: true })).toBeVisible();
    await expect(detail.getByText('Status', { exact: true })).toBeVisible();
    await expect(detail.getByText('Roles', { exact: true })).toBeVisible();
    await expect(detail.getByText('Created', { exact: true })).toBeVisible();
    await expect(detail.getByText('Last Login', { exact: true })).toBeVisible();
    await expect(detail).not.toContainText('2024-01-01T00:00:00Z');
    await expect(detail).not.toContainText('2024-01-10T00:00:00Z');

    const created = await adminPage.evaluate(() => {
      const date = new Date('2024-01-01T00:00:00Z');
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
    const lastLogin = await adminPage.evaluate(() => {
      const date = new Date('2024-01-10T00:00:00Z');
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
    await expect(detail).toContainText(created);
    await expect(detail).toContainText(lastLogin);

    await managerRow.click();
    await expect(detail.getByText('Username', { exact: true })).toHaveCount(0);
    await expect(adminPage.getByTestId('admin-row-manager-user-id-456')).toHaveAttribute(
      'aria-expanded',
      'false'
    );

    await adminPage.getByTitle('Make Admin').first().click();
    await expect(adminPage.getByTitle('Remove Admin').first()).toBeVisible();
    await expect(
      managerRow.getByText('Admin', { exact: true }).filter({ visible: true })
    ).toHaveCount(1);

    await adminPage.getByRole('button', { name: 'More actions' }).first().click();
    await adminPage.getByRole('menuitem', { name: 'Delete User' }).click();
    await adminPage
      .getByRole('alertdialog')
      .getByRole('button', { name: 'Delete User' })
      .click();
    await expect(adminPage.getByRole('alertdialog')).not.toBeVisible();
    await expect(
      adminPage.getByRole('row', { name: /manager@example.com Manager User/ })
    ).toHaveCount(0);
  });
});
