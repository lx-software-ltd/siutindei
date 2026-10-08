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

function textValue(children: ReactNode): string | null {
  if (typeof children === 'string' || typeof children === 'number') {
    return String(children);
  }
  return null;
}

/**
 * Labelled read-only value for detail panels (audit logs, issued
 * certificates). Sits inside `AdminFieldGrid` next to editable fields.
 * Text values stay associated with the label so assistive tech and
 * tests can address them by name.
 */
export function AdminReadOnlyValue({
  label,
  children,
  mono = false,
  span = 1,
  className,
}: AdminReadOnlyValueProps) {
  const valueId = useId();
  const value = textValue(children);
  const isMultiline = value?.includes('\n') ?? false;
  const valueClassName = clsx(
    'mt-1 w-full border-0 bg-transparent p-0 text-slate-800 focus:outline-none',
    mono ? 'font-mono text-xs wrap-anywhere' : undefined
  );

  return (
    <div className={clsx('min-w-0 text-sm', spanStyles[span], className)}>
      <label
        htmlFor={valueId}
        className='block text-xs font-medium text-slate-500'
      >
        {label}
      </label>
      {value === null ? (
        <div id={valueId} className={valueClassName}>
          {children}
        </div>
      ) : isMultiline ? (
        <textarea
          id={valueId}
          readOnly
          rows={Math.min(8, value.split('\n').length)}
          value={value}
          className={clsx(valueClassName, 'resize-none')}
        />
      ) : (
        <input id={valueId} readOnly value={value} className={valueClassName} />
      )}
    </div>
  );
}
