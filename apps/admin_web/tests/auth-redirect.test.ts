import { describe, expect, it } from 'vitest';

import { sanitizeLoginRedirect } from '@/lib/auth';

describe('sanitizeLoginRedirect', () => {
  it('keeps a safe in-app path', () => {
    expect(sanitizeLoginRedirect('/admin/imports/')).toBe('/admin/imports/');
  });

  it('sends dashboard return paths home so CloudFront cannot loop', () => {
    expect(sanitizeLoginRedirect('/admin/dashboard')).toBe('/');
    expect(sanitizeLoginRedirect('/admin/dashboard/')).toBe('/');
    expect(sanitizeLoginRedirect('/admin/dashboard?section=imports')).toBe('/');
    expect(sanitizeLoginRedirect('/auth/callback')).toBe('/');
    expect(sanitizeLoginRedirect('https://example.com')).toBe('/');
  });
});
