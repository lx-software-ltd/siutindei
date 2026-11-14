import type { Locale } from '@/content/locales';
import { localizePath } from '@/lib/locale-routing';
import { ROUTES } from '@/lib/routes';

/** The pre-rendered page of an activity in the build's catalogue. */
export function staticActivityPath(locale: Locale, activityId: string): string {
  return localizePath(`${ROUTES.activity}/${encodeURIComponent(activityId)}`, locale);
}

/** The client-rendered page that works for any activity id. */
export function dynamicActivityHref(locale: Locale, activityId: string): string {
  return `${localizePath(ROUTES.activity, locale)}?id=${encodeURIComponent(activityId)}`;
}

export function activityHref(
  locale: Locale,
  activityId: string,
  hasStaticPage: boolean,
): string {
  return hasStaticPage
    ? staticActivityPath(locale, activityId)
    : dynamicActivityHref(locale, activityId);
}

export function categoryLandingPath(locale: Locale, activityTypeId: string): string {
  return localizePath(`${ROUTES.activities}/${activityTypeId}`, locale);
}
