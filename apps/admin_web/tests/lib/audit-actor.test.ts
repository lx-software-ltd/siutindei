import { describe, expect, it } from 'vitest';

import { formatAuditActor } from '@/lib/audit-actor';

describe('formatAuditActor', () => {
  it('prints migration when the audit row has no user', () => {
    expect(formatAuditActor(null, {})).toEqual({
      kind: 'migration',
      text: 'migration',
    });
    expect(formatAuditActor(undefined, {})).toEqual({
      kind: 'migration',
      text: 'migration',
    });
    expect(formatAuditActor('', { 'user-1': 'a@example.com' })).toEqual({
      kind: 'migration',
      text: 'migration',
    });
  });

  it('prints the resolved email when the user is known', () => {
    expect(formatAuditActor('user-1', { 'user-1': 'a@example.com' })).toEqual({
      kind: 'user',
      text: 'a@example.com',
    });
  });

  it('prints an em dash when the user id is present but unknown', () => {
    expect(formatAuditActor('missing', {})).toEqual({
      kind: 'user',
      text: '—',
    });
  });

  it('prints the key name when the actor is an API key', () => {
    expect(
      formatAuditActor('api-key:key-1', { 'api-key:key-1': 'a@example.com' }, {
        'key-1': 'Partner read key',
      })
    ).toEqual({ kind: 'key', text: 'Partner read key' });
  });

  it('prints an em dash for a key with a blank or unknown name', () => {
    expect(formatAuditActor('api-key:key-1', {}, { 'key-1': '  ' })).toEqual({
      kind: 'key',
      text: '—',
    });
    expect(formatAuditActor('api-key:missing', {}, {})).toEqual({
      kind: 'key',
      text: '—',
    });
    expect(formatAuditActor('api-key:', {}, {})).toEqual({
      kind: 'key',
      text: '—',
    });
  });
});
