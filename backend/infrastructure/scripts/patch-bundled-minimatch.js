/**
 * Replaces the bundled minimatch inside aws-cdk-lib with the top-level
 * minimatch dependency (11.0.1+) that includes the GHSA-g3hv-75wg-m249
 * fix. aws-cdk-lib 2.275.0 still ships minimatch 10.2.6 in its tarball,
 * so npm overrides cannot replace it. Copy the patched tree after every
 * install, and record that version on the inBundle lockfile entry.
 * Dependabot and npm audit read the lockfile, not the copied tree.
 * Ignoring the package instead makes the security job fail with
 * all_versions_ignored (update 1692171577). Drop this script when
 * aws-cdk-lib bundles minimatch 11 (aws/aws-cdk#39595).
 */

const fs = require('fs');
const path = require('path');

const MIN_PATCHED_VERSION = '11.0.1';
const BUNDLED_LOCK_KEY = '"node_modules/aws-cdk-lib/node_modules/minimatch"';

const source = path.join(__dirname, '..', 'node_modules', 'minimatch');
const target = path.join(
  __dirname,
  '..',
  'node_modules',
  'aws-cdk-lib',
  'node_modules',
  'minimatch',
);
const lockfilePath = path.join(__dirname, '..', 'package-lock.json');

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

function bundledLockBlock(lockText) {
  const start = lockText.indexOf(BUNDLED_LOCK_KEY);
  if (start < 0) {
    throw new Error(
      '[patch-bundled-minimatch] package-lock.json has no aws-cdk-lib bundled minimatch entry',
    );
  }
  const boundary = lockText.indexOf(
    '\n    "node_modules/',
    start + BUNDLED_LOCK_KEY.length,
  );
  const end = boundary === -1 ? lockText.length : boundary;
  return { start, end, block: lockText.slice(start, end) };
}

function replaceBundledMinimatchVersion(lockText, version) {
  const { start, end, block } = bundledLockBlock(lockText);
  if (!/"version":\s*"[^"]+"/.test(block)) {
    throw new Error(
      '[patch-bundled-minimatch] bundled minimatch lock entry has no version',
    );
  }
  const updated = block.replace(
    /"version":\s*"[^"]+"/,
    `"version": "${version}"`,
  );
  return lockText.slice(0, start) + updated + lockText.slice(end);
}

function bundledLockfileVersion(lockText) {
  const { block } = bundledLockBlock(lockText);
  const match = block.match(/"version":\s*"([^"]+)"/);
  if (!match) {
    throw new Error(
      '[patch-bundled-minimatch] bundled minimatch lock entry has no version',
    );
  }
  return match[1];
}

function syncLockfileVersion(version) {
  const lockText = fs.readFileSync(lockfilePath, 'utf8');
  const updated = replaceBundledMinimatchVersion(lockText, version);
  if (updated === lockText) {
    return false;
  }
  fs.writeFileSync(lockfilePath, updated);
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

  const rewroteLockfile = syncLockfileVersion(patchedVersion);
  console.log(
    `[patch-bundled-minimatch] replaced bundled minimatch with ${patchedVersion}` +
      (rewroteLockfile ? ' and recorded it in package-lock.json' : ''),
  );
  return patchedVersion;
}

module.exports = {
  MIN_PATCHED_VERSION,
  BUNDLED_LOCK_KEY,
  source,
  target,
  lockfilePath,
  versionAtLeast,
  replaceBundledMinimatchVersion,
  bundledLockfileVersion,
  syncLockfileVersion,
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
