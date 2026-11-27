import { deflateSync } from 'node:zlib';

import { expect, test, type Page } from '@playwright/test';

const PORTRAIT = '/e2e-gallery-portrait.png';
const WIDE = '/e2e-gallery-wide.png';
const SQUARE = '/e2e-gallery-square.png';

function png(width: number, height: number, rgb: readonly [number, number, number]): Buffer {
  const row = Buffer.alloc(1 + width * 3);
  for (let x = 0; x < width; x += 1) {
    row[x * 3 + 1] = rgb[0];
    row[x * 3 + 2] = rgb[1];
    row[x * 3 + 3] = rgb[2];
  }
  const raw = Buffer.concat(Array.from({ length: height }, () => row));

  function chunk(tag: string, data: Buffer): Buffer {
    const body = Buffer.concat([Buffer.from(tag), data]);
    const length = Buffer.alloc(4);
    length.writeUInt32BE(data.length);
    const crc = Buffer.alloc(4);
    crc.writeUInt32BE(crc32(body));
    return Buffer.concat([length, body, crc]);
  }

  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header[8] = 8;
  header[9] = 2;
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk('IHDR', header),
    chunk('IDAT', deflateSync(raw)),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}

function crc32(data: Buffer): number {
  let crc = 0xffffffff;
  for (const byte of data) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

const IMAGES: Record<string, Buffer> = {
  [PORTRAIT]: png(300, 600, [180, 40, 40]),
  [WIDE]: png(800, 300, [40, 80, 180]),
  [SQUARE]: png(400, 400, [40, 140, 80]),
};

async function servePictures(page: Page): Promise<void> {
  for (const [path, body] of Object.entries(IMAGES)) {
    await page.route(`**${path}`, (route) =>
      route.fulfill({ status: 200, contentType: 'image/png', body }),
    );
  }
}

test('gallery tiles keep their frame for a portrait photo and a wide photo', async ({ page }) => {
  const fixture = await page.request.get('/fixtures/activity_search_staging.json');
  const payload = (await fixture.json()) as {
    items: Array<{ activity: { id: string }; pricing: unknown; organization: { media_urls?: string[] } }>;
  };
  const activity = payload.items.find((item) => item.pricing);
  if (!activity) {
    throw new Error('staging fixture has no priced activity');
  }
  await servePictures(page);
  await page.route('**/fixtures/activity_search_staging.json', async (route) => {
    const json = (await (await route.fetch()).json()) as typeof payload;
    for (const item of json.items) {
      if (item.activity.id === activity.activity.id && item.organization) {
        item.organization.media_urls = [PORTRAIT, WIDE, SQUARE];
      }
    }
    await route.fulfill({ json });
  });

  await page.goto(`/en/activity?id=${encodeURIComponent(activity.activity.id)}`);
  const gallery = page.getByRole('region', { name: 'Photos' });
  await expect(page.getByRole('button', { name: 'Show all 3 photos' })).toBeAttached({
    timeout: 30_000,
  });

  await page.setViewportSize({ width: 390, height: 844 });
  const slide = gallery.locator('.snap-start').first();
  await expect(slide).toBeVisible();
  const phone = await slide.boundingBox();
  const phoneImage = await slide.locator('img').boundingBox();
  expect(phone).toBeTruthy();
  expect(phoneImage).toBeTruthy();
  expect(Math.abs(phoneImage!.width - phone!.width)).toBeLessThanOrEqual(2);
  expect(Math.abs(phoneImage!.height - phone!.height)).toBeLessThanOrEqual(2);
  expect(phone!.width / phone!.height).toBeCloseTo(4 / 3, 1);

  await page.setViewportSize({ width: 900, height: 1200 });
  const mosaic = gallery.locator('.md\\:grid');
  await expect(mosaic).toBeVisible();
  const main = mosaic.locator('button').first();
  const small = mosaic.locator('button').nth(1);
  await expect(main).toBeVisible();
  const mainBox = await main.boundingBox();
  const smallBox = await small.boundingBox();
  const mosaicBox = await mosaic.boundingBox();
  expect(mainBox).toBeTruthy();
  expect(smallBox).toBeTruthy();
  expect(mosaicBox).toBeTruthy();
  expect(mainBox!.height).toBeGreaterThan(380);
  expect(Math.abs(mainBox!.height - mosaicBox!.height)).toBeLessThanOrEqual(2);
  expect(smallBox!.height).toBeGreaterThan(150);
  expect(smallBox!.height).toBeLessThan(mainBox!.height * 0.7);
  const mainImage = await main.locator('img').boundingBox();
  expect(Math.abs(mainImage!.width - mainBox!.width)).toBeLessThanOrEqual(2);
  expect(Math.abs(mainImage!.height - mainBox!.height)).toBeLessThanOrEqual(2);

  await page.getByRole('button', { name: 'Show all 3 photos' }).click();
  const frames = page.getByRole('dialog').locator('li');
  await expect(frames).toHaveCount(3);
  const frameBoxes = await frames.evaluateAll((items) =>
    items.map((item) => {
      const rect = item.getBoundingClientRect();
      return { width: rect.width, height: rect.height };
    }),
  );
  for (const box of frameBoxes) {
    expect(Math.abs(box.width - frameBoxes[0].width)).toBeLessThanOrEqual(2);
    expect(Math.abs(box.height - frameBoxes[0].height)).toBeLessThanOrEqual(2);
    expect(box.width / box.height).toBeCloseTo(4 / 3, 1);
  }
});

test('a listing tile stays the same size for a portrait photo and a wide photo', async ({
  page,
}) => {
  await servePictures(page);
  let src = PORTRAIT;
  await page.route('**/fixtures/activity_search_staging.json', async (route) => {
    const json = (await (await route.fetch()).json()) as {
      items: Array<{ organization?: { media_urls?: string[] } }>;
    };
    for (const item of json.items) {
      if (item.organization) {
        item.organization.media_urls = [src];
      }
    }
    await route.fulfill({ json });
  });

  async function tileSize(next: string): Promise<{ width: number; height: number }> {
    src = next;
    await page.goto('/en/search/?view=list');
    const frame = page.locator('article.listing-card .relative').first();
    await expect(frame).toBeVisible({ timeout: 30_000 });
    const image = frame.locator(`img[src="${next}"]`);
    await expect(image).toBeVisible();
    const frameBox = await frame.boundingBox();
    const imageBox = await image.boundingBox();
    expect(frameBox).toBeTruthy();
    expect(imageBox).toBeTruthy();
    expect(Math.abs(imageBox!.width - frameBox!.width)).toBeLessThanOrEqual(2);
    expect(Math.abs(imageBox!.height - frameBox!.height)).toBeLessThanOrEqual(2);
    return { width: frameBox!.width, height: frameBox!.height };
  }

  await page.setViewportSize({ width: 390, height: 844 });
  const portrait = await tileSize(PORTRAIT);
  const wide = await tileSize(WIDE);
  expect(Math.abs(wide.width - portrait.width)).toBeLessThanOrEqual(2);
  expect(Math.abs(wide.height - portrait.height)).toBeLessThanOrEqual(2);

  await page.setViewportSize({ width: 1280, height: 900 });
  const desktopPortrait = await tileSize(PORTRAIT);
  const desktopWide = await tileSize(WIDE);
  expect(Math.abs(desktopWide.width - desktopPortrait.width)).toBeLessThanOrEqual(2);
  expect(Math.abs(desktopWide.height - desktopPortrait.height)).toBeLessThanOrEqual(2);
});
