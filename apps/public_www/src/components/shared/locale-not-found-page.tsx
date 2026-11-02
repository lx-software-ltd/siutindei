'use client';

import { usePathname } from 'next/navigation';

import { useChromeCopy } from '@/components/shared/chrome-copy';
import { StatusPage } from '@/components/shared/status-page';
import { getLocaleFromPath } from '@/lib/locale-routing';

export function LocaleNotFoundPage() {
  const pathname = usePathname();
  const locale = getLocaleFromPath(pathname ?? '/');
  const copy = useChromeCopy(locale);

  return (
    <StatusPage
      locale={locale}
      copy={copy.notFound}
      homeLabel={copy.notFound.homeLabel}
    />
  );
}
