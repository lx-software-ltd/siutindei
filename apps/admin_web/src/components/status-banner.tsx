import type { ReactNode } from 'react';

const variantStyles = {
  info: 'border-blue-200 bg-blue-50 text-blue-900',
  error: 'border-red-200 bg-red-50 text-red-900',
  success: 'border-emerald-200 bg-emerald-50 text-emerald-900',
};

/** Fixed banner titles. Callers pass the body; the heading comes from `kind`. */
export type StatusBannerKind = 'error' | 'saved' | 'pending-review' | 'info';

const kindTitle: Record<StatusBannerKind, string> = {
  error: 'Error',
  saved: 'Saved',
  'pending-review': 'Pending review',
  info: 'Info',
};

type StatusBannerBase = {
  variant: 'info' | 'error' | 'success';
  children: ReactNode;
};

export type StatusBannerProps = StatusBannerBase &
  (
    | { kind: StatusBannerKind; title?: never }
    | { title: string; kind?: never }
  );

export function StatusBanner({
  variant,
  title,
  kind,
  children,
}: StatusBannerProps) {
  const heading = kind ? kindTitle[kind] : title;

  return (
    <div
      className={`w-full rounded-lg border px-3 py-2.5 sm:px-4 sm:py-3 ${variantStyles[variant]}`}
    >
      <p className='text-xs font-semibold sm:text-sm'>{heading}</p>
      <p className='mt-1 text-xs sm:text-sm'>{children}</p>
    </div>
  );
}
