// Reads the static export without a browser and fails the build when an
// indexable page loses what search engines and AI search read from the
// HTML: one H1, a title, a description, and a canonical pointing at itself.
// Activity pages also need their Course JSON-LD, the home pages need links
// into the catalogue, and every sitemap URL must be an indexable page.

import { promises as fs } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ACTIVITY_PAGE = /^\/(en|zh-HK)\/activity\/[^/]+\/$/;
const HOME_PAGE = /^\/(en|zh-HK)\/$/;

async function htmlFiles(dir) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const files = await Promise.all(
    entries.map((entry) => {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        return htmlFiles(full);
      }
      return entry.name.endsWith('.html') ? [full] : [];
    }),
  );
  return files.flat();
}

function pagePath(outDir, file) {
  const relative = path.relative(outDir, file).split(path.sep).join('/');
  if (relative === 'index.html') {
    return '/';
  }
  return relative.endsWith('/index.html')
    ? `/${relative.slice(0, -'index.html'.length)}`
    : `/${relative}`;
}

function attribute(tag, name) {
  return new RegExp(`\\s${name}="([^"]*)"`, 'i').exec(tag)?.[1] ?? null;
}

function metaContent(html, name) {
  const tag = new RegExp(`<meta[^>]*\\sname="${name}"[^>]*>`, 'i').exec(html)?.[0];
  return tag ? attribute(tag, 'content') : null;
}

function jsonLdTypes(html) {
  const types = [];
  for (const match of html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)) {
    try {
      const data = JSON.parse(match[1]);
      for (const node of data['@graph'] ?? [data]) {
        types.push(node['@type']);
      }
    } catch {
      types.push('invalid');
    }
  }
  return types;
}

/** Problems with one exported page; empty when it is fine or not indexable. */
export function pageProblems(urlPath, html, { siteOrigin, hasCatalogue }) {
  if (/http-equiv="refresh"/i.test(html)) {
    return [];
  }
  const robots = metaContent(html, 'robots') ?? '';
  if (/noindex/i.test(robots)) {
    return [];
  }
  const problems = [];
  const h1Count = (html.match(/<h1[\s>]/gi) ?? []).length;
  if (h1Count !== 1) {
    problems.push(`has ${h1Count} <h1> elements, expected 1`);
  }
  const title = /<title>([^<]*)<\/title>/i.exec(html)?.[1]?.trim() ?? '';
  if (!title) {
    problems.push('has no <title>');
  }
  if (!(metaContent(html, 'description') ?? '').trim()) {
    problems.push('has no meta description');
  }
  const canonicalTag = /<link[^>]*\srel="canonical"[^>]*>/i.exec(html)?.[0];
  const canonical = canonicalTag ? attribute(canonicalTag, 'href') : null;
  const expected = new URL(urlPath, siteOrigin).toString();
  if (canonical !== expected) {
    problems.push(`canonical is ${canonical ?? 'missing'}, expected ${expected}`);
  }
  if (jsonLdTypes(html).includes('invalid')) {
    problems.push('has JSON-LD that does not parse');
  }
  if (ACTIVITY_PAGE.test(urlPath) && !jsonLdTypes(html).includes('Course')) {
    problems.push('is an activity page without Course JSON-LD');
  }
  if (hasCatalogue && HOME_PAGE.test(urlPath)) {
    const locale = HOME_PAGE.exec(urlPath)[1];
    if (!new RegExp(`href="/${locale}/activity/[^"?]+/?"`).test(html)) {
      problems.push('is a home page with no links to activity pages');
    }
  }
  return problems;
}

export function sitemapUrls(xml) {
  return [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((match) => match[1]);
}

export async function validateSeoOutput(outDir, siteOrigin) {
  const origin = new URL(siteOrigin).origin;
  let hasCatalogue = false;
  try {
    const pages = JSON.parse(await fs.readFile(path.join(outDir, 'activity-pages.json'), 'utf8'));
    hasCatalogue = (pages.ids ?? []).length > 0;
  } catch {
    hasCatalogue = false;
  }

  const problems = [];
  const indexable = new Set();
  for (const file of await htmlFiles(outDir)) {
    const urlPath = pagePath(outDir, file);
    if (urlPath === '/404.html' || urlPath.startsWith('/404/') || urlPath.startsWith('/_not-found/')) {
      continue;
    }
    const html = await fs.readFile(file, 'utf8');
    for (const problem of pageProblems(urlPath, html, { siteOrigin: origin, hasCatalogue })) {
      problems.push(`${urlPath} ${problem}`);
    }
    const robots = metaContent(html, 'robots') ?? '';
    if (!/noindex/i.test(robots) && !/http-equiv="refresh"/i.test(html)) {
      indexable.add(`${origin}${urlPath}`);
    }
  }

  const sitemap = await fs.readFile(path.join(outDir, 'sitemap.xml'), 'utf8').catch(() => null);
  if (sitemap === null) {
    problems.push('sitemap.xml is missing');
  } else {
    for (const url of sitemapUrls(sitemap)) {
      if (!indexable.has(url)) {
        problems.push(`sitemap lists ${url}, which is not an indexable page in the export`);
      }
    }
  }
  return { problems, pageCount: indexable.size };
}

function isMain() {
  const self = fileURLToPath(import.meta.url);
  return process.argv[1] ? path.resolve(process.argv[1]) === self : false;
}

if (isMain()) {
  const outDir = path.resolve(process.env.PUBLIC_WWW_OUT_DIR ?? 'out');
  const siteOrigin = process.env.NEXT_PUBLIC_SITE_ORIGIN?.trim();
  if (!siteOrigin) {
    console.error('seo:validate needs NEXT_PUBLIC_SITE_ORIGIN.');
    process.exit(1);
  }
  const { problems, pageCount } = await validateSeoOutput(outDir, siteOrigin);
  if (problems.length > 0) {
    console.error(`seo:validate found ${problems.length} problem(s):`);
    for (const problem of problems) {
      console.error(`- ${problem}`);
    }
    process.exit(1);
  }
  console.log(`seo:validate — ${pageCount} indexable page(s) pass.`);
}
