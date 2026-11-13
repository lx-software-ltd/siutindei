import { afterEach, describe, expect, it, vi } from 'vitest';

describe('robots.txt', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it('lets search and AI search crawlers read pages and blocks training crawlers', async () => {
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
      {
        userAgent: [
          'OAI-SearchBot',
          'ChatGPT-User',
          'PerplexityBot',
          'Perplexity-User',
          'Claude-SearchBot',
          'Claude-User',
        ],
        allow: '/',
        disallow: ['/v1/', '/cdn-cgi/'],
      },
      {
        userAgent: [
          'GPTBot',
          'ClaudeBot',
          'CCBot',
          'Google-Extended',
          'Applebot-Extended',
          'Bytespider',
        ],
        disallow: '/',
      },
    ]);
    expect(result.sitemap).toBe('https://www.example.test/sitemap.xml');
    expect(result).not.toHaveProperty('host');
  });

  it('does not let a search group and a training group name the same crawler', async () => {
    const { AI_SEARCH_USER_AGENTS, AI_TRAINING_USER_AGENTS } = await import('@/lib/routes');
    const training = new Set<string>(AI_TRAINING_USER_AGENTS);
    expect(AI_SEARCH_USER_AGENTS.filter((agent) => training.has(agent))).toEqual([]);
  });
});
