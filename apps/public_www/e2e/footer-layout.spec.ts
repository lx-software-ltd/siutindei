import { expect, test, type Page } from '@playwright/test';

interface FooterBoxes {
  readonly logo: Box;
  readonly explore: Box;
  readonly email: Box;
  readonly whatsapp: Box;
  readonly instagram: Box;
  readonly scrollWidth: number;
  readonly innerWidth: number;
}

interface Box {
  readonly top: number;
  readonly left: number;
  readonly right: number;
  readonly height: number;
}

function midY(box: Box): number {
  return box.top + box.height / 2;
}

async function measureFooter(
  page: Page,
  exploreHeading: string,
  emailName: string,
): Promise<FooterBoxes> {
  return page.evaluate(
    ({ exploreText, emailLabel }) => {
      const footer = document.querySelector('footer');
      if (!footer) {
        throw new Error('footer missing');
      }
      const logo = footer.querySelector('img');
      const paragraphs = [...footer.querySelectorAll('p')];
      const exploreNode = paragraphs.find(
        (node) => node.textContent?.trim() === exploreText,
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
      if (!logo || !exploreNode || !email || !whatsapp || !instagram) {
        throw new Error('footer columns missing');
      }
      const box = (element: Element) => {
        const rect = element.getBoundingClientRect();
        return {
          top: rect.top,
          left: rect.left,
          right: rect.right,
          height: rect.height,
        };
      };
      return {
        logo: box(logo),
        explore: box(exploreNode),
        email: box(email),
        whatsapp: box(whatsapp),
        instagram: box(instagram),
        scrollWidth: document.documentElement.scrollWidth,
        innerWidth: window.innerWidth,
      };
    },
    {
      exploreText: exploreHeading,
      emailLabel: emailName,
    },
  );
}

test.describe('footer columns', () => {
  test('keeps contact icons in line with the logo on a phone', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/en/about/');
    await expect(page.getByText('An LX Software product. Hong Kong, SAR.')).toHaveCount(0);
    await expect(page.locator('footer p', { hasText: /^Contact$/ })).toHaveCount(0);

    const boxes = await measureFooter(page, 'Explore', 'Email');

    expect(boxes.scrollWidth).toBeLessThanOrEqual(boxes.innerWidth + 1);
    expect(boxes.email.left).toBeGreaterThan(boxes.logo.right - 1);
    expect(Math.abs(midY(boxes.email) - midY(boxes.logo))).toBeLessThan(4);
    expect(Math.abs(boxes.whatsapp.top - boxes.email.top)).toBeLessThan(2);
    expect(Math.abs(boxes.instagram.top - boxes.email.top)).toBeLessThan(2);
    expect(boxes.whatsapp.left).toBeGreaterThan(boxes.email.left);
    expect(boxes.instagram.left).toBeGreaterThan(boxes.whatsapp.left);
    expect(boxes.explore.top).toBeGreaterThan(boxes.logo.top + boxes.logo.height - 1);
  });

  for (const viewport of [
    { name: 'iPad portrait', width: 820, height: 1180 },
    { name: 'iPad landscape', width: 1024, height: 768 },
    { name: 'iPad Air landscape', width: 1180, height: 820 },
  ]) {
    test(`places contact beside the logo on ${viewport.name}`, async ({
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

      const boxes = await measureFooter(page, 'Explore', 'Email');

      expect(boxes.scrollWidth).toBeLessThanOrEqual(boxes.innerWidth + 1);
      expect(boxes.email.left).toBeGreaterThan(boxes.logo.right - 1);
      expect(Math.abs(midY(boxes.email) - midY(boxes.logo))).toBeLessThan(4);
      expect(Math.abs(boxes.whatsapp.top - boxes.email.top)).toBeLessThan(2);
      expect(boxes.whatsapp.left).toBeGreaterThan(boxes.email.left);
      if (viewport.width >= 1024) {
        expect(boxes.instagram.right).toBeLessThanOrEqual(boxes.explore.left + 1);
        expect(Math.abs(boxes.explore.top - boxes.logo.top)).toBeLessThan(8);
      }
    });
  }

  test('places the Chinese contact column beside the logo on iPad landscape', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1024, height: 768 });
    await page.goto('/zh-HK/about/');
    await expect(
      page.getByRole('banner').getByRole('link', { name: '刊登活動' }),
    ).toHaveCount(0);
    await expect(page.getByText('LX Software 產品。香港特別行政區。')).toHaveCount(0);

    const boxes = await measureFooter(page, '探索', '電郵');

    expect(boxes.scrollWidth).toBeLessThanOrEqual(boxes.innerWidth + 1);
    expect(boxes.email.left).toBeGreaterThan(boxes.logo.right - 1);
    expect(Math.abs(midY(boxes.email) - midY(boxes.logo))).toBeLessThan(4);
    expect(boxes.instagram.right).toBeLessThanOrEqual(boxes.explore.left + 1);
    expect(Math.abs(boxes.explore.top - boxes.logo.top)).toBeLessThan(8);
    await expect(page.locator('footer p', { hasText: /^聯絡我們$/ })).toHaveCount(0);
  });
});
