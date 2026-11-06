import { test, expect } from './fixtures/test-fixtures';

test.describe('Locations Panel', () => {
  test('lists locations and deletes one', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=locations&org=org-1');
    await expect(
      adminPage.getByRole('heading', { name: 'Test Organization 1' })
    ).toBeVisible();
    await expect(adminPage.getByRole('table', { name: 'Locations' })).toBeVisible();
    await expect(adminPage.getByTestId('admin-filter-bar')).toHaveCount(0);
    await expect(adminPage.getByPlaceholder('Name or address')).toHaveCount(0);
    await expect(adminPage.getByRole('columnheader', { name: 'Version' })).toHaveCount(0);
    await expect(adminPage.getByRole('cell', { name: 'v1' })).toHaveCount(0);
    await adminPage.getByRole('row', { name: /123 Test Street/ }).first().click();
    await expect(adminPage.getByText('Organization Version 2')).toBeVisible();
    const editor = adminPage.getByTestId('admin-editor-panel');
    const accessory = editor.getByTestId('admin-editor-accessory');
    const version = accessory.getByRole('button', { name: 'Version 2 · Latest' });
    await expect(version).toBeVisible();
    await expect(adminPage.getByRole('button', { name: 'History' })).toHaveCount(0);
    const accessoryBox = await accessory.boundingBox();
    const editorBox = await editor.boundingBox();
    const versionBox = await version.boundingBox();
    const nameField = editor.getByLabel('Name');
    const statusField = editor.getByLabel('Status');
    const nameBox = await nameField.boundingBox();
    const statusBox = await statusField.boundingBox();
    const addressBox = await editor.getByLabel('Address').boundingBox();
    expect(accessoryBox).toBeTruthy();
    expect(editorBox).toBeTruthy();
    expect(versionBox).toBeTruthy();
    expect(nameBox).toBeTruthy();
    expect(statusBox).toBeTruthy();
    expect(addressBox).toBeTruthy();
    expect(accessoryBox!.y).toBeLessThan(nameBox!.y);
    expect(Math.abs(statusBox!.y - nameBox!.y)).toBeLessThan(8);
    expect(statusBox!.x).toBeGreaterThan(nameBox!.x);
    expect(nameBox!.y).toBeLessThan(addressBox!.y);
    await expect(nameField).toHaveValue('Harbour Hall');
    await expect(nameField).toHaveAttribute('maxlength', '200');
    await expect(statusField).toHaveValue('temporarily_closed');
    const closedRow = adminPage.getByRole('row', { name: /123 Test Street/ });
    await expect(
      closedRow.getByRole('img', { name: 'Temporarily Closed' })
    ).toBeVisible();
    await expect(
      adminPage.getByRole('row', { name: /9 Hill Road/ }).getByRole('img', { name: /Closed/ })
    ).toHaveCount(0);
    const addressField = editor.getByLabel('Address');
    const countryField = editor.getByLabel('Country');
    const regionField = editor.getByLabel('Region');
    const latField = editor.getByLabel('Latitude');
    const lngField = editor.getByLabel('Longitude');
    await expect(nameField).toBeEnabled();
    await expect(statusField).toBeEnabled();
    await expect(addressField).toBeDisabled();
    await expect(countryField).toBeDisabled();
    await expect(regionField).toBeDisabled();
    await expect(editor.getByLabel('District')).toBeDisabled();
    await expect(editor.getByLabel('Neighbourhood')).toBeDisabled();
    await expect(latField).toBeDisabled();
    await expect(lngField).toBeDisabled();
    const addressBackground = await addressField.evaluate(
      (element) => getComputedStyle(element).backgroundColor
    );
    const countryBackground = await countryField.evaluate(
      (element) => getComputedStyle(element).backgroundColor
    );
    expect(addressBackground).toBe(countryBackground);
    await statusField.selectOption('open');
    await expect(addressField).toBeEnabled();
    await expect(regionField).toBeEnabled();
    await expect(countryField).toBeDisabled();
    await statusField.selectOption('temporarily_closed');
    await expect(addressField).toBeDisabled();
    await expect(statusField.locator('option')).toHaveText([
      'Open',
      'Temporarily Closed',
      'Permanently Closed',
    ]);
    await version.click();
    await adminPage.getByRole('menuitem', { name: /Version 1/ }).click();
    await expect(nameField).toHaveValue('');
    await expect(statusField).toHaveValue('open');
    await expect(editor.getByText('Latest: Harbour Hall')).toBeVisible();
    await expect(editor.getByText('Latest: Temporarily Closed')).toBeVisible();
    await editor.getByRole('button', { name: 'Back to latest' }).click();
    await expect(nameField).toHaveValue('Harbour Hall');
    await expect(statusField).toHaveValue('temporarily_closed');
    await nameField.fill('Studio Hall');
    await statusField.selectOption('permanently_closed');
    const saved = adminPage.waitForRequest(
      (request) =>
        request.method() === 'PUT' &&
        request.url().includes('/admin/locations/')
    );
    await editor.getByRole('button', { name: 'Update' }).click();
    expect((await saved).postDataJSON()).toMatchObject({
      name: 'Studio Hall',
      status: 'permanently_closed',
    });
    expect(
      Math.abs(versionBox!.x + versionBox!.width - (editorBox!.x + editorBox!.width))
    ).toBeLessThan(32);

    await adminPage.getByRole('button', { name: 'Delete' }).first().click();
    await adminPage
      .getByRole('alertdialog')
      .getByRole('button', { name: 'Delete' })
      .click();
    await expect(adminPage.getByRole('alertdialog')).not.toBeVisible();

    await adminPage.getByRole('button', { name: 'New location' }).click();
    const draft = adminPage.getByTestId('admin-editor-panel');
    await expect(draft.getByLabel('Status')).toHaveValue('open');
    await expect(draft.getByLabel('Address')).toBeEnabled();
    await draft.getByLabel('Status').selectOption('permanently_closed');
    await expect(draft.getByLabel('Name')).toBeEnabled();
    await expect(draft.getByLabel('Address')).toBeDisabled();
    await expect(draft.getByLabel('Latitude')).toBeDisabled();
  });
});
