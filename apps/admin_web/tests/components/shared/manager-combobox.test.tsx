import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  formatManagerLabel,
  ManagerCombobox,
} from '@/components/shared/organizations/manager-combobox';
import { listCognitoUsers } from '@/lib/api-client-cognito';
import type { CognitoUser } from '@/types/admin';

vi.mock('@/lib/api-client-cognito', () => ({
  listCognitoUsers: vi.fn(),
}));

function makeUser(
  overrides: Partial<CognitoUser> & Pick<CognitoUser, 'sub' | 'email'>
): CognitoUser {
  return {
    username: overrides.email,
    email_verified: true,
    enabled: true,
    status: 'CONFIRMED',
    groups: ['manager'],
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    attributes: { email: overrides.email },
    ...overrides,
  };
}

const users = [
  makeUser({
    sub: 'manager-user-id-456',
    email: 'manager@example.com',
    name: 'Manager User',
  }),
  makeUser({
    sub: 'admin-manager-id-789',
    email: 'admin-manager@example.com',
    name: 'Admin Manager User',
  }),
];

const listCognitoUsersMock = vi.mocked(listCognitoUsers);

describe('formatManagerLabel', () => {
  it('includes email and name when both are present', () => {
    expect(formatManagerLabel(users[0])).toBe(
      'manager@example.com (Manager User)'
    );
  });
});

describe('ManagerCombobox', () => {
  beforeEach(() => {
    listCognitoUsersMock.mockResolvedValue({
      items: users,
      pagination_token: null,
    });
  });

  it('renders one searchable field and lists users in the same control', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(
      <label htmlFor='org-manager'>
        Manager
        <ManagerCombobox
          id='org-manager'
          value=''
          onChange={onChange}
        />
      </label>
    );

    const field = screen.getByRole('combobox', { name: 'Manager' });
    expect(field).toBeVisible();
    expect(screen.queryByLabelText('Email prefix')).toBeNull();

    await user.click(field);
    expect(
      await screen.findByRole('option', {
        name: 'manager@example.com (Manager User)',
      })
    ).toBeVisible();
    expect(
      screen.getByRole('option', { name: 'You (leave blank)' })
    ).toBeVisible();

    await user.click(
      screen.getByRole('option', { name: 'manager@example.com (Manager User)' })
    );
    expect(onChange).toHaveBeenCalledWith('manager-user-id-456');
  });

  it('shows the selected manager and searches from the same field', async () => {
    const user = userEvent.setup();

    render(
      <ManagerCombobox
        id='org-manager'
        value='manager-user-id-456'
        onChange={vi.fn()}
      />
    );

    expect(
      await screen.findByDisplayValue('manager@example.com (Manager User)')
    ).toBeVisible();

    const field = screen.getByRole('combobox');
    await user.clear(field);
    await user.type(field, 'admin-');
    await waitFor(() => {
      expect(listCognitoUsersMock).toHaveBeenCalledWith(
        undefined,
        60,
        'admin-'
      );
    });
  });
});
