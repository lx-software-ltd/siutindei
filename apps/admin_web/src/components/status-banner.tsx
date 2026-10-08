import type { ReactNode } from 'react';

const variantStyles = {
  info: 'border-blue-200 bg-blue-50 text-blue-900',
  error: 'border-red-200 bg-red-50 text-red-900',
  success: 'border-emerald-200 bg-emerald-50 text-emerald-900',
};

/** Fixed banner titles. Callers pass the body; the heading comes from `kind`. */
export type StatusBannerKind = 'error' | 'saved' | 'pending-review' | 'info';

type StatusBannerVariant = 'info' | 'error' | 'success';

const kindTitle: Record<StatusBannerKind, string> = {
  error: 'Error',
  saved: 'Saved',
  'pending-review': 'Pending review',
  info: 'Info',
};

const kindVariant: Record<StatusBannerKind, StatusBannerVariant> = {
  error: 'error',
  saved: 'success',
  'pending-review': 'info',
  info: 'info',
};

type StatusBannerBase = {
  children: ReactNode;
};

/**
 * `kind` sets the colour and the default heading. `title` overrides that
 * heading. The `variant` + `title` pair remains for the auth callback,
 * which cannot take `kind` from this change.
 */
export type StatusBannerProps = StatusBannerBase &
  (
    | { kind: StatusBannerKind; title?: string; variant?: never }
    | { title: string; variant: StatusBannerVariant; kind?: never }
  );

export function StatusBanner({
  variant,
  title,
  kind,
  children,
}: StatusBannerProps) {
  const resolvedVariant = kind ? kindVariant[kind] : variant;
  const heading = title ?? (kind ? kindTitle[kind] : '');

  return (
    <div
      className={`w-full rounded-lg border px-3 py-2.5 sm:px-4 sm:py-3 ${variantStyles[resolvedVariant]}`}
    >
      <p className='text-xs font-semibold sm:text-sm'>{heading}</p>
      <p className='mt-1 text-xs sm:text-sm'>{children}</p>
    </div>
  );
}
