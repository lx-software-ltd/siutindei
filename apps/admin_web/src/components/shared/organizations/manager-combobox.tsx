'use client';

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from 'react';

import { ApiError } from '../../../lib/api-client';
import { listCognitoUsers } from '../../../lib/api-client-cognito';
import type { CognitoUser } from '../../../types/admin';
import { Input } from '../../ui/input';

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

function ChevronIcon() {
  return (
    <svg
      className='h-4 w-4 text-slate-400'
      viewBox='0 0 20 20'
      fill='currentColor'
      aria-hidden='true'
    >
      <path
        fillRule='evenodd'
        d='M5.23 7.21a.75.75 0 011.06.02L10 11.17l3.71-3.94a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z'
        clipRule='evenodd'
      />
    </svg>
  );
}

function SpinnerIcon() {
  return (
    <svg
      className='h-4 w-4 animate-spin text-slate-400'
      viewBox='0 0 24 24'
      fill='none'
      aria-hidden='true'
    >
      <circle
        className='opacity-25'
        cx='12'
        cy='12'
        r='10'
        stroke='currentColor'
        strokeWidth='4'
      />
      <path
        className='opacity-75'
        fill='currentColor'
        d='M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z'
      />
    </svg>
  );
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
  const wrapperRef = useRef<HTMLDivElement>(null);
  const listboxId = `${id}-listbox`;

  const selectedUser = useMemo(
    () => users.find((user) => user.sub === value) ?? null,
    [users, value]
  );

  const selectedLabel = selectedUser
    ? formatManagerLabel(selectedUser)
    : value;

  const inputValue = isTyping ? query : selectedLabel;

  const options = useMemo(() => {
    const items: Array<{ id: string; label: string }> = [];
    items.push({
      id: '',
      label: allowEmpty ? 'You (leave blank)' : 'Select a manager',
    });
    if (value && !users.some((user) => user.sub === value)) {
      items.push({ id: value, label: value });
    }
    for (const user of users) {
      items.push({ id: user.sub, label: formatManagerLabel(user) });
    }
    return items;
  }, [allowEmpty, users, value]);

  useEffect(() => {
    let cancelled = false;
    const handle = window.setTimeout(() => {
      setIsLoading(true);
      listCognitoUsers(undefined, 60, query)
        .then((response) => {
          if (!cancelled) {
            setUsers(response.items);
          }
        })
        .catch((err: unknown) => {
          if (cancelled) {
            return;
          }
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

  const selectOption = (managerId: string) => {
    onChange(managerId);
    closeSearch();
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
          {isLoading ? <SpinnerIcon /> : <ChevronIcon />}
        </span>
      </div>
      {isOpen ? (
        <ul
          id={listboxId}
          role='listbox'
          className={
            'absolute z-50 mt-1 max-h-60 w-full overflow-auto rounded-md ' +
            'border border-slate-200 bg-white py-1 shadow-lg'
          }
        >
          {isLoading && options.length <= 1 ? (
            <li className='px-3 py-2 text-sm text-slate-500'>
              {emptyMessage}
            </li>
          ) : (
            options.map((option, index) => (
              <li
                key={`${option.id || 'empty'}-${index}`}
                id={`${listboxId}-option-${index}`}
                role='option'
                aria-selected={option.id === value}
                className={
                  'cursor-pointer px-3 py-2 text-sm ' +
                  (index === activeIndex
                    ? 'bg-slate-100 text-slate-900'
                    : option.id === value
                      ? 'bg-slate-50 text-slate-900'
                      : 'text-slate-700 hover:bg-slate-50')
                }
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => selectOption(option.id)}
                onMouseEnter={() => setActiveIndex(index)}
              >
                {option.label}
              </li>
            ))
          )}
          {!isLoading && users.length === 0 && query.trim() ? (
            <li className='px-3 py-2 text-sm text-slate-500'>
              No matching users
            </li>
          ) : null}
        </ul>
      ) : null}
    </div>
  );
}
