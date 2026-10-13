'use client';

import type { ButtonHTMLAttributes, ReactNode } from 'react';

import { clsx } from 'clsx';

export interface AdminTabItem<T extends string = string> {
  key: T;
  label: string;
}

/**
 * Sentence case for in-area tab labels: first word capital, later words
 * lower (`Feedback labels`, `API keys`). All-caps tokens such as API stay.
 */
export function formatAdminTabLabel(label: string): string {
  return label
    .trim()
    .split(/\s+/)
    .map((word, index) => {
      if (/^[A-Z0-9]{2,}$/.test(word)) {
        return word;
      }
      const lower = word.toLowerCase();
      if (index === 0) {
        return lower.charAt(0).toUpperCase() + lower.slice(1);
      }
      return lower;
    })
    .join(' ');
}

export interface AdminTabStripProps<T extends string> {
  items: readonly AdminTabItem<T>[];
  activeKey: T;
  onChange: (key: T) => void;
  'aria-label'?: string;
}

/**
 * In-area view switcher (button group, not ARIA tabs). The active control is
 * a white card with a uniform 1px `slate-300` border on all four sides; hover
 * previews the same white surface. On phones the controls fill the row two
 * per line so every view stays readable without horizontal scrolling.
 * Labels render in sentence case (first word capital, later words lower).
 */
export function AdminTabStrip<T extends string>({
  items,
  activeKey,
  onChange,
  'aria-label': ariaLabel,
}: AdminTabStripProps<T>) {
  return (
    <div
      className='grid grid-cols-2 gap-1 rounded-lg bg-slate-100 p-1 sm:inline-flex sm:flex-wrap'
      role='group'
      aria-label={ariaLabel ?? 'Section views'}
    >
      {items.map((item) => {
        const isActive = activeKey === item.key;
        return (
          <button
            key={item.key}
            type='button'
            aria-pressed={isActive}
            onClick={() => onChange(item.key)}
            className={clsx(
              'inline-flex h-9 w-full items-center justify-center rounded-md border px-3 text-sm font-semibold transition sm:w-auto',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400',
              isActive
                ? 'border-slate-300 bg-white text-slate-900 shadow-sm'
                : 'border-transparent text-slate-600 hover:border-slate-300 hover:bg-white hover:text-slate-900'
            )}
          >
            {formatAdminTabLabel(item.label)}
          </button>
        );
      })}
    </div>
  );
}

const toggleChipClassName = (pressed: boolean) =>
  clsx(
    'inline-flex h-8 items-center justify-center rounded-md border px-3 text-sm font-semibold transition',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400',
    pressed
      ? 'border-slate-300 bg-white text-slate-900 shadow-sm'
      : 'border-transparent bg-slate-100 text-slate-600 hover:border-slate-300 hover:bg-white hover:text-slate-900'
  );

export interface AdminToggleChipProps
  extends ButtonHTMLAttributes<HTMLButtonElement> {
  pressed: boolean;
  children: ReactNode;
}

/** Multi-select chip. Same surface as the active control in `AdminTabStrip`. */
export function AdminToggleChip({
  pressed,
  className,
  children,
  type = 'button',
  ...rest
}: AdminToggleChipProps) {
  return (
    <button
      type={type}
      aria-pressed={pressed}
      className={clsx(toggleChipClassName(pressed), className)}
      {...rest}
    >
      {children}
    </button>
  );
}
