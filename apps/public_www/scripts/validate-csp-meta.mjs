// Validates that every HTML file in the static export carries the CSP meta
// marker injected by inject-csp-meta.mjs. Runs after the inject step so that
// "build" never deploys partially protected HTML.

import { promises as fs } from 'node:fs';
import path from 'node:path';

import { collectInlineScriptHashesFromHtml } from './csp-inline-script-hashes.mjs';

const OUT_DIR = path.resolve('out');
const META_MARKER = '<!-- csp-meta -->';
const MAX_CSP_META_LENGTH = 8192;

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
 * @param {string} contents
 */
function readCspMetaContent(contents) {
  const match = contents.match(
    /<meta\s+http-equiv="Content-Security-Policy"\s+content="([^"]*)"/i,
  );
  return match?.[1] ?? null;
}

async function main() {
  const missing = [];
  const missingHashes = [];
  const oversized = [];
  for await (const filePath of walk(OUT_DIR)) {
    const contents = await fs.readFile(filePath, 'utf8');
    if (!contents.includes(META_MARKER)) {
      missing.push(filePath);
      continue;
    }
    const csp = readCspMetaContent(contents);
    if (csp && csp.length > MAX_CSP_META_LENGTH) {
      oversized.push(`${filePath} (${csp.length} bytes)`);
    }
    const inlineHashes = collectInlineScriptHashesFromHtml(contents);
    const absent = inlineHashes.filter((hash) => !csp?.includes(hash));
    if (absent.length > 0) {
      missingHashes.push(filePath);
    }
  }
  if (missing.length > 0) {
    console.error('csp:validate — HTML files without CSP meta:');
    for (const filePath of missing) {
      console.error(`- ${filePath}`);
    }
    process.exit(1);
  }
  if (oversized.length > 0) {
    console.error('csp:validate — CSP meta content longer than 8192 bytes:');
    for (const filePath of oversized) {
      console.error(`- ${filePath}`);
    }
    process.exit(1);
  }
  if (missingHashes.length > 0) {
    console.error(
      'csp:validate — HTML with inline scripts but no sha256- in CSP:',
    );
    for (const filePath of missingHashes) {
      console.error(`- ${filePath}`);
    }
    process.exit(1);
  }
  console.log('csp:validate — all HTML files contain a CSP meta tag.');
}

main().catch((error) => {
  console.error('csp:validate failed:', error);
  process.exit(1);
});
