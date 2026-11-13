import type { CheckedFact } from '@/lib/activities/listing-facts';

import { DetailSection } from './detail-section';
import type { ActivityDetailCopy } from './types';

type FactLabels = ActivityDetailCopy['factLabels'];

function factText(labels: FactLabels, fact: CheckedFact): string | null {
  const entry = (labels as Readonly<Record<string, { present: string; absent: string }>>)[fact.key];
  if (!entry) {
    return null;
  }
  return fact.present ? entry.present : entry.absent;
}

/** What a parent saw on a visit. Nothing renders until a parent checked a fact. */
export function ActivityGoodToKnow({
  facts,
  copy,
}: {
  readonly facts: readonly CheckedFact[];
  readonly copy: ActivityDetailCopy;
}) {
  const rows = facts
    .map((fact) => ({ ...fact, text: factText(copy.factLabels, fact) }))
    .filter((row): row is CheckedFact & { text: string } => row.text !== null);
  if (rows.length === 0) {
    return null;
  }
  return (
    <DetailSection id="good-to-know" title={copy.goodToKnowHeading}>
      <p className="text-sm text-ink-500">{copy.goodToKnowHint}</p>
      <ul className="mt-3 grid gap-2 sm:grid-cols-2">
        {rows.map((row) => (
          <li
            key={row.key}
            data-fact={row.key}
            data-present={row.present}
            className="flex items-center gap-2 text-sm font-medium text-ink-900"
          >
            <span
              aria-hidden="true"
              className={
                'inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs ' +
                (row.present ? 'bg-leaf-500/20 text-ink-900' : 'bg-brand-100 text-ink-500')
              }
            >
              {row.present ? '✓' : '–'}
            </span>
            {row.text}
          </li>
        ))}
      </ul>
    </DetailSection>
  );
}
