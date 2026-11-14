'use client';

import { useSearchParams } from 'next/navigation';
import { useEffect } from 'react';

import type { Locale } from '@/content/locales';
import type { SiteContent } from '@/content/types';
import { ActivityDetailEmpty } from '@/components/sections/activity-detail/activity-detail-states';
import { staticActivityPath } from '@/lib/activities/activity-href';
import { loadStaticActivityIds } from '@/lib/activities/static-activity-ids';
import { ActivityDetailPage } from './activity-detail-page';

interface ActivityDetailRouteProps {
  readonly locale: Locale;
  readonly copy: SiteContent['activityDetail'];
  readonly landingTypeIds?: readonly string[];
}

export function ActivityDetailRoute({ locale, copy, landingTypeIds }: ActivityDetailRouteProps) {
  const searchParams = useSearchParams();
  const activityId = searchParams.get('id');

  useEffect(() => {
    if (!activityId) {
      return undefined;
    }
    let cancelled = false;
    void loadStaticActivityIds().then((ids) => {
      if (!cancelled && ids.has(activityId)) {
        window.location.replace(staticActivityPath(locale, activityId));
      }
    });
    return () => {
      cancelled = true;
    };
  }, [activityId, locale]);

  if (!activityId) {
    return <ActivityDetailEmpty locale={locale} reason="notFound" copy={copy} />;
  }

  return (
    <ActivityDetailPage
      locale={locale}
      activityId={activityId}
      copy={copy}
      landingTypeIds={landingTypeIds}
    />
  );
}
