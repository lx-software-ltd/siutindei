'use client';

import type { SelectHTMLAttributes } from 'react';

export interface SelectProps
  extends SelectHTMLAttributes<HTMLSelectElement> {}

export function Select({ className = '', ...props }: SelectProps) {
  return (
    <select
      className={
        'h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-base ' +
        'text-slate-900 shadow-sm focus:border-slate-500 focus:outline-none ' +
        'focus:ring-1 focus:ring-slate-500 disabled:cursor-not-allowed ' +
        `disabled:bg-slate-100 sm:h-9 sm:text-sm ${className}`
      }
      {...props}
    />
  );
}
