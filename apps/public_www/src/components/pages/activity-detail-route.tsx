'use client';

import { useSearchParams } from 'next/navigation';

import type { Locale } from '@/content/locales';
import type { SiteContent } from '@/content/types';
import { ActivityDetailPage } from './activity-detail-page';

interface ActivityDetailRouteProps {
  readonly locale: Locale;
  readonly copy: SiteContent['activityDetail'];
}

export function ActivityDetailRoute({ locale, copy }: ActivityDetailRouteProps) {
  const searchParams = useSearchParams();
  const activityId = searchParams.get('id');

  if (!activityId) {
    return (
      <p className="mx-auto max-w-4xl px-4 py-16 text-center text-ink-700">
        {copy.notFoundLabel}
      </p>
    );
  }

  return (
    <ActivityDetailPage locale={locale} activityId={activityId} copy={copy} />
  );
}
