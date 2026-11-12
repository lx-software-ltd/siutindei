import type { Locale } from '@/content/locales';
import { listingLanguagesLabel } from '@/lib/activities/listing-facts';
import {
  dayLabel,
  formatSessionTimes,
  hongKongSessions,
  sessionsByDay,
} from '@/lib/activities/schedule-format';
import type { WeeklyScheduleEntry } from '@/lib/activities/types';
import { formatTemplate } from '@/lib/format-template';

import { DetailSection } from './detail-section';
import type { ActivityDetailCopy } from './types';

export function ActivitySchedule({
  locale,
  entries,
  languages,
  copy,
}: {
  readonly locale: Locale;
  readonly entries: readonly WeeklyScheduleEntry[];
  readonly languages: readonly string[];
  readonly copy: ActivityDetailCopy;
}) {
  const days = sessionsByDay(hongKongSessions(entries));
  const languagesLabel = listingLanguagesLabel(locale, languages);
  return (
    <DetailSection id="schedule" title={copy.scheduleHeading}>
      {days.length === 0 ? (
        <p className="text-sm text-ink-500">{copy.scheduleMissingLabel}</p>
      ) : (
        <>
          <ul className="divide-y divide-brand-100 rounded-xl border border-brand-100">
            {days.map((group) => (
              <li
                key={group.day}
                className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 px-4 py-3"
              >
                <span className="font-semibold text-ink-900">
                  {dayLabel(locale, group.day, 'long')}
                </span>
                <span className="flex flex-wrap gap-2">
                  {group.sessions.map((session) => (
                    <span
                      key={`${session.startMinutes}-${session.endMinutes}`}
                      className="rounded-md bg-brand-50 px-2 py-1 text-sm tabular-nums text-ink-900"
                    >
                      {formatSessionTimes(session)}
                    </span>
                  ))}
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-ink-500">{copy.scheduleTimeZoneNote}</p>
        </>
      )}
      {languagesLabel ? (
        <p className="mt-3 text-sm text-ink-700">
          {formatTemplate(copy.taughtInLabel, { languages: languagesLabel })}
        </p>
      ) : null}
    </DetailSection>
  );
}
