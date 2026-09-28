import type { ReactNode } from 'react';
import { clsx } from 'clsx';

const sizeStyles = {
  sm: 'text-sm',
  xs: 'text-xs',
};

export interface AdminInlineErrorProps {
  children: ReactNode;
  className?: string;
  size?: keyof typeof sizeStyles;
  role?: 'alert' | 'status';
  id?: string;
}

export function AdminInlineError({
  children,
  className,
  size = 'sm',
  role = 'alert',
  id,
}: AdminInlineErrorProps) {
  return (
    <p id={id} role={role} className={clsx(sizeStyles[size], 'text-red-600', className)}>
      {children}
    </p>
  );
}
