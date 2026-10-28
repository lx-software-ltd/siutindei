import { test, expect } from './fixtures/test-fixtures';

test.describe('Feedback Panel', () => {
  test('views feedback entries and opens edit form from row', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=feedback');
    const feedbackTabs = adminPage.getByRole('group', { name: 'Feedback' });
    await expect(
      feedbackTabs.getByRole('button', { name: 'Feedback', exact: true })
    ).toHaveAttribute('aria-pressed', 'true');
    await expect(
      adminPage.getByRole('table', { name: 'Feedback', exact: true })
    ).toBeVisible();
    await expect(adminPage.getByPlaceholder('Search feedback...')).toHaveCount(0);

    await expect(
      adminPage.getByRole('cell', { name: 'Test Organization' }).first()
    ).toBeVisible();
    await expect(
      adminPage.getByRole('columnheader', { name: 'Submitted' })
    ).toBeVisible();
    const submitted = await adminPage.evaluate(() => {
      const date = new Date('2024-01-03T00:00:00Z');
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
    await expect(adminPage.getByRole('table', { name: 'Feedback', exact: true })).toContainText(
      submitted
    );

    await adminPage.getByRole('row', { name: /Test Organization/ }).first().click();
    await expect(
      adminPage.getByRole('button', { name: /Set rating to 5 stars/ })
    ).toBeVisible();
    await expect(adminPage.getByLabel('Description')).toBeVisible();
  });

  test('switches between feedback entries and labels', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=feedback');
    const feedbackTabs = adminPage.getByRole('group', { name: 'Feedback' });

    await feedbackTabs.getByRole('button', { name: 'Labels' }).click();
    await expect(adminPage).toHaveURL(/feedbackView=labels/);
    await expect(
      adminPage.getByRole('table', { name: 'Feedback · Labels' })
    ).toBeVisible();
    await expect(adminPage.getByPlaceholder('Search labels...')).toHaveCount(0);
    await expect(
      adminPage.getByRole('button', { name: 'New label' })
    ).toBeVisible();
    await expect(
      adminPage.getByRole('table', { name: 'Feedback', exact: true })
    ).toHaveCount(0);

    await feedbackTabs.getByRole('button', { name: 'Feedback', exact: true }).click();
    await expect(adminPage).not.toHaveURL(/feedbackView=/);
    await expect(
      adminPage.getByRole('table', { name: 'Feedback', exact: true })
    ).toBeVisible();
    await expect(
      adminPage.getByRole('table', { name: 'Feedback · Labels' })
    ).toHaveCount(0);
  });

  test('legacy feedback-labels section opens the labels tab', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=feedback-labels');
    const feedbackTabs = adminPage.getByRole('group', { name: 'Feedback' });
    await expect(
      feedbackTabs.getByRole('button', { name: 'Labels' })
    ).toHaveAttribute('aria-pressed', 'true');
    await expect(
      adminPage.getByRole('table', { name: 'Feedback · Labels' })
    ).toBeVisible();
    const feedbackNav = adminPage
      .locator('nav.sticky')
      .getByRole('button', { name: 'Feedback', exact: true });
    await expect(feedbackNav).toHaveClass(/bg-ink-900/);
    await expect(
      adminPage.locator('nav.sticky').getByRole('button', { name: 'Feedback labels' })
    ).toHaveCount(0);
  });
});
