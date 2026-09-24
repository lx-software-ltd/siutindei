import { test, expect, mockOrganizations, mockCognitoUsers } from './fixtures/test-fixtures';

test.describe('Organizations Panel', () => {
  test.beforeEach(async ({ adminPage }) => {
  await adminPage.goto('/admin/dashboard');
    // Organizations is the default section, so we should already be there
  });

  test('should display the organizations form', async ({ adminPage }) => {
    await adminPage.getByRole('button', { name: 'New organization', exact: true }).click();

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
    await expect(adminPage.locator('#org-email')).toBeVisible();
    await expect(adminPage.getByLabel('Phone country')).toBeVisible();
    await expect(adminPage.getByLabel('Phone number')).toBeVisible();
    await expect(adminPage.locator('#org-whatsapp')).toBeVisible();
    await expect(adminPage.locator('#org-twitter')).toBeVisible();
    await expect(adminPage.locator('#org-wechat')).toBeVisible();

    // Check for submit button
    await expect(adminPage.getByRole('button', { name: 'Create' })).toBeVisible();
  });

  test('should display existing organizations table', async ({ adminPage }) => {
    await expect(adminPage.getByRole('table', { name: 'Organizations' })).toBeVisible();

    // Check for table headers
    await expect(adminPage.getByRole('columnheader', { name: 'Name' })).toBeVisible();
    await expect(adminPage.getByRole('columnheader', { name: 'Manager' })).toBeVisible();
    await expect(adminPage.getByRole('columnheader', { name: 'Description' })).toBeVisible();
    await expect(adminPage.getByRole('columnheader', { name: 'Operations' })).toBeVisible();

    // Check for organization data
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();
    await expect(adminPage.getByText('Test Organization 2')).toBeVisible();
  });

  test('should display manager selector with Cognito users', async ({ adminPage }) => {
    await adminPage.getByRole('button', { name: 'New organization', exact: true }).click();
    const managerSelect = adminPage.getByLabel('Manager');
    await expect(managerSelect).toBeVisible();

    // Click to open the select
    await managerSelect.click();

    // Check that users are available in the dropdown
    await expect(
      adminPage.locator('#org-manager option[value="manager-user-id-456"]')
    ).toBeAttached();
  });

  test('should validate required fields on submit', async ({ adminPage }) => {
    // Try to submit empty form
    await adminPage.getByRole('button', { name: 'New organization', exact: true }).click();
    await adminPage.getByRole('button', { name: 'Create' }).click();

    // Should show error message
    await expect(adminPage.getByText('Name is required.')).toBeVisible();
  });

  test('should validate manager field on submit', async ({ adminPage }) => {
    await adminPage.getByRole('button', { name: 'New organization', exact: true }).click();
    // Fill only name
    await adminPage.getByLabel('Name').fill('Test Org');

    // Try to submit without manager
    await adminPage.getByRole('button', { name: 'Create' }).click();

    // Should show error message for manager
    await expect(adminPage.getByText('Manager is required.')).toBeVisible();
  });

  test('should fill out the organization form', async ({ adminPage }) => {
    await adminPage.getByRole('button', { name: 'New organization', exact: true }).click();
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
    await adminPage.getByRole('button', { name: 'New organization', exact: true }).click();
    // Fill the form
    await adminPage.getByLabel('Name').fill('Brand New Organization');
    await adminPage.getByLabel('Manager').selectOption({ index: 1 }); // Select first user
    await adminPage.getByLabel('Description').fill('A brand new organization');

    // Submit the form
    await adminPage.getByRole('button', { name: 'Create' }).click();

    // Form should be reset after successful creation
    // Note: In real test, we'd verify the API was called and the table updated
  });

  test('should show edit form when clicking row', async ({ adminPage }) => {
    // Wait for the table to load
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();

    // Click first organization row
    await adminPage.getByRole('row', { name: /Test Organization 1/ }).first().click();

    await expect(adminPage.getByRole('button', { name: 'Update' })).toBeVisible();
    await expect(adminPage.getByRole('button', { name: 'Cancel' })).toHaveCount(0);
  });

  test('should populate form with existing data when editing', async ({ adminPage }) => {
    // Wait for the table to load
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();

    // Click row
    await adminPage.getByRole('row', { name: /Test Organization 1/ }).first().click();

    // Form should be populated with existing data
    await expect(adminPage.getByLabel('Name')).toHaveValue('Test Organization 1');
    await expect(adminPage.getByLabel('Description')).toHaveValue('First test organization');
  });

  test('should cancel editing and reset form', async ({ adminPage }) => {
    // Wait for the table to load
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();

    // Click row
    await adminPage.getByRole('row', { name: /Test Organization 1/ }).first().click();

    await expect(adminPage.getByRole('button', { name: 'Update' })).toBeVisible();

    // Clicking the open row collapses the editor.
    await adminPage.getByRole('row', { name: /Test Organization 1/ }).first().click();

    await expect(adminPage.getByLabel('Name')).toHaveCount(0);
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
  await adminPage.goto('/admin/dashboard');

    // Should see both organizations
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();
    await expect(adminPage.getByText('Test Organization 2')).toBeVisible();
  });

  test('admin should see manager column', async ({ adminPage }) => {
  await adminPage.goto('/admin/dashboard');

    // Should see Manager column header
    await expect(adminPage.getByRole('columnheader', { name: 'Manager' })).toBeVisible();
  });

  test('admin should see manager selector in form', async ({ adminPage }) => {
  await adminPage.goto('/admin/dashboard');
    await adminPage.getByRole('button', { name: 'New organization', exact: true }).click();

    // Should see Manager field
    await expect(adminPage.getByLabel('Manager')).toBeVisible();
  });

  test('admin should be able to create new organizations', async ({ adminPage }) => {
  await adminPage.goto('/admin/dashboard');

    await expect(adminPage.getByRole('button', { name: 'New organization', exact: true })).toBeVisible();
    await adminPage.getByRole('button', { name: 'New organization', exact: true }).click();
    await expect(adminPage.getByRole('button', { name: 'Create' })).toBeVisible();
  });
});
