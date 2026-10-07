import { test, expect } from './fixtures/test-fixtures';

test.describe('Admin Dashboard', () => {
  test('should display header with title and description', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    // Check header
    await expect(adminPage.getByRole('heading', { name: 'Siu Tin Dei Admin' })).toBeVisible();
    await expect(
      adminPage.getByText('Manage organizations, activities, and schedules.')
    ).toBeVisible();
    const brandLogo = adminPage.locator('header img[alt=""]');
    await expect(brandLogo).toBeVisible();
    await expect(brandLogo).toHaveAttribute('src', '/images/siutindei-logo.svg');
    await expect(brandLogo).toHaveCSS('width', '64px');
    await expect(brandLogo).toHaveCSS('height', '64px');
    await expect(adminPage.locator('[class*="max-w-7xl"]')).toHaveCount(3);
  });

  test('should display all navigation sections', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    // Check all navigation buttons
    const expectedSections = [
      'Catalog',
      'Organization',
      'Media',
      'Locations',
      'Activities',
      'Pricing',
      'Schedules',
      'Imports',
      'Tickets',
      'Data quality',
      'Categories',
      'Feedback',
      'API Keys',
      'Users',
      'Audit Logs',
    ];

    const desktopNavButtons = adminPage.locator('aside.hidden nav button');
    await expect(desktopNavButtons).toHaveText(expectedSections);
  });

  test('should highlight Catalog as the default active section', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    const catalogButton = adminPage.getByRole('button', { name: 'Catalog' });
    await expect(catalogButton).toBeVisible();
    await expect(adminPage.getByRole('table', { name: 'Catalog' })).toBeVisible();
  });

  test('should navigate to Media section', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    // Click Media
    await adminPage.getByRole('button', { name: 'Media' }).click();

    // Should show Media panel content
    await expect(adminPage.getByText('Choose an organization')).toBeVisible();
  });

  test('should navigate to Locations section', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    // Click Locations
    await adminPage.getByRole('button', { name: 'Locations' }).click();

    await expect(adminPage.getByText('Choose an organization')).toBeVisible();
  });

  test('should navigate to Activities section', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    // Click Activities
    await adminPage.getByRole('button', { name: 'Activities' }).click();

    await expect(adminPage.getByText('Choose an organization')).toBeVisible();
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
    await expect(adminPage.getByText('Choose an organization')).toBeVisible();
  });

  test('should navigate to Schedules section', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    // Click Schedules
    await adminPage.getByRole('button', { name: 'Schedules' }).click();

    // Should show Schedules panel content
    await expect(adminPage.getByText('Choose an organization')).toBeVisible();
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

    await expect(adminPage.getByRole('table', { name: 'Catalog' })).toBeVisible();

    await adminPage.getByRole('button', { name: 'Activities' }).click();
    await expect(adminPage.getByText('Choose an organization')).toBeVisible();

    await adminPage.getByRole('button', { name: 'Locations' }).click();
    await expect(adminPage.getByText('Choose an organization')).toBeVisible();

    await adminPage.getByRole('button', { name: 'Catalog', exact: true }).click();
    await expect(adminPage.getByRole('table', { name: 'Catalog' })).toBeVisible();
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

    // Each section renders twice: desktop sidebar and mobile drawer.
    const navButtons = adminPage.locator('nav button');
    await expect(navButtons).toHaveCount(30);
  });

  test('should have main content area', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    // Main content should be visible
    const mainContent = adminPage.locator('main');
    await expect(mainContent).toBeVisible();
  });

  test('separates catalog and schedules with rules', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    await expect(adminPage.getByText('Workspace', { exact: true })).toHaveCount(0);
    const desktopItems = adminPage.locator('aside.hidden nav').locator('button, hr');
    await expect(desktopItems).toHaveCount(17);
    const labels = await desktopItems.evaluateAll((elements) =>
      elements.map((element) =>
        element.tagName === 'HR' ? '---' : (element.textContent ?? '').trim()
      )
    );
    expect(labels[0]).toBe('Catalog');
    expect(labels[1]).toBe('---');
    expect(labels[7]).toBe('Schedules');
    expect(labels[8]).toBe('---');
    expect(labels.filter((label) => label === '---')).toHaveLength(2);
  });
});
