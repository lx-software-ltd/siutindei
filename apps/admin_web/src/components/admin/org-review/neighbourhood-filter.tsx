'use client';

import { useEffect, useId, useMemo, useRef, useState } from 'react';

import type { NeighbourhoodFilterOption } from '../../../lib/neighbourhood-options';
import { Input } from '../../ui/input';

interface NeighbourhoodFilterProps {
  id: string;
  value: string;
  /** Name of `value` when it is a region or district, so it can appear in the list. */
  valueName?: string;
  options: readonly NeighbourhoodFilterOption[];
  onChange: (areaId: string) => void;
}

export function NeighbourhoodFilter({
  id,
  value,
  valueName = '',
  options,
  onChange,
}: NeighbourhoodFilterProps) {
  const listboxId = useId();
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const listed = useMemo(() => {
    if (!value || !valueName || options.some((option) => option.id === value)) {
      return options;
    }
    return [{ id: value, name: valueName, group: '' }, ...options];
  }, [options, value, valueName]);
  const selected = listed.find((option) => option.id === value) ?? null;

  const matches = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) {
      return listed;
    }
    return listed.filter((option) => {
      const name = option.name.toLowerCase();
      const group = option.group.toLowerCase();
      return name.includes(needle) || group.includes(needle);
    });
  }, [listed, query]);

  const choices = useMemo(
    () => [{ id: '', name: 'All neighbourhoods', group: '' }, ...matches],
    [matches]
  );

  useEffect(() => {
    if (!open) {
      return;
    }
    function onPointerDown(event: MouseEvent) {
      if (!wrapperRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', onPointerDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
    };
  }, [open]);

  let closedLabel = '';
  if (selected) {
    closedLabel = selected.name;
  } else if (value) {
    closedLabel = valueName;
  }
  const inputValue = open ? query : closedLabel;

  function choose(areaId: string) {
    onChange(areaId);
    setQuery('');
    setOpen(false);
  }

  return (
    <div ref={wrapperRef} className='relative'>
      <Input
        id={id}
        role='combobox'
        aria-expanded={open}
        aria-controls={listboxId}
        aria-autocomplete='list'
        aria-label='Neighbourhood'
        autoComplete='off'
        placeholder='All neighbourhoods'
        value={inputValue}
        onFocus={() => {
          setQuery('');
          setActiveIndex(0);
          setOpen(true);
        }}
        onClick={() => {
          setQuery('');
          setActiveIndex(0);
          setOpen(true);
        }}
        onChange={(event) => {
          setQuery(event.target.value);
          setActiveIndex(0);
          setOpen(true);
        }}
        onKeyDown={(event) => {
          if (event.key === 'ArrowDown') {
            event.preventDefault();
            setOpen(true);
            setActiveIndex((index) => Math.min(index + 1, choices.length - 1));
          } else if (event.key === 'ArrowUp') {
            event.preventDefault();
            setActiveIndex((index) => Math.max(index - 1, 0));
          } else if (event.key === 'Enter' && open) {
            event.preventDefault();
            const choice = choices[activeIndex];
            if (choice) {
              choose(choice.id);
            }
          } else if (event.key === 'Escape') {
            setOpen(false);
            setQuery('');
          }
        }}
      />
      {open ? (
        <ul
          id={listboxId}
          role='listbox'
          className='absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-md border border-brand-100 bg-white py-1 shadow-lg'
        >
          {choices.length === 0 ? (
            <li className='px-3 py-2 text-sm text-ink-500'>No neighbourhoods</li>
          ) : (
            choices.map((option, index) => (
              <li key={option.id || 'all'} role='presentation'>
                <button
                  type='button'
                  role='option'
                  aria-selected={option.id === value}
                  className={
                    index === activeIndex
                      ? 'flex w-full items-baseline gap-2 bg-brand-50 px-3 py-2 text-left text-sm text-ink-900'
                      : 'flex w-full items-baseline gap-2 px-3 py-2 text-left text-sm text-ink-900 hover:bg-brand-50'
                  }
                  onMouseDown={(event) => {
                    event.preventDefault();
                  }}
                  onMouseEnter={() => setActiveIndex(index)}
                  onClick={() => choose(option.id)}
                >
                  <span>{option.name}</span>
                  {option.group ? (
                    <span className='text-xs text-ink-500'>{option.group}</span>
                  ) : null}
                </button>
              </li>
            ))
          )}
        </ul>
      ) : null}
    </div>
  );
}
