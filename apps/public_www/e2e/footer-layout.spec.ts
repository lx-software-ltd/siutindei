import { expect, test, type Page } from '@playwright/test';

interface FooterBoxes {
  readonly logo: Box;
  readonly explore: Box;
  readonly support: Box;
  readonly email: Box;
  readonly whatsapp: Box;
  readonly instagram: Box;
  readonly facebook: Box;
  readonly copyright: Box;
  readonly scrollWidth: number;
  readonly innerWidth: number;
}

interface Box {
  readonly top: number;
  readonly left: number;
  readonly right: number;
  readonly height: number;
}

function midX(box: Box): number {
  return box.left + (box.right - box.left) / 2;
}

function midY(box: Box): number {
  return box.top + box.height / 2;
}

async function measureFooter(
  page: Page,
  exploreHeading: string,
  supportHeading: string,
  emailName: string,
): Promise<FooterBoxes> {
  return page.evaluate(
    ({ exploreText, supportText, emailLabel }) => {
      const footer = document.querySelector('footer');
      if (!footer) {
        throw new Error('footer missing');
      }
      const logo = footer.querySelector('img');
      const paragraphs = [...footer.querySelectorAll('p')];
      const heading = (text: string) => paragraphs.find(
        (node) => node.textContent?.trim() === text,
      );
      const exploreNode = heading(exploreText)?.parentElement ?? null;
      const supportNode = heading(supportText)?.parentElement ?? null;
      const copyright = paragraphs.find((node) =>
        /All rights reserved|版權所有/.test(node.textContent ?? ''),
      );
      const linkBox = (name: string) => {
        const link = [...footer.querySelectorAll('a')].find((node) =>
          (node.getAttribute('aria-label') ?? node.textContent ?? '').includes(name)
            || node.querySelector('img')?.getAttribute('alt')?.includes(name),
        );
        return link ?? null;
      };
      const email = linkBox(emailLabel);
      const whatsapp = linkBox('WhatsApp');
      const instagram = linkBox('Instagram');
      const facebook = linkBox('Facebook');
      if (
        !logo
        || !exploreNode
        || !supportNode
        || !copyright
        || !email
        || !whatsapp
        || !instagram
        || !facebook
      ) {
        throw new Error('footer columns missing');
      }
      const box = (rect: DOMRect) => ({
        top: rect.top,
        left: rect.left,
        right: rect.right,
        height: rect.height,
      });
      const range = document.createRange();
      range.selectNodeContents(copyright);
      return {
        logo: box(logo.getBoundingClientRect()),
        explore: box(exploreNode.getBoundingClientRect()),
        support: box(supportNode.getBoundingClientRect()),
        email: box(email.getBoundingClientRect()),
        whatsapp: box(whatsapp.getBoundingClientRect()),
        instagram: box(instagram.getBoundingClientRect()),
        facebook: box(facebook.getBoundingClientRect()),
        copyright: box(range.getBoundingClientRect()),
        scrollWidth: document.documentElement.scrollWidth,
        innerWidth: window.innerWidth,
      };
    },
    {
      exploreText: exploreHeading,
      supportText: supportHeading,
      emailLabel: emailName,
    },
  );
}

function expectIconsInARow(boxes: FooterBoxes): void {
  expect(Math.abs(boxes.whatsapp.top - boxes.email.top)).toBeLessThan(2);
  expect(Math.abs(boxes.instagram.top - boxes.email.top)).toBeLessThan(2);
  expect(Math.abs(boxes.facebook.top - boxes.email.top)).toBeLessThan(2);
  expect(boxes.whatsapp.left).toBeGreaterThan(boxes.email.left);
  expect(boxes.instagram.left).toBeGreaterThan(boxes.whatsapp.left);
  expect(boxes.facebook.left).toBeGreaterThan(boxes.instagram.left);
}

function expectCopyrightCentered(boxes: FooterBoxes): void {
  expect(Math.abs(midX(boxes.copyright) - boxes.innerWidth / 2)).toBeLessThan(12);
}

test.describe('footer columns', () => {
  test('keeps contact icons on the right of the logo row on a phone', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/en/about/');
    await expect(page.getByText('An LX Software product. Hong Kong, SAR.')).toHaveCount(0);
    await expect(page.locator('footer p', { hasText: /^Contact$/ })).toHaveCount(0);

    const boxes = await measureFooter(page, 'Explore', 'Support', 'Email');

    expect(boxes.scrollWidth).toBeLessThanOrEqual(boxes.innerWidth + 1);
    expect(boxes.email.left).toBeGreaterThan(boxes.logo.right);
    expect(Math.abs(midY(boxes.email) - midY(boxes.logo))).toBeLessThan(8);
    expect(Math.abs(boxes.innerWidth - boxes.facebook.right - 16)).toBeLessThan(4);
    expectIconsInARow(boxes);
    expect(boxes.explore.top).toBeGreaterThan(boxes.logo.top + boxes.logo.height - 1);
    expect(Math.abs(boxes.support.top - boxes.explore.top)).toBeLessThan(2);
    expect(boxes.support.left).toBeGreaterThan(boxes.explore.left);
    expectCopyrightCentered(boxes);
  });

  for (const viewport of [
    { name: 'iPad portrait', width: 820, height: 1180 },
    { name: 'iPad landscape', width: 1024, height: 768 },
    { name: 'iPad Air landscape', width: 1180, height: 820 },
    { name: 'desktop', width: 1280, height: 800 },
  ]) {
    test(`centers the icons and pins the columns right on ${viewport.name}`, async ({
      page,
    }) => {
      await page.setViewportSize({
        width: viewport.width,
        height: viewport.height,
      });
      await page.goto('/en/about/');
      await expect(
        page.getByRole('banner').getByRole('link', { name: 'List your activity' }),
      ).toHaveCount(0);

      const boxes = await measureFooter(page, 'Explore', 'Support', 'Email');
      const padding = viewport.width >= 1024 ? 32 : 24;

      expect(boxes.scrollWidth).toBeLessThanOrEqual(boxes.innerWidth + 1);
      expect(Math.abs(boxes.logo.left - padding)).toBeLessThan(4);
      expect(boxes.email.left).toBeGreaterThan(boxes.logo.right);
      expectIconsInARow(boxes);
      expect(Math.abs(midX({
        top: boxes.email.top,
        left: boxes.email.left,
        right: boxes.facebook.right,
        height: boxes.email.height,
      }) - boxes.innerWidth / 2)).toBeLessThan(16);
      expect(boxes.explore.left).toBeGreaterThan(boxes.facebook.right);
      expect(boxes.support.left).toBeGreaterThan(boxes.explore.left);
      expect(boxes.support.right).toBeGreaterThan(boxes.innerWidth - padding - 160);
      expect(boxes.innerWidth - boxes.support.right).toBeLessThan(padding + 8);
      expectCopyrightCentered(boxes);
    });
  }

  test('centers the Chinese icons and copyright on iPad landscape', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1024, height: 768 });
    await page.goto('/zh-HK/about/');
    await expect(
      page.getByRole('banner').getByRole('link', { name: '刊登活動' }),
    ).toHaveCount(0);
    await expect(page.getByText('LX Software 產品。香港特別行政區。')).toHaveCount(0);

    const boxes = await measureFooter(page, '探索', '支援', '電郵');

    expect(boxes.scrollWidth).toBeLessThanOrEqual(boxes.innerWidth + 1);
    expect(boxes.email.left).toBeGreaterThan(boxes.logo.right);
    expect(Math.abs(midX({
      top: boxes.email.top,
      left: boxes.email.left,
      right: boxes.facebook.right,
      height: boxes.email.height,
    }) - boxes.innerWidth / 2)).toBeLessThan(16);
    expect(boxes.explore.left).toBeGreaterThan(boxes.facebook.right);
    expect(boxes.innerWidth - boxes.support.right).toBeLessThan(40);
    expectCopyrightCentered(boxes);
    await expect(page.locator('footer p', { hasText: /^聯絡我們$/ })).toHaveCount(0);
  });
});
