import { test, expect, mockOrganizations, mockCognitoUsers } from './fixtures/test-fixtures';

test.describe('Organizations Panel', () => {
  test.beforeEach(async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');
    await adminPage.getByRole('button', { name: 'Organizations' }).click();
  });

  test('should display the organizations form', async ({ adminPage }) => {
    // Check for New Organization form
    await expect(adminPage.getByRole('heading', { name: 'New Organization' })).toBeVisible();

    // Check form fields
    await expect(adminPage.getByLabel('Name')).toBeVisible();
    await expect(adminPage.getByLabel('Manager')).toBeVisible();
    await expect(adminPage.getByLabel('Description')).toBeVisible();
    await expect(
      adminPage
        .getByRole('button', { name: 'Select English (en)' })
        .first()
    ).toBeVisible();
    await expect(
      adminPage
        .getByRole('button', { name: 'Select Chinese (zh)' })
        .first()
    ).toBeVisible();
    await expect(
      adminPage
        .getByRole('button', { name: 'Select Cantonese (yue)' })
        .first()
    ).toBeVisible();
    await expect(adminPage.getByLabel('Email')).toBeVisible();
    await expect(adminPage.getByLabel('Phone country')).toBeVisible();
    await expect(adminPage.getByLabel('Phone number')).toBeVisible();
    await expect(adminPage.getByLabel('WhatsApp')).toBeVisible();
    await expect(adminPage.getByLabel('X')).toBeVisible();
    await expect(adminPage.getByLabel('WeChat')).toBeVisible();

    // Check for submit button
    await expect(adminPage.getByRole('button', { name: 'Add Organization' })).toBeVisible();
  });

  test('should display existing organizations table', async ({ adminPage }) => {
    // Check for existing organizations section
    await expect(adminPage.getByRole('heading', { name: 'Existing Organizations' })).toBeVisible();

    // Check for table headers
    await expect(adminPage.getByRole('columnheader', { name: 'Name' })).toBeVisible();
    await expect(adminPage.getByRole('columnheader', { name: 'Manager' })).toBeVisible();
    await expect(adminPage.getByRole('columnheader', { name: 'Description' })).toBeVisible();
    await expect(adminPage.getByRole('columnheader', { name: 'Actions' })).toBeVisible();

    // Check for organization data
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();
    await expect(adminPage.getByText('Test Organization 2')).toBeVisible();
  });

  test('should display manager selector with Cognito users', async ({ adminPage }) => {
    const managerSelect = adminPage.getByLabel('Manager');
    await expect(managerSelect).toBeVisible();

    // Click to open the select
    await managerSelect.click();

    // Check that users are available in the dropdown
    await expect(adminPage.locator('option').filter({ hasText: 'manager@example.com' })).toBeVisible();
  });

  test('should validate required fields on submit', async ({ adminPage }) => {
    // Try to submit empty form
    await adminPage.getByRole('button', { name: 'Add Organization' }).click();

    // Should show error message
    await expect(adminPage.getByText('Name is required.')).toBeVisible();
  });

  test('should validate manager field on submit', async ({ adminPage }) => {
    // Fill only name
    await adminPage.getByLabel('Name').fill('Test Org');

    // Try to submit without manager
    await adminPage.getByRole('button', { name: 'Add Organization' }).click();

    // Should show error message for manager
    await expect(adminPage.getByText('Manager is required.')).toBeVisible();
  });

  test('should fill out the organization form', async ({ adminPage }) => {
    // Fill name
    await adminPage.getByLabel('Name').fill('New Test Organization');

    // Select manager
    const managerSelect = adminPage.getByLabel('Manager');
    await managerSelect.selectOption({ index: 1 });

    // Fill description
    await adminPage.getByLabel('Description').fill('This is a test organization description');

    // Verify form is filled
    await expect(adminPage.getByLabel('Name')).toHaveValue('New Test Organization');
    await expect(adminPage.getByLabel('Description')).toHaveValue(
      'This is a test organization description'
    );
  });

  test('should create a new organization', async ({ adminPage }) => {
    // Fill the form
    await adminPage.getByLabel('Name').fill('Brand New Organization');
    await adminPage.getByLabel('Manager').selectOption({ index: 1 }); // Select first user
    await adminPage.getByLabel('Description').fill('A brand new organization');

    // Submit the form
    await adminPage.getByRole('button', { name: 'Add Organization' }).click();

    // Form should be reset after successful creation
    // Note: In real test, we'd verify the API was called and the table updated
  });

  test('should show edit form when clicking row', async ({ adminPage }) => {
    // Wait for the table to load
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();

    // Click first organization row
    await adminPage.getByRole('row', { name: /Test Organization 1/ }).click();

    // Form title should change to "Edit Organization"
    await expect(adminPage.getByRole('heading', { name: 'Edit Organization' })).toBeVisible();

    // Cancel button should appear
    await expect(adminPage.getByRole('button', { name: 'Cancel' })).toBeVisible();

    // Submit button text should change
    await expect(adminPage.getByRole('button', { name: 'Update Organization' })).toBeVisible();
  });

  test('should populate form with existing data when editing', async ({ adminPage }) => {
    // Wait for the table to load
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();

    // Click row
    await adminPage.getByRole('row', { name: /Test Organization 1/ }).click();

    // Form should be populated with existing data
    await expect(adminPage.getByLabel('Name')).toHaveValue('Test Organization 1');
    await expect(adminPage.getByLabel('Description')).toHaveValue('First test organization');
  });

  test('should cancel editing and reset form', async ({ adminPage }) => {
    // Wait for the table to load
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();

    // Click row
    await adminPage.getByRole('row', { name: /Test Organization 1/ }).click();

    // Verify we're in edit mode
    await expect(adminPage.getByRole('heading', { name: 'Edit Organization' })).toBeVisible();

    // Click Cancel
    await adminPage.getByRole('button', { name: 'Cancel' }).click();

    // Should return to "New Organization" form
    await expect(adminPage.getByRole('heading', { name: 'New Organization' })).toBeVisible();

    // Form should be reset
    await expect(adminPage.getByLabel('Name')).toHaveValue('');
  });

  test('should have delete button for each organization', async ({ adminPage }) => {
    // Wait for the table to load
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();

    // Each row should have a Delete button
    const deleteButtons = adminPage.getByRole('button', { name: 'Delete' });
    await expect(deleteButtons).toHaveCount(2); // We have 2 mock organizations
  });

  test('should have search input for organizations', async ({ adminPage }) => {
    // Wait for the table to load
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();

    // Check for search input
    const searchInput = adminPage.getByPlaceholder('Search organizations...');
    await expect(searchInput).toBeVisible();
  });

  test('should filter organizations by search query', async ({ adminPage }) => {
    // Wait for the table to load
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();
    await expect(adminPage.getByText('Test Organization 2')).toBeVisible();

    // Type in search
    const searchInput = adminPage.getByPlaceholder('Search organizations...');
    await searchInput.fill('Organization 1');

    // Should only show matching organization
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();
    await expect(adminPage.getByText('Test Organization 2')).not.toBeVisible();
  });

  test('should show no results message when search has no matches', async ({ adminPage }) => {
    // Wait for the table to load
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();

    // Type in search with no matches
    const searchInput = adminPage.getByPlaceholder('Search organizations...');
    await searchInput.fill('NonexistentOrganization');

    // Should show no results message
    await expect(adminPage.getByText('No organizations match your search.')).toBeVisible();
  });

  test('should clear search and show all organizations', async ({ adminPage }) => {
    // Wait for the table to load
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();

    // Type in search
    const searchInput = adminPage.getByPlaceholder('Search organizations...');
    await searchInput.fill('Organization 1');

    // Should only show one
    await expect(adminPage.getByText('Test Organization 2')).not.toBeVisible();

    // Clear search
    await searchInput.fill('');

    // Should show all again
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();
    await expect(adminPage.getByText('Test Organization 2')).toBeVisible();
  });
});

test.describe('Organizations Panel - Admin vs Manager', () => {
  test('admin should see all organizations', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=organizations');

    // Should see both organizations
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();
    await expect(adminPage.getByText('Test Organization 2')).toBeVisible();
  });

  test('admin should see manager column', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=organizations');

    // Should see Manager column header
    await expect(adminPage.getByRole('columnheader', { name: 'Manager' })).toBeVisible();
  });

  test('admin should see manager selector in form', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=organizations');

    // Should see Manager field
    await expect(adminPage.getByLabel('Manager')).toBeVisible();
  });

  test('admin should be able to create new organizations', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=organizations');

    // Should see the "New Organization" form
    await expect(adminPage.getByRole('heading', { name: 'New Organization' })).toBeVisible();
    await expect(adminPage.getByRole('button', { name: 'Add Organization' })).toBeVisible();
  });
});
