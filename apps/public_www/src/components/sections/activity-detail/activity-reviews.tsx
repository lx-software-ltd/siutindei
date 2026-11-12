import type { Locale } from '@/content/locales';
import { pickTranslation } from '@/lib/activities/listing-utils';
import type { FeedbackRating, FeedbackReview } from '@/lib/activities/types';
import { formatTemplate } from '@/lib/format-template';

import { ratingText } from './activity-title-block';
import { DetailSection } from './detail-section';
import { RatingStars } from './rating-stars';
import type { ActivityDetailCopy } from './types';

function formatReviewDate(locale: Locale, value: string): string | null {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return new Intl.DateTimeFormat(locale === 'zh-HK' ? 'zh-HK' : 'en-GB', {
    month: 'short',
    year: 'numeric',
    timeZone: 'Asia/Hong_Kong',
  }).format(date);
}

export function ActivityReviews({
  locale,
  rating,
  reviews,
  copy,
}: {
  readonly locale: Locale;
  readonly rating: FeedbackRating | null;
  readonly reviews: readonly FeedbackReview[];
  readonly copy: ActivityDetailCopy;
}) {
  if (!rating && reviews.length === 0) {
    return null;
  }
  return (
    <DetailSection id="reviews" title={copy.reviewsHeading}>
      {rating ? (
        <p className="flex flex-wrap items-center gap-3">
          <span className="text-3xl font-bold text-ink-900">
            {rating.averageStars.toFixed(1)}
          </span>
          <RatingStars stars={rating.averageStars} className="h-5 w-5" />
          <span className="text-sm text-ink-700">{ratingText(copy, rating)}</span>
        </p>
      ) : null}
      {reviews.length > 0 ? (
        <ul className="mt-4 space-y-3">
          {reviews.map((review) => {
            const date = formatReviewDate(locale, review.createdAt);
            return (
              <li key={review.id} className="rounded-xl border border-brand-100 p-4">
                <p className="flex flex-wrap items-center gap-2">
                  <RatingStars stars={review.stars} />
                  <span className="sr-only">
                    {formatTemplate(copy.starsLabel, { stars: review.stars })}
                  </span>
                  {date ? <span className="text-xs text-ink-500">{date}</span> : null}
                </p>
                {review.labels.length > 0 ? (
                  <ul className="mt-2 flex flex-wrap gap-1.5">
                    {review.labels.map((label) => (
                      <li
                        key={label.id}
                        className="rounded-full bg-brand-50 px-2.5 py-0.5 text-xs font-medium text-ink-700"
                      >
                        {pickTranslation(locale, label.name, label.nameTranslations)}
                      </li>
                    ))}
                  </ul>
                ) : null}
                {review.description ? (
                  <p className="mt-2 whitespace-pre-line text-sm leading-6 text-ink-700">
                    {review.description}
                  </p>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}
    </DetailSection>
  );
}
