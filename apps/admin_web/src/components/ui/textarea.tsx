'use client';

import type { TextareaHTMLAttributes } from 'react';

export interface TextareaProps
  extends TextareaHTMLAttributes<HTMLTextAreaElement> {}

export function Textarea({ className = '', ...props }: TextareaProps) {
  return (
    <textarea
      className={
        'w-full rounded-md border border-slate-300 bg-white px-3 py-2.5 text-base ' +
        'text-slate-900 shadow-sm focus:border-slate-500 focus:outline-none ' +
        'focus:ring-1 focus:ring-slate-500 disabled:cursor-not-allowed ' +
        `disabled:bg-slate-100 sm:py-2 sm:text-sm ${className}`
      }
      {...props}
    />
  );
}
