import { expect, test, type Locator, type Page } from '@playwright/test';

/**
 * Phones keep the screen for content: one header row, one filter row, icon
 * choices in even columns, actions pinned in reach, and a short footer.
 */
const PHONE = { width: 390, height: 844 } as const;
const SMALL_PHONE = { width: 320, height: 568 } as const;
/** An iPhone screen with the browser toolbars showing. */
const PHONE_WITH_TOOLBARS = { width: 390, height: 664 } as const;

interface Box {
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
}

async function boxOf(locator: Locator): Promise<Box> {
  const box = await locator.boundingBox();
  if (!box) {
    throw new Error('element has no box');
  }
  return box;
}

async function boxesOf(locator: Locator): Promise<Box[]> {
  const count = await locator.count();
  const boxes: Box[] = [];
  for (let index = 0; index < count; index += 1) {
    boxes.push(await boxOf(locator.nth(index)));
  }
  return boxes;
}

/** How many distinct left edges and top edges a set of boxes has. */
function gridShape(boxes: readonly Box[]): { columns: number; rows: number } {
  const distinct = (values: readonly number[]) =>
    new Set(values.map((value) => Math.round(value))).size;
  return {
    columns: distinct(boxes.map((box) => box.x)),
    rows: distinct(boxes.map((box) => box.y)),
  };
}

async function expectNoSidewaysScroll(page: Page): Promise<void> {
  const widths = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  }));
  expect(widths.scrollWidth).toBeLessThanOrEqual(widths.innerWidth + 1);
}

test.describe('phone layout', () => {
  for (const viewport of [PHONE, SMALL_PHONE]) {
    test(`search results start under one header row and one filter row at ${viewport.width}px`, async ({
      page,
    }) => {
      await page.setViewportSize(viewport);
      await page.goto('/en/search/?view=list');
      const firstCard = page.locator('article.listing-card').first();
      await expect(firstCard).toBeVisible({ timeout: 30_000 });

      const header = await boxOf(page.getByRole('banner'));
      expect(header.height).toBeLessThanOrEqual(72);
      const bar = page.getByRole('banner').locator('.site-header__bar');
      const parts = await boxesOf(bar.locator(':scope > *'));
      expect(parts).toHaveLength(3);
      for (const part of parts) {
        expect(part.y + part.height).toBeLessThanOrEqual(header.y + header.height + 1);
      }

      // The header and the filter row are all that sit above the results.
      expect((await boxOf(firstCard)).y).toBeLessThanOrEqual(150);

      // The count is read out, not shown.
      const count = await boxOf(page.locator('.search-results-summary [role="status"]'));
      expect(count.width).toBeLessThanOrEqual(1);
      expect(count.height).toBeLessThanOrEqual(1);

      // Sorting lives in the filter row, and the wide copy is hidden.
      await expect(page.getByRole('combobox', { name: 'Sort by' })).toHaveCount(1);
      await expect(
        page.locator('.search-toolbar').getByRole('combobox', { name: 'Sort by' }),
      ).toBeVisible();

      // Over the results the WhatsApp button is its icon alone.
      const fab = page.locator('.whatsapp-fab');
      if ((await fab.count()) > 0) {
        expect((await boxOf(fab)).width).toBeLessThanOrEqual(56);
        await expect(fab).toHaveAccessibleName('Chat on WhatsApp');
      }

      await expectNoSidewaysScroll(page);
    });

    test(`search panel lays its choices out in even columns at ${viewport.width}px`, async ({
      page,
    }) => {
      await page.setViewportSize(viewport);
      await page.goto('/en/search/?view=list');
      await expect(page.locator('article.listing-card').first()).toBeVisible({
        timeout: 30_000,
      });
      await page.getByRole('banner').getByRole('button', { name: 'Search activities' }).first().click();
      const dialog = page.getByRole('dialog', { name: 'Search activities' });
      await expect(dialog).toBeVisible();

      const fieldsets = dialog.locator('fieldset');
      const areas = fieldsets.nth(0).locator('.search-choice');
      const ages = fieldsets.nth(1).locator('.search-choice');
      const types = fieldsets.nth(2).locator('.search-choice');

      const areaBoxes = await boxesOf(areas);
      const dialogBox = await boxOf(dialog);
      // The first area covers the others and spans the sheet.
      expect(areaBoxes[0].width).toBeGreaterThan(dialogBox.width * 0.8);
      expect(gridShape(areaBoxes.slice(1))).toEqual({ columns: 2, rows: 2 });

      const ageBoxes = await boxesOf(ages);
      expect(gridShape(ageBoxes)).toEqual({ columns: ageBoxes.length, rows: 1 });

      const typeBoxes = await boxesOf(types);
      expect(gridShape(typeBoxes).columns).toBe(2);
      expect(new Set(typeBoxes.map((box) => Math.round(box.width))).size).toBe(1);

      for (const choices of [areas, ages, types]) {
        await expect(choices.first().locator('img')).toBeVisible();
      }
      for (const box of [...areaBoxes, ...ageBoxes, ...typeBoxes]) {
        expect(box.height).toBeGreaterThanOrEqual(44);
      }

      await expectNoSidewaysScroll(page);
    });
  }

  test('wizard keeps its actions in view with the browser toolbars showing', async ({
    page,
  }) => {
    await page.setViewportSize(PHONE_WITH_TOOLBARS);
    await page.goto('/en/');
    await page.locator('.small-world-hero__copy > button').click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();

    await dialog.getByRole('button', { name: 'All Hong Kong', exact: true }).click();
    const ages = dialog.locator('fieldset .choice-tile');
    expect(gridShape(await boxesOf(ages))).toEqual({ columns: 3, rows: 1 });
    await ages.nth(1).click();

    const back = dialog.getByRole('button', { name: 'Back', exact: true });
    const see = dialog.getByRole('button', { name: 'See activities', exact: true });
    await expect(see).toBeVisible();
    const backBox = await boxOf(back);
    const seeBox = await boxOf(see);
    expect(Math.abs(backBox.y - seeBox.y)).toBeLessThanOrEqual(1);
    expect(seeBox.y + seeBox.height).toBeLessThanOrEqual(PHONE_WITH_TOOLBARS.height);
    expect(seeBox.width).toBeGreaterThan(backBox.width);

    await expectNoSidewaysScroll(page);
  });

  test('footer is short, with the link columns side by side', async ({ page }) => {
    await page.setViewportSize(PHONE);
    await page.goto('/en/about/');
    const footer = page.locator('footer');
    await footer.scrollIntoViewIfNeeded();

    expect((await boxOf(footer)).height).toBeLessThanOrEqual(520);

    const explore = await boxOf(footer.getByText('Explore', { exact: true }));
    const support = await boxOf(footer.getByText('Support', { exact: true }));
    expect(Math.abs(explore.y - support.y)).toBeLessThanOrEqual(1);
    expect(support.x).toBeGreaterThan(explore.x + 100);

    const logo = await boxOf(footer.locator('img').first());
    expect(logo.width).toBeLessThanOrEqual(96);

    for (const link of await boxesOf(footer.locator('ul a'))) {
      expect(link.height).toBeGreaterThanOrEqual(30);
    }

    // At the end of the page the floating button sits under the copyright.
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    const fab = page.locator('.whatsapp-fab');
    if ((await fab.count()) > 0) {
      const copyright = await boxOf(footer.getByText(/All rights reserved/));
      expect(copyright.y + copyright.height).toBeLessThanOrEqual((await boxOf(fab)).y);
    }

    await expectNoSidewaysScroll(page);
  });
});
