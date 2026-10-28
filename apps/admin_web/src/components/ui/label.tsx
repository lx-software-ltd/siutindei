import type { LabelHTMLAttributes } from 'react';

export interface LabelProps
  extends LabelHTMLAttributes<HTMLLabelElement> {}

export function Label({ className = '', ...props }: LabelProps) {
  return (
    <label
      className={`mb-1 block text-sm font-semibold text-ink-900 ${className}`}
      {...props}
    />
  );
}
