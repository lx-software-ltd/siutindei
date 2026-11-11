import { expect, test, type Page } from '@playwright/test';

interface FooterBoxes {
  readonly logo: Box;
  readonly tagline: Box;
  readonly contact: Box;
  readonly explore: Box;
  readonly scrollWidth: number;
  readonly innerWidth: number;
}

interface Box {
  readonly top: number;
  readonly left: number;
  readonly right: number;
  readonly height: number;
}

const TAGLINES = {
  en: 'An LX Software product. Hong Kong, SAR.',
  'zh-HK': 'LX Software 產品。香港特別行政區。',
} as const;

async function measureFooter(
  page: Page,
  tagline: string,
  contactHeading: string,
  exploreHeading: string,
): Promise<FooterBoxes> {
  return page.evaluate(
    ({ taglineText, contactText, exploreText }) => {
      const footer = document.querySelector('footer');
      if (!footer) {
        throw new Error('footer missing');
      }
      const logo = footer.querySelector('img');
      const paragraphs = [...footer.querySelectorAll('p')];
      const taglineNode = paragraphs.find((node) =>
        node.textContent?.includes(taglineText),
      );
      const contactNode = paragraphs.find(
        (node) => node.textContent?.trim() === contactText,
      );
      const exploreNode = paragraphs.find(
        (node) => node.textContent?.trim() === exploreText,
      );
      if (!logo || !taglineNode || !contactNode || !exploreNode) {
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
        tagline: box(taglineNode),
        contact: box(contactNode),
        explore: box(exploreNode),
        scrollWidth: document.documentElement.scrollWidth,
        innerWidth: window.innerWidth,
      };
    },
    {
      taglineText: tagline,
      contactText: contactHeading,
      exploreText: exploreHeading,
    },
  );
}

test.describe('footer columns', () => {
  test('keeps contact under the tagline on a phone', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/en/about/');

    const boxes = await measureFooter(
      page,
      TAGLINES.en,
      'Contact',
      'Explore',
    );

    expect(boxes.scrollWidth).toBeLessThanOrEqual(boxes.innerWidth + 1);
    expect(boxes.contact.top).toBeGreaterThan(
      boxes.tagline.top + boxes.tagline.height - 1,
    );
    expect(boxes.contact.left).toBeLessThan(boxes.logo.right);
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

      const boxes = await measureFooter(
        page,
        TAGLINES.en,
        'Contact',
        'Explore',
      );

      expect(boxes.scrollWidth).toBeLessThanOrEqual(boxes.innerWidth + 1);
      expect(boxes.contact.left).toBeGreaterThanOrEqual(boxes.logo.right - 1);
      expect(Math.abs(boxes.contact.top - boxes.logo.top)).toBeLessThan(8);
      expect(boxes.tagline.top).toBeGreaterThan(boxes.logo.top);
      expect(boxes.tagline.right).toBeLessThanOrEqual(boxes.contact.left + 1);
      expect(boxes.tagline.height).toBeLessThan(28);
      if (viewport.width >= 1024) {
        expect(Math.abs(boxes.explore.top - boxes.contact.top)).toBeLessThan(8);
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

    const boxes = await measureFooter(
      page,
      TAGLINES['zh-HK'],
      '聯絡我們',
      '探索',
    );

    expect(boxes.scrollWidth).toBeLessThanOrEqual(boxes.innerWidth + 1);
    expect(boxes.contact.left).toBeGreaterThanOrEqual(boxes.logo.right - 1);
    expect(Math.abs(boxes.contact.top - boxes.logo.top)).toBeLessThan(8);
    expect(boxes.tagline.right).toBeLessThanOrEqual(boxes.contact.left + 1);
    expect(boxes.tagline.height).toBeLessThan(28);
    expect(Math.abs(boxes.explore.top - boxes.contact.top)).toBeLessThan(8);
  });
});
