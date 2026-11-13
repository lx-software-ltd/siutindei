'use client';

import { createContext, useContext, useMemo, useSyncExternalStore, type ReactNode } from 'react';

import type { Locale } from '@/content/locales';
import { activityHref } from '@/lib/activities/activity-href';
import {
  getServerStaticActivityIds,
  getStaticActivityIds,
  subscribeStaticActivityIds,
} from '@/lib/activities/static-activity-ids';

const RenderedActivityIdsContext = createContext<ReadonlySet<string>>(new Set());

interface StaticActivityPagesProps {
  /** Ids the server knows were pre-rendered, so the HTML links to them. */
  readonly ids: readonly string[];
  readonly children: ReactNode;
}

export function StaticActivityPages({ ids, children }: StaticActivityPagesProps) {
  const parent = useContext(RenderedActivityIdsContext);
  const value = useMemo(() => new Set([...parent, ...ids]), [parent, ids]);
  return (
    <RenderedActivityIdsContext.Provider value={value}>{children}</RenderedActivityIdsContext.Provider>
  );
}

/** The static page when the build exported one, else the `?id=` page. */
export function useActivityHref(locale: Locale, activityId: string): string {
  const rendered = useContext(RenderedActivityIdsContext);
  const loaded = useSyncExternalStore(
    subscribeStaticActivityIds,
    getStaticActivityIds,
    getServerStaticActivityIds,
  );
  return activityHref(locale, activityId, rendered.has(activityId) || loaded.has(activityId));
}
