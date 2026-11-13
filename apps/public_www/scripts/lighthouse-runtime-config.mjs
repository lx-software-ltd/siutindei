/**
 * Build the Lighthouse CI runtime config used by
 * `.github/workflows/lighthouse-public-www.yml`.
 *
 * `/` is a locale redirect (`inject-static-redirects.mjs` and the CloudFront
 * path-rewrite function). Auditing it makes LCP include that hop, which is
 * what failed when the workflow default was `/`. The collect URL becomes
 * `/en/` instead. Pass a full `https://` URL to audit a live host.
 *
 * Collect uses applied devtools throttling. Lantern's simulated LCP for this
 * text heading is the slowest node on the page (about 2.9s) even when the
 * heading paints in about 1.4s under the same 4x CPU and Slow 4G settings.
 *
 * The workflow builds from the committed catalogue fixture, so the activities
 * hub, a type page, and an activity page are default targets too.
 *
 * Search is not a default target. The Lighthouse build has no search API, so
 * the only large text on `/en/search/` is the client-rendered error, and that
 * paints after hydration (about 3.1s). Pass the path explicitly to audit it.
 */

import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

/** An activity in `tests/fixtures/catalogue-snapshot.json`, which the workflow builds from. */
export const FIXTURE_ACTIVITY_ID = '81622378-60bf-506b-b132-9b71f0fa4913';

export const DEFAULT_PAGE_PATHS = [
  '/en/',
  '/zh-HK/',
  '/en/activities/',
  '/en/activities/arts/',
  `/en/activity/${FIXTURE_ACTIVITY_ID}/`,
];
export const STATIC_COLLECT_ORIGIN = 'http://localhost:9000';

export function parsePagePaths(raw) {
  const requested = String(raw ?? '')
    .split(/[\n,]+/)
    .map((value) => value.trim())
    .filter(Boolean);
  return requested.length > 0 ? requested : [...DEFAULT_PAGE_PATHS];
}

export function collectUrl(target) {
  if (/^https?:\/\//i.test(target)) {
    return target;
  }
  let pathname = target.startsWith('/') ? target : `/${target}`;
  if (pathname === '/') {
    pathname = '/en/';
  }
  return `${STATIC_COLLECT_ORIGIN}${pathname}`;
}

export function buildRuntimeConfig({
  pagePathsRaw,
  stagingOrigin,
  bypassSecret,
  baseConfig,
}) {
  const urls = parsePagePaths(pagePathsRaw).map(collectUrl);
  const config = structuredClone(baseConfig);
  config.ci = config.ci ?? {};
  config.ci.collect = config.ci.collect ?? {};
  config.ci.collect.url = urls;

  const origin = String(stagingOrigin ?? '').trim();
  const auditsStaging =
    origin !== '' &&
    urls.some((url) => new URL(url).origin === new URL(origin).origin);
  if (auditsStaging) {
    const secret = String(bypassSecret ?? '').trim();
    if (!secret) {
      throw new Error(
        'STAGING_BYPASS_SECRET is required to audit the IP-gated staging site.',
      );
    }
    config.ci.collect.settings = {
      ...(config.ci.collect.settings ?? {}),
      extraHeaders: JSON.stringify({ 'x-staging-bypass': secret }),
    };
  }

  return { config, urls };
}

function isMain() {
  const self = fileURLToPath(import.meta.url);
  const invoked = process.argv[1] ? path.resolve(process.argv[1]) : '';
  return self === invoked;
}

if (isMain()) {
  const baseConfigPath = path.resolve('.lighthouserc.json');
  const runtimeConfigPath = path.resolve('.lighthouserc.runtime.json');
  const { config, urls } = buildRuntimeConfig({
    pagePathsRaw: process.env.LIGHTHOUSE_PAGE_PATHS,
    stagingOrigin: process.env.STAGING_SITE_ORIGIN,
    bypassSecret: process.env.STAGING_BYPASS_SECRET,
    baseConfig: JSON.parse(readFileSync(baseConfigPath, 'utf8')),
  });
  writeFileSync(runtimeConfigPath, `${JSON.stringify(config, null, 2)}\n`);
  console.log('Lighthouse targets:');
  for (const url of urls) {
    console.log(`- ${url}`);
  }
}
