'use client';

import { useEffect, useId, useState } from 'react';

import {
  searchUserOrganizations,
  type OrganizationLookup,
} from '../../lib/api-client-user';
import { Input } from './input';

const MIN_QUERY_LENGTH = 2;
const SEARCH_DEBOUNCE_MS = 300;

interface OrganizationAutocompleteProps {
  id: string;
  selected: OrganizationLookup | null;
  onSelect: (organization: OrganizationLookup | null) => void;
  onBlur?: () => void;
  className?: string;
  placeholder?: string;
}

/**
 * Organization name field. Suggestions come from
 * `searchUserOrganizations`, the lookup the feedback form already uses.
 */
export function OrganizationAutocomplete({
  id,
  selected,
  onSelect,
  onBlur,
  className,
  placeholder = 'Search organizations...',
}: OrganizationAutocompleteProps) {
  const listboxId = useId();
  const [query, setQuery] = useState(selected?.name ?? '');
  const [matches, setMatches] = useState<OrganizationLookup[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const selectedName = selected?.name ?? '';

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < MIN_QUERY_LENGTH || trimmed === selectedName) {
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      searchUserOrganizations(trimmed, 10)
        .then((response) => {
          if (!cancelled) {
            setMatches(response.items);
          }
        })
        .catch(() => {
          if (!cancelled) {
            setMatches([]);
          }
        })
        .finally(() => {
          if (!cancelled) {
            setIsSearching(false);
          }
        });
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [query, selectedName]);

  function handleQueryChange(next: string) {
    setQuery(next);
    if (selected) {
      onSelect(null);
    }
    const trimmed = next.trim();
    if (trimmed.length < MIN_QUERY_LENGTH || trimmed === selectedName) {
      setMatches([]);
      setIsSearching(false);
      return;
    }
    setMatches([]);
    setIsSearching(true);
  }

  const showMatches = matches.length > 0 && !selected;

  return (
    <div>
      <Input
        id={id}
        role='combobox'
        aria-expanded={showMatches}
        aria-controls={listboxId}
        aria-autocomplete='list'
        autoComplete='off'
        className={className}
        value={query}
        placeholder={placeholder}
        onBlur={onBlur}
        onChange={(event) => handleQueryChange(event.target.value)}
      />
      {isSearching ? (
        <p className='mt-1 text-xs text-slate-500'>Searching...</p>
      ) : null}
      {showMatches ? (
        <ul
          id={listboxId}
          role='listbox'
          className='mt-2 rounded border border-brand-100 bg-white'
        >
          {matches.map((org) => (
            <li key={org.id} role='presentation'>
              <button
                type='button'
                role='option'
                aria-selected={false}
                onClick={() => {
                  setQuery(org.name);
                  setMatches([]);
                  setIsSearching(false);
                  onSelect(org);
                }}
                className='flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-brand-50'
              >
                <span>{org.name}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
