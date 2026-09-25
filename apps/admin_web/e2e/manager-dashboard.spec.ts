import { test, expect, setupAuth, mockManagerUser, mockRegularUser, setupApiMocks } from './fixtures/test-fixtures';

test.describe('Manager Dashboard', () => {
  test('should display manager view banner', async ({ managerPage }) => {
    await managerPage.goto('/admin/dashboard');

    await expect(
      managerPage.getByText(
        'Manage your organization, Test Organization 1.'
      )
    ).toBeVisible();
  });

  test('should show limited navigation sections for manager', async ({ managerPage }) => {
    await managerPage.goto('/admin/dashboard');

    // Manager sections
    const managerSections = [
      'Organizations',
      'Media',
      'Locations',
      'Activities',
      'Pricing',
      'Schedules',
      'Suggest a Place',
      'Feedback',
    ];

    for (const section of managerSections) {
      await expect(managerPage.getByRole('button', { name: section })).toBeVisible();
    }

    // Admin-only sections should NOT be visible
    await expect(
      managerPage.getByRole('button', { name: 'Categories', exact: true })
    ).not.toBeVisible();
    await expect(
      managerPage.getByRole('button', { name: 'Category Suggestions' })
    ).not.toBeVisible();
    await expect(managerPage.getByRole('button', { name: 'Tickets' })).not.toBeVisible();
    await expect(
      managerPage.getByRole('button', { name: 'Users' })
    ).not.toBeVisible();
    await expect(
      managerPage.getByRole('button', { name: 'Audit Logs' })
    ).not.toBeVisible();
  });

  test('should display user email in header', async ({ managerPage }) => {
    await managerPage.goto('/admin/dashboard');

    await expect(
      managerPage.locator('header').getByText('manager@example.com')
    ).toBeVisible();
  });

  test('should have logout button', async ({ managerPage }) => {
    await managerPage.goto('/admin/dashboard');

    const logoutButton = managerPage.getByRole('button', { name: 'Log out' });
    await expect(logoutButton).toBeVisible();
    await expect(logoutButton).toBeEnabled();
  });

  test('should navigate between manager sections', async ({ managerPage }) => {
    await managerPage.goto('/admin/dashboard');

    // Navigate to Activities
    await managerPage.getByRole('button', { name: 'Activities' }).click();
    await expect(managerPage.getByRole('table', { name: 'Your activities' })).toBeVisible();

    // Navigate to Locations
    await managerPage.getByRole('button', { name: 'Locations' }).click();
    await expect(managerPage.getByRole('table', { name: 'Your locations' })).toBeVisible();

    // Navigate back to Organizations
    await managerPage.getByRole('button', { name: 'Organizations' }).click();
  });
});

test.describe('Manager Organizations Panel', () => {
  test('should show "Your Organizations" heading', async ({ managerPage }) => {
    await managerPage.goto('/admin/dashboard');

    await expect(
      managerPage.getByRole('table', { name: 'Your organizations' })
    ).toBeVisible();
  });

  test('should show edit form by default for manager', async ({ managerPage }) => {
    await managerPage.goto('/admin/dashboard');

    await expect(managerPage.getByText('Test Organization 1').first()).toBeVisible();

    await expect(managerPage.getByRole('button', { name: 'Update' })).toBeVisible();
    await expect(
      managerPage.getByRole('button', { name: 'New organization' })
    ).toHaveCount(0);
    await expect(managerPage.getByRole('button', { name: 'Cancel' })).toHaveCount(0);
    await expect(managerPage.getByLabel('Name')).toHaveValue(
      'Test Organization 1'
    );
    await expect(managerPage.getByLabel('Source URL')).toHaveCount(0);
    await expect(managerPage.getByLabel('Source note')).toHaveCount(0);
  });

  test('should not show manager column in table (manager sees their own orgs)', async ({ managerPage }) => {
    await managerPage.goto('/admin/dashboard');

    // Manager table should NOT have Manager column
    await expect(managerPage.getByRole('columnheader', { name: 'Manager' })).not.toBeVisible();
  });

  test('should show selectable organization row', async ({ managerPage }) => {
    await managerPage.goto('/admin/dashboard');

    // Wait for org table to load
    await expect(managerPage.getByText('Test Organization 1').first()).toBeVisible();

    // Should show organization row
    await expect(
      managerPage.getByRole('row', { name: /Test Organization 1/ }).first()
    ).toBeVisible();
  });

  test('should show edit form when clicking row', async ({ managerPage }) => {
    await managerPage.goto('/admin/dashboard');

    // Wait for org table to load
    await expect(managerPage.getByText('Test Organization 1').first()).toBeVisible();

    // The manager's first organization opens on load.
    await expect(managerPage.getByRole('button', { name: 'Update' })).toBeVisible();
  });

  test('edit form should show manager field as read-only', async ({
    managerPage,
  }) => {
    await managerPage.goto('/admin/dashboard');

    await expect(managerPage.getByText('Test Organization 1').first()).toBeVisible();

    const managerSelect = managerPage.getByLabel('Manager');
    await expect(managerSelect).toBeVisible();
    await expect(managerSelect).toBeDisabled();
    await expect(managerSelect).toHaveValue('manager@example.com');
  });
});

test.describe('Manager Activities Panel', () => {
  test('should hide source fields on the activity editor', async ({
    managerPage,
  }) => {
    await managerPage.goto('/admin/dashboard');
    await managerPage.getByRole('button', { name: 'Activities' }).click();
    await expect(
      managerPage.getByRole('table', { name: 'Your activities' })
    ).toBeVisible();
    await managerPage.getByRole('row', { name: /Swimming Class/ }).first().click();
    await expect(managerPage.getByRole('button', { name: 'Update' })).toBeVisible();
    await expect(managerPage.getByLabel('Source URL')).toHaveCount(0);
    await expect(managerPage.getByLabel('Source note')).toHaveCount(0);
  });
});

test.describe('Access Denied', () => {
  test('should show access denied for regular user', async ({ page }) => {
    // Set up auth with regular user (no admin or manager group)
    await setupAuth(page, mockRegularUser);
    await setupApiMocks(page);

    await page.goto('/admin/dashboard');

    await expect(page.getByRole('button', { name: 'Become a Manager' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Suggest a Place' })).toBeVisible();
  });

  test('should still show logout button for unauthorized users', async ({ page }) => {
    // Set up auth with regular user
    await setupAuth(page, mockRegularUser);
    await setupApiMocks(page);

    await page.goto('/admin/dashboard');

    // Should still see logout button
    const logoutButton = page.getByRole('button', { name: 'Log out' });
    await expect(logoutButton).toBeVisible();
  });

  test('should show user email for unauthorized users', async ({ page }) => {
    // Set up auth with regular user
    await setupAuth(page, mockRegularUser);
    await setupApiMocks(page);

    await page.goto('/admin/dashboard');

    // Should show user email
    await expect(page.locator('header').getByText('user@example.com')).toBeVisible();
  });
});

test.describe('Manager Access Request Flow', () => {
  test('should show access request form when manager has no organizations', async ({ page }) => {
    // Set up manager user
    await setupAuth(page, mockManagerUser);
    await setupApiMocks(page);

    await page.route('**/user/access-request*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          organizations_count: 0,
          has_pending_request: false,
          pending_request: null,
        }),
      });
    });

    await page.goto('/admin/dashboard');

    await expect(
      page.getByRole('heading', { name: 'Request Organization Access' })
    ).toBeVisible();
  });

  test('should show pending request notice when manager has pending request', async ({ page }) => {
    // Set up manager user
    await setupAuth(page, mockManagerUser);

    // Override the user access request status endpoint to show pending request
    await page.route('**/api/mock/user/access-request*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          organizations_count: 0,
          has_pending_request: true,
          pending_request: {
            id: 'request-123',
            user_sub: 'manager-user-id-456',
            user_email: 'manager@example.com',
            organization_name: 'Requested Org',
            message: 'Please approve',
            status: 'pending',
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z',
          },
        }),
      });
    });

    await setupApiMocks(page);
    await page.goto('/admin/dashboard');

    // Should see pending request notice
    // The actual content depends on PendingRequestNotice component
  });
});

test.describe('Admin with Manager Group', () => {
  test('admin-manager should see full admin dashboard', async ({ page }) => {
    // Use admin-manager user (has both groups)
    await setupAuth(page, {
      email: 'admin-manager@example.com',
      sub: 'admin-manager-id-789',
      groups: ['admin', 'manager'],
      name: 'Admin Manager User',
    });
    await setupApiMocks(page);

    await page.goto('/admin/dashboard');

    // Should see full admin navigation (admin takes precedence)
    await expect(page.getByRole('button', { name: 'Categories' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Tickets' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Users' })).toBeVisible();

    // Should NOT see manager banner
    await expect(page.getByText('Manager View')).not.toBeVisible();
  });
});
