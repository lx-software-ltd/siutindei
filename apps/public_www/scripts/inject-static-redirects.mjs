/**
 * Static export cannot serve Next.js `redirect()` as HTTP 307 on S3. Root
 * pages that only emit NEXT_REDIRECT in the RSC payload render blank on
 * CloudFront. Inject meta refresh + canonical into known locale-alias HTML.
 */

import { promises as fs } from 'node:fs';
import path from 'node:path';

const OUT_DIR = path.resolve('out');

/** Relative paths under out/ → default-locale destination (trailing slash). */
const REDIRECT_HTML_FILES = {
  'index.html': '/en/',
  'about/index.html': '/en/about/',
  'search/index.html': '/en/search/',
  'privacy/index.html': '/en/privacy/',
  'terms/index.html': '/en/terms/',
  'activity/index.html': '/en/activity/',
  'activities/index.html': '/en/activities/',
};

const META_REFRESH_TEMPLATE = (target) =>
  `<meta http-equiv="refresh" content="0;url=${target}">`;
const CANONICAL_TEMPLATE = (target) =>
  `<link rel="canonical" href="${target}">`;
const ACTIVITY_QUERY_SCRIPT = `
    <script>
      (function () {
        var params = new URLSearchParams(window.location.search);
        var id = params.get('id');
        if (!id) {
          return;
        }
        var target = '/en/activity/?id=' + encodeURIComponent(id);
        var meta = document.querySelector('meta[http-equiv="refresh"]');
        if (meta) {
          meta.setAttribute('content', '0;url=' + target);
        }
        var canonical = document.querySelector('link[rel="canonical"]');
        if (canonical) {
          canonical.setAttribute('href', target);
        }
      })();
    </script>`;

async function injectRedirectIntoFile(filePath, target, extraHeadInjection = '') {
  const original = await fs.readFile(filePath, 'utf8');
  if (original.includes('http-equiv="refresh"')) {
    return false;
  }

  const headOpenRegex = /<head([^>]*)>/i;
  if (!headOpenRegex.test(original)) {
    console.warn(`inject-static-redirects: no <head> in ${filePath}`);
    return false;
  }

  const injection =
    `${META_REFRESH_TEMPLATE(target)}\n    ` +
    `${CANONICAL_TEMPLATE(target)}${extraHeadInjection}`;
  const updated = original.replace(
    headOpenRegex,
    `<head$1>\n    ${injection}`,
  );
  await fs.writeFile(filePath, updated, 'utf8');
  return true;
}

async function main() {
  let updatedCount = 0;

  for (const [relativePath, target] of Object.entries(REDIRECT_HTML_FILES)) {
    const filePath = path.join(OUT_DIR, relativePath);
    try {
      await fs.access(filePath);
    } catch {
      console.warn(`inject-static-redirects: missing ${relativePath}`);
      continue;
    }

    const extraInjection =
      relativePath === 'activity/index.html' ? ACTIVITY_QUERY_SCRIPT : '';
    const updated = await injectRedirectIntoFile(
      filePath,
      target,
      extraInjection,
    );
    if (updated) {
      updatedCount += 1;
    }
  }

  console.log(
    `inject-static-redirects — updated ${updatedCount} HTML file(s).`,
  );
}

main().catch((error) => {
  console.error('inject-static-redirects failed:', error);
  process.exit(1);
});
