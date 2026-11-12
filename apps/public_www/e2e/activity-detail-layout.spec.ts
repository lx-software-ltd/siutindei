import { expect, test, type Page } from '@playwright/test';

const VIEWPORTS = [
  { name: 'phone portrait', width: 390, height: 844 },
  { name: 'phone landscape', width: 844, height: 390 },
  { name: 'iPad portrait', width: 820, height: 1180 },
  { name: 'iPad landscape', width: 1180, height: 820 },
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'desktop portrait', width: 1080, height: 1920 },
] as const;

const ENQUIRY_TEXT = /^Ask on WhatsApp$/;
const PRICE_TEXT = /HK\$\d/;

async function pricedActivityHref(page: Page): Promise<string> {
  await page.goto('/en/search/?price=400&view=list');
  const link = page.locator('article.listing-card h3 a').first();
  await expect(link).toBeVisible({ timeout: 30_000 });
  const href = await link.getAttribute('href');
  if (!href) {
    throw new Error('listing card link missing');
  }
  return href;
}

/** True when an element matching the selector and text is painted inside the first screen. */
async function visibleInFirstScreen(
  page: Page,
  selector: string,
  text: RegExp | null = null,
): Promise<boolean> {
  return page.evaluate(
    ({ query, pattern }) => {
      const matcher = pattern ? new RegExp(pattern) : null;
      return [...document.querySelectorAll(query)].some((element) => {
        const rect = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        return (
          (!matcher || matcher.test(element.textContent ?? '')) &&
          rect.width > 0 &&
          rect.height > 0 &&
          style.visibility !== 'hidden' &&
          rect.top >= 0 &&
          rect.bottom <= window.innerHeight + 1
        );
      });
    },
    { query: selector, pattern: text?.source ?? null },
  );
}

test.describe('activity detail layout', () => {
  let href = '';

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    href = await pricedActivityHref(page);
    await page.close();
  });

  for (const viewport of VIEWPORTS) {
    test(`shows the title, price, and enquiry in the first screen on ${viewport.name}`, async ({
      page,
    }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto(href);
      await expect(page.locator('article h1')).toBeVisible({ timeout: 30_000 });

      expect(await visibleInFirstScreen(page, 'article h1')).toBe(true);
      expect(await visibleInFirstScreen(page, 'article a', ENQUIRY_TEXT)).toBe(true);
      expect(await visibleInFirstScreen(page, 'article p, article dd', PRICE_TEXT)).toBe(true);

      const widths = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        innerWidth: window.innerWidth,
      }));
      expect(widths.scrollWidth).toBeLessThanOrEqual(widths.innerWidth + 1);
      await expect(page.locator('.whatsapp-fab')).toHaveCount(0);
    });
  }
});
