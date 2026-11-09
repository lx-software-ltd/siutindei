/**
 * CI check that postinstall actually replaced aws-cdk-lib's bundled
 * minimatch with a GHSA-g3hv-75wg-m249-patched copy (11.0.1+).
 */

const fs = require('fs');
const path = require('path');
const {
  MIN_PATCHED_VERSION,
  target,
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
