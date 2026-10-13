import { describe, expect, it } from 'vitest';

import { formatAuditActor } from '@/lib/audit-actor';

describe('formatAuditActor', () => {
  it('prints migration when the audit row has no user', () => {
    expect(formatAuditActor(null, {})).toBe('migration');
    expect(formatAuditActor(undefined, {})).toBe('migration');
    expect(formatAuditActor('', { 'user-1': 'a@example.com' })).toBe(
      'migration'
    );
  });

  it('prints the resolved email when the user is known', () => {
    expect(formatAuditActor('user-1', { 'user-1': 'a@example.com' })).toBe(
      'a@example.com'
    );
  });

  it('prints an em dash when the user id is present but unknown', () => {
    expect(formatAuditActor('missing', {})).toBe('—');
  });
});
