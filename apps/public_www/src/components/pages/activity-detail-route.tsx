'use client';

import { useSearchParams } from 'next/navigation';

import type { Locale } from '@/content/locales';
import type { SiteContent } from '@/content/types';
import { ActivityDetailEmpty } from '@/components/sections/activity-detail/activity-detail-states';
import { ActivityDetailPage } from './activity-detail-page';

interface ActivityDetailRouteProps {
  readonly locale: Locale;
  readonly copy: SiteContent['activityDetail'];
}

export function ActivityDetailRoute({ locale, copy }: ActivityDetailRouteProps) {
  const searchParams = useSearchParams();
  const activityId = searchParams.get('id');

  if (!activityId) {
    return <ActivityDetailEmpty locale={locale} reason="notFound" copy={copy} />;
  }

  return (
    <ActivityDetailPage locale={locale} activityId={activityId} copy={copy} />
  );
}
