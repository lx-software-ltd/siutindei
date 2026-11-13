import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const functionsDir = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  '../lib/functions',
);
const source = fs.readFileSync(
  path.join(functionsDir, 'public-www-path-rewrite.js'),
  'utf8',
);
// The stack prepends the edge-verify snippet; load it the same way with the
// placeholders resolved so the check can be exercised here too.
const edgeVerifySource = fs
  .readFileSync(path.join(functionsDir, 'public-www-edge-verify.js'), 'utf8')
  .replace('__EDGE_VERIFY_SECRET__', '')
  .replace('__EDGE_VERIFY_SECRET_PREVIOUS__', '');
const context = {};
vm.createContext(context);
vm.runInContext(
  `${edgeVerifySource}\n${source}\nglobalThis.handler = handler;`,
  context,
);

function run(uri, extra = {}) {
  const raw = extra.rawQueryString ?? '';
  return context.handler({
    request: {
      uri,
      headers: extra.headers ?? {},
      querystring: extra.querystring ?? {},
      rawQueryString() {
        return raw;
      },
    },
  });
}

test('serves normally when no edge-verify secret is configured', () => {
  const response = run('/en/about/', {
    headers: { 'x-proxy-verify': { value: 'anything' } },
  });
  assert.equal(response.uri, '/en/about/index.html');
});

test('refuses requests without the edge header once a secret is set', () => {
  const enforced = {};
  vm.createContext(enforced);
  const enforcedEdge = fs
    .readFileSync(path.join(functionsDir, 'public-www-edge-verify.js'), 'utf8')
    .replace('__EDGE_VERIFY_SECRET__', 'current-secret-value-0123456789abcdef')
    .replace('__EDGE_VERIFY_SECRET_PREVIOUS__', '');
  vm.runInContext(
    `${enforcedEdge}\n${source}\nglobalThis.handler = handler;`,
    enforced,
  );
  const refused = enforced.handler({
    request: { uri: '/en/', headers: {}, rawQueryString: () => '' },
  });
  assert.equal(refused.statusCode, 403);
  const allowed = enforced.handler({
    request: {
      uri: '/en/',
      headers: {
        'x-proxy-verify': { value: 'current-secret-value-0123456789abcdef' },
      },
      rawQueryString: () => '',
    },
  });
  assert.equal(allowed.uri, '/en/index.html');
});

test('redirects the bare home path to the english locale', () => {
  const response = run('/');
  assert.equal(response.statusCode, 302);
  assert.equal(response.headers.location.value, '/en/');
});

test('redirects an unprefixed search path and keeps the query string', () => {
  const response = run('/search', {
    rawQueryString: 'q=art',
  });
  assert.equal(response.headers.location.value, '/en/search/?q=art');
});

test('does not re-encode an already encoded query string', () => {
  const response = run('/search', {
    rawQueryString: 'q=%E8%8B%B1%E6%96%87&topic=art+class',
  });
  assert.equal(
    response.headers.location.value,
    '/en/search/?q=%E8%8B%B1%E6%96%87&topic=art+class',
  );
});

test('keeps english when chinese is only a lower-priority language', () => {
  const response = run('/', {
    headers: { 'accept-language': { value: 'en-US,en;q=0.9,zh;q=0.1' } },
  });
  assert.equal(response.headers.location.value, '/en/');
});

test('uses zh-HK when the accept-language header asks for chinese', () => {
  const response = run('/about/', {
    headers: { 'accept-language': { value: 'zh-HK,zh;q=0.9' } },
  });
  assert.equal(response.headers.location.value, '/zh-HK/about/');
});

test('redirects the unprefixed activities hub to a locale', () => {
  const response = run('/activities/', {
    headers: { 'accept-language': { value: 'zh-HK,zh;q=0.9' } },
  });
  assert.equal(response.statusCode, 302);
  assert.equal(response.headers.location.value, '/zh-HK/activities/');
});

test('serves an activity page and a landing page from their index files', () => {
  assert.equal(
    run('/en/activity/3f6c1f9e-0000-4000-8000-000000000001/').uri,
    '/en/activity/3f6c1f9e-0000-4000-8000-000000000001/index.html',
  );
  assert.equal(
    run('/zh-HK/activities/sports').uri,
    '/zh-HK/activities/sports/index.html',
  );
});

test('rewrites a locale path to index.html', () => {
  const response = run('/en/search/');
  assert.equal(response.uri, '/en/search/index.html');
});

test('leaves hashed next assets alone', () => {
  const response = run('/_next/static/chunks/app.js');
  assert.equal(response.uri, '/_next/static/chunks/app.js');
});
