import Link from 'next/link';

import { Skeleton } from '@/components/shared/ui/skeleton';

import type { ActivityDetailCopy } from './types';

export function ActivityDetailSkeleton({ copy }: { readonly copy: ActivityDetailCopy }) {
  return (
    <div className="mx-auto max-w-6xl px-4 pb-16 pt-4 sm:px-6 lg:px-8" aria-busy="true">
      <p className="sr-only" aria-live="polite">
        {copy.loadingLabel}
      </p>
      <Skeleton className="h-5 w-40" />
      <Skeleton className="mt-4 aspect-[4/3] w-full md:aspect-auto md:h-[420px]" />
      <div className="mt-6 grid gap-8 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-3">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-9 w-4/5" />
          <Skeleton className="h-5 w-1/2" />
          <div className="grid gap-3 pt-2 sm:grid-cols-2">
            {Array.from({ length: 4 }, (_, index) => (
              <Skeleton key={index} className="h-16 w-full" />
            ))}
          </div>
        </div>
        <Skeleton className="hidden h-80 w-full lg:block" />
      </div>
    </div>
  );
}

export function ActivityDetailEmpty({
  message,
  isError,
  searchHref,
  homeHref,
  copy,
}: {
  readonly message: string;
  readonly isError: boolean;
  readonly searchHref: string;
  readonly homeHref: string;
  readonly copy: ActivityDetailCopy;
}) {
  return (
    <div className="mx-auto max-w-xl px-4 py-16 text-center">
      <p
        role={isError ? 'alert' : undefined}
        className="text-lg font-semibold text-ink-900"
      >
        {message}
      </p>
      {isError ? null : <p className="mt-2 text-sm text-ink-500">{copy.notFoundHint}</p>}
      <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
        <Link
          href={searchHref}
          className="link-unadorned inline-flex min-h-11 items-center justify-center rounded-lg bg-accent-500 px-5 text-sm font-semibold text-ink-900 hover:bg-accent-600"
        >
          {copy.browseActivitiesLabel}
        </Link>
        <Link
          href={homeHref}
          className="link-unadorned inline-flex min-h-11 items-center justify-center rounded-lg border border-ink-900/15 px-5 text-sm font-semibold text-ink-900 hover:bg-brand-50"
        >
          {copy.goHomeLabel}
        </Link>
      </div>
    </div>
  );
}
