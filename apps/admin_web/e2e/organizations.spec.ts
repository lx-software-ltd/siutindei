import { test, expect, mockOrganizations, mockCognitoUsers } from './fixtures/test-fixtures';

test.describe('Organizations Panel', () => {
  test.beforeEach(async ({ adminPage }) => {
  await adminPage.goto('/admin/dashboard?section=catalog');
  });

  test('should display the organizations form', async ({ adminPage }) => {
    await adminPage.getByRole('button', { name: 'New organization', exact: true }).click();

    // Check form fields
    await expect(adminPage.getByLabel('Name')).toBeVisible();
    await expect(adminPage.getByLabel('Manager')).toBeVisible();
    await expect(adminPage.getByLabel('Description', { exact: true })).toBeVisible();
    await expect(adminPage.getByLabel('Source URL')).toBeVisible();
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
    await expect(
      adminPage.getByText(
        'Catalog and page attribution, stored separately from the description.'
      )
    ).toHaveCount(0);
    await expect(
      adminPage.getByText('Use @handle or https:// URLs for each network.')
    ).toHaveCount(0);

    // Check for submit button
    await expect(adminPage.getByRole('button', { name: 'Create' })).toBeVisible();
  });

  test('should display the catalog of organizations', async ({ adminPage }) => {
    await expect(adminPage.getByRole('table', { name: 'Catalog' })).toBeVisible();
    const pendingReviewCard = adminPage
      .getByText('Pending review', { exact: true })
      .locator('..');
    await expect(pendingReviewCard).toBeVisible();
    await expect(pendingReviewCard).toHaveCSS(
      'background-color',
      'rgb(255, 255, 255)'
    );
    await expect(adminPage.getByText('With missing details')).toBeVisible();
    await expect(
      adminPage.getByText('Approved', { exact: true })
    ).toBeVisible();

    await expect(adminPage.getByRole('columnheader', { name: 'Name' })).toBeVisible();
    await expect(adminPage.getByRole('columnheader', { name: 'Review' })).toBeVisible();
    await expect(adminPage.getByRole('columnheader', { name: 'Contact' })).toBeVisible();
    await expect(adminPage.getByRole('columnheader', { name: 'Import job' })).toBeVisible();
    await expect(adminPage.getByRole('columnheader', { name: 'Manager' })).toHaveCount(0);
    await expect(adminPage.locator('#review-status-filter')).toHaveValue('');
    await expect(adminPage.getByText('First test organization')).toHaveCount(0);
    await expect(
      adminPage.getByRole('cell', { name: /pending review/ }).first()
    ).toBeVisible();
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();
    await expect(adminPage.getByText('Test Organization 2')).toBeVisible();
    await expect(adminPage.getByText('contact@org-one.test')).toBeVisible();
    await expect(adminPage.getByRole('cell', { name: 'job-1' })).toBeVisible();
    await expect(adminPage.getByText('Manager manager-user-id-456')).toBeVisible();
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

  test('should create without a manager and default it on the server', async ({
    adminPage,
  }) => {
    await adminPage.getByRole('button', { name: 'New organization', exact: true }).click();
    await adminPage.locator('#org-name').fill('Test Org');
    await adminPage.getByRole('button', { name: 'Create' }).click();
    await expect(adminPage.getByText('Manager is required.')).toHaveCount(0);
  });

  test('should fill out the organization form', async ({ adminPage }) => {
    await adminPage.getByRole('button', { name: 'New organization', exact: true }).click();
    // Fill name
    await adminPage.getByLabel('Name').fill('New Test Organization');

    // Select manager
    const managerSelect = adminPage.getByLabel('Manager');
    await managerSelect.selectOption({ index: 1 });

    // Fill description
    await adminPage
      .getByLabel('Description', { exact: true })
      .fill('This is a test organization description');
    await adminPage.getByLabel('Source URL').fill('https://neworg.example');
    await adminPage.getByLabel('Source note').fill('Imported from the catalog');

    // Verify form is filled
    await expect(adminPage.getByLabel('Name')).toHaveValue('New Test Organization');
    await expect(adminPage.getByLabel('Description', { exact: true })).toHaveValue(
      'This is a test organization description'
    );
    await expect(adminPage.getByLabel('Source URL')).toHaveValue(
      'https://neworg.example'
    );
    await expect(adminPage.getByLabel('Source note')).toHaveValue(
      'Imported from the catalog'
    );
  });

  test('should create a new organization', async ({ adminPage }) => {
    await adminPage.getByRole('button', { name: 'New organization', exact: true }).click();
    // Fill the form
    await adminPage.getByLabel('Name').fill('Brand New Organization');
    await adminPage.getByLabel('Manager').selectOption({ index: 1 }); // Select first user
    await adminPage
      .getByLabel('Description', { exact: true })
      .fill('A brand new organization');
    await adminPage.getByLabel('Source', { exact: true }).selectOption('places');

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
    await expect(adminPage.getByLabel('Description', { exact: true })).toHaveValue(
      'First test organization'
    );
    await expect(adminPage.getByLabel('Source URL')).toHaveValue(
      'https://lcsd.example/org-one'
    );
    await expect(adminPage.getByLabel('Source note')).toHaveValue('Checked listing');
    await expect(adminPage.getByLabel('Source', { exact: true })).toHaveValue('lcsd');
    await expect(adminPage.getByLabel('Description origin')).toHaveValue('official');
  });

  test('should leave the organization workspace from the catalog', async ({
    adminPage,
  }) => {
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();
    await adminPage.getByRole('row', { name: /Test Organization 1/ }).first().click();
    await expect(adminPage.getByRole('button', { name: 'Update' })).toBeVisible();
    await adminPage.getByRole('button', { name: 'Catalog' }).click();
    await expect(adminPage.getByRole('button', { name: 'Update' })).toHaveCount(0);
  });

  test('should have a delete button on the open organization', async ({
    adminPage,
  }) => {
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();
    await adminPage.getByRole('row', { name: /Test Organization 1/ }).first().click();
    await expect(adminPage.getByRole('button', { name: 'Delete' })).toBeVisible();
  });

  test('should have a name filter for the catalog', async ({ adminPage }) => {
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();
    await expect(adminPage.locator('#review-name-filter')).toBeVisible();
    await expect(adminPage.locator('label', { hasText: /^Search$/ })).toHaveCount(0);
  });

  test('should filter organizations by search query', async ({ adminPage }) => {
    // Wait for the table to load
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();
    await expect(adminPage.getByText('Test Organization 2')).toBeVisible();

    // Type in search
    const searchInput = adminPage.locator('#review-name-filter');
    await searchInput.fill('Organization 1');
    await searchInput.press('Enter');

    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();
    await expect(adminPage.getByText('Test Organization 2')).toHaveCount(0);
  });

  test('should show no results message when search has no matches', async ({ adminPage }) => {
    // Wait for the table to load
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();

    // Type in search with no matches
    const searchInput = adminPage.locator('#review-name-filter');
    await searchInput.fill('NonexistentOrganization');
    await searchInput.press('Enter');

    await expect(
      adminPage.getByText('No organizations match these filters.')
    ).toBeVisible();
  });

  test('should clear search and show all organizations', async ({ adminPage }) => {
    // Wait for the table to load
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();

    // Type in search
    const searchInput = adminPage.locator('#review-name-filter');
    await searchInput.fill('Organization 1');
    await searchInput.press('Enter');
    await expect(adminPage.getByText('Test Organization 2')).toHaveCount(0);

    await searchInput.fill('');
    await searchInput.press('Enter');

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

  test('admin should see the review column', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=catalog');
    await expect(adminPage.getByRole('columnheader', { name: 'Review' })).toBeVisible();
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
