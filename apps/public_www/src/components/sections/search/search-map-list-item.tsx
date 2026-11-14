'use client';

import Link from 'next/link';
import { useState } from 'react';

import type { Locale } from '@/content/locales';
import {
  listingCardRules,
  listingFactsLine,
  listingMetaLine,
} from '@/components/sections/listings/listing-card';
import { useActivityHref } from '@/components/shared/static-activity-pages';
import type { ActivityListing } from '@/lib/activities/types';
import { listingAgeLabel } from '@/lib/activities/listing-facts';
import { listingImageUrl, listingTitle } from '@/lib/activities/listing-utils';
import { formatListingPriceSummary } from '@/lib/activities/price-format';
import { iconSrcForListing } from '@/lib/home-wizard/choice-icons';
import { LISTING_IMAGE_HEIGHT, LISTING_IMAGE_WIDTH } from '@/lib/listing-image';

export interface SearchMapListItemLabels {
  readonly imageFallback: string;
  readonly view: string;
  readonly locationsCount: string;
  readonly detailsOnRequest: string;
}

interface SearchMapListItemBase {
  readonly locale: Locale;
  readonly listing: ActivityListing;
  readonly labels: SearchMapListItemLabels;
  readonly className?: string;
}

interface SearchMapSelectItemProps extends SearchMapListItemBase {
  readonly kind: 'select';
  readonly isSelected: boolean;
  readonly onSelect: () => void;
}

interface SearchMapSummaryItemProps extends SearchMapListItemBase {
  readonly kind: 'summary';
  /** Marks the card whose pin is selected on the map. */
  readonly isSelected?: boolean;
  /** Phones swap the View pill for a chevron, so the title keeps the width. */
  readonly compact?: boolean;
}

export type SearchMapListItemProps = SearchMapSelectItemProps | SearchMapSummaryItemProps;

function Thumbnail({ listing, title }: { readonly listing: ActivityListing; readonly title: string }) {
  const imageUrl = listingImageUrl(listing);
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const showImage = imageUrl !== null && imageUrl !== failedUrl;
  return (
    <div className="relative h-20 w-20 shrink-0 overflow-hidden rounded-lg bg-brand-100">
      {showImage ? (
        <img
          src={imageUrl}
          alt={title}
          width={LISTING_IMAGE_WIDTH}
          height={LISTING_IMAGE_HEIGHT}
          loading="lazy"
          decoding="async"
          onError={() => setFailedUrl(imageUrl)}
          className="h-full w-full object-cover"
        />
      ) : (
        <span className="flex h-full items-center justify-center">
          <img
            src={iconSrcForListing(listing.activity)}
            alt=""
            width={40}
            height={40}
            aria-hidden="true"
            className="h-10 w-10 object-contain opacity-80"
          />
        </span>
      )}
    </div>
  );
}

function SummaryBody({ locale, listing, labels }: SearchMapListItemBase) {
  const title = listingTitle(locale, listing);
  const age = listingAgeLabel(locale, listing);
  const { place, schedule } = listingMetaLine(locale, listing, labels.locationsCount);
  const meta = [place, schedule].filter(Boolean).join(' · ');
  const factsLine = listingFactsLine(locale, listing);
  const price = formatListingPriceSummary(locale, listing);

  return (
    <>
      <Thumbnail listing={listing} title={title} />
      <div className="min-w-0 flex-1">
        {age ? (
          <span className="mb-1 inline-flex rounded-full bg-brand-100 px-2 py-0.5 text-xs font-semibold text-ink-900">
            {age}
          </span>
        ) : null}
        <h3 className="line-clamp-2 text-sm font-semibold text-ink-900">{title}</h3>
        {meta ? <p className="mt-0.5 line-clamp-1 text-xs text-ink-700">{meta}</p> : null}
        {factsLine ? (
          <p className="mt-0.5 line-clamp-1 text-xs text-ink-700">{factsLine}</p>
        ) : null}
        {price || listingCardRules(listing).detailsOnRequest ? (
          <p className="mt-0.5 text-sm font-semibold text-ink-900">
            {price ?? <span className="font-normal text-ink-500">{labels.detailsOnRequest}</span>}
          </p>
        ) : null}
      </div>
    </>
  );
}

const CHEVRON_RIGHT_SRC = '/images/ui/chevron-right.svg';

const VIEW_CLASS_NAME =
  'link-unadorned inline-flex min-h-11 shrink-0 items-center self-center rounded-full ' +
  'border border-ink-900/15 bg-white px-4 text-sm font-semibold text-ink-900 hover:bg-brand-50';

export function SearchMapListItem(props: SearchMapListItemProps) {
  const href = useActivityHref(props.locale, props.listing.activity.id);
  const isSelected = props.isSelected === true;
  const title = listingTitle(props.locale, props.listing);

  const articleClassName = `search-map-list-item flex gap-3 rounded-xl border p-3 transition ${
    isSelected ? 'border-brand-500 bg-brand-50' : 'border-brand-100 bg-white hover:border-brand-200'
  } ${props.className ?? ''}`;

  if (props.kind === 'summary') {
    return (
      <article
        className={`${articleClassName} shadow-lg`}
        aria-current={isSelected ? 'true' : undefined}
      >
        <Link
          href={href}
          className="link-unadorned flex min-w-0 flex-1 items-center gap-3 text-left"
        >
          <SummaryBody locale={props.locale} listing={props.listing} labels={props.labels} />
          {props.compact ? (
            <img
              src={CHEVRON_RIGHT_SRC}
              alt=""
              width={12}
              height={12}
              decoding="async"
              aria-hidden="true"
              className="h-3 w-3 shrink-0 opacity-60"
            />
          ) : (
            <span className={VIEW_CLASS_NAME}>{props.labels.view}</span>
          )}
        </Link>
      </article>
    );
  }

  return (
    <article className={articleClassName} aria-current={isSelected ? 'true' : undefined}>
      <button
        type="button"
        className="flex min-w-0 flex-1 gap-3 text-left"
        onClick={props.onSelect}
      >
        <SummaryBody locale={props.locale} listing={props.listing} labels={props.labels} />
      </button>
      <Link href={href} aria-label={`${props.labels.view}: ${title}`} className={VIEW_CLASS_NAME}>
        {props.labels.view}
      </Link>
    </article>
  );
}
