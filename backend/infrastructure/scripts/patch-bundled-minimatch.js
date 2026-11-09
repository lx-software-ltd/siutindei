/**
 * Replaces the bundled minimatch inside aws-cdk-lib with the top-level
 * minimatch dependency (11.0.1+) that includes the GHSA-g3hv-75wg-m249
 * fix. aws-cdk-lib 2.275.0 still ships minimatch 10.2.6 in its tarball,
 * so npm overrides cannot replace it. Copy the patched tree after every
 * install. Drop this script when aws-cdk-lib bundles minimatch 11
 * (aws/aws-cdk#39595).
 */

const fs = require('fs');
const path = require('path');

const MIN_PATCHED_VERSION = '11.0.1';

const source = path.join(__dirname, '..', 'node_modules', 'minimatch');
const target = path.join(
  __dirname,
  '..',
  'node_modules',
  'aws-cdk-lib',
  'node_modules',
  'minimatch',
);

function versionAtLeast(version, min) {
  const a = String(version)
    .split('.')
    .map((part) => Number.parseInt(part, 10) || 0);
  const b = String(min)
    .split('.')
    .map((part) => Number.parseInt(part, 10) || 0);
  const len = Math.max(a.length, b.length);
  for (let i = 0; i < len; i += 1) {
    const av = a[i] || 0;
    const bv = b[i] || 0;
    if (av > bv) {
      return true;
    }
    if (av < bv) {
      return false;
    }
  }
  return true;
}

function patchBundledMinimatch() {
  if (!fs.existsSync(source)) {
    throw new Error(`[patch-bundled-minimatch] source not found at ${source}`);
  }
  if (!fs.existsSync(target)) {
    throw new Error(`[patch-bundled-minimatch] target not found at ${target}`);
  }

  fs.cpSync(source, target, { recursive: true });

  const patchedVersion = require(path.join(target, 'package.json')).version;
  if (!versionAtLeast(patchedVersion, MIN_PATCHED_VERSION)) {
    throw new Error(
      `[patch-bundled-minimatch] patched minimatch ${patchedVersion} is below ${MIN_PATCHED_VERSION} (GHSA-g3hv-75wg-m249)`,
    );
  }

  console.log(
    `[patch-bundled-minimatch] replaced bundled minimatch with ${patchedVersion}`,
  );
  return patchedVersion;
}

module.exports = {
  MIN_PATCHED_VERSION,
  source,
  target,
  versionAtLeast,
  patchBundledMinimatch,
};

if (require.main === module) {
  try {
    patchBundledMinimatch();
  } catch (err) {
    console.error(err.message);
    process.exit(1);
  }
}
