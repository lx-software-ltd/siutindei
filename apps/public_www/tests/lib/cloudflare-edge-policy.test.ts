import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  ACTIVITY_DETAIL_PAGE_LIMIT,
  DISCOVERY_HOME_SEARCH_LIMIT,
  DISCOVERY_RECENT_SEARCH_LIMIT,
  RELATED_ACTIVITIES_LIMIT,
  SEARCH_RESULTS_PAGE_LIMIT,
} from '@/lib/activities/search-limits';
import {
  AI_SEARCH_USER_AGENTS,
  AI_TRAINING_USER_AGENTS,
  ROBOTS_DISALLOWED_PATHS,
} from '@/lib/routes';

/** `scripts/smoke-staging.mjs` probes the search API with one listing. */
const SMOKE_CHECK_LIMIT = 1;
/** Discovery carousels after the first page render 12 at a time. */
const DISCOVERY_CAROUSEL_LIMIT = 12;
const SEARCH_PATH = '/v1/activities/search';

interface EdgeRule {
  readonly description: string;
  readonly expression: string;
  readonly action: string;
}

interface EdgePolicy {
  readonly hostname: string;
  readonly bot_management: Record<string, string | boolean>;
  readonly rulesets: Record<string, { readonly rules: readonly EdgeRule[] }>;
}

function loadPolicy(): EdgePolicy {
  const file = path.resolve(
    __dirname,
    '../../../../scripts/cloudflare/public_www_edge_policy.json',
  );
  return JSON.parse(readFileSync(file, 'utf8')) as EdgePolicy;
}

function allowedLimits(expression: string): number[] {
  return [...expression.matchAll(/\["limit"\]\[\*\] eq "(\d+)"/g)].map(
    (match) => Number(match[1]),
  );
}

describe('Cloudflare edge policy contract', () => {
  const policy = loadPolicy();

  it('allow-lists exactly the search limits the site sends', () => {
    const rule = policy.rulesets.http_request_firewall_custom.rules.find(
      (candidate) => candidate.description === 'search-limit-allowlist',
    );
    expect(rule).toBeDefined();
    expect(rule?.action).toBe('block');

    const siteLimits = new Set([
      SMOKE_CHECK_LIMIT,
      DISCOVERY_CAROUSEL_LIMIT,
      DISCOVERY_RECENT_SEARCH_LIMIT,
      DISCOVERY_HOME_SEARCH_LIMIT,
      SEARCH_RESULTS_PAGE_LIMIT,
      ACTIVITY_DETAIL_PAGE_LIMIT,
      RELATED_ACTIVITIES_LIMIT,
    ]);
    expect(new Set(allowedLimits(rule?.expression ?? ''))).toEqual(siteLimits);
  });

  it('scopes every blocking rule to the search API path', () => {
    const blockingPhases = ['http_ratelimit', 'http_request_firewall_custom'];
    for (const phase of blockingPhases) {
      for (const rule of policy.rulesets[phase].rules) {
        expect(rule.expression).toContain(
          `http.request.uri.path eq "${SEARCH_PATH}"`,
        );
        expect(rule.action).toBe('block');
      }
    }
  });

  it('keeps robots.txt and the proxied API path aligned', () => {
    const apiPrefix = ROBOTS_DISALLOWED_PATHS.find((prefix) =>
      SEARCH_PATH.startsWith(prefix),
    );
    expect(apiPrefix).toBe('/v1/');
    expect(ROBOTS_DISALLOWED_PATHS).toContain('/cdn-cgi/');
  });

  it('admits AI search and user fetchers and blocks training crawlers, as robots.txt says', () => {
    expect(policy.bot_management).toMatchObject({
      ai_training: 'block',
      ai_search: 'disabled',
      ai_user: 'disabled',
      is_robots_txt_managed: false,
      bot_preference_sync_enabled: false,
    });
    expect(AI_SEARCH_USER_AGENTS).toContain('OAI-SearchBot');
    expect(AI_TRAINING_USER_AGENTS).toContain('GPTBot');
  });

  it('never stores the edge secret in the repository', () => {
    const transform = policy.rulesets.http_request_late_transform.rules[0];
    expect(JSON.stringify(transform)).toContain(
      '${PUBLIC_WWW_EDGE_VERIFY_SECRET}',
    );
  });
});
