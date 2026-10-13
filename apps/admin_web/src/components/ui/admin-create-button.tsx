'use client';

import { clsx } from 'clsx';

import { Button } from './button';

export interface AdminCreateButtonProps {
  /** Visible label and accessible name, for example `New contact`. */
  label: string;
  onClick: () => void;
  disabled?: boolean;
  /** Set while the draft row is open so the control reads as toggled. */
  active?: boolean;
  className?: string;
}

/**
 * The create control that opens a draft row above a record table. It spells
 * out its label ("New contact", "New note") — no plus icon — and matches
 * `Button` `md` (`h-10` below `sm`, `h-9` from `sm`, `w-auto`).
 */
export function AdminCreateButton({ label, onClick, disabled, active, className }: AdminCreateButtonProps) {
  return (
    <Button
      type='button'
      aria-pressed={active ? true : undefined}
      disabled={disabled}
      onClick={onClick}
      data-testid='admin-create-button'
      className={clsx('w-auto shrink-0 whitespace-nowrap', className)}
    >
      {label}
    </Button>
  );
}
