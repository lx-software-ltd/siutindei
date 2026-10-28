import { test, expect, mockOrganizations, mockCognitoUsers } from './fixtures/test-fixtures';

test.describe('Organizations Panel', () => {
  test.beforeEach(async ({ adminPage }) => {
  await adminPage.goto('/admin/dashboard?section=catalog');
  });

  test('should display the organizations form', async ({ adminPage }) => {
    await adminPage.getByRole('button', { name: 'New organization', exact: true }).click();
    await expect(
      adminPage.getByRole('heading', { name: 'New organization' })
    ).toBeVisible();
    await expect(adminPage.getByRole('heading', { name: 'Details' })).toBeVisible();
    await expect(adminPage.getByText('operational', { exact: true })).toHaveCount(0);
    await expect(adminPage.getByText('pending review', { exact: true })).toHaveCount(0);

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
    await expect(adminPage.getByLabel('Website')).toBeVisible();
    const emailBox = await adminPage.locator('#org-email').boundingBox();
    const websiteBox = await adminPage.locator('#org-website').boundingBox();
    expect(emailBox && websiteBox).toBeTruthy();
    expect(Math.abs((emailBox?.y ?? 0) - (websiteBox?.y ?? 0))).toBeLessThan(8);
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
    const kpiCards = adminPage.getByTestId('admin-kpi-card');
    await expect(kpiCards).toHaveCount(3);
    for (const card of await kpiCards.all()) {
      await expect(card).toHaveCSS('background-color', 'rgb(255, 255, 255)');
    }
    await expect(kpiCards).toContainText([
      'Pending review',
      'With missing details',
      'Approved',
    ]);

    await expect(adminPage.getByRole('columnheader', { name: 'Name' })).toBeVisible();
    await expect(adminPage.getByRole('columnheader', { name: 'Review' })).toBeVisible();
    await expect(adminPage.getByRole('columnheader', { name: 'Contact' })).toHaveCount(0);
    await expect(adminPage.getByRole('columnheader', { name: 'Email' })).toHaveCount(0);
    await expect(adminPage.getByRole('columnheader', { name: 'Phone' })).toHaveCount(0);
    await expect(adminPage.getByRole('columnheader', { name: 'Manager' })).toHaveCount(0);
    await expect(adminPage.getByRole('columnheader', { name: 'Import', exact: true })).toBeVisible();
    await expect(adminPage.getByRole('columnheader', { name: 'Import job' })).toHaveCount(0);
    await expect(adminPage.getByRole('columnheader', { name: 'Version' })).toHaveCount(0);
    await expect(adminPage.getByRole('cell', { name: 'v2' })).toHaveCount(0);
    const reviewFilter = adminPage.locator('#review-status-filter');
    await expect(reviewFilter).toHaveValue('');
    await expect(
      reviewFilter.getByRole('option', { name: 'Pending', exact: true })
    ).toHaveCount(1);
    const sourceFilter = adminPage.locator('#review-source-filter');
    await expect(sourceFilter).toHaveValue('');
    for (const label of [
      'Any source',
      'LCSD',
      'EDB',
      'SWD',
      'Places',
      'Competitor',
      'Recommendation',
    ]) {
      await expect(
        sourceFilter.getByRole('option', { name: label, exact: true })
      ).toHaveCount(1);
    }
    await expect(
      reviewFilter.getByRole('option', { name: 'Pending review' })
    ).toHaveCount(0);
    await expect(adminPage.getByText('First test organization')).toHaveCount(0);
    await expect(
      adminPage.getByRole('cell', { name: 'Pending', exact: true }).first()
    ).toBeVisible();
    await expect(
      adminPage.getByRole('cell', { name: /pending review/i })
    ).toHaveCount(0);
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();
    await expect(adminPage.getByText('Test Organization 2')).toBeVisible();
    await expect(adminPage.getByRole('cell', { name: 'contact@org-one.test' })).toHaveCount(0);
    await expect(adminPage.getByRole('cell', { name: '12345678' })).toHaveCount(0);
    await expect(adminPage.getByText('No phone')).toHaveCount(0);
    await expect(adminPage.getByText('No manager')).toHaveCount(0);
    const importedAt = await adminPage.evaluate(() => {
      const date = new Date('2024-02-01T00:00:00Z');
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
    const importedRow = adminPage.getByRole('row', { name: /Test Organization 1/ });
    await expect(importedRow).toContainText(importedAt);
    await expect(importedRow).not.toContainText('job-1');
    const neverImported = adminPage.getByRole('row', { name: /Quiet Hall/ });
    await expect(neverImported).toContainText('—');
    await expect(neverImported).not.toContainText('job-');
    await adminPage
      .getByRole('table', { name: 'Catalog' })
      .screenshot({ path: '/opt/cursor/artifacts/catalog-import-column.png' });
    await expect(adminPage.getByRole('cell', { name: 'manager-user-id-456' })).toHaveCount(0);
    await expect(adminPage.getByText('Manager manager-user-id-456')).toHaveCount(0);
  });

  test('filters the catalog by source', async ({ adminPage }) => {
    await expect(adminPage.getByText('Test Organization 2')).toBeVisible();
    await adminPage.screenshot({
      path: '/opt/cursor/artifacts/catalog-source-filter-any.png',
    });
    const requestPromise = adminPage.waitForRequest(
      (request) =>
        request.method() === 'GET' &&
        request.url().includes('/admin/org-review') &&
        !request.url().includes('/summary') &&
        new URL(request.url()).searchParams.get('source') === 'lcsd'
    );
    await adminPage.locator('#review-source-filter').selectOption('lcsd');
    await requestPromise;
    await expect(
      adminPage.getByRole('cell', { name: 'Test Organization 1', exact: true })
    ).toBeVisible();
    await expect(adminPage.getByText('Test Organization 2')).toHaveCount(0);
    await expect(adminPage.getByText('Quiet Hall')).toHaveCount(0);
    await adminPage.screenshot({
      path: '/opt/cursor/artifacts/catalog-source-filter-lcsd.png',
    });

    await adminPage.getByRole('button', { name: 'Map' }).click();
    await expect(adminPage.locator('#review-source-filter')).toHaveValue('lcsd');
    await expect(adminPage.getByText('1 organization has no map pin.')).toBeVisible();
    await expect(adminPage.getByText('Test Organization 2')).toHaveCount(0);
    await expect(adminPage.getByText('Quiet Hall')).toHaveCount(0);
    await adminPage.screenshot({
      path: '/opt/cursor/artifacts/catalog-source-filter-map.png',
    });
  });

  test('filters the catalog by an import time', async ({ adminPage }) => {
    const listed = adminPage.waitForRequest((request) => {
      const url = new URL(request.url());
      return (
        request.method() === 'GET' &&
        url.pathname.endsWith('/admin/imports') &&
        url.searchParams.get('limit') === '20'
      );
    });
    await adminPage.reload();
    await listed;

    const imports = adminPage.locator('#review-import-filter');
    const name = adminPage.locator('#review-name-filter');
    const sort = adminPage.locator('#review-sort');
    await expect(imports).toHaveValue('');
    await expect(imports.locator('option').first()).toHaveText('All imports');
    const followsName = await name.evaluate((nameField, importId) => {
      const importField = document.getElementById(importId);
      const sortField = document.getElementById('review-sort');
      if (!importField || !sortField) {
        return false;
      }
      const afterName =
        nameField.compareDocumentPosition(importField) &
        Node.DOCUMENT_POSITION_FOLLOWING;
      const beforeSort =
        importField.compareDocumentPosition(sortField) &
        Node.DOCUMENT_POSITION_FOLLOWING;
      return Boolean(afterName && beforeSort);
    }, 'review-import-filter');
    expect(followsName).toBe(true);
    await expect(sort).toBeVisible();

    const values = await imports.locator('option').evaluateAll((options) =>
      options.map((option) => (option as HTMLOptionElement).value)
    );
    expect(values[0]).toBe('');
    expect(values).toEqual([
      '',
      '2024-02-01T00:00:00Z',
      '2024-01-15T00:00:00Z',
      '2024-01-20T00:00:00Z',
    ]);
    const importedAt = await adminPage.evaluate(() => {
      const date = new Date('2024-02-01T00:00:00Z');
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
    await expect(
      imports.locator('option[value="2024-02-01T00:00:00Z"]')
    ).toHaveText(importedAt);

    const requestPromise = adminPage.waitForRequest((request) => {
      if (request.method() !== 'GET' || request.url().includes('/summary')) {
        return false;
      }
      const url = new URL(request.url());
      return (
        url.pathname.includes('/admin/org-review') &&
        url.searchParams.get('import_job_id') === 'job-1'
      );
    });
    await imports.selectOption('2024-02-01T00:00:00Z');
    await requestPromise;
    await expect(imports).toHaveValue('2024-02-01T00:00:00Z');
    await expect(adminPage.getByText('Filtered to this import.')).toBeVisible();
    await expect(
      adminPage.getByRole('cell', { name: 'Test Organization 1', exact: true })
    ).toBeVisible();
    await expect(
      adminPage.getByRole('cell', { name: 'Test Organization 2', exact: true })
    ).toBeVisible();
    await expect(adminPage.getByText('Quiet Hall')).toHaveCount(0);
    await adminPage.screenshot({
      path: '/opt/cursor/artifacts/catalog-import-filter.png',
    });

    await adminPage.getByRole('button', { name: 'Map' }).click();
    await expect(adminPage.locator('#review-import-filter')).toHaveValue(
      '2024-02-01T00:00:00Z'
    );
    await expect(adminPage.getByText('Quiet Hall')).toHaveCount(0);
    await expect(
      adminPage.getByRole('link', { name: 'Open Test Organization 2 in Google Maps' })
    ).toBeVisible();

    await adminPage.getByRole('button', { name: 'Table' }).click();
    await imports.selectOption('');
    await expect(imports).toHaveValue('');
    await expect(adminPage.getByText('Quiet Hall')).toBeVisible();
    await expect(adminPage.getByText('Filtered to this import.')).toHaveCount(0);
  });

  test('should display manager selector with Cognito users', async ({ adminPage }) => {
    await adminPage.getByRole('button', { name: 'New organization', exact: true }).click();
    const managerField = adminPage.getByLabel('Manager');
    await expect(managerField).toBeVisible();
    await expect(adminPage.locator('#org-manager-search')).toHaveCount(0);
    await expect(adminPage.getByLabel('Email prefix')).toHaveCount(0);

    await managerField.click();

    await expect(
      adminPage.getByRole('option', {
        name: 'manager@example.com (Manager User)',
      })
    ).toBeVisible();
  });

  test('should add a typed email as a manager on organization details', async ({
    adminPage,
  }) => {
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();
    await adminPage.getByRole('row', { name: /Test Organization 1/ }).first().click();
    const managerField = adminPage.getByLabel('Manager');
    const searchResponse = adminPage.waitForResponse(
      (response) =>
        response.request().method() === 'GET' &&
        response.url().includes('/admin/cognito-users') &&
        response.url().includes('new.manager%40example.com')
    );
    await managerField.fill('new.manager@example.com');
    await searchResponse;
    const addOption = adminPage.getByRole('option', {
      name: 'Add new.manager@example.com as manager',
    });
    await expect(addOption).toBeVisible();
    await adminPage.screenshot({
      path: '/opt/cursor/artifacts/add-manager-by-email.png',
    });

    await addOption.click();
    const dialog = adminPage.getByRole('alertdialog', { name: 'Add manager' });
    await expect(dialog).toContainText('new.manager@example.com');
    await expect(dialog).toContainText('signed out of every device');
    await adminPage.screenshot({
      path: '/opt/cursor/artifacts/add-manager-confirm.png',
    });
    const requestPromise = adminPage.waitForRequest(
      (request) =>
        request.method() === 'POST' &&
        request.url().includes('/admin/cognito-users') &&
        !request.url().includes('/groups/')
    );
    await dialog.getByRole('button', { name: 'Add manager' }).click();
    const request = await requestPromise;
    expect(request.postDataJSON()).toEqual({
      email: 'new.manager@example.com',
    });
    await expect(dialog).toBeHidden();
    await expect(adminPage.getByRole('combobox', { name: 'Manager' })).toHaveValue(
      'new.manager@example.com'
    );
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

    const managerField = adminPage.getByLabel('Manager');
    await managerField.click();
    await adminPage
      .getByRole('option', { name: 'manager@example.com (Manager User)' })
      .click();
    await expect(managerField).toHaveValue(
      'manager@example.com (Manager User)'
    );

    // Fill description
    await adminPage
      .getByLabel('Description', { exact: true })
      .fill('This is a test organization description');
    await adminPage.getByLabel('Source URL').fill('https://neworg.example');
    await adminPage.getByLabel('Website').fill('https://neworg.example/home');
    await adminPage.getByLabel('Source note').fill('Imported from the catalog');

    // Verify form is filled
    await expect(adminPage.getByLabel('Name')).toHaveValue('New Test Organization');
    await expect(adminPage.getByLabel('Description', { exact: true })).toHaveValue(
      'This is a test organization description'
    );
    await expect(adminPage.getByLabel('Source URL')).toHaveValue(
      'https://neworg.example'
    );
    await expect(adminPage.getByLabel('Website')).toHaveValue(
      'https://neworg.example/home'
    );
    await expect(adminPage.getByLabel('Source note')).toHaveValue(
      'Imported from the catalog'
    );
  });

  test('should create a new organization', async ({ adminPage }) => {
    await adminPage.getByRole('button', { name: 'New organization', exact: true }).click();
    // Fill the form
    await adminPage.getByLabel('Name').fill('Brand New Organization');
    await adminPage.getByLabel('Manager').click();
    await adminPage
      .getByRole('option', { name: 'manager@example.com (Manager User)' })
      .click();
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
    await expect(adminPage.getByLabel('Website')).toHaveValue(
      'https://org-one.example'
    );
    await expect(adminPage.getByLabel('Source note')).toHaveValue('Checked listing');
    await expect(adminPage.getByLabel('Source', { exact: true })).toHaveValue('lcsd');
    await expect(adminPage.getByLabel('Description origin')).toHaveValue('official');
    await expect(adminPage.getByLabel('Manager')).toHaveValue(
      'manager@example.com (Manager User)'
    );
    await expect(adminPage.getByLabel('Listing status')).toBeVisible();
    await expect(adminPage.getByText(/Review state is changed/)).toHaveCount(0);
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
    await adminPage.getByRole('button', { name: 'Delete' }).click();
    await expect(adminPage.getByRole('alertdialog')).toContainText(
      'Import will skip this organization'
    );
    await adminPage.getByRole('button', { name: 'Cancel' }).click();
    await expect(adminPage.getByRole('alertdialog')).toHaveCount(0);
  });

  test('filters organizations by neighbourhood and maps them', async ({
    adminPage,
  }) => {
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();
    await expect(adminPage.getByText('Test Organization 2')).toBeVisible();
    await adminPage.getByLabel('Neighbourhood').click();
    await adminPage.getByRole('option', { name: 'Causeway Bay' }).click();
    await expect(adminPage.getByText('Test Organization 1')).toHaveCount(0);
    await expect(adminPage.getByText('Test Organization 2')).toBeVisible();

    await adminPage.getByRole('button', { name: 'Map' }).click();
    await expect(
      adminPage.getByRole('application', { name: 'Filtered organizations' })
    ).toBeVisible();
    const mapsLink = adminPage.getByRole('link', {
      name: 'Open Test Organization 2 in Google Maps',
    });
    await expect(mapsLink).toBeVisible();
    await expect(mapsLink).toHaveAttribute(
      'href',
      'https://www.google.com/maps/search/?api=1&query=22.2803,114.1846'
    );
    const orgLink = adminPage.getByRole('link', {
      name: 'Test Organization 2',
      exact: true,
    });
    await expect(orgLink).toBeVisible();
    await expect(orgLink).toHaveAttribute(
      'href',
      '/admin/dashboard?section=organizations&org=org-2'
    );
    await expect(adminPage.getByText('Test Organization 1')).toHaveCount(0);
    await orgLink.click();
    await expect(adminPage).toHaveURL(/section=organizations/);
    await expect(adminPage).toHaveURL(/org=org-2/);
    await expect(
      adminPage.getByRole('heading', { name: 'Test Organization 2' })
    ).toBeVisible();
  });

  test('should have a name filter for the catalog', async ({ adminPage }) => {
    await expect(adminPage.getByText('Test Organization 1')).toBeVisible();
    await expect(adminPage.locator('#review-name-filter')).toBeVisible();
    await expect(adminPage.getByPlaceholder('Organization name')).toBeVisible();
    await expect(adminPage.getByPlaceholder('Name', { exact: true })).toHaveCount(0);
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

  test('shows listing status in the title after review is decided', async ({
    adminPage,
  }) => {
    await adminPage.goto('/admin/dashboard?section=organizations&org=org-2');
    await expect(
      adminPage.getByRole('heading', { name: 'Test Organization 2' })
    ).toBeVisible();
    const titleRow = adminPage.getByRole('heading', {
      name: 'Test Organization 2',
    }).locator('xpath=..');
    await expect(titleRow.getByText('operational', { exact: true })).toBeVisible();
    await expect(titleRow.getByText('approved', { exact: true })).toBeVisible();
  });

  test('shows the organization version dropdown and a previous snapshot', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=organizations&org=org-1');
    await expect(
      adminPage.getByRole('heading', { name: 'Test Organization 1' })
    ).toBeVisible();
    const titleRow = adminPage.getByRole('heading', {
      name: 'Test Organization 1',
    }).locator('xpath=..');
    await expect(titleRow.getByText('operational', { exact: true })).toHaveCount(0);
    await expect(titleRow.getByText('pending review', { exact: true })).toBeVisible();
    const details = adminPage.getByRole('heading', { name: 'Details' });
    await expect(details).toBeVisible();
    const card = details.locator('xpath=ancestor::section[1]');
    await expect(card.getByText('operational', { exact: true })).toHaveCount(0);
    await expect(adminPage.getByText('v2', { exact: true })).toHaveCount(0);
    await expect(adminPage.getByRole('button', { name: 'History' })).toHaveCount(0);
    await expect(adminPage.getByTestId('admin-field-divider')).toHaveCount(2);
    const version = adminPage.getByRole('button', { name: 'Version 2 · Latest' });
    await expect(version).toBeVisible();
    const detailsBox = await details.boundingBox();
    const versionBox = await version.boundingBox();
    const cardBox = await card.boundingBox();
    expect(detailsBox).toBeTruthy();
    expect(versionBox).toBeTruthy();
    expect(cardBox).toBeTruthy();
    expect(versionBox!.x).toBeGreaterThan(detailsBox!.x);
    expect(
      Math.abs(versionBox!.x + versionBox!.width - (cardBox!.x + cardBox!.width))
    ).toBeLessThan(48);
    await expect(adminPage.getByLabel('Name')).toHaveValue('Test Organization 1');
    await version.click();
    const menu = adminPage.getByRole('menu');
    await expect(menu).toBeVisible();
    const menuBox = await menu.boundingBox();
    expect(menuBox?.x ?? 0).toBeGreaterThan(240);
    await adminPage.getByRole('menuitem', { name: /Version 1/ }).click();
    await expect(adminPage.getByText(/Viewing version/)).toHaveCount(0);
    await expect(adminPage.getByLabel('Name')).toHaveValue('Organization One Original');
    await expect(adminPage.getByText('Latest: Test Organization 1')).toBeVisible();
    await expect(adminPage.getByRole('button', { name: 'Update' })).toHaveCount(0);
    const backToLatest = adminPage.getByRole('button', { name: 'Back to latest' });
    await expect(backToLatest).toHaveCount(1);
    const editor = adminPage.getByTestId('admin-editor-panel');
    await expect(editor.getByRole('button', { name: 'Back to latest' })).toBeVisible();
    const backBox = await backToLatest.boundingBox();
    const nameBox = await adminPage.getByLabel('Name').boundingBox();
    expect(backBox).toBeTruthy();
    expect(nameBox).toBeTruthy();
    expect(backBox!.y).toBeGreaterThan(nameBox!.y);
    await expect(adminPage.getByText('Removed records')).toBeVisible();
    await expect(adminPage.getByText(/Removed Class/)).toBeVisible();
    const forgetRequest = adminPage.waitForRequest(
      (request) =>
        request.method() === 'POST' &&
        request.url().includes('/admin/versions/ver-removed/forget')
    );
    await adminPage.getByRole('button', { name: 'Forget' }).click();
    await forgetRequest;
    await expect(adminPage.getByText(/Removed Class/)).toHaveCount(0);
    await backToLatest.click();
    await expect(adminPage.getByLabel('Name')).toHaveValue('Test Organization 1');
    await expect(adminPage.getByRole('button', { name: 'Update' })).toBeVisible();
  });

  test('enriches one organization from its website', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=organizations&org=org-1');
    const enrich = adminPage.getByTestId('enrich-from-website');
    const version = adminPage.getByRole('button', { name: 'Version 2 · Latest' });
    await expect(enrich).toBeVisible();
    await expect(version).toBeVisible();
    const enrichBox = await enrich.boundingBox();
    const versionBox = await version.boundingBox();
    expect(enrichBox).toBeTruthy();
    expect(versionBox).toBeTruthy();
    expect(enrichBox!.x + enrichBox!.width).toBeLessThanOrEqual(versionBox!.x);
    await expect(
      adminPage.getByRole('heading', { name: 'Website enrichment' })
    ).toHaveCount(0);
    const started = adminPage.waitForRequest(
      (request) =>
        request.method() === 'POST' &&
        request.url().includes('/organizations/org-1/enrichment') &&
        !request.url().includes('/apply')
    );
    await enrich.click();
    await started;
    await expect(
      adminPage.getByRole('heading', { name: 'Website enrichment' })
    ).toBeVisible();
    const proposal = adminPage.locator('td').filter({
      hasText: 'description: Saturday classes for children.',
    }).filter({ hasText: 'Now: Empty' });
    await expect(
      proposal.getByText('description: Saturday classes for children.')
    ).toBeVisible();
    await expect(proposal.getByText('Now: Empty')).toBeVisible();
    const media = adminPage
      .getByRole('heading', { name: 'Media', exact: true })
      .locator('xpath=ancestor::section[1]');
    const preview = media.getByRole('img', { name: 'Children painting' });
    await expect(preview).toBeVisible();
    await expect(preview).toHaveAttribute('src', 'https://cdn.example/class.png');
    await expect(media.getByText('https://cdn.example/class.png')).toHaveCount(0);
    await expect(media.getByText(/source_url/)).toHaveCount(0);
    await adminPage.setViewportSize({ width: 390, height: 844 });
    await expect(preview).toBeVisible();
    await adminPage.setViewportSize({ width: 1280, height: 720 });
    await expect(
      adminPage.getByText(
        'Copied from the provider website for this catalog. Copyright remains with the provider.'
      )
    ).toBeVisible();
    await version.click();
    await adminPage.getByRole('menuitem', { name: /Version 1/ }).click();
    await expect(enrich).toHaveCount(0);
    await expect(
      adminPage.getByRole('heading', { name: 'Website enrichment' })
    ).toHaveCount(0);
  });

  test('enables website enrichment as soon as a website is typed', async ({
    adminPage,
  }) => {
    await adminPage.goto('/admin/dashboard?section=organizations&org=org-2');
    const enrich = adminPage.getByTestId('enrich-from-website');
    await expect(enrich).toBeDisabled();
    await expect(enrich).toHaveAttribute('title', 'Add a website first');
    await adminPage.getByLabel('Website').fill('https://typed.example');
    await expect(enrich).toBeEnabled();
    await expect(enrich).toHaveAttribute('title', 'Enrich from the website');
    const started = adminPage.waitForRequest(
      (request) =>
        request.method() === 'POST' &&
        request.url().includes('/organizations/org-2/enrichment') &&
        !request.url().includes('/apply')
    );
    await enrich.click();
    expect((await started).postDataJSON()).toEqual({
      website: 'https://typed.example',
    });
    await expect(adminPage.getByLabel('Website')).toHaveValue(
      'https://typed.example'
    );
  });

  test('applies enrichment with the fields the website left out', async ({
    adminPage,
  }) => {
    const org = mockOrganizations.find((item) => item.id === 'org-1');
    await adminPage.route(
      '**/api/mock/**/admin/organizations/org-1',
      async (route) => {
        if (route.request().method() !== 'GET') {
          await route.fallback();
          return;
        }
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ...org,
            description: 'Saturday classes for children.',
          }),
        });
      }
    );
    await adminPage.route(
      '**/api/mock/**/admin/enrichment-settings',
      async (route) => {
        const saved = {
          monthly_cost_limit_usd: 25,
          max_pages: route.request().method() === 'PUT' ? 4 : 6,
          max_page_bytes: 1000000,
          copy_media: true,
          min_confidence_shown: 0.5,
        };
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(saved),
        });
      }
    );
    let applyBody: { ids?: string[]; overrides?: Record<string, unknown> } = {};
    await adminPage.route(
      '**/api/mock/**/admin/organizations/*/enrichment/apply',
      async (route) => {
        applyBody = route.request().postDataJSON();
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            results: (applyBody.ids ?? []).map((id) => ({
              id,
              status: 'applied',
            })),
            data_quality_run_id: 'run-enrich-1',
          }),
        });
      }
    );
    await adminPage.goto('/admin/dashboard?section=organizations&org=org-1');
    await adminPage.getByTestId('enrich-from-website').click();
    await adminPage.getByTestId('enrichment-settings').click();
    await expect(adminPage.getByLabel('Pages per site')).toHaveValue('6');
    await adminPage.getByLabel('Pages per site').fill('4');
    await adminPage.getByRole('button', { name: 'Save limits' }).click();
    await expect(adminPage.getByText('Crawl limits saved.')).toBeVisible();
    await adminPage.getByLabel('Description', { exact: true }).fill('Unsaved edit');
    await expect(adminPage.getByRole('button', { name: 'Apply selected' })).toBeDisabled();
    await expect(
      adminPage.getByText('Save or discard the Details edits before applying')
    ).toBeVisible();
    await adminPage.reload();
    await expect(
      adminPage.getByRole('heading', { name: 'Website enrichment' })
    ).toBeVisible();
    await adminPage.getByRole('checkbox', { name: 'Select Description' }).check();
    await adminPage.getByRole('checkbox', { name: 'Select Activity · Painting' }).check();
    await adminPage.getByRole('checkbox', { name: 'Select Location · 1 Test Street' }).check();
    await expect(
      adminPage.getByText('Matched Hong Kong Island · Wan Chai.')
    ).toBeVisible();
    await expect(adminPage.getByLabel('Region')).toHaveValue('area-hk-island');
    await expect(adminPage.getByLabel('District')).toHaveValue('area-hk-wanchai');
    await adminPage.getByLabel('Minimum age').fill('5');
    await adminPage.getByLabel('Maximum age').fill('8');
    await adminPage.getByLabel('Category').selectOption({ label: 'Sport' });
    await adminPage.getByLabel('Neighbourhood').selectOption({ label: 'Causeway Bay' });
    await adminPage.getByRole('button', { name: 'Apply selected' }).click();
    await expect(adminPage.getByText('Selected changes were applied.')).toBeVisible();
    await expect(adminPage.getByRole('link', { name: 'done' })).toHaveAttribute(
      'href',
      '/admin/dashboard?section=data-quality&tab=runs&run=run-enrich-1'
    );
    await expect(adminPage.getByLabel('Description', { exact: true })).toHaveValue(
      'Saturday classes for children.'
    );
    expect(applyBody.ids).toEqual(
      expect.arrayContaining(['prop-1', 'prop-activity', 'prop-location'])
    );
    expect(applyBody.overrides?.['prop-activity']).toMatchObject({
      category_id: 'cat-sport',
      age_min: 5,
      age_max: 8,
    });
    expect(applyBody.overrides?.['prop-location']).toMatchObject({
      area_id: 'area-hk-causeway',
    });
  });
});

test.describe('Organizations Panel - versions unavailable', () => {
  test.use({ versionsUnavailable: true });

  test('shows an unavailable version control when history returns 404', async ({
    adminPage,
  }) => {
    await adminPage.goto('/admin/dashboard?section=organizations&org=org-1');
    await expect(adminPage.getByRole('heading', { name: 'Test Organization 1' })).toBeVisible();
    await expect(adminPage.getByRole('heading', { name: 'Details' })).toBeVisible();
    await expect(adminPage.getByRole('button', { name: 'Versions unavailable' })).toBeDisabled();
    await expect(adminPage.getByRole('button', { name: /Latest/ })).toHaveCount(0);
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
