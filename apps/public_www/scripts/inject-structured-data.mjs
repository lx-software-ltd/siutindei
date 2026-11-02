// Injects sitewide WebSite + Organization JSON-LD into the exported locale
// home pages. Runs at build time (like redirect:inject / lang:inject) so
// crawlers see structured data in the static HTML without client-side JS.
// Per-activity JSON-LD is injected client-side by activity-detail-page.tsx.

import { promises as fs } from 'node:fs';
import path from 'node:path';

const OUT_DIR = process.env.PUBLIC_WWW_OUT_DIR
  ? path.resolve(process.env.PUBLIC_WWW_OUT_DIR)
  : path.resolve('out');
const CONTENT_DIR = path.resolve('src/content');
const SUPPORTED_LOCALES = ['en', 'zh-HK'];
const DEFAULT_SOCIAL_IMAGE = '/images/seo/siutindei-og-default.jpg';
const JSON_LD_MARKER = '<!-- jsonld-structured-data -->';

function requireEnv(name) {
  const value = process.env[name]?.trim() ?? '';
  if (value === '') {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

/**
 * Serialize JSON-LD safely for embedding in HTML: escape `<` so a value can
 * never close the script tag or open a new element.
 */
function serializeJsonLd(data) {
  return JSON.stringify(data).replaceAll('<', '\\u003c');
}

async function loadLocaleDescription(locale) {
  const contentPath = path.join(CONTENT_DIR, `${locale}.json`);
  const raw = await fs.readFile(contentPath, 'utf8');
  const content = JSON.parse(raw);
  return content?.seo?.fallbackDescription ?? '';
}

function buildStructuredData({ siteName, siteOrigin, locale, description }) {
  const localeHomeUrl = `${siteOrigin}/${locale}/`;
  const organization = {
    '@type': 'Organization',
    '@id': `${siteOrigin}/#organization`,
    name: siteName,
    legalName: 'LX Software Limited',
    url: siteOrigin,
    logo: `${siteOrigin}${DEFAULT_SOCIAL_IMAGE}`,
  };
  const webSite = {
    '@type': 'WebSite',
    '@id': `${siteOrigin}/#website`,
    name: siteName,
    url: localeHomeUrl,
    inLanguage: locale,
    description,
    publisher: { '@id': `${siteOrigin}/#organization` },
  };
  return {
    '@context': 'https://schema.org',
    '@graph': [organization, webSite],
  };
}

async function injectIntoFile(filePath, structuredData) {
  const original = await fs.readFile(filePath, 'utf8');
  if (original.includes(JSON_LD_MARKER)) {
    return false;
  }

  const headCloseRegex = /<\/head>/i;
  if (!headCloseRegex.test(original)) {
    console.warn(`jsonld:inject — no </head> in ${filePath}`);
    return false;
  }

  const injection =
    `${JSON_LD_MARKER}<script type="application/ld+json">` +
    `${serializeJsonLd(structuredData)}</script>`;
  const updated = original.replace(headCloseRegex, `${injection}</head>`);
  await fs.writeFile(filePath, updated, 'utf8');
  return true;
}

async function main() {
  const siteName = requireEnv('NEXT_PUBLIC_SITE_NAME');
  const siteOrigin = new URL(requireEnv('NEXT_PUBLIC_SITE_ORIGIN')).origin;

  let updatedCount = 0;
  for (const locale of SUPPORTED_LOCALES) {
    const filePath = path.join(OUT_DIR, locale, 'index.html');
    try {
      await fs.access(filePath);
    } catch {
      console.warn(`jsonld:inject — missing ${locale}/index.html`);
      continue;
    }

    const description = await loadLocaleDescription(locale);
    const structuredData = buildStructuredData({
      siteName,
      siteOrigin,
      locale,
      description,
    });
    if (await injectIntoFile(filePath, structuredData)) {
      updatedCount += 1;
    }
  }

  console.log(`jsonld:inject — updated ${updatedCount} HTML file(s).`);
}

main().catch((error) => {
  console.error('jsonld:inject failed:', error);
  process.exit(1);
});
