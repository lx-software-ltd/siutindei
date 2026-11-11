// Pages smoke test for the public website. Crawls /sitemap.xml and
// makes sure every URL it lists responds with 2xx/3xx. Falls back to a fixed
// list when the sitemap is unavailable. When staging search is live, also
// requests /v1/activities/search?limit=1 with the website credentials.
//
// Required env:
//   SMOKE_BASE_URL         absolute origin to test (https in production-like
//                          environments, http allowed only for localhost)
//
// Optional env:
//   SMOKE_TIMEOUT_MS       per-request timeout in milliseconds (default 15000)
//   SMOKE_MAX_PAGES        cap the number of URLs crawled
//   STAGING_BYPASS_SECRET  sent as x-staging-bypass so the staging IP
//                          allow-list Worker lets the runner through
//   NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED
//                          false/0/no probes GET /v1/activities/search.
//                          Anything else, including unset, skips that probe.
//   NEXT_PUBLIC_SEARCH_API_KEY
//   NEXT_PUBLIC_DEVICE_ATTESTATION_TOKEN
//                          required for the live search probe
//
// A response whose final URL left the base host fails: the staging gate
// redirects unlisted clients to production, which would otherwise pass.

import path from 'node:path';
import { fileURLToPath } from 'node:url';

const SMOKE_BASE_URL_ENV = 'SMOKE_BASE_URL';
const SMOKE_TIMEOUT_MS_ENV = 'SMOKE_TIMEOUT_MS';
const SMOKE_MAX_PAGES_ENV = 'SMOKE_MAX_PAGES';
const STAGING_BYPASS_SECRET_ENV = 'STAGING_BYPASS_SECRET';
const STAGING_BYPASS_HEADER = 'x-staging-bypass';

const DEFAULT_TIMEOUT_MS = 15_000;
const USER_AGENT = 'siutindei-public-www-smoke-runner/1.0';
const FALLBACK_PAGES = ['/'];

function isLocalhost(hostname) {
  const value = hostname.toLowerCase();
  return value === 'localhost' || value === '127.0.0.1' || value === '::1';
}

function resolveBaseUrl() {
  const raw = (process.env[SMOKE_BASE_URL_ENV] ?? '').trim();
  if (!raw) {
    throw new Error(`${SMOKE_BASE_URL_ENV} is required.`);
  }
  let parsed;
  try {
    parsed = new URL(raw);
  } catch {
    throw new Error(`${SMOKE_BASE_URL_ENV} must be a valid absolute URL.`);
  }
  const protocol = parsed.protocol.toLowerCase();
  if (protocol === 'http:' && !isLocalhost(parsed.hostname)) {
    throw new Error(`${SMOKE_BASE_URL_ENV} must use https except for localhost.`);
  }
  if (protocol !== 'https:' && protocol !== 'http:') {
    throw new Error(`${SMOKE_BASE_URL_ENV} must use http or https.`);
  }
  parsed.hash = '';
  parsed.search = '';
  parsed.pathname = '/';
  return parsed;
}

function resolveTimeoutMs() {
  const raw = (process.env[SMOKE_TIMEOUT_MS_ENV] ?? '').trim();
  if (!raw) {
    return DEFAULT_TIMEOUT_MS;
  }
  const value = Number.parseInt(raw, 10);
  if (!Number.isFinite(value) || value <= 0) {
    throw new Error(`${SMOKE_TIMEOUT_MS_ENV} must be a positive integer.`);
  }
  return value;
}

function resolveMaxPages() {
  const raw = (process.env[SMOKE_MAX_PAGES_ENV] ?? '').trim();
  if (!raw) {
    return null;
  }
  const value = Number.parseInt(raw, 10);
  if (!Number.isFinite(value) || value <= 0) {
    throw new Error(`${SMOKE_MAX_PAGES_ENV} must be a positive integer.`);
  }
  return value;
}

export function shouldProbeLiveSearch(raw) {
  const value = String(raw ?? '').trim().toLowerCase();
  return value === 'false' || value === '0' || value === 'no';
}

export function buildLiveSearchProbe(baseUrl, env) {
  const key = String(env.NEXT_PUBLIC_SEARCH_API_KEY ?? '').trim();
  const token = String(env.NEXT_PUBLIC_DEVICE_ATTESTATION_TOKEN ?? '').trim();
  if (!key || !token) {
    throw new Error(
      'Live search probe requires NEXT_PUBLIC_SEARCH_API_KEY and NEXT_PUBLIC_DEVICE_ATTESTATION_TOKEN.',
    );
  }
  const url = new URL('/v1/activities/search', baseUrl);
  url.searchParams.set('limit', '1');
  return {
    url: url.toString(),
    headers: {
      accept: 'application/json',
      'x-api-key': key,
      'x-device-attestation': token,
    },
  };
}

function resolveBypassHeaders() {
  const secret = (process.env[STAGING_BYPASS_SECRET_ENV] ?? '').trim();
  return secret ? { [STAGING_BYPASS_HEADER]: secret } : {};
}

async function fetchWithTimeout(url, init, timeoutMs) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      ...init,
      signal: controller.signal,
      headers: {
        'user-agent': USER_AGENT,
        ...resolveBypassHeaders(),
        ...(init?.headers ?? {}),
      },
    });
    const requestedHost = new URL(url).host;
    const finalHost = response.url ? new URL(response.url).host : requestedHost;
    if (finalHost !== requestedHost) {
      throw new Error(
        `redirected off ${requestedHost} to ${response.url}; is ${STAGING_BYPASS_SECRET_ENV} set and current?`,
      );
    }
    return response;
  } finally {
    clearTimeout(timeoutId);
  }
}

function parseLocValues(xml) {
  const values = [];
  const regex = /<loc>([^<]+)<\/loc>/gi;
  let match = regex.exec(xml);
  while (match) {
    const value = (match[1] ?? '').trim();
    if (value) {
      values.push(value);
    }
    match = regex.exec(xml);
  }
  return values;
}

function mapToBaseOrigin(url, baseUrl) {
  const mapped = new URL(url.toString());
  mapped.protocol = baseUrl.protocol;
  mapped.hostname = baseUrl.hostname;
  mapped.port = baseUrl.port;
  mapped.hash = '';
  return mapped;
}

async function collectSitemapPageUrls({ baseUrl, timeoutMs }) {
  const initialSitemap = new URL('/sitemap.xml', baseUrl).toString();
  const queue = [initialSitemap];
  const seen = new Set();
  const pages = new Set();
  while (queue.length > 0) {
    const current = queue.shift();
    if (!current || seen.has(current)) {
      continue;
    }
    seen.add(current);
    const response = await fetchWithTimeout(current, {}, timeoutMs);
    if (!response.ok) {
      throw new Error(`Failed to fetch ${current}: HTTP ${response.status}`);
    }
    const xml = await response.text();
    const locs = parseLocValues(xml);
    if (locs.length === 0) {
      continue;
    }
    if (xml.includes('<sitemapindex')) {
      for (const value of locs) {
        try {
          const resolved = new URL(value, baseUrl);
          queue.push(mapToBaseOrigin(resolved, baseUrl).toString());
        } catch {
          // ignore unparsable
        }
      }
      continue;
    }
    for (const value of locs) {
      try {
        const resolved = new URL(value, baseUrl);
        const mapped = mapToBaseOrigin(resolved, baseUrl);
        mapped.search = '';
        pages.add(mapped.toString());
      } catch {
        // ignore unparsable
      }
    }
  }
  return [...pages].sort();
}

function buildFallbackPages(baseUrl) {
  return FALLBACK_PAGES.map((p) => new URL(p, baseUrl).toString());
}

async function main() {
  const baseUrl = resolveBaseUrl();
  const timeoutMs = resolveTimeoutMs();
  const maxPages = resolveMaxPages();

  console.log(`Base URL: ${baseUrl.toString()}`);
  console.log(`Timeout: ${timeoutMs}ms`);

  let pages = [];
  try {
    pages = await collectSitemapPageUrls({ baseUrl, timeoutMs });
    console.log(`Discovered ${pages.length} URL(s) from sitemap.`);
  } catch (error) {
    console.warn(`Sitemap discovery failed: ${error.message}`);
  }
  if (pages.length === 0) {
    pages = buildFallbackPages(baseUrl);
    console.log(`Using fallback list of ${pages.length} URL(s).`);
  }
  if (maxPages !== null && pages.length > maxPages) {
    pages = pages.slice(0, maxPages);
    console.log(`Capped to ${maxPages} URL(s).`);
  }

  let passed = 0;
  let checks = pages.length;
  const failures = [];
  for (const url of pages) {
    try {
      const response = await fetchWithTimeout(
        url,
        {
          method: 'GET',
          redirect: 'follow',
          headers: { accept: 'text/html,*/*;q=0.8' },
        },
        timeoutMs,
      );
      if (response.status >= 400) {
        failures.push({ url, status: response.status });
        console.log(`FAIL ${response.status} ${url}`);
        continue;
      }
      passed += 1;
      console.log(`PASS ${response.status} ${url}`);
    } catch (error) {
      failures.push({ url, status: null, detail: error.message });
      console.log(`FAIL ERR ${url} :: ${error.message}`);
    }
  }

  if (shouldProbeLiveSearch(process.env.NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED)) {
    checks += 1;
    try {
      const probe = buildLiveSearchProbe(baseUrl, process.env);
      const response = await fetchWithTimeout(
        probe.url,
        { method: 'GET', headers: probe.headers, redirect: 'follow' },
        timeoutMs,
      );
      const body = await response.text();
      let itemCount = null;
      try {
        const payload = JSON.parse(body);
        if (Array.isArray(payload.items)) {
          itemCount = payload.items.length;
        }
      } catch {
        itemCount = null;
      }
      if (!response.ok || itemCount === null) {
        failures.push({ url: probe.url, status: response.status });
        console.log(`FAIL ${response.status} ${probe.url}`);
      } else {
        passed += 1;
        console.log(`PASS ${response.status} ${probe.url} (${itemCount} item(s))`);
      }
    } catch (error) {
      failures.push({
        url: new URL('/v1/activities/search', baseUrl).toString(),
        status: null,
        detail: error.message,
      });
      console.log(`FAIL ERR live search probe :: ${error.message}`);
    }
  } else {
    console.log('Live search probe skipped (fixture mode).');
  }

  console.log(`\nResult: ${passed}/${checks} passed.`);
  if (failures.length > 0) {
    process.exit(1);
  }
}

function isMain() {
  const self = fileURLToPath(import.meta.url);
  const invoked = process.argv[1] ? path.resolve(process.argv[1]) : '';
  return self === invoked;
}

if (isMain()) {
  main().catch((error) => {
    console.error(`Smoke run crashed: ${error.message ?? error}`);
    process.exit(1);
  });
}
