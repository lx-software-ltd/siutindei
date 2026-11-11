import type { ButtonHTMLAttributes, ReactNode } from 'react';

interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  readonly children: ReactNode;
  readonly isSelected?: boolean;
}

export function Chip({
  children,
  isSelected = false,
  className = '',
  type = 'button',
  ...props
}: ChipProps) {
  const stateClassName = isSelected
    ? 'border-ink-900 bg-accent-500 text-ink-900'
    : 'border-ink-900/15 bg-white text-ink-700 hover:border-ink-900/30';

  return (
    <button
      type={type}
      className={
        'inline-flex min-h-11 shrink-0 items-center gap-2 rounded-full border ' +
        `px-4 py-2 text-sm font-medium transition ${stateClassName} ${className}`
      }
      {...props}
    >
      {children}
    </button>
  );
}
