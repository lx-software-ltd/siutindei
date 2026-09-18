import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const MAINTENANCE_DIR = resolve(__dirname, '../../maintenance');
const PUBLIC_DIR = resolve(__dirname, '../../public');

const HOLDING_PAGES = ['index.html', '404.html'] as const;

const SHARED_PLACEHOLDERS = [
  '__NEXT_PUBLIC_EMAIL__',
  '__NEXT_PUBLIC_LX_SOFTWARE_URL__',
  '__NEXT_PUBLIC_BUILD_YEAR__',
] as const;

const FRONT_PAGE_PLACEHOLDERS = [
  ...SHARED_PLACEHOLDERS,
  '__NEXT_PUBLIC_WHATSAPP_URL__',
  '__NEXT_PUBLIC_INSTAGRAM_URL__',
] as const;

const REQUIRED_ASSETS = [
  'images/brand/siutindei-logo-stacked.svg',
  'images/small-world/bubble-junk.webp',
  'images/small-world/bubble-tram.webp',
  'images/small-world/bubble-bao.webp',
  'images/small-world/bubble-clock-tower.webp',
  'images/small-world/bubble-bauhinia.webp',
  'images/small-world/bubble-lantern.webp',
] as const;

function readMaintenance(fileName: string): string {
  return readFileSync(resolve(MAINTENANCE_DIR, fileName), 'utf8');
}

describe('pre-launch holding page', () => {
  it.each(HOLDING_PAGES)(
    'keeps %s noindex and placeholder-driven',
    (fileName) => {
      const html = readMaintenance(fileName);
      expect(html).toContain('noindex, nofollow');
      expect(html).toContain('/images/brand/siutindei-logo-stacked.svg');
      expect(html).not.toMatch(/mailto:(?!__NEXT_PUBLIC_EMAIL__)/);
      expect(html).not.toContain('https://lx-software.com');
      expect(html).not.toContain('siutindei.com');
      const placeholders = fileName === 'index.html'
        ? FRONT_PAGE_PLACEHOLDERS
        : SHARED_PLACEHOLDERS;
      for (const placeholder of placeholders) {
        expect(html).toContain(placeholder);
      }
    },
  );

  it('uses launching-soon copy on the front page', () => {
    const html = readMaintenance('index.html');
    expect(html).toContain('Coming soon');
    expect(html).toContain('Every child deserves their own small world');
    expect(html).toContain('Siu Tin Dei is launching soon');
    expect(html).toContain('LX Software');
  });

  it('keeps brand tokens and reduced-motion guards in CSS', () => {
    const css = readMaintenance('styles.css');
    expect(css).toContain('--color-brand-500: #f5c51b');
    expect(css).toContain('--color-ink-900: #2e1d12');
    expect(css).toContain('prefers-reduced-motion');
    expect(css).toContain('min-height: 44px');
  });

  it('references Small World bubbles that exist in public assets', () => {
    const html = readMaintenance('index.html');
    for (const asset of REQUIRED_ASSETS) {
      expect(html).toContain(`/${asset}`);
      expect(existsSync(resolve(PUBLIC_DIR, asset))).toBe(true);
    }
  });
});
