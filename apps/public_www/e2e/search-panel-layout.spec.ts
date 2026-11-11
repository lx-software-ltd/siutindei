import { expect, test, type Page } from '@playwright/test';

/**
 * The search panel must fit phone screens: nothing past the right edge,
 * the title and close button on screen, and Search within reach.
 * Heights are the visible area with the browser toolbars showing.
 */
const VIEWPORTS = [
  { name: 'iPhone 11 portrait', width: 414, height: 715, pinned: true },
  { name: 'small phone portrait', width: 320, height: 454, pinned: true },
  { name: 'iPhone 11 landscape', width: 800, height: 364, pinned: false },
] as const;

const LOCALES = [
  { locale: 'en', title: 'Search activities', search: 'Search' },
  { locale: 'zh-HK', title: '搜尋活動', search: '搜尋' },
] as const;

interface PanelBoxes {
  readonly innerWidth: number;
  readonly innerHeight: number;
  readonly pageScrollWidth: number;
  readonly dialogTop: number;
  readonly dialogBottom: number;
  readonly titleTop: number;
  readonly closeTop: number;
  readonly sidewaysScroll: number;
  readonly elementsPastEdge: number;
  readonly searchBottom: number;
  readonly searchBottomAfterScroll: number;
}

async function measurePanel(page: Page, searchLabel: string): Promise<PanelBoxes> {
  return page.evaluate((label) => {
    const dialog = document.querySelector('[role="dialog"]');
    const title = dialog?.querySelector('h2');
    const close = dialog?.querySelector('button[aria-label="Close"]');
    const search = [...(dialog?.querySelectorAll('button') ?? [])].find(
      (button) => button.textContent?.trim() === label,
    );
    if (!dialog || !title || !close || !search) {
      throw new Error('search panel parts missing');
    }
    const descendants = [...dialog.querySelectorAll('*')];
    const elementsPastEdge = descendants.filter((element) => {
      const rect = element.getBoundingClientRect();
      return (
        rect.width > 0 &&
        (rect.right > window.innerWidth + 0.5 || rect.left < -0.5)
      );
    }).length;
    const scrollers = descendants.filter((element) => {
      const style = getComputedStyle(element);
      return style.overflowX !== 'visible' || style.overflowY !== 'visible';
    });
    const sidewaysScroll = Math.max(
      0,
      ...scrollers.map((element) => element.scrollWidth - element.clientWidth),
    );
    const searchBottom = search.getBoundingClientRect().bottom;
    for (const element of descendants) {
      element.scrollTop = element.scrollHeight;
    }
    const dialogRect = dialog.getBoundingClientRect();
    return {
      innerWidth: window.innerWidth,
      innerHeight: window.innerHeight,
      pageScrollWidth: document.documentElement.scrollWidth,
      dialogTop: dialogRect.top,
      dialogBottom: dialogRect.bottom,
      titleTop: title.getBoundingClientRect().top,
      closeTop: close.getBoundingClientRect().top,
      sidewaysScroll,
      elementsPastEdge,
      searchBottom,
      searchBottomAfterScroll: search.getBoundingClientRect().bottom,
    };
  }, searchLabel);
}

for (const viewport of VIEWPORTS) {
  for (const { locale, title, search } of LOCALES) {
    test(`search panel fits ${viewport.name} (${locale})`, async ({ page }) => {
      await page.setViewportSize({
        width: viewport.width,
        height: viewport.height,
      });
      await page.goto(`/${locale}/`);

      await page
        .locator('#main-content [role="search"] button:visible')
        .first()
        .click();
      await expect(page.getByRole('dialog', { name: title })).toBeVisible();

      const boxes = await measurePanel(page, search);

      expect(boxes.pageScrollWidth).toBeLessThanOrEqual(boxes.innerWidth);
      expect(boxes.elementsPastEdge).toBe(0);
      expect(boxes.sidewaysScroll).toBe(0);

      expect(boxes.dialogTop).toBeGreaterThanOrEqual(0);
      expect(boxes.titleTop).toBeGreaterThanOrEqual(0);
      expect(boxes.closeTop).toBeGreaterThanOrEqual(0);
      expect(boxes.dialogBottom).toBeLessThanOrEqual(boxes.innerHeight + 0.5);

      if (viewport.pinned) {
        expect(boxes.searchBottom).toBeLessThanOrEqual(boxes.innerHeight + 0.5);
      }
      expect(boxes.searchBottomAfterScroll).toBeLessThanOrEqual(
        boxes.innerHeight + 0.5,
      );
    });
  }
}
