import { execSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const appRoot = join(process.cwd());
const scriptPath = join(appRoot, 'scripts/inject-structured-data.mjs');

const HOME_HTML =
  '<!DOCTYPE html><html lang="en"><head><title>x</title></head>'
  + '<body></body></html>';

function makeOutDir(): string {
  const outDir = mkdtempSync(join(tmpdir(), 'public-www-jsonld-'));
  for (const locale of ['en', 'zh-HK']) {
    mkdirSync(join(outDir, locale), { recursive: true });
    writeFileSync(join(outDir, locale, 'index.html'), HOME_HTML, 'utf8');
  }
  return outDir;
}

function runInject(outDir: string): void {
  execSync(`node "${scriptPath}"`, {
    cwd: appRoot,
    env: {
      ...process.env,
      PUBLIC_WWW_OUT_DIR: outDir,
      NEXT_PUBLIC_SITE_ORIGIN: 'https://example.com',
      NEXT_PUBLIC_SITE_NAME: 'Siu Tin Dei',
    },
    stdio: 'pipe',
  });
}

function extractJsonLd(html: string): Record<string, unknown> {
  const match = html.match(
    /<script type="application\/ld\+json">([\s\S]*?)<\/script>/,
  );
  expect(match).not.toBeNull();
  return JSON.parse(match![1]) as Record<string, unknown>;
}

interface JsonLdNode {
  '@type': string;
  [key: string]: unknown;
}

describe('inject-structured-data', () => {
  it('injects WebSite and Organization JSON-LD into locale home pages', () => {
    const outDir = makeOutDir();

    runInject(outDir);

    for (const locale of ['en', 'zh-HK']) {
      const html = readFileSync(join(outDir, locale, 'index.html'), 'utf8');
      const jsonLd = extractJsonLd(html);
      expect(jsonLd['@context']).toBe('https://schema.org');

      const graph = jsonLd['@graph'] as JsonLdNode[];
      const organization = graph.find((n) => n['@type'] === 'Organization');
      const webSite = graph.find((n) => n['@type'] === 'WebSite');

      expect(organization).toMatchObject({
        name: 'Siu Tin Dei',
        legalName: 'LX Software',
        url: 'https://example.com',
      });
      expect(webSite).toMatchObject({
        name: 'Siu Tin Dei',
        url: `https://example.com/${locale}/`,
        inLanguage: locale,
      });
      expect((webSite?.description as string).length).toBeGreaterThan(0);
    }
  });

  it('is idempotent across repeated runs', () => {
    const outDir = makeOutDir();

    runInject(outDir);
    runInject(outDir);

    const html = readFileSync(join(outDir, 'en', 'index.html'), 'utf8');
    const occurrences = html.match(/application\/ld\+json/g) ?? [];
    expect(occurrences).toHaveLength(1);
  });
});
