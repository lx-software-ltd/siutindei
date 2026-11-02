'use client';

import { usePathname } from 'next/navigation';

import { useChromeCopy } from '@/components/shared/chrome-copy';
import { getLocaleFromPath, localizePath } from '@/lib/locale-routing';
import { ROUTES } from '@/lib/routes';

interface MinimalStatusChromeProps {
  readonly variant: 'notFound' | 'serverError';
  readonly onRetry?: () => void;
}

export function MinimalStatusChrome({
  variant,
  onRetry,
}: MinimalStatusChromeProps) {
  const pathname = usePathname();
  const locale = getLocaleFromPath(pathname ?? '/');
  const copy = useChromeCopy(locale);
  const status = variant === 'notFound' ? copy.notFound : copy.serverError;
  const homeHref = localizePath(ROUTES.home, locale);

  return (
    <main
      id="main-content"
      className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center px-6 py-16 text-center"
    >
      <img
        src="/images/brand/siutindei-logo-mark.svg"
        alt=""
        width={64}
        height={64}
      />
      <h1 className="mt-6 text-2xl font-bold text-ink-900">{status.title}</h1>
      <p className="mt-3 text-base text-ink-700">{status.description}</p>
      <a
        href={homeHref}
        className="link-unadorned mt-8 inline-flex min-h-11 items-center rounded-full bg-brand-500 px-5 py-2 font-semibold text-ink-900"
      >
        {copy.notFound.homeLabel}
      </a>
      {variant === 'serverError' && onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 text-sm font-semibold text-ink-700 underline"
        >
          {copy.serverError.retryLabel}
        </button>
      ) : null}
    </main>
  );
}
