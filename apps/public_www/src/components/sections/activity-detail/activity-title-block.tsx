import type { ReactNode } from 'react';

import type { ActivityDetailCopy } from './types';
import { RatingStars } from './rating-stars';
import type { FeedbackRating } from '@/lib/activities/types';
import { formatTemplate } from '@/lib/format-template';

interface ActivityTitleBlockProps {
  readonly title: string;
  readonly categoryLabel: string | null;
  readonly categoryIconSrc: string | null;
  readonly organiserName: string;
  readonly organiserLogoUrl: string | null;
  readonly isTemporarilyClosed: boolean;
  readonly hasFreeTrial: boolean;
  readonly isParentVerified: boolean;
  readonly rating: FeedbackRating | null;
  readonly copy: ActivityDetailCopy;
  readonly actions?: ReactNode;
}

function Badge({
  tone,
  children,
}: {
  readonly tone: 'warn' | 'good' | 'plain';
  readonly children: ReactNode;
}) {
  const toneClassName = {
    warn: 'bg-amber-100 text-amber-900',
    good: 'bg-leaf-500/20 text-ink-900',
    plain: 'bg-brand-100 text-ink-900',
  }[tone];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold ${toneClassName}`}
    >
      {children}
    </span>
  );
}

export function ratingText(copy: ActivityDetailCopy, rating: FeedbackRating): string {
  const template = rating.count === 1 ? copy.ratingSingleLabel : copy.ratingSummaryLabel;
  return formatTemplate(template, {
    average: rating.averageStars.toFixed(1),
    count: rating.count,
  });
}

export function ActivityTitleBlock({
  title,
  categoryLabel,
  categoryIconSrc,
  organiserName,
  organiserLogoUrl,
  isTemporarilyClosed,
  hasFreeTrial,
  isParentVerified,
  rating,
  copy,
  actions,
}: ActivityTitleBlockProps) {
  const hasBadges = isTemporarilyClosed || hasFreeTrial || isParentVerified;
  return (
    <header className="space-y-3 short:space-y-2">
      {categoryLabel ? (
        <p className="inline-flex items-center gap-2 rounded-full bg-brand-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-ink-700 short:hidden">
          {categoryIconSrc ? (
            <img src={categoryIconSrc} alt="" width={18} height={18} aria-hidden="true" className="h-[18px] w-[18px] object-contain" />
          ) : null}
          {categoryLabel}
        </p>
      ) : null}
      <h1 className="text-2xl font-bold leading-tight text-ink-900 sm:text-4xl short:text-xl">
        {title}
      </h1>
      <p className="flex items-center gap-2 text-base font-medium text-ink-700 short:text-sm">
        {organiserLogoUrl ? (
          <img
            src={organiserLogoUrl}
            alt=""
            width={32}
            height={32}
            aria-hidden="true"
            className="h-8 w-8 rounded-full border border-brand-100 bg-white object-contain"
          />
        ) : null}
        <a href="#organiser" className="hover:underline">
          {organiserName}
        </a>
      </p>
      {rating ? (
        <p className="flex items-center gap-2 text-sm text-ink-700">
          <RatingStars stars={rating.averageStars} />
          <a href="#reviews" className="hover:underline">
            {ratingText(copy, rating)}
          </a>
        </p>
      ) : null}
      {hasBadges ? (
        <p className="flex flex-wrap gap-2">
          {isTemporarilyClosed ? <Badge tone="warn">{copy.temporarilyClosedLabel}</Badge> : null}
          {hasFreeTrial ? <Badge tone="plain">{copy.freeTrialLabel}</Badge> : null}
          {isParentVerified ? (
            <Badge tone="good">
              <img
                src="/images/brand/parent-verified.svg"
                alt=""
                width={14}
                height={14}
                aria-hidden="true"
              />
              {copy.parentVerifiedLabel}
            </Badge>
          ) : null}
        </p>
      ) : null}
      {isParentVerified ? (
        <p className="text-sm text-ink-700 short:hidden">{copy.parentVerifiedExplainer}</p>
      ) : null}
      {actions}
    </header>
  );
}
