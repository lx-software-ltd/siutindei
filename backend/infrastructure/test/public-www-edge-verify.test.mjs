import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const sourcePath = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  '../lib/functions/public-www-edge-verify.js',
);
const template = fs.readFileSync(sourcePath, 'utf8');
const CURRENT = 'current-secret-value-0123456789abcdefghij';
const PREVIOUS = 'previous-secret-value-0123456789abcdefghi';

function load({ current, previous }) {
  const context = {};
  vm.createContext(context);
  const source = template
    .replace('__EDGE_VERIFY_SECRET__', current)
    .replace('__EDGE_VERIFY_SECRET_PREVIOUS__', previous);
  vm.runInContext(
    `${source}\nglobalThis.edgeVerifyRejection = edgeVerifyRejection;`,
    context,
  );
  return (headers) => context.edgeVerifyRejection({ headers });
}

test('does nothing when both secrets are empty', () => {
  const check = load({ current: '', previous: '' });
  assert.equal(check({}), null);
  assert.equal(check({ 'x-edge-verify': { value: 'anything' } }), null);
});

test('accepts the current secret', () => {
  const check = load({ current: CURRENT, previous: '' });
  assert.equal(check({ 'x-edge-verify': { value: CURRENT } }), null);
});

test('accepts the previous secret during rotation', () => {
  const check = load({ current: CURRENT, previous: PREVIOUS });
  assert.equal(check({ 'x-edge-verify': { value: PREVIOUS } }), null);
  assert.equal(check({ 'x-edge-verify': { value: CURRENT } }), null);
});

test('refuses a missing, empty, or wrong header with an uncacheable 403', () => {
  const check = load({ current: CURRENT, previous: '' });
  for (const headers of [
    {},
    undefined,
    { 'x-edge-verify': { value: '' } },
    { 'x-edge-verify': { value: `${CURRENT}x` } },
    { 'x-edge-verify': { value: PREVIOUS } },
  ]) {
    const response = check(headers);
    assert.equal(response.statusCode, 403);
    assert.equal(response.headers['cache-control'].value, 'no-store');
  }
});

test('enforces when only the previous secret is set', () => {
  const check = load({ current: '', previous: PREVIOUS });
  assert.equal(check({}).statusCode, 403);
  assert.equal(check({ 'x-edge-verify': { value: PREVIOUS } }), null);
});

test('stays within the CloudFront Functions size budget with the largest body', () => {
  const pathRewrite = fs.readFileSync(
    path.join(path.dirname(sourcePath), 'public-www-path-rewrite.js'),
    'utf8',
  );
  const combined = `${template
    .replace('__EDGE_VERIFY_SECRET__', 'x'.repeat(64))
    .replace('__EDGE_VERIFY_SECRET_PREVIOUS__', 'y'.repeat(64))}\n${pathRewrite}`;
  assert.ok(Buffer.byteLength(combined, 'utf8') < 10 * 1024);
});
