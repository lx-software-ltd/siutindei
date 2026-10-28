'use client';

import type { InputHTMLAttributes } from 'react';

import { twMerge } from 'tailwind-merge';

export interface InputProps
  extends InputHTMLAttributes<HTMLInputElement> {}

const fieldClassName =
  'h-10 w-full rounded-md border border-ink-900/15 bg-white px-3 text-base ' +
  'text-ink-900 shadow-sm focus:border-brand-700 focus:outline-none ' +
  'focus:ring-1 focus:ring-brand-700 disabled:cursor-not-allowed ' +
  'disabled:bg-brand-50 sm:h-9 sm:text-sm';

export function Input({ className = '', ...props }: InputProps) {
  return <input className={twMerge(fieldClassName, className)} {...props} />;
}
