import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  formatManagerLabel,
  ManagerCombobox,
} from '@/components/shared/organizations/manager-combobox';
import {
  createCognitoManager,
  listCognitoUsers,
} from '@/lib/api-client-cognito';
import type { CognitoUser } from '@/types/admin';

vi.mock('@/lib/api-client-cognito', () => ({
  listCognitoUsers: vi.fn(),
  createCognitoManager: vi.fn(),
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
const createCognitoManagerMock = vi.mocked(createCognitoManager);

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

  it('adds a typed email that is not already a user', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    createCognitoManagerMock.mockResolvedValue(
      makeUser({
        sub: 'new-manager-id-001',
        email: 'new.manager@example.com',
      })
    );

    const { rerender } = render(
      <ManagerCombobox id='org-manager' value='' onChange={onChange} />
    );

    const field = screen.getByRole('combobox');
    await user.type(field, 'new.manager@example.com');

    await user.click(
      await screen.findByRole('option', {
        name: 'Add new.manager@example.com as manager',
      })
    );

    await waitFor(() => {
      expect(createCognitoManagerMock).toHaveBeenCalledWith(
        'new.manager@example.com'
      );
    });
    expect(onChange).toHaveBeenCalledWith('new-manager-id-001');
    rerender(
      <ManagerCombobox
        id='org-manager'
        value='new-manager-id-001'
        onChange={onChange}
      />
    );
    expect(field).toHaveValue('new.manager@example.com');
  });

  it('keeps the current manager label while searching for a new email', async () => {
    const user = userEvent.setup();
    listCognitoUsersMock.mockImplementation(async (_token, _limit, query) => {
      if (query === 'new.manager@example.com') {
        return { items: [], pagination_token: null };
      }
      return { items: users, pagination_token: null };
    });

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

    await user.type(screen.getByRole('combobox'), 'new.manager@example.com');

    expect(
      await screen.findByRole('option', {
        name: 'Add new.manager@example.com as manager',
      })
    ).toBeVisible();
    expect(
      screen.getByRole('option', {
        name: 'manager@example.com (Manager User)',
      })
    ).toBeVisible();
    expect(screen.queryByRole('option', { name: 'manager-user-id-456' })).toBeNull();
  });

  it('does not offer add when the email already matches a user', async () => {
    const user = userEvent.setup();

    render(
      <ManagerCombobox id='org-manager' value='' onChange={vi.fn()} />
    );

    await user.type(screen.getByRole('combobox'), 'manager@example.com');

    await screen.findByRole('option', {
      name: 'manager@example.com (Manager User)',
    });
    expect(
      screen.queryByRole('option', { name: /Add manager@example.com/ })
    ).toBeNull();
  });
});
