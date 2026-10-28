'use client';

import type { TextareaHTMLAttributes } from 'react';

import { twMerge } from 'tailwind-merge';

export interface TextareaProps
  extends TextareaHTMLAttributes<HTMLTextAreaElement> {}

const fieldClassName =
  'w-full rounded-md border border-ink-900/15 bg-white px-3 py-2.5 text-base ' +
  'text-ink-900 shadow-sm focus:border-brand-700 focus:outline-none ' +
  'focus:ring-1 focus:ring-brand-700 disabled:cursor-not-allowed ' +
  'disabled:bg-brand-50 sm:py-2 sm:text-sm';

export function Textarea({ className = '', ...props }: TextareaProps) {
  return (
    <textarea className={twMerge(fieldClassName, className)} {...props} />
  );
}
