// Inserts a <meta http-equiv="Content-Security-Policy"> tag into every
// generated HTML in the static export. Aligns with evolvesprouts: extend
// script-src / connect-src when GTM or Meta Pixel init scripts are enabled.
// Next.js inline flight scripts are allowed via build-time sha256- hashes.

import { promises as fs } from 'node:fs';
import path from 'node:path';

import { collectInlineScriptHashesFromHtml } from './csp-inline-script-hashes.mjs';

const OUT_DIR = path.resolve('out');
const META_MARKER = '<!-- csp-meta -->';
const MAX_CSP_META_LENGTH = 8192;

const GTM_SCRIPT_ORIGINS = [
  'https://www.googletagmanager.com',
  'https://googleads.g.doubleclick.net',
  'https://www.googleadservices.com',
];
const GTM_CONNECT_ORIGINS = [
  'https://www.google-analytics.com',
  'https://analytics.google.com',
  'https://region1.google-analytics.com',
  'https://stats.g.doubleclick.net',
  'https://www.google.com',
  'https://googleads.g.doubleclick.net',
];
const META_PIXEL_SCRIPT_ORIGINS = ['https://connect.facebook.net'];
const META_PIXEL_CONNECT_ORIGINS = ['https://www.facebook.com'];
const GOOGLE_MAPS_SCRIPT_ORIGINS = ['https://maps.googleapis.com'];
const GOOGLE_MAPS_CONNECT_ORIGINS = [
  'https://maps.googleapis.com',
  'https://maps.gstatic.com',
];

/**
 * @param {string[]} inlineScriptHashes
 */
function buildCspDirectives(inlineScriptHashes) {
  const hasGtm = Boolean(process.env.NEXT_PUBLIC_GTM_ID?.trim());
  const hasMetaPixel = Boolean(process.env.NEXT_PUBLIC_META_PIXEL_ID?.trim());

  const scriptSources = ["'self'", ...inlineScriptHashes];
  const connectSources = ["'self'"];

  const searchApiOrigin = process.env.NEXT_PUBLIC_SEARCH_API_BASE_URL?.trim();
  if (searchApiOrigin) {
    try {
      connectSources.push(new URL(searchApiOrigin).origin);
    } catch {
      console.warn(
        'csp:inject — NEXT_PUBLIC_SEARCH_API_BASE_URL is not a valid URL.',
      );
    }
  }

  if (hasGtm) {
    scriptSources.push(...GTM_SCRIPT_ORIGINS);
    connectSources.push(...GTM_CONNECT_ORIGINS);
  }
  if (hasMetaPixel) {
    scriptSources.push(...META_PIXEL_SCRIPT_ORIGINS);
    connectSources.push(...META_PIXEL_CONNECT_ORIGINS);
  }

  const hasGoogleMaps = Boolean(
    process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY?.trim(),
  );
  if (hasGoogleMaps) {
    scriptSources.push(...GOOGLE_MAPS_SCRIPT_ORIGINS);
    connectSources.push(...GOOGLE_MAPS_CONNECT_ORIGINS);
  }

  return [
    "default-src 'self'",
    `img-src 'self' data: https:`,
    "style-src 'self'",
    `script-src ${[...new Set(scriptSources)].join(' ')}`,
    "font-src 'self' data:",
    `connect-src ${[...new Set(connectSources)].join(' ')}`,
    "base-uri 'self'",
    "object-src 'none'",
    "frame-ancestors 'none'",
  ].join('; ');
}

async function* walk(dir) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      yield* walk(fullPath);
    } else if (entry.isFile() && entry.name.endsWith('.html')) {
      yield fullPath;
    }
  }
}

/**
 * @param {string} filePath
 */
async function injectIntoFile(filePath) {
  const original = await fs.readFile(filePath, 'utf8');
  if (original.includes(META_MARKER)) {
    return false;
  }
  const headOpenRegex = /<head([^>]*)>/i;
  if (!headOpenRegex.test(original)) {
    return false;
  }
  const inlineScriptHashes = collectInlineScriptHashesFromHtml(original);
  const metaTag = `<meta http-equiv="Content-Security-Policy" content="${buildCspDirectives(inlineScriptHashes)}">`;
  if (metaTag.length > MAX_CSP_META_LENGTH) {
    throw new Error(
      `CSP meta tag is ${metaTag.length} bytes in ${filePath}; ` +
        `the limit is ${MAX_CSP_META_LENGTH}. Hash only this page's scripts.`,
    );
  }
  const replacement = `<head$1>\n    ${META_MARKER}\n    ${metaTag}`;
  const updated = original.replace(headOpenRegex, replacement);
  await fs.writeFile(filePath, updated, 'utf8');
  return true;
}

async function main() {
  try {
    await fs.access(OUT_DIR);
  } catch {
    console.error(`Build output not found: ${OUT_DIR}`);
    process.exit(1);
  }

  let updatedCount = 0;
  let totalCount = 0;
  for await (const filePath of walk(OUT_DIR)) {
    totalCount += 1;
    const updated = await injectIntoFile(filePath);
    if (updated) {
      updatedCount += 1;
    }
  }
  console.log(
    `csp:inject — ${updatedCount}/${totalCount} HTML files updated ` +
      '(one CSP policy per page).',
  );
}

main().catch((error) => {
  console.error('csp:inject failed:', error);
  process.exit(1);
});
