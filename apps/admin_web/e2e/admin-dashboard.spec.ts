import { test, expect } from './fixtures/test-fixtures';

test.describe('Admin Dashboard', () => {
  test('should display header with title and description', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    // Check header
    await expect(adminPage.getByRole('heading', { name: 'Siu Tin Dei Admin' })).toBeVisible();
    await expect(
      adminPage.getByText('Manage organizations, activities, and schedules.')
    ).toBeVisible();
  });

  test('should display all navigation sections', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    // Check all navigation buttons
    const expectedSections = [
      'Organizations',
      'Media',
      'Locations',
      'Categories',
      'Category Suggestions',
      'Activities',
      'Pricing',
      'Schedules',
      'Imports',
      'Tickets',
      'Feedback',
      'Feedback Labels',
      'Users',
      'API Keys',
      'Audit Logs',
    ];

    for (const section of expectedSections) {
      await expect(
        adminPage.getByRole('button', { name: section, exact: true })
      ).toBeVisible();
    }
  });

  test('should highlight Organizations as default active section', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    // Organizations should be selected by default
    const organizationsButton = adminPage.getByRole('button', { name: 'Organizations' });
    await expect(organizationsButton).toBeVisible();

    // Check that Organizations panel is visible
    await expect(adminPage.getByRole('table', { name: 'Organizations' })).toBeVisible();
  });

  test('should navigate to Media section', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    // Click Media
    await adminPage.getByRole('button', { name: 'Media' }).click();

    // Should show Media panel content
    await expect(
      adminPage.getByRole('heading', { name: 'Organization Media' })
    ).toBeVisible();
  });

  test('should navigate to Locations section', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    // Click Locations
    await adminPage.getByRole('button', { name: 'Locations' }).click();

    // Should show Locations panel content
    await expect(adminPage.getByRole('table', { name: 'Locations' })).toBeVisible();
  });

  test('should navigate to Activities section', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    // Click Activities
    await adminPage.getByRole('button', { name: 'Activities' }).click();

    // Should show Activities panel content
    await expect(adminPage.getByRole('table', { name: 'Activities' })).toBeVisible();
  });

  test('should navigate to Categories section', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    // Click Categories
    await adminPage.getByRole('button', { name: 'Categories' }).click();

    // Should show Categories panel content
    await expect(adminPage.getByRole('table', { name: 'Categories' })).toBeVisible();
  });

  test('should navigate to Pricing section', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    // Click Pricing
    await adminPage.getByRole('button', { name: 'Pricing' }).click();

    // Should show Pricing panel content
    await expect(adminPage.getByRole('table', { name: 'Pricing' })).toBeVisible();
  });

  test('should navigate to Schedules section', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    // Click Schedules
    await adminPage.getByRole('button', { name: 'Schedules' }).click();

    // Should show Schedules panel content
    await expect(adminPage.getByRole('table', { name: 'Schedules' })).toBeVisible();
  });

  test('should navigate to Imports section', async ({ adminPage }) => {
    await adminPage.goto('/');

    // Click Imports
    await adminPage.getByRole('button', { name: 'Imports' }).click();

    // Should show Imports panel content
    await expect(adminPage.getByRole('heading', { name: 'Imports' })).toBeVisible();
  });

  test('should navigate to Tickets section', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    // Click Tickets
    await adminPage.getByRole('button', { name: 'Tickets' }).click();

    // Should show Tickets panel content
    await expect(adminPage.getByRole('table', { name: 'Tickets' })).toBeVisible();
  });

  test('should navigate to Users section', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    // Click Users
    await adminPage.getByRole('button', { name: 'Users' }).click();

    // Should show Users panel content
    await expect(adminPage.getByRole('table', { name: 'Users' })).toBeVisible();
  });

  test('should switch between sections correctly', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    // Start at Organizations (default)
    await expect(adminPage.getByRole('table', { name: 'Organizations' })).toBeVisible();

    // Switch to Activities
    await adminPage.getByRole('button', { name: 'Activities' }).click();
    await expect(adminPage.getByRole('table', { name: 'Activities' })).toBeVisible();

    // Switch to Locations
    await adminPage.getByRole('button', { name: 'Locations' }).click();
    await expect(adminPage.getByRole('table', { name: 'Locations' })).toBeVisible();

    // Switch back to Organizations
    await adminPage.getByRole('button', { name: 'Organizations' }).click();
    await expect(adminPage.getByRole('table', { name: 'Organizations' })).toBeVisible();
  });

  test('should display user email in header', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    await expect(adminPage.locator('header').getByText('admin@example.com')).toBeVisible();
  });

  test('should have visible logout button', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    const logoutButton = adminPage.getByRole('button', { name: 'Log out' });
    await expect(logoutButton).toBeVisible();
    await expect(logoutButton).toBeEnabled();
  });
});

test.describe('Admin Dashboard Layout', () => {
  test('should have sidebar navigation', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    // Check that nav element exists with buttons. Each of the 15 sections
    // renders twice: desktop sidebar + mobile drawer.
    const navButtons = adminPage.locator('nav button');
    await expect(navButtons).toHaveCount(30);
  });

  test('should have main content area', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    // Main content should be visible
    const mainContent = adminPage.locator('main');
    await expect(mainContent).toBeVisible();
  });

  test('should display divider before Tickets section', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    // One divider per navigation (desktop sidebar + mobile drawer)
    const dividers = adminPage.locator('nav hr');
    await expect(dividers).toHaveCount(2);
  });
});
