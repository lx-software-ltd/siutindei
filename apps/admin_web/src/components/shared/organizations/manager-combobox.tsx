'use client';

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from 'react';

import { ApiError } from '../../../lib/api-client';
import {
  createCognitoManager,
  listCognitoUsers,
} from '../../../lib/api-client-cognito';
import type { CognitoUser } from '../../../types/admin';
import { ChevronDownIcon, SpinnerIcon } from '../../icons/action-icons';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { Input } from '../../ui/input';

const MANAGER_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const ADD_MANAGER_PREFIX = 'add:';

function addManagerMessage(email: string): string {
  return (
    `Grant manager access to ${email}. This creates a passwordless ` +
    'account when none exists, even if the organization is not saved. ' +
    'An existing account is signed out of every device. They sign in ' +
    'with the one-time email code. Google or Apple sign-in uses this ' +
    'account only when that provider is not already a separate user. ' +
    'Check the address before continuing.'
  );
}

interface ManagerComboboxProps {
  id: string;
  value: string;
  onChange: (managerId: string) => void;
  onError?: (message: string) => void;
  hasError?: boolean;
  allowEmpty?: boolean;
  disabled?: boolean;
  inputClassName?: string;
}

export function formatManagerLabel(user: Pick<
  CognitoUser,
  'email' | 'username' | 'sub' | 'name'
>): string {
  const primary = user.email || user.username || user.sub;
  return user.name ? `${primary} (${user.name})` : primary;
}

export function ManagerCombobox({
  id,
  value,
  onChange,
  onError,
  hasError = false,
  allowEmpty = true,
  disabled = false,
  inputClassName = '',
}: ManagerComboboxProps) {
  const [users, setUsers] = useState<CognitoUser[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [isTyping, setIsTyping] = useState(false);
  const [query, setQuery] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [pendingEmail, setPendingEmail] = useState<string | null>(null);
  const [loadedQuery, setLoadedQuery] = useState<string | null>(null);
  const [addedUser, setAddedUser] = useState<CognitoUser | null>(null);
  const [remembered, setRemembered] = useState<{
    id: string;
    label: string;
  } | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const creatingRef = useRef(false);
  const listboxId = `${id}-listbox`;

  const selectedUser = useMemo(() => {
    const listed = users.find((user) => user.sub === value);
    if (listed) {
      return listed;
    }
    return addedUser?.sub === value ? addedUser : null;
  }, [addedUser, users, value]);

  if (selectedUser) {
    const label = formatManagerLabel(selectedUser);
    if (remembered?.id !== selectedUser.sub || remembered.label !== label) {
      setRemembered({ id: selectedUser.sub, label });
    }
  }

  const selectedLabel = selectedUser
    ? formatManagerLabel(selectedUser)
    : remembered?.id === value
      ? remembered.label
      : value;

  const inputValue = isTyping ? query : selectedLabel;
  const typedEmail = query.trim().toLowerCase();
  const showAdd =
    isTyping &&
    !isLoading &&
    loadedQuery !== null &&
    loadedQuery.trim().toLowerCase() === typedEmail &&
    MANAGER_EMAIL.test(typedEmail) &&
    !users.some((user) => (user.email || '').toLowerCase() === typedEmail);

  const options = useMemo(() => {
    const items: Array<{ id: string; label: string }> = [];
    items.push({
      id: '',
      label: allowEmpty ? 'You (leave blank)' : 'Select a manager',
    });
    if (value && !users.some((user) => user.sub === value)) {
      items.push({ id: value, label: selectedLabel || value });
    }
    for (const user of users) {
      items.push({ id: user.sub, label: formatManagerLabel(user) });
    }
    if (showAdd) {
      items.push({
        id: `${ADD_MANAGER_PREFIX}${typedEmail}`,
        label: isCreating
          ? `Adding ${typedEmail} as manager`
          : `Add ${typedEmail} as manager`,
      });
    }
    return items;
  }, [allowEmpty, isCreating, typedEmail, selectedLabel, showAdd, users, value]);

  useEffect(() => {
    let cancelled = false;
    const handle = window.setTimeout(() => {
      setIsLoading(true);
      listCognitoUsers(undefined, 60, query)
        .then((response) => {
          if (!cancelled) {
            setUsers(response.items);
            setLoadedQuery(query);
          }
        })
        .catch((err: unknown) => {
          if (cancelled) {
            return;
          }
          setLoadedQuery(null);
          const message =
            err instanceof ApiError
              ? err.message
              : 'Failed to load users for manager selection.';
          onError?.(message);
        })
        .finally(() => {
          if (!cancelled) {
            setIsLoading(false);
          }
        });
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(handle);
    };
  }, [onError, query]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        wrapperRef.current &&
        !wrapperRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
        setIsTyping(false);
        setQuery('');
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const closeSearch = () => {
    setIsTyping(false);
    setQuery('');
    setIsOpen(false);
    setActiveIndex(-1);
  };

  const addManager = async (email: string) => {
    if (creatingRef.current) {
      return;
    }
    creatingRef.current = true;
    setIsCreating(true);
    try {
      const created = await createCognitoManager(email);
      setAddedUser(created);
      setUsers((current) =>
        current.some((user) => user.sub === created.sub)
          ? current.map((user) => (user.sub === created.sub ? created : user))
          : [created, ...current]
      );
      onChange(created.sub);
      closeSearch();
    } catch (err: unknown) {
      const message =
        err instanceof ApiError ? err.message : 'Failed to add this manager.';
      onError?.(message);
    } finally {
      creatingRef.current = false;
      setIsCreating(false);
      setPendingEmail(null);
    }
  };

  const selectOption = (managerId: string) => {
    if (isCreating || pendingEmail) {
      return;
    }
    if (managerId.startsWith(ADD_MANAGER_PREFIX)) {
      setPendingEmail(managerId.slice(ADD_MANAGER_PREFIX.length));
      return;
    }
    onChange(managerId);
    closeSearch();
  };

  const cancelAdd = () => {
    if (isCreating) {
      return;
    }
    setPendingEmail(null);
  };

  const handleInputChange = (nextQuery: string) => {
    setIsTyping(true);
    setQuery(nextQuery);
    setIsOpen(true);
    setActiveIndex(-1);
    if (!nextQuery.trim()) {
      onChange('');
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Escape') {
      setIsTyping(false);
      setQuery('');
      setIsOpen(false);
      setActiveIndex(-1);
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setIsOpen(true);
      setActiveIndex((prev) =>
        prev < options.length - 1 ? prev + 1 : 0
      );
      return;
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      setIsOpen(true);
      setActiveIndex((prev) =>
        prev > 0 ? prev - 1 : options.length - 1
      );
      return;
    }
    if (event.key === 'Enter' && isOpen && activeIndex >= 0) {
      event.preventDefault();
      const option = options[activeIndex];
      if (option) {
        selectOption(option.id);
      }
    }
  };

  const emptyMessage = isLoading
    ? 'Loading users...'
    : query.trim()
      ? 'No matching users'
      : 'No users found';

  return (
    <div ref={wrapperRef} className='relative'>
      <div className='relative'>
        <Input
          id={id}
          role='combobox'
          aria-expanded={isOpen}
          aria-controls={listboxId}
          aria-autocomplete='list'
          aria-activedescendant={
            activeIndex >= 0
              ? `${listboxId}-option-${activeIndex}`
              : undefined
          }
          autoComplete='off'
          value={inputValue}
          placeholder={
            isLoading ? 'Loading users...' : 'Search by email'
          }
          disabled={disabled}
          onChange={(event) => handleInputChange(event.target.value)}
          onFocus={(event) => {
            setIsOpen(true);
            event.target.select();
          }}
          onKeyDown={handleKeyDown}
          className={`pr-9 ${inputClassName}`}
          aria-invalid={hasError || undefined}
        />
        <span className='pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3'>
          {isLoading ? (
            <SpinnerIcon className='h-4 w-4 animate-spin text-ink-500' />
          ) : (
            <ChevronDownIcon className='h-4 w-4 text-ink-500' />
          )}
        </span>
      </div>
      {isOpen ? (
        <ul
          id={listboxId}
          role='listbox'
          className={
            'absolute z-50 mt-1 max-h-60 w-full overflow-auto rounded-md ' +
            'border border-brand-100 bg-white py-1 shadow-lg'
          }
        >
          {isLoading && options.length <= 1 ? (
            <li className='px-3 py-2 text-sm text-ink-500'>
              {emptyMessage}
            </li>
          ) : (
            options.map((option, index) => {
              const addDisabled =
                option.id.startsWith(ADD_MANAGER_PREFIX) &&
                (isCreating || pendingEmail !== null);
              const highlighted =
                index === activeIndex || option.id === value;
              return (
                <li
                  key={`${option.id || 'empty'}-${index}`}
                  id={`${listboxId}-option-${index}`}
                  role='option'
                  aria-selected={option.id === value}
                  aria-disabled={addDisabled || undefined}
                  className={
                    'px-3 py-2 text-sm ' +
                    (addDisabled
                      ? 'cursor-not-allowed text-ink-500'
                      : highlighted
                        ? 'cursor-pointer bg-brand-50 text-ink-900'
                        : 'cursor-pointer text-ink-700 hover:bg-brand-50')
                  }
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => {
                    if (!addDisabled) {
                      selectOption(option.id);
                    }
                  }}
                  onMouseEnter={() => setActiveIndex(index)}
                >
                  {option.label}
                </li>
              );
            })
          )}
          {!isLoading && users.length === 0 && query.trim() && !showAdd ? (
            <li className='px-3 py-2 text-sm text-ink-500'>
              No matching users
            </li>
          ) : null}
        </ul>
      ) : null}
      <ConfirmDialog
        open={pendingEmail !== null}
        title='Add manager'
        message={pendingEmail ? addManagerMessage(pendingEmail) : ''}
        confirmLabel='Add manager'
        confirmLoading={isCreating}
        confirmLoadingLabel='Adding…'
        onConfirm={() => {
          if (pendingEmail) {
            void addManager(pendingEmail);
          }
        }}
        onCancel={cancelAdd}
      />
    </div>
  );
}
