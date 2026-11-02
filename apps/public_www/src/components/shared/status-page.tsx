import Link from 'next/link';

import type { Locale } from '@/content/locales';
import { localizePath } from '@/lib/locale-routing';
import { ROUTES } from '@/lib/routes';

interface StatusPageCopy {
  readonly code: string;
  readonly title: string;
  readonly description: string;
}

interface StatusPageProps {
  readonly locale: Locale;
  readonly copy: StatusPageCopy;
  readonly homeLabel: string;
  readonly action?: {
    readonly label: string;
    readonly onClick: () => void;
  };
}

export function StatusPage({
  locale,
  copy,
  homeLabel,
  action,
}: StatusPageProps) {
  const homeHref = localizePath(ROUTES.home, locale);

  return (
    <div className="mx-auto flex max-w-md flex-col items-center px-4 py-16 text-center sm:py-24">
      <p className="text-sm font-semibold uppercase tracking-widest text-brand-500">
        {copy.code}
      </p>
      <h1 className="mt-4 text-2xl font-bold tracking-tight text-ink-900 sm:text-3xl">
        {copy.title}
      </h1>
      <p className="mt-3 text-base text-ink-700">{copy.description}</p>
      <div className="mt-8 flex flex-col gap-3 sm:flex-row">
        <Link
          href={homeHref}
          className="link-unadorned inline-flex min-h-11 items-center justify-center rounded-full bg-brand-500 px-5 py-2 font-semibold text-ink-900 transition hover:bg-brand-600"
        >
          {homeLabel}
        </Link>
        {action ? (
          <button
            type="button"
            onClick={action.onClick}
            className="inline-flex min-h-11 items-center justify-center rounded-full border border-brand-300 bg-white px-5 py-2 font-semibold text-brand-700 transition hover:bg-brand-50"
          >
            {action.label}
          </button>
        ) : null}
      </div>
    </div>
  );
}
