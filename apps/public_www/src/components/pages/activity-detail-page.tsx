'use client';

import { useEffect, useMemo, useState } from 'react';

import type { Locale, SiteContent } from '@/content';
import { TrackedWhatsappLink } from '@/components/shared/tracked-whatsapp-link';
import { preloadActivityImage } from '@/lib/activity-image-preload';
import { logActivityLoadError } from '@/lib/activities/load-error';
import { fetchActivityListingById } from '@/lib/activities/search-client';
import {
  formatListingPrice,
  formatScheduleSnippet,
  listingImageUrl,
  listingOrgName,
  listingTitle,
  pickTranslation,
  regionLabelForListing,
} from '@/lib/activities/listing-utils';
import { rememberViewedActivity } from '@/lib/activities/recent-storage';
import type { ActivityListing } from '@/lib/activities/types';
import {
  LISTING_IMAGE_HEIGHT,
  LISTING_IMAGE_WIDTH,
} from '@/lib/listing-image';
import {
  itemFieldsFromListing,
  trackViewItem,
} from '@/lib/analytics/data-layer';
import { getSiteConfig } from '@/lib/site-config';

interface ActivityDetailPageProps {
  readonly locale: Locale;
  readonly activityId: string;
  readonly copy: SiteContent['activityDetail'];
}

function buildWhatsappHref(
  whatsappUrl: string | undefined,
  listing: ActivityListing,
  locale: Locale,
): string | null {
  if (!whatsappUrl) {
    return null;
  }
  const title = listingTitle(locale, listing);
  const message = encodeURIComponent(
    locale === 'zh-HK'
      ? `你好，我想查詢「${title}」的詳情。`
      : `Hi, I would like to ask about "${title}".`,
  );
  const separator = whatsappUrl.includes('?') ? '&' : '?';
  return `${whatsappUrl}${separator}text=${message}`;
}

export function ActivityDetailPage({
  locale,
  activityId,
  copy,
}: ActivityDetailPageProps) {
  const [listing, setListing] = useState<ActivityListing | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const { contact, siteName } = getSiteConfig();

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setErrorMessage(null);

    fetchActivityListingById(activityId)
      .then((item) => {
        if (cancelled) {
          return;
        }
        if (!item) {
          setErrorMessage(copy.notFoundLabel);
          setListing(null);
          return;
        }
        setListing(item);
        rememberViewedActivity(item.activity.id);
      })
      .catch((error: unknown) => {
        logActivityLoadError('activity detail', error);
        if (!cancelled) {
          setErrorMessage(copy.errorLabel);
          setListing(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activityId, copy.errorLabel, copy.notFoundLabel]);

  const imageUrl = listing ? listingImageUrl(listing) : null;

  useEffect(() => {
    if (!imageUrl) {
      return undefined;
    }
    return preloadActivityImage(imageUrl);
  }, [imageUrl]);

  const whatsappHref = useMemo(
    () => (listing ? buildWhatsappHref(contact.whatsappUrl, listing, locale) : null),
    [contact.whatsappUrl, listing, locale],
  );

  useEffect(() => {
    if (!listing) {
      return undefined;
    }
    const activityTitle = listingTitle(locale, listing);
    const activityDescription = pickTranslation(
      locale,
      listing.activity.description ?? '',
      listing.activity.descriptionTranslations,
    );
    const organizationName = listingOrgName(locale, listing);
    const structuredData = {
      '@context': 'https://schema.org',
      '@type': 'Course',
      name: activityTitle,
      description: activityDescription || undefined,
      provider: {
        '@type': 'Organization',
        name: organizationName,
      },
      offers: {
        '@type': 'Offer',
        price: listing.pricing.amount,
        priceCurrency: listing.pricing.currency,
      },
    };
    const script = document.createElement('script');
    script.type = 'application/ld+json';
    script.textContent = JSON.stringify(structuredData);
    document.head.appendChild(script);

    // The static export ships one generic /activity/ page; give each
    // activity a real tab/browser title once its data loads.
    const previousTitle = document.title;
    document.title = `${activityTitle} · ${siteName}`;

    return () => {
      document.head.removeChild(script);
      document.title = previousTitle;
    };
  }, [listing, locale, siteName]);

  useEffect(() => {
    if (!listing) {
      return;
    }
    trackViewItem(locale, listing);
  }, [listing, locale]);

  if (isLoading) {
    return (
      <p
        aria-live="polite"
        className="mx-auto max-w-4xl px-4 py-16 text-center text-ink-500"
      >
        {copy.loadingLabel}
      </p>
    );
  }

  if (!listing || errorMessage) {
    return (
      <p className="mx-auto max-w-4xl px-4 py-16 text-center text-red-700">
        {errorMessage ?? copy.notFoundLabel}
      </p>
    );
  }

  const title = listingTitle(locale, listing);
  const description = pickTranslation(
    locale,
    listing.activity.description ?? '',
    listing.activity.descriptionTranslations,
  );
  const orgName = listingOrgName(locale, listing);
  const region = regionLabelForListing(locale, listing);
  const schedule = formatScheduleSnippet(locale, listing.schedule.weeklyEntries);
  const price = formatListingPrice(locale, listing);

  return (
    <article className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="grid gap-8 lg:grid-cols-2">
        <div className="relative aspect-[4/3] overflow-hidden rounded-2xl bg-brand-100">
          {imageUrl ? (
            <img
              src={imageUrl}
              alt={title}
              width={LISTING_IMAGE_WIDTH}
              height={LISTING_IMAGE_HEIGHT}
              decoding="async"
              fetchPriority="high"
              className="h-full w-full object-cover"
            />
          ) : (
            <div className="flex h-full items-center justify-center px-6 text-center text-ink-500">
              {copy.imageFallbackLabel}
            </div>
          )}
        </div>
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-ink-500">
            {orgName}
          </p>
          <h1 className="mt-2 text-3xl font-bold text-ink-900 sm:text-4xl">
            {title}
          </h1>
          <p className="mt-3 text-lg font-semibold text-ink-900">{price}</p>
          <ul className="mt-4 space-y-2 text-sm text-ink-700">
            {region ? <li>{region}</li> : null}
            {listing.location.address ? <li>{listing.location.address}</li> : null}
            {schedule ? <li>{schedule}</li> : null}
            {listing.pricing.freeTrialClassOffered ? (
              <li>{copy.freeTrialLabel}</li>
            ) : null}
          </ul>
          {description ? (
            <p className="mt-6 leading-7 text-ink-700">{description}</p>
          ) : null}
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            {whatsappHref ? (
              <TrackedWhatsappLink
                href={whatsappHref}
                leadType="whatsapp_activity"
                item={itemFieldsFromListing(locale, listing)}
                locationId={listing.location.id}
                activityId={listing.activity.id}
                className={
                  'link-unadorned inline-flex min-h-11 w-full ' +
                  'items-center justify-center rounded-lg border ' +
                  'border-ink-900/20 bg-accent-500 px-4 text-sm ' +
                  'font-semibold text-ink-900 transition ' +
                  'hover:bg-accent-600 sm:w-auto'
                }
              >
                {copy.whatsappCtaLabel}
              </TrackedWhatsappLink>
            ) : null}
          </div>
        </div>
      </div>
    </article>
  );
}
