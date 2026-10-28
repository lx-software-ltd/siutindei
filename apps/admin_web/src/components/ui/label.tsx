import type { LabelHTMLAttributes } from 'react';

import { twMerge } from 'tailwind-merge';

export interface LabelProps
  extends LabelHTMLAttributes<HTMLLabelElement> {}

export function Label({ className = '', ...props }: LabelProps) {
  return (
    <label
      className={twMerge(
        'mb-1 block text-sm font-semibold text-slate-700',
        className
      )}
      {...props}
    />
  );
}
