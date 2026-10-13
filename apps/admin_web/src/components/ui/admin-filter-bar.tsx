'use client';

import type { ReactNode } from 'react';

import { clsx } from 'clsx';

import { Label } from './label';

export interface AdminFilterBarProps {
  /** Filter fields (`AdminFilterField`), laid out in one wrapping row. */
  children?: ReactNode;
  className?: string;
}

/**
 * Filter row that sits at the top of a record table. Fields are left-aligned.
 * Create, sweep, and bulk buttons belong on the table `actions` row, not here.
 */
export function AdminFilterBar({ children, className }: AdminFilterBarProps) {
  if (children == null) {
    return null;
  }
  return (
    <div className={clsx('mb-3', className)} data-testid='admin-filter-bar'>
      <div className='flex min-w-0 flex-wrap items-end gap-3'>{children}</div>
    </div>
  );
}

export interface AdminFilterFieldProps {
  /** Visible title above the control. Omit when the control should stand alone. */
  label?: ReactNode;
  htmlFor?: string;
  children: ReactNode;
  /** Width class; defaults to a compact filter width that grows on wide screens. */
  className?: string;
}

export function AdminFilterField({ label, htmlFor, children, className }: AdminFilterFieldProps) {
  return (
    <div className={clsx('min-w-[10rem] flex-1 sm:flex-none sm:basis-48', className)}>
      {label ? <Label htmlFor={htmlFor}>{label}</Label> : null}
      {children}
    </div>
  );
}
