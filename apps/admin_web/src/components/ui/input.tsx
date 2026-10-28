'use client';

import type { InputHTMLAttributes } from 'react';

export interface InputProps
  extends InputHTMLAttributes<HTMLInputElement> {}

export function Input({ className = '', ...props }: InputProps) {
  return (
    <input
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
