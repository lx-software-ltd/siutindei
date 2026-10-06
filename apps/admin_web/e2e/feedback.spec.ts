import { test, expect } from './fixtures/test-fixtures';

test.describe('Feedback Panel', () => {
  test('views feedback entries and opens edit form from row', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=feedback');
    const feedbackTabs = adminPage.getByRole('group', { name: 'Feedback' });
    await expect(
      feedbackTabs.getByRole('button', { name: 'Feedback', exact: true })
    ).toHaveAttribute('aria-pressed', 'true');
    await expect(
      adminPage.getByRole('table', { name: 'Organization feedback' })
    ).toBeVisible();
    await expect(adminPage.getByPlaceholder('Search feedback...')).toHaveCount(0);

    await expect(
      adminPage.getByRole('cell', { name: 'Test Organization' }).first()
    ).toBeVisible();

    await adminPage.getByRole('row', { name: /Test Organization/ }).first().click();
    await expect(
      adminPage.getByRole('button', { name: /Set rating to 5 stars/ })
    ).toBeVisible();
    await expect(adminPage.getByLabel('Description')).toBeVisible();
  });

  test('switches between feedback entries and labels', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=feedback');
    const feedbackTabs = adminPage.getByRole('group', { name: 'Feedback' });

    await feedbackTabs.getByRole('button', { name: 'Feedback Labels' }).click();
    await expect(adminPage).toHaveURL(/feedbackView=labels/);
    await expect(
      adminPage.getByRole('table', { name: 'Feedback labels' })
    ).toBeVisible();
    await expect(adminPage.getByPlaceholder('Search labels...')).toHaveCount(0);
    await expect(
      adminPage.getByRole('button', { name: 'New feedback label' })
    ).toBeVisible();
    await expect(
      adminPage.getByRole('table', { name: 'Organization feedback' })
    ).toHaveCount(0);

    await feedbackTabs.getByRole('button', { name: 'Feedback', exact: true }).click();
    await expect(adminPage).not.toHaveURL(/feedbackView=/);
    await expect(
      adminPage.getByRole('table', { name: 'Organization feedback' })
    ).toBeVisible();
    await expect(
      adminPage.getByRole('table', { name: 'Feedback labels' })
    ).toHaveCount(0);
  });

  test('legacy feedback-labels section opens the labels tab', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard?section=feedback-labels');
    const feedbackTabs = adminPage.getByRole('group', { name: 'Feedback' });
    await expect(
      feedbackTabs.getByRole('button', { name: 'Feedback Labels' })
    ).toHaveAttribute('aria-pressed', 'true');
    await expect(
      adminPage.getByRole('table', { name: 'Feedback labels' })
    ).toBeVisible();
    const feedbackNav = adminPage
      .locator('nav.sticky')
      .getByRole('button', { name: 'Feedback', exact: true });
    await expect(feedbackNav).toHaveClass(/bg-slate-900/);
    await expect(
      adminPage.locator('nav.sticky').getByRole('button', { name: 'Feedback Labels' })
    ).toHaveCount(0);
  });
});
