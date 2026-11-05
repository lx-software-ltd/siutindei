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
    const nameBox = await nameField.boundingBox();
    const addressBox = await editor.getByLabel('Address').boundingBox();
    expect(accessoryBox).toBeTruthy();
    expect(editorBox).toBeTruthy();
    expect(versionBox).toBeTruthy();
    expect(nameBox).toBeTruthy();
    expect(addressBox).toBeTruthy();
    expect(accessoryBox!.y).toBeLessThan(nameBox!.y);
    expect(nameBox!.y).toBeLessThan(addressBox!.y);
    await expect(nameField).toHaveValue('Harbour Hall');
    await expect(nameField).toHaveAttribute('maxlength', '200');
    await version.click();
    await adminPage.getByRole('menuitem', { name: /Version 1/ }).click();
    await expect(nameField).toHaveValue('');
    await expect(editor.getByText('Latest: Harbour Hall')).toBeVisible();
    await editor.getByRole('button', { name: 'Back to latest' }).click();
    await expect(nameField).toHaveValue('Harbour Hall');
    await nameField.fill('Studio Hall');
    const saved = adminPage.waitForRequest(
      (request) =>
        request.method() === 'PUT' &&
        request.url().includes('/admin/locations/')
    );
    await editor.getByRole('button', { name: 'Update' }).click();
    expect((await saved).postDataJSON()).toMatchObject({ name: 'Studio Hall' });
    expect(
      Math.abs(versionBox!.x + versionBox!.width - (editorBox!.x + editorBox!.width))
    ).toBeLessThan(32);

    await adminPage.getByRole('button', { name: 'Delete' }).first().click();
    await adminPage
      .getByRole('alertdialog')
      .getByRole('button', { name: 'Delete' })
      .click();
    await expect(adminPage.getByRole('alertdialog')).not.toBeVisible();
  });
});
