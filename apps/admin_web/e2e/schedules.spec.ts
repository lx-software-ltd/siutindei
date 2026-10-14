import { test, expect } from './fixtures/test-fixtures';

test.describe('Schedules Panel', () => {
  test('creates a weekly schedule entry', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=schedules&org=org-1');
    await expect(adminPage.getByRole('table', { name: 'Schedules' })).toBeVisible();
    await expect(adminPage.getByRole('columnheader', { name: 'Version' })).toHaveCount(0);
    await expect(adminPage.getByRole('cell', { name: 'v1' })).toHaveCount(0);
    await expect(adminPage.getByTestId('admin-filter-bar')).toHaveCount(0);
    await expect(adminPage.getByPlaceholder('Activity, location, or time')).toHaveCount(0);
    await adminPage.getByRole('row', { name: /123 Test Street/ }).first().click();
    await expect(adminPage.getByText('Organization Version 2')).toBeVisible();
    const editor = adminPage.getByTestId('admin-editor-panel');
    const accessory = editor.getByTestId('admin-editor-accessory');
    const version = accessory.getByRole('button', { name: 'Version 1 · Latest' });
    await expect(version).toBeVisible();
    await expect(adminPage.getByRole('button', { name: 'History' })).toHaveCount(0);
    const editorBox = await editor.boundingBox();
    const versionBox = await version.boundingBox();
    const locationBox = await editor.locator('#schedule-location').boundingBox();
    expect(editorBox).toBeTruthy();
    expect(versionBox).toBeTruthy();
    expect(locationBox).toBeTruthy();
    expect(versionBox!.y).toBeLessThan(locationBox!.y);
    expect(
      Math.abs(versionBox!.x + versionBox!.width - (editorBox!.x + editorBox!.width))
    ).toBeLessThan(32);
    await adminPage.getByRole('button', { name: 'New schedule' }).click();

    await adminPage.locator('#schedule-location').selectOption('loc-1');
    await adminPage.locator('#schedule-activity').selectOption('activity-1');

    await adminPage.getByRole('button', { name: 'Mon' }).click();
    await adminPage.getByLabel('Start Time (Local)').first().selectOption({ index: 2 });
    await adminPage.getByLabel('End Time (Local)').first().selectOption({ index: 4 });
    await adminPage.getByRole('button', { name: /Toggle English/i }).click();

    await adminPage.getByRole('button', { name: 'Create' }).click();
    await expect(adminPage.getByRole('table')).toContainText('01:00-02:00');
    await expect(adminPage.getByRole('table')).toContainText('Monday');
  });
});
