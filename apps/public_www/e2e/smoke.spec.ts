import { expect, test, type Page } from '@playwright/test';

function collectPageErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  return errors;
}

test('home page renders the discovery heading', async ({ page }) => {
  const errors = collectPageErrors(page);
  await page.goto('/en/');

  await expect(page).toHaveTitle(/.+/);
  await expect(page.locator('h1').first()).toBeVisible();
  expect(errors).toEqual([]);
});

test('search lists fixture activities that link to detail pages', async ({
  page,
}) => {
  const errors = collectPageErrors(page);
  await page.goto('/en/search/');

  const cards = page.locator('article.listing-card');
  await expect(cards.first()).toBeVisible({ timeout: 30_000 });
  expect(await cards.count()).toBeGreaterThan(0);

  const title = cards.first().locator('h3');
  const name = (await title.innerText()).trim();
  expect(name.length).toBeGreaterThan(0);

  await title.click();
  await expect(page).toHaveURL(/\/en\/activity\//);
  await expect(page.locator('article h1')).toHaveText(name, {
    timeout: 30_000,
  });
  expect(errors).toEqual([]);
});

test('Traditional Chinese home page renders Chinese copy', async ({ page }) => {
  await page.goto('/zh-HK/');

  await expect(page.locator('h1').first()).toHaveText(/[\u4e00-\u9fff]/);
});

test('legal pages render', async ({ page }) => {
  for (const path of ['/en/privacy/', '/en/terms/']) {
    const response = await page.goto(path);
    expect(response?.status()).toBe(200);
    await expect(page.locator('h1').first()).toBeVisible();
  }
});
