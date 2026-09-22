import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const APP_DIR = resolve(__dirname, '../..');
const MAINTENANCE_DIR = resolve(APP_DIR, 'maintenance');
const PUBLIC_DIR = resolve(APP_DIR, 'public');
const DEPLOY_SCRIPT = resolve(
  APP_DIR,
  '../../scripts/deploy/deploy-public-www.sh',
);

const HOLDING_PAGES = ['index.html', '404.html'] as const;
const PARTIAL_MARKERS = [
  '__MAINTENANCE_BUBBLES__',
  '__MAINTENANCE_FOOTER__',
] as const;
const PLACEHOLDER_RE = /__[A-Z][A-Z0-9_]*__/g;

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

function uniquePlaceholders(text: string): string[] {
  return [...new Set(text.match(PLACEHOLDER_RE) ?? [])].sort();
}

function assembleHoldingPage(fileName: string): string {
  let html = readMaintenance(fileName);
  html = html.replace(
    '__MAINTENANCE_BUBBLES__',
    readMaintenance('partials/bubbles.html').trimEnd(),
  );
  html = html.replace(
    '__MAINTENANCE_FOOTER__',
    readMaintenance('partials/footer.html').trimEnd(),
  );
  return html;
}

describe('pre-launch holding page', () => {
  it.each(HOLDING_PAGES)(
    'keeps %s noindex and placeholder-driven',
    (fileName) => {
      const html = readMaintenance(fileName);
      expect(html).toContain('noindex, nofollow');
      expect(html).toContain('/images/brand/siutindei-logo-stacked.svg');
      expect(html).not.toMatch(/<section class="card"/);
      expect(html).toContain('<div class="card">');
      for (const marker of PARTIAL_MARKERS) {
        expect(html).toContain(marker);
      }
    },
  );

  it.each(HOLDING_PAGES)(
    'assembles %s without leftover markers or spaced punctuation',
    (fileName) => {
      const html = assembleHoldingPage(fileName);
      expect(html).not.toContain('__MAINTENANCE_BUBBLES__');
      expect(html).not.toContain('__MAINTENANCE_FOOTER__');
      expect(html).not.toMatch(/<\/a>\s+\./);
      expect(html).toMatch(/<\/a>\./);
      expect(html).not.toMatch(/mailto:(?!__NEXT_PUBLIC_EMAIL__)/);
      expect(html).not.toContain('https://lx-software.com');
      expect(html).not.toContain('siutindei.com');
      for (const asset of REQUIRED_ASSETS) {
        expect(html).toContain(`/${asset}`);
        expect(existsSync(resolve(PUBLIC_DIR, asset))).toBe(true);
      }
    },
  );

  it('uses the public brand contacts for the holding page', () => {
    const defaults = JSON.parse(
      readFileSync(resolve(APP_DIR, 'build-env.defaults.json'), 'utf8'),
    ) as {
      contactEmail: string;
      whatsappUrl: string;
      whatsappDisplay: string;
    };
    expect(defaults.contactEmail).toBe('hello@siutindei.com');
    expect(defaults.whatsappUrl).toBe('https://wa.me/85294460861');
    expect(defaults.whatsappDisplay).toBe('+852 9446 0861');
    for (const fileName of HOLDING_PAGES) {
      const html = assembleHoldingPage(fileName);
      expect(html).toContain('__NEXT_PUBLIC_WHATSAPP_DISPLAY__');
      expect(html).toContain('or WhatsApp');
    }
  });

  it('uses launching-soon copy on the front page', () => {
    const html = readMaintenance('index.html');
    expect(html).toContain('Coming soon');
    expect(html).toContain('Every child deserves their own small world');
    expect(html).toContain('Siu Tin Dei is launching soon');
    expect(assembleHoldingPage('index.html')).toContain('LX Software');
  });

  it('keeps brand tokens, reduced-motion, and dynamic viewport height', () => {
    const css = readMaintenance('styles.css');
    expect(css).toContain('--color-brand-500: #f5c51b');
    expect(css).toContain('--color-ink-900: #2e1d12');
    expect(css).toContain('prefers-reduced-motion');
    expect(css).toContain('100dvh');
    expect(css).toContain('.card a[href^="mailto:"]:not(.btn)');
    expect(css).toContain('white-space: nowrap');
    expect(css).toContain('hyphens: none');
  });

  it('keeps deploy-script placeholders aligned with assembled HTML', () => {
    const deployScript = readFileSync(DEPLOY_SCRIPT, 'utf8');
    const assembledPlaceholders = uniquePlaceholders(
      HOLDING_PAGES.map((fileName) => assembleHoldingPage(fileName)).join('\n'),
    );
    const injectedPlaceholders = uniquePlaceholders(deployScript).filter(
      (placeholder) => placeholder.startsWith('__NEXT_PUBLIC_'),
    );

    expect(assembledPlaceholders).toEqual(injectedPlaceholders);
    for (const marker of PARTIAL_MARKERS) {
      expect(deployScript).toContain(marker);
    }
    expect(deployScript).toContain('contactEmail');
    expect(deployScript).toContain('whatsappUrl');
    expect(deployScript).toContain('whatsappDisplay');
    expect(deployScript).not.toContain('maintenanceContactEmail');
    expect(deployScript).toContain('__NEXT_PUBLIC_WHATSAPP_DISPLAY__');
    expect(deployScript).toContain(
      'DEFAULT_LX_SOFTWARE_URL="https://www.lx-software.com"',
    );
    expect(deployScript).toContain(
      'MAINTENANCE_ASSET_CACHE_CONTROL="public, max-age=3600, must-revalidate"',
    );
    expect(deployScript).toContain('--exclude "images/*"');
  });
});
