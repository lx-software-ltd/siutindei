/**
 * Build the Lighthouse CI runtime config used by
 * `.github/workflows/lighthouse-public-www.yml`.
 *
 * `/` is a locale redirect (`inject-static-redirects.mjs` and the CloudFront
 * path-rewrite function). Auditing it makes LCP include that hop, which is
 * what failed when the workflow default was `/`. The collect URL becomes
 * `/en/` instead. Pass a full `https://` URL to audit a live host.
 */

import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const DEFAULT_PAGE_PATHS = ['/en/', '/zh-HK/', '/en/search/'];
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
