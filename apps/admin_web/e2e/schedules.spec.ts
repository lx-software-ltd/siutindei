import { test, expect } from './fixtures/test-fixtures';

test.describe('Schedules Panel', () => {
  test('creates a weekly schedule entry', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=schedules&org=org-1');
    const schedules = adminPage.getByRole('table', { name: 'Schedules' });
    await expect(schedules).toBeVisible();
    await expect(
      schedules
        .getByRole('img', { name: 'Cantonese (yue) flag' })
        .filter({ visible: true })
    ).not.toHaveCount(0);
    await expect(schedules.getByText('zh-HK', { exact: true })).toHaveCount(0);
    await expect(adminPage.getByRole('columnheader', { name: 'Version' })).toHaveCount(0);
    await expect(adminPage.getByRole('cell', { name: 'v1' })).toHaveCount(0);
    await expect(adminPage.getByTestId('admin-filter-bar')).toHaveCount(0);
    await expect(adminPage.getByPlaceholder('Activity, location, or time')).toHaveCount(0);
    await adminPage.getByRole('row', { name: /Harbour Hall/ }).first().click();
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

    await expect(adminPage.locator('#schedule-location')).toContainText(
      'Harbour Hall · 123 Test Street'
    );
    await expect(adminPage.locator('#schedule-location')).toContainText(
      'Harbour Hall · 9 Hill Road'
    );
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

  test('adds two dated sessions to one camp', async ({ adminPage }) => {
    const posted: Record<string, unknown>[] = [];
    adminPage.on('request', (request) => {
      if (request.method() === 'POST' && request.url().includes('/admin/schedules')) {
        posted.push(request.postDataJSON());
      }
    });
    await adminPage.goto('/admin/dashboard?section=schedules&org=org-1');
    const schedules = adminPage.getByRole('table', { name: 'Schedules' });
    await expect(schedules).toBeVisible();

    const addSession = async (firstDay: string, lastDay: string) => {
      await adminPage.getByRole('button', { name: 'New schedule' }).click();
      await adminPage.locator('#schedule-location').selectOption('loc-1');
      await adminPage.locator('#schedule-activity').selectOption('activity-1');
      await adminPage.getByLabel('First day').fill(firstDay);
      await adminPage.getByLabel('Last day').fill(lastDay);
      for (const day of ['Mon', 'Tue']) {
        await adminPage.getByRole('button', { name: day, exact: true }).click();
      }
      await adminPage.getByRole('button', { name: /Toggle English/i }).click();
      await adminPage.getByRole('button', { name: 'Create' }).click();
    };

    await addSession('2026-07-20', '2026-07-24');
    await expect(schedules).toContainText('20 Jul 2026 – 24 Jul 2026');
    await addSession('2026-08-03', '2026-08-07');
    await expect(schedules).toContainText('3 Aug 2026 – 7 Aug 2026');
    await expect(schedules).toContainText('20 Jul 2026 – 24 Jul 2026');

    expect(posted).toHaveLength(2);
    expect(posted[0]).toMatchObject({
      activity_id: 'activity-1',
      location_id: 'loc-1',
      starts_on: '2026-07-20',
      ends_on: '2026-07-24',
    });
    expect(posted[1]).toMatchObject({
      starts_on: '2026-08-03',
      ends_on: '2026-08-07',
    });
  });

  test('rejects a day outside the session dates', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=schedules&org=org-1');
    await adminPage.getByRole('button', { name: 'New schedule' }).click();
    await adminPage.locator('#schedule-location').selectOption('loc-1');
    await adminPage.locator('#schedule-activity').selectOption('activity-1');
    await adminPage.getByLabel('First day').fill('2026-07-20');
    await adminPage.getByLabel('Last day').fill('2026-07-20');
    await adminPage.getByRole('button', { name: 'Sun', exact: true }).click();
    await adminPage.getByRole('button', { name: /Toggle English/i }).click();
    await adminPage.getByRole('button', { name: 'Create' }).click();

    await expect(
      adminPage.getByText('Every day must fall between the first and last day.').first()
    ).toBeVisible();
  });
});
