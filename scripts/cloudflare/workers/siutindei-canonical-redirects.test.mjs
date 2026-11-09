import assert from 'node:assert/strict';
import test from 'node:test';

import { handleRequest } from './siutindei-canonical-redirects.js';

test('www keeps the path and query on the way to the apex', async () => {
  const response = await handleRequest(
    new Request('https://www.siutindei.com/en/search/?q=swim'),
  );

  assert.equal(response.status, 301);
  assert.equal(
    response.headers.get('location'),
    'https://siutindei.com/en/search/?q=swim',
  );
});

test('the retired lx-software host is not redirected', async () => {
  const calls = [];
  const original = globalThis.fetch;
  globalThis.fetch = async (request) => {
    calls.push(request.url);
    return new Response('origin', { status: 200 });
  };
  try {
    const response = await handleRequest(
      new Request('https://siutindei-www.lx-software.com/en/'),
    );
    assert.equal(response.status, 200);
    assert.deepEqual(calls, ['https://siutindei-www.lx-software.com/en/']);
  } finally {
    globalThis.fetch = original;
  }
});
