import { expect, test, type Page } from '@playwright/test';

import en from '../src/content/en.json';

/**
 * Search crawlers and AI fetchers often skip or time out on API calls.
 * The catalogue pages must still carry their content when every data
 * request fails.
 */
async function blockSearchData(page: Page) {
  await page.route('**/v1/**', (route) => route.abort());
  await page.route('**/fixtures/**', (route) => route.abort());
}

test('home links into the catalogue and activity pages render without the search API', async ({
  page,
}) => {
  await blockSearchData(page);
  const searchFailed = page.waitForEvent('requestfailed');
  await page.goto('/en/');
  await searchFailed;

  await expect(page.locator('h1')).toHaveCount(1);
  await expect(page.getByText(en.discovery.errorLabel)).toHaveCount(0);
  const catalogue = page.locator('section[aria-labelledby="home-catalogue-heading"]');
  await expect(catalogue).toBeVisible();
  const activityLink = catalogue.locator('a[href*="/en/activity/"]').first();
  await expect(activityLink).toBeVisible();
  const name = (await activityLink.innerText()).split('\n')[0]?.trim() ?? '';
  expect(name.length).toBeGreaterThan(0);

  await page.goto((await activityLink.getAttribute('href')) ?? '');

  await expect(page.locator('article h1')).toHaveText(name);
  await expect(page.getByText(en.activityDetail.notFoundLabel)).toHaveCount(0);
  await expect(page.getByText(en.activityDetail.errorLabel)).toHaveCount(0);
});

test('activities hub lists types and activities without the search API', async ({
  page,
}) => {
  await blockSearchData(page);
  await page.goto('/en/activities/');

  await expect(page.locator('h1')).toHaveCount(1);
  await expect(page.locator('a[href*="/en/activities/"]').first()).toBeVisible();
  await expect(page.locator('a[href*="/en/activity/"]').first()).toBeVisible();
});
