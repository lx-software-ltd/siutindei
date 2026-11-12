import { describe, expect, it } from 'vitest';

import { formatAuditActor } from '@/lib/audit-actor';

const users = {
  'user-1': { email: 'a@example.com', username: 'google_user-1' },
};

describe('formatAuditActor', () => {
  it('prints system when the audit row has no user', () => {
    expect(formatAuditActor(null, {})).toEqual({
      kind: 'system',
      text: 'system',
    });
    expect(formatAuditActor(undefined, {})).toEqual({
      kind: 'system',
      text: 'system',
    });
    expect(formatAuditActor('', users)).toEqual({
      kind: 'system',
      text: 'system',
    });
  });

  it('prints the resolved email and sign-in name when the user is known', () => {
    expect(formatAuditActor('user-1', users)).toEqual({
      kind: 'user',
      text: 'a@example.com',
      username: 'google_user-1',
    });
  });

  it('prints an em dash when the user id is present but unknown', () => {
    expect(formatAuditActor('missing', {})).toEqual({
      kind: 'user',
      text: '—',
      username: null,
    });
  });

  it('prints the key name when the actor is an API key', () => {
    expect(
      formatAuditActor(
        'api-key:key-1',
        { 'api-key:key-1': { email: 'a@example.com' } },
        { 'key-1': 'Partner read key' }
      )
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

  it('prints a job name and hides the run id', () => {
    expect(formatAuditActor('category-scan:run-1', users)).toEqual({
      kind: 'job',
      text: 'category check',
    });
    expect(formatAuditActor('location-scan:run-9', {})).toEqual({
      kind: 'job',
      text: 'location scan',
    });
  });
});
