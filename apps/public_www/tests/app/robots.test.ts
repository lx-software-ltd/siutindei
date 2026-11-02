import { afterEach, describe, expect, it, vi } from 'vitest';

describe('robots.txt', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it('allows pages, disallows the proxied API and the challenge platform', async () => {
    vi.stubEnv('NEXT_PUBLIC_SITE_ORIGIN', 'https://www.example.test');
    const { default: robots } = await import('@/app/robots');

    const result = robots();
    const rules = Array.isArray(result.rules) ? result.rules : [result.rules];

    expect(rules).toEqual([
      {
        userAgent: '*',
        allow: '/',
        disallow: ['/v1/', '/cdn-cgi/'],
      },
    ]);
    expect(result.sitemap).toBe('https://www.example.test/sitemap.xml');
    expect(result.host).toBe('www.example.test');
  });
});
