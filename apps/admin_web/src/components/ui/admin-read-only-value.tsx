import { useId, type ReactNode } from 'react';

import { clsx } from 'clsx';

const spanStyles = {
  1: null,
  2: 'sm:col-span-2',
  full: 'col-span-full',
} as const;

export interface AdminReadOnlyValueProps {
  label: string;
  children: ReactNode;
  /** Monospace value for ids, hashes, and other machine tokens. */
  mono?: boolean;
  /** Columns to span inside the parent grid. */
  span?: keyof typeof spanStyles;
  className?: string;
}

/**
 * Labelled read-only text for detail panels. The value is not a form
 * control, so long tokens wrap. The label matches `Label`.
 */
export function AdminReadOnlyValue({
  label,
  children,
  mono = false,
  span = 1,
  className,
}: AdminReadOnlyValueProps) {
  const labelId = useId();

  return (
    <div className={clsx('min-w-0 text-sm', spanStyles[span], className)}>
      <span
        id={labelId}
        className='mb-1 block text-sm font-medium text-slate-700'
      >
        {label}
      </span>
      <div
        aria-labelledby={labelId}
        className={
          mono
            ? 'wrap-anywhere font-mono text-xs text-slate-800'
            : 'text-slate-800'
        }
      >
        {children}
      </div>
    </div>
  );
}
