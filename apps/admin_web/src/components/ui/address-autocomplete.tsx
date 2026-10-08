'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { SpinnerIcon } from '../icons/action-icons';
import {
  searchAddress,
  type NominatimAddress,
  type NominatimResult,
} from '../../lib/api-client';

/**
 * Address autocomplete powered by Nominatim (OpenStreetMap).
 *
 * - Completely free, no API key required.
 * - Usage policy: max 1 req/s, must display attribution.
 * - Returns structured address data including lat/lng.
 *
 * @see https://nominatim.org/release-docs/develop/api/Search/
 */

/** Structured result returned when the user picks an address. */
export interface AddressSelection {
  /** Full formatted address string. */
  displayName: string;
  /** Latitude as a number. */
  lat: number;
  /** Longitude as a number. */
  lng: number;
  /** Suburb / quarter / district extracted from the result. */
  district: string;
  /** Country extracted from the result. */
  country: string;
  /** Raw Nominatim address components (for advanced use). */
  raw: NominatimAddress;
}

interface AddressAutocompleteProps {
  /** Current text value of the input. */
  value: string;
  /** Called on every keystroke so the parent can track the raw text. */
  onChange: (value: string) => void;
  /** Called when the user selects an address from the dropdown. */
  onSelect: (selection: AddressSelection) => void;
  /** HTML id for the input element. */
  id?: string;
  /** Placeholder text. */
  placeholder?: string;
  /** Maximum character length. */
  maxLength?: number;
  /** Whether the input is disabled. */
  disabled?: boolean;
  /** Additional CSS classes for the wrapper div. */
  className?: string;
  /** Additional CSS classes for the input element. */
  inputClassName?: string;
  /** Whether the input is in an error state. */
  hasError?: boolean;
  /** Called when the input loses focus. */
  onBlur?: () => void;
  /**
   * Comma-separated ISO 3166-1 alpha-2 country codes to scope Nominatim
   * results (e.g., "hk,sg").  When empty, no country filtering is applied.
   */
  countryCodes?: string;
}

/** Minimum characters before we query Nominatim. */
const MIN_QUERY_LENGTH = 3;
/** Debounce delay in ms (Nominatim asks for max 1 req/s). */
const DEBOUNCE_MS = 400;

/**
 * Extract the best "district" string from a Nominatim address object.
 * Falls back through several fields that Nominatim may populate.
 */
function extractDistrict(addr: NominatimAddress): string {
  return (
    addr.suburb ||
    addr.quarter ||
    addr.city_district ||
    addr.neighbourhood ||
    addr.city ||
    addr.town ||
    addr.village ||
    ''
  );
}

export function AddressAutocomplete({
  value,
  onChange,
  onSelect,
  id,
  placeholder = 'Start typing an address...',
  maxLength,
  disabled,
  className = '',
  inputClassName = '',
  hasError = false,
  onBlur,
  countryCodes,
}: AddressAutocompleteProps) {
  const [suggestions, setSuggestions] = useState<NominatimResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);

  const wrapperRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  /** Tracks the latest request so stale responses are discarded. */
  const requestId = useRef(0);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        wrapperRef.current &&
        !wrapperRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const fetchSuggestions = useCallback(async (query: string) => {
    const currentRequestId = ++requestId.current;
    setIsLoading(true);
    try {
      const data = await searchAddress(query, {
        countryCodes,
        limit: 5,
      });
      // Only apply if this is still the latest request.
      if (currentRequestId === requestId.current) {
        setSuggestions(data);
        setIsOpen(data.length > 0);
        setActiveIndex(-1);
      }
    } catch {
      if (currentRequestId === requestId.current) {
        setSuggestions([]);
        setIsOpen(false);
      }
    } finally {
      if (currentRequestId === requestId.current) {
        setIsLoading(false);
      }
    }
  }, [countryCodes]);

  const handleInputChange = (newValue: string) => {
    onChange(newValue);

    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
    }

    if (newValue.trim().length < MIN_QUERY_LENGTH) {
      setSuggestions([]);
      setIsOpen(false);
      return;
    }

    debounceTimer.current = setTimeout(() => {
      fetchSuggestions(newValue.trim());
    }, DEBOUNCE_MS);
  };

  const handleSelect = (result: NominatimResult) => {
    const selection: AddressSelection = {
      displayName: result.display_name,
      lat: parseFloat(result.lat),
      lng: parseFloat(result.lon),
      district: extractDistrict(result.address),
      country: result.address.country || '',
      raw: result.address,
    };
    onChange(result.display_name);
    onSelect(selection);
    setIsOpen(false);
    setSuggestions([]);
    setActiveIndex(-1);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!isOpen || suggestions.length === 0) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setActiveIndex((prev) =>
          prev < suggestions.length - 1 ? prev + 1 : 0
        );
        break;
      case 'ArrowUp':
        e.preventDefault();
        setActiveIndex((prev) =>
          prev > 0 ? prev - 1 : suggestions.length - 1
        );
        break;
      case 'Enter':
        e.preventDefault();
        if (activeIndex >= 0 && activeIndex < suggestions.length) {
          handleSelect(suggestions[activeIndex]);
        }
        break;
      case 'Escape':
        setIsOpen(false);
        setActiveIndex(-1);
        break;
    }
  };

  // Clean up debounce timer on unmount.
  useEffect(() => {
    return () => {
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
      }
    };
  }, []);

  const listboxId = id ? `${id}-listbox` : 'address-listbox';

  return (
    <div ref={wrapperRef} className={`relative ${className}`}>
      <div className='relative'>
        <input
          ref={inputRef}
          id={id}
          type='text'
          role='combobox'
          aria-expanded={isOpen}
          aria-controls={listboxId}
          aria-activedescendant={
            activeIndex >= 0 ? `${listboxId}-option-${activeIndex}` : undefined
          }
          aria-autocomplete='list'
          autoComplete='off'
          value={value}
          onChange={(e) => handleInputChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => {
            if (suggestions.length > 0) setIsOpen(true);
          }}
          placeholder={placeholder}
          maxLength={maxLength}
          disabled={disabled}
          onBlur={onBlur}
          aria-invalid={hasError || undefined}
          className={
            'h-10 w-full rounded-md border border-slate-300 px-3 text-base ' +
            'text-slate-900 shadow-sm placeholder:text-slate-400 ' +
            'focus:border-slate-500 focus:outline-none focus:ring-1 ' +
            'focus:ring-slate-500 disabled:cursor-not-allowed ' +
            `disabled:bg-slate-100 sm:h-9 sm:text-sm ${inputClassName}`
          }
        />
        {isLoading && (
          <div className='pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3'>
            <SpinnerIcon className='h-4 w-4 animate-spin text-slate-400' />
          </div>
        )}
      </div>

      {isOpen && suggestions.length > 0 && (
        <ul
          id={listboxId}
          role='listbox'
          className={
            'absolute z-50 mt-1 max-h-60 w-full overflow-auto rounded-md border ' +
            'border-slate-200 bg-white py-1 shadow-lg'
          }
        >
          {suggestions.map((result, index) => (
            <li
              key={result.place_id}
              id={`${listboxId}-option-${index}`}
              role='option'
              aria-selected={index === activeIndex}
              className={
                'cursor-pointer px-3 py-2 text-sm ' +
                (index === activeIndex
                  ? 'bg-slate-100 text-slate-900'
                  : 'text-slate-700 hover:bg-slate-50')
              }
              onMouseDown={(e) => {
                // Prevent blur on the input before we can handle the click.
                e.preventDefault();
              }}
              onClick={() => handleSelect(result)}
              onMouseEnter={() => setActiveIndex(index)}
            >
              <span className='line-clamp-2'>{result.display_name}</span>
            </li>
          ))}
          <li className='px-3 py-1.5 text-xs text-slate-400' aria-hidden>
            Powered by{' '}
            <a
              href='https://www.openstreetmap.org/copyright'
              target='_blank'
              rel='noopener noreferrer'
              className='underline hover:text-slate-500'
            >
              OpenStreetMap
            </a>
          </li>
        </ul>
      )}
    </div>
  );
}
