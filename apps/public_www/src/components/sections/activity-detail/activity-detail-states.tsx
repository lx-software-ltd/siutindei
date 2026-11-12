import Link from 'next/link';

import { Skeleton } from '@/components/shared/ui/skeleton';
import type { Locale } from '@/content/locales';
import { buildSearchPageHref } from '@/lib/activities/map-search-url';
import { DEFAULT_SEARCH_FILTERS } from '@/lib/activities/search-params';
import { localizePath } from '@/lib/locale-routing';
import { ROUTES } from '@/lib/routes';

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

export type ActivityDetailEmptyReason = 'notFound' | 'error';

const HIDE_AND_SEEK_WIDTH = 240;
const HIDE_AND_SEEK_HEIGHT = 220;

/** A bao hiding in a dim sum steamer. The lid is its own layer so CSS can lift it. */
function HideAndSeekSteamer() {
  return (
    <div className="hide-and-seek relative w-48 shrink-0 sm:w-60 short:w-44" aria-hidden="true">
      <img
        src="/images/small-world/hide-and-seek-steamer.svg"
        alt=""
        width={HIDE_AND_SEEK_WIDTH}
        height={HIDE_AND_SEEK_HEIGHT}
        className="block h-auto w-full"
      />
      <img
        src="/images/small-world/hide-and-seek-lid.svg"
        alt=""
        width={HIDE_AND_SEEK_WIDTH}
        height={HIDE_AND_SEEK_HEIGHT}
        className="hide-and-seek__lid absolute inset-0 h-full w-full"
      />
    </div>
  );
}

export function ActivityDetailEmpty({
  locale,
  reason,
  copy,
}: {
  readonly locale: Locale;
  readonly reason: ActivityDetailEmptyReason;
  readonly copy: ActivityDetailCopy;
}) {
  const isError = reason === 'error';
  const searchHref = buildSearchPageHref(locale, DEFAULT_SEARCH_FILTERS, { view: 'list' });
  const homeHref = localizePath(ROUTES.home, locale);

  return (
    <div className="mx-auto flex max-w-xl flex-col items-center px-4 py-12 text-center sm:py-16 short:max-w-3xl short:flex-row short:justify-center short:gap-8 short:py-6 short:text-left">
      <HideAndSeekSteamer />
      <div className="mt-6 w-full short:mt-0 short:w-auto">
        <div role={isError ? 'alert' : undefined}>
          <h1 className="text-balance text-2xl font-bold tracking-tight text-ink-900 sm:text-3xl">
            {isError ? copy.errorLabel : copy.notFoundLabel}
          </h1>
          <p className="mt-3 text-pretty text-base text-ink-700">
            {isError ? copy.errorHint : copy.notFoundHint}
          </p>
        </div>
        <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row short:mt-4 short:justify-start">
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
    </div>
  );
}
