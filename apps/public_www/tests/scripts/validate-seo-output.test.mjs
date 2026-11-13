import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { pageProblems, validateSeoOutput } from '../../scripts/validate-seo-output.mjs';

const ORIGIN = 'https://example.com';

function page({
  path,
  h1 = '<h1>Heading</h1>',
  robots = 'index, follow',
  canonical = `${ORIGIN}${path}`,
  body = '',
  jsonLd = [],
}) {
  const scripts = jsonLd
    .map((data) => `<script type="application/ld+json">${JSON.stringify(data)}</script>`)
    .join('');
  return (
    '<!DOCTYPE html><html><head><title>Page · Siu Tin Dei</title>'
    + '<meta name="description" content="A page."/>'
    + `<meta name="robots" content="${robots}"/>`
    + (canonical ? `<link rel="canonical" href="${canonical}"/>` : '')
    + `${scripts}</head><body>${h1}${body}</body></html>`
  );
}

const options = { siteOrigin: ORIGIN, hasCatalogue: true };

describe('pageProblems', () => {
  it('accepts an indexable page with one H1 and a self canonical', () => {
    expect(pageProblems('/en/about/', page({ path: '/en/about/' }), options)).toEqual([]);
  });

  it('flags a missing H1, a second H1, and a canonical to another page', () => {
    expect(pageProblems('/en/about/', page({ path: '/en/about/', h1: '' }), options)).toEqual([
      'has 0 <h1> elements, expected 1',
    ]);
    expect(
      pageProblems('/en/about/', page({ path: '/en/about/', h1: '<h1>A</h1><h1>B</h1>' }), options),
    ).toEqual(['has 2 <h1> elements, expected 1']);
    expect(
      pageProblems('/en/about/', page({ path: '/en/about/', canonical: `${ORIGIN}/en/` }), options),
    ).toEqual([`canonical is ${ORIGIN}/en/, expected ${ORIGIN}/en/about/`]);
  });

  it('skips noindex pages and redirect stubs', () => {
    expect(pageProblems('/en/search/', page({ path: '/en/search/', h1: '', robots: 'noindex, follow' }), options)).toEqual([]);
    expect(pageProblems('/about/', '<meta http-equiv="refresh" content="0;url=/en/about/">', options)).toEqual([]);
  });

  it('needs Course JSON-LD on activity pages and catalogue links on home pages', () => {
    expect(pageProblems('/en/activity/a1/', page({ path: '/en/activity/a1/' }), options)).toEqual([
      'is an activity page without Course JSON-LD',
    ]);
    expect(
      pageProblems(
        '/en/activity/a1/',
        page({ path: '/en/activity/a1/', jsonLd: [{ '@type': 'Course' }] }),
        options,
      ),
    ).toEqual([]);
    expect(pageProblems('/en/', page({ path: '/en/' }), options)).toEqual([
      'is a home page with no links to activity pages',
    ]);
    expect(
      pageProblems('/en/', page({ path: '/en/', body: '<a href="/en/activity/a1/">A</a>' }), options),
    ).toEqual([]);
    expect(pageProblems('/en/', page({ path: '/en/' }), { ...options, hasCatalogue: false })).toEqual([]);
  });
});

describe('validateSeoOutput', () => {
  function writeOut(files) {
    const outDir = mkdtempSync(join(tmpdir(), 'seo-output-'));
    for (const [name, contents] of Object.entries(files)) {
      mkdirSync(dirname(join(outDir, name)), { recursive: true });
      writeFileSync(join(outDir, name), contents);
    }
    return outDir;
  }

  it('reports sitemap URLs that are not indexable pages', async () => {
    const outDir = writeOut({
      'en/about/index.html': page({ path: '/en/about/' }),
      'en/search/index.html': page({ path: '/en/search/', robots: 'noindex, follow' }),
      'sitemap.xml': `<urlset><url><loc>${ORIGIN}/en/about/</loc></url><url><loc>${ORIGIN}/en/search/</loc></url></urlset>`,
    });

    const { problems, pageCount } = await validateSeoOutput(outDir, ORIGIN);

    expect(pageCount).toBe(1);
    expect(problems).toEqual([
      `sitemap lists ${ORIGIN}/en/search/, which is not an indexable page in the export`,
    ]);
  });
});
