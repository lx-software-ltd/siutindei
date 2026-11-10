import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import test from 'node:test';

const require = createRequire(import.meta.url);
const {
  replaceBundledMinimatchVersion,
  bundledLockfileVersion,
} = require('../scripts/patch-bundled-minimatch.js');

const LOCK = `{
  "packages": {
    "node_modules/aws-cdk-lib/node_modules/minimatch": {
      "version": "10.2.6",
      "inBundle": true
    },
    "node_modules/minimatch": {
      "version": "11.0.5"
    }
  }
}
`;

test('lockfile rewrite updates only the bundled minimatch version', () => {
  const updated = replaceBundledMinimatchVersion(LOCK, '11.0.5');
  const expected = LOCK.replace(
    '"node_modules/aws-cdk-lib/node_modules/minimatch": {\n      "version": "10.2.6"',
    '"node_modules/aws-cdk-lib/node_modules/minimatch": {\n      "version": "11.0.5"',
  );
  assert.equal(updated, expected);
  assert.equal(bundledLockfileVersion(updated), '11.0.5');
  assert.equal(replaceBundledMinimatchVersion(updated, '11.0.5'), updated);
});

test('lockfile rewrite rejects a lockfile without the bundled entry', () => {
  assert.throws(
    () => replaceBundledMinimatchVersion('{"packages":{}}', '11.0.5'),
    /no aws-cdk-lib bundled minimatch entry/,
  );
});
