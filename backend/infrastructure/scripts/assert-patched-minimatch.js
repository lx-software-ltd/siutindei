/**
 * CI check that postinstall replaced aws-cdk-lib's bundled minimatch
 * with a GHSA-g3hv-75wg-m249-patched copy (11.0.1+), and that
 * package-lock.json records that version. Dependabot security updates
 * read the lockfile entry.
 */

const fs = require('fs');
const path = require('path');
const {
  MIN_PATCHED_VERSION,
  lockfilePath,
  target,
  bundledLockfileVersion,
  versionAtLeast,
} = require('./patch-bundled-minimatch');

if (
  !versionAtLeast('11.0.1', MIN_PATCHED_VERSION) ||
  versionAtLeast('10.2.6', MIN_PATCHED_VERSION) ||
  !versionAtLeast('11.0.5', MIN_PATCHED_VERSION)
) {
  console.error('[assert-patched-minimatch] versionAtLeast self-check failed');
  process.exit(1);
}

const pkgPath = path.join(target, 'package.json');
if (!fs.existsSync(pkgPath)) {
  console.error(`[assert-patched-minimatch] missing ${pkgPath}`);
  process.exit(1);
}

const { version } = require(pkgPath);
if (!versionAtLeast(version, MIN_PATCHED_VERSION)) {
  console.error(
    `[assert-patched-minimatch] nested minimatch ${version} is below ${MIN_PATCHED_VERSION}`,
  );
  process.exit(1);
}

console.log(
  `[assert-patched-minimatch] aws-cdk-lib nested minimatch is ${version} (>= ${MIN_PATCHED_VERSION})`,
);

const lockVersion = bundledLockfileVersion(fs.readFileSync(lockfilePath, 'utf8'));
if (!versionAtLeast(lockVersion, MIN_PATCHED_VERSION)) {
  console.error(
    `[assert-patched-minimatch] lockfile minimatch ${lockVersion} is below ${MIN_PATCHED_VERSION}`,
  );
  process.exit(1);
}

console.log(
  `[assert-patched-minimatch] package-lock.json bundled minimatch is ${lockVersion} (>= ${MIN_PATCHED_VERSION})`,
);
