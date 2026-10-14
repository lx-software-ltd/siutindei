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
      'Roles',
      'Last Login',
      'Operations',
    ]);
    await expect(table.getByRole('columnheader', { name: 'Name' })).toHaveCount(0);
    await expect(table.getByRole('columnheader', { name: 'Provider' })).toHaveCount(0);
    await expect(table.getByRole('columnheader', { name: 'Created' })).toHaveCount(0);

    const managerRow = table.getByRole('row', { name: /manager@example.com/ }).first();
    const emailCell = managerRow.getByRole('cell').nth(1);
    await expect(emailCell).toContainText('manager@example.com');
    await expect(emailCell.getByRole('img', { name: 'Email' })).toBeVisible();
    await expect(managerRow.getByText('Manager User', { exact: true })).toHaveCount(0);
    await table.screenshot({ path: '/opt/cursor/artifacts/users-table-desktop.png' });
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
    const labels = detail.locator('dt');
    await expect(labels).toHaveText([
      'Email',
      'Username',
      'Name',
      'Provider',
      'Status',
      'Roles',
      'Created',
      'Last Login',
    ]);
    await expect(detail.locator('dd').nth(0)).toHaveText('manager@example.com');
    await expect(detail.locator('dd').nth(1)).toHaveText('manager@example.com');
    await expect(detail.locator('dd').nth(2)).toHaveText('Manager User');
    await expect(detail.locator('dd').nth(3)).toHaveText('Email');
    await expect(detail.locator('dd').nth(4)).toHaveText('confirmed');
    await expect(detail.locator('dd').nth(5)).toHaveText('Manager');
    await expect(detail.getByText(/^CONFIRMED$/)).toHaveCount(0);
    await expect(detail.locator('dt', { hasText: /^Username$/ }).locator('xpath=following-sibling::dd[1]')).toHaveClass(
      /font-mono/
    );
    await detail.screenshot({ path: '/opt/cursor/artifacts/users-row-expanded.png' });
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
      table.getByRole('cell', { name: 'manager@example.com Email', exact: true })
    ).toHaveCount(0);
  });
});
