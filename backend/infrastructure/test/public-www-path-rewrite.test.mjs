import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const sourcePath = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  '../lib/functions/public-www-path-rewrite.js',
);
const source = fs.readFileSync(sourcePath, 'utf8');
const context = {};
vm.createContext(context);
vm.runInContext(`${source}\nglobalThis.handler = handler;`, context);

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

test('rewrites a locale path to index.html', () => {
  const response = run('/en/search/');
  assert.equal(response.uri, '/en/search/index.html');
});

test('leaves hashed next assets alone', () => {
  const response = run('/_next/static/chunks/app.js');
  assert.equal(response.uri, '/_next/static/chunks/app.js');
});
