import type { Locale } from '@/content/locales';
import { listingLanguagesLabel } from '@/lib/activities/listing-facts';
import { formatDateRange } from '@/lib/activities/schedule-dates';
import {
  dayLabel,
  formatSessionTimes,
  hongKongSessions,
} from '@/lib/activities/schedule-format';
import type { ActivityListingVariant } from '@/lib/activities/types';
import { formatTemplate } from '@/lib/format-template';

import { DetailSection } from './detail-section';
import type { ActivityDetailCopy } from './types';

/** Upcoming dated sessions, one row per session with its days and times. */
export function ActivityDates({
  locale,
  sessions,
  languages,
  copy,
}: {
  readonly locale: Locale;
  readonly sessions: readonly ActivityListingVariant[];
  readonly languages: readonly string[];
  readonly copy: ActivityDetailCopy;
}) {
  const languagesLabel = listingLanguagesLabel(locale, languages);
  return (
    <DetailSection id="dates" title={copy.datesHeading}>
      <ul className="divide-y divide-brand-100 rounded-xl border border-brand-100">
        {sessions.map((session) => {
          const schedule = session.schedule;
          if (!schedule) {
            return null;
          }
          const times = hongKongSessions(schedule.weeklyEntries);
          return (
            <li
              key={`${schedule.startsOn}-${session.location.id}`}
              className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 px-4 py-3"
            >
              <span className="font-semibold text-ink-900">
                {formatDateRange(locale, schedule.startsOn, schedule.endsOn)}
              </span>
              <span className="flex flex-wrap gap-2">
                {times.map((time) => (
                  <span
                    key={`${time.day}-${time.startMinutes}-${time.endMinutes}`}
                    className="rounded-md bg-brand-50 px-2 py-1 text-sm tabular-nums text-ink-900"
                  >
                    {dayLabel(locale, time.day, 'short')} {formatSessionTimes(time)}
                  </span>
                ))}
              </span>
            </li>
          );
        })}
      </ul>
      {languagesLabel ? (
        <p className="mt-3 text-sm text-ink-700">
          {formatTemplate(copy.taughtInLabel, { languages: languagesLabel })}
        </p>
      ) : null}
    </DetailSection>
  );
}
