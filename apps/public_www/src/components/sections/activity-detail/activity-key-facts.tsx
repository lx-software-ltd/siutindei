import type { ActivityDetailCopy } from './types';
import { DetailIcon, type DetailIconName } from './detail-icon';

export interface KeyFact {
  readonly id: 'ages' | 'when' | 'where' | 'price' | 'language';
  readonly icon: DetailIconName;
  readonly value: string | null;
  readonly detail?: string | null;
}

interface ActivityKeyFactsProps {
  readonly facts: readonly KeyFact[];
  readonly copy: ActivityDetailCopy;
  readonly enquiryHref: string | null;
  readonly compact?: boolean;
}

function labelFor(copy: ActivityDetailCopy, id: KeyFact['id']): string {
  return {
    ages: copy.agesLabel,
    when: copy.whenLabel,
    where: copy.whereLabel,
    price: copy.priceLabel,
    language: copy.languageLabel,
  }[id];
}

function missingFor(copy: ActivityDetailCopy, id: KeyFact['id']): string | null {
  return {
    ages: copy.askForAgesLabel,
    when: copy.askForTimesLabel,
    where: copy.askForPlaceLabel,
    price: copy.askForPriceLabel,
    language: null,
  }[id];
}

/** Labelled facts. A missing one is a quiet "ask" line, not a fake value. */
export function ActivityKeyFacts({
  facts,
  copy,
  enquiryHref,
  compact = false,
}: ActivityKeyFactsProps) {
  const shown = facts.filter((fact) => fact.value || missingFor(copy, fact.id));
  return (
    <dl
      aria-label={copy.keyFactsLabel}
      className={
        compact
          ? 'space-y-3'
          : 'grid gap-3 sm:grid-cols-2 short:grid-cols-2 xl:grid-cols-3'
      }
    >
      {shown.map((fact) => {
        const missing = missingFor(copy, fact.id);
        return (
          <div
            key={fact.id}
            data-fact={fact.id}
            className={
              compact
                ? 'flex gap-3'
                : 'flex gap-3 rounded-xl border border-brand-100 bg-brand-50/60 p-3'
            }
          >
            <DetailIcon name={fact.icon} className="mt-0.5 h-5 w-5" />
            <div className="min-w-0">
              <dt className="text-xs font-semibold uppercase tracking-wide text-ink-500">
                {labelFor(copy, fact.id)}
              </dt>
              <dd className="text-sm font-semibold text-ink-900">
                {fact.value ? (
                  fact.value
                ) : enquiryHref ? (
                  <a
                    href={enquiryHref}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="font-medium text-ink-500 underline decoration-dotted underline-offset-4"
                  >
                    {missing}
                  </a>
                ) : (
                  <span className="font-medium text-ink-500">{missing}</span>
                )}
              </dd>
              {fact.value && fact.detail ? (
                <dd className="text-xs text-ink-500">{fact.detail}</dd>
              ) : null}
            </div>
          </div>
        );
      })}
    </dl>
  );
}
