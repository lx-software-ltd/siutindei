'use client';

import { usePathname } from 'next/navigation';

import { useChromeCopy } from '@/components/shared/chrome-copy';
import { StatusPage } from '@/components/shared/status-page';
import { getLocaleFromPath } from '@/lib/locale-routing';

interface LocaleErrorPageProps {
  readonly reset: () => void;
}

export function LocaleErrorPage({ reset }: LocaleErrorPageProps) {
  const pathname = usePathname();
  const locale = getLocaleFromPath(pathname ?? '/');
  const copy = useChromeCopy(locale);

  return (
    <StatusPage
      locale={locale}
      copy={copy.serverError}
      homeLabel={copy.notFound.homeLabel}
      action={{
        label: copy.serverError.retryLabel,
        onClick: reset,
      }}
    />
  );
}
