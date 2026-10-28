'use client';

import type { ButtonHTMLAttributes } from 'react';

import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

import { SpinnerIcon } from '@/components/icons/action-icons';

const baseStyles =
  'inline-flex items-center justify-center rounded-lg border text-sm ' +
  'font-semibold transition ' +
  'disabled:cursor-not-allowed disabled:opacity-60';

const brandStyles =
  'border-ink-900/20 bg-accent-500 text-ink-900 hover:bg-accent-600';

const surfaceStyles =
  'border-ink-900/15 bg-white text-ink-900 hover:bg-brand-50';

const variantStyles = {
  primary: brandStyles,
  secondary: surfaceStyles,
  outline: surfaceStyles,
  brand: brandStyles,
  ghost: 'border-transparent text-ink-700 hover:bg-brand-50',
  danger: 'border-red-600 bg-red-600 text-white hover:bg-red-500',
  success: 'border-emerald-600 bg-emerald-600 text-white hover:bg-emerald-500',
};

export const BUTTON_DEFAULT_LOADING_LABEL = 'Saving…';

const sizeStyles = {
  sm: 'h-8 px-3',
  md: 'h-10 px-4 sm:h-9',
  lg: 'h-10 px-5',
};

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof variantStyles;
  size?: keyof typeof sizeStyles;
  /**
   * In-flight API call triggered by this button. The button becomes disabled
   * and swaps its content for a spinner plus `loadingLabel` (default
   * "Saving…").
   */
  loading?: boolean;
  loadingLabel?: string;
}

export function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  loading = false,
  loadingLabel = BUTTON_DEFAULT_LOADING_LABEL,
  disabled,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={twMerge(
        clsx(baseStyles, variantStyles[variant], sizeStyles[size]),
        className
      )}
      disabled={disabled || loading}
      aria-busy={loading ? true : undefined}
      data-loading={loading ? 'true' : undefined}
      {...props}
    >
      {loading ? (
        <span className='inline-flex items-center gap-2'>
          <SpinnerIcon className='h-4 w-4 shrink-0 animate-spin' />
          {loadingLabel}
        </span>
      ) : (
        children
      )}
    </button>
  );
}
