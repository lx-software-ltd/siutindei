import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import {
  AuditActorCaption,
  AuditActorValue,
} from '@/components/admin/audit-logs-panel';

describe('AuditActorValue', () => {
  it('marks an empty actor as system without calling it a migration', () => {
    render(<AuditActorValue actor={{ kind: 'system', text: 'system' }} />);

    expect(screen.getByText('system')).toBeVisible();
    expect(screen.queryByRole('img', { name: 'GitHub' })).toBeNull();
    expect(screen.queryByText('migration')).toBeNull();
  });

  it('marks a job by name and does not use the person icon', () => {
    render(<AuditActorValue actor={{ kind: 'job', text: 'category check' }} />);

    expect(screen.getByText('category check')).toBeVisible();
    expect(screen.queryByRole('img', { name: 'User' })).toBeNull();
  });

  it('uses the sign-in icon for a known user', () => {
    render(
      <AuditActorValue
        actor={{ kind: 'user', text: 'a@example.com', username: 'google_user-1' }}
      />
    );

    expect(screen.getByRole('img', { name: 'Google' })).toBeVisible();
    expect(screen.queryByRole('img', { name: 'User' })).toBeNull();
  });

  it('uses a person icon when the user id does not resolve', () => {
    render(
      <AuditActorValue actor={{ kind: 'user', text: '—', username: null }} />
    );

    expect(screen.getByRole('img', { name: 'User' })).toBeVisible();
  });

  it('keeps the key icon next to the key name', () => {
    render(<AuditActorValue actor={{ kind: 'key', text: 'Partner read key' }} />);

    expect(screen.getByRole('img', { name: 'API key' })).toBeVisible();
  });
});

describe('AuditActorCaption', () => {
  it('keeps the actor icon when the phone caption names an empty value', () => {
    render(<AuditActorCaption actor={{ kind: 'key', text: '—' }} />);

    expect(screen.getByText('Actor')).toBeVisible();
    expect(screen.getByRole('img', { name: 'API key' })).toBeVisible();
  });
});
