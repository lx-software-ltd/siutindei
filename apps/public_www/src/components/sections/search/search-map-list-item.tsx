'use client';

import Link from 'next/link';

import type { Locale } from '@/content/locales';
import type { ActivityListing } from '@/lib/activities/types';
import {
  formatListingPrice,
  listingImageUrl,
  listingTitle,
  regionLabelForListing,
} from '@/lib/activities/listing-utils';
import { localizePath } from '@/lib/locale-routing';
import {
  LISTING_IMAGE_HEIGHT,
  LISTING_IMAGE_WIDTH,
} from '@/lib/listing-image';

interface SearchMapListItemBase {
  readonly locale: Locale;
  readonly listing: ActivityListing;
  readonly imageFallbackLabel: string;
}

interface SearchMapSelectItemProps extends SearchMapListItemBase {
  readonly kind: 'select';
  readonly isSelected: boolean;
  readonly onSelect: () => void;
}

interface SearchMapSummaryItemProps extends SearchMapListItemBase {
  readonly kind: 'summary';
}

export type SearchMapListItemProps =
  | SearchMapSelectItemProps
  | SearchMapSummaryItemProps;

function SummaryBody({
  locale,
  listing,
  imageFallbackLabel,
}: SearchMapListItemBase) {
  const imageUrl = listingImageUrl(listing);
  const title = listingTitle(locale, listing);
  const region = regionLabelForListing(locale, listing);
  const price = formatListingPrice(locale, listing);

  return (
    <>
      <div className="relative h-20 w-20 shrink-0 overflow-hidden rounded-lg bg-brand-100">
        {imageUrl ? (
          <img
            src={imageUrl}
            alt={title}
            width={LISTING_IMAGE_WIDTH}
            height={LISTING_IMAGE_HEIGHT}
            loading="lazy"
            decoding="async"
            className="h-full w-full object-cover"
          />
        ) : (
          <span className="flex h-full items-center justify-center px-1 text-center text-[10px] text-ink-500">
            {imageFallbackLabel}
          </span>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <h3 className="line-clamp-2 text-sm font-semibold text-ink-900">
          {title}
        </h3>
        {region ? (
          <p className="mt-1 text-xs text-ink-500">{region}</p>
        ) : null}
        <p className="mt-1 text-sm font-semibold text-ink-900">{price}</p>
      </div>
    </>
  );
}

export function SearchMapListItem(props: SearchMapListItemProps) {
  const href = `${localizePath('/activity', props.locale)}?id=${props.listing.activity.id}`;
  const isSelected = props.kind === 'select' && props.isSelected;

  const articleClassName = `search-map-list-item flex gap-3 rounded-xl border p-3 transition ${
    isSelected
      ? 'border-brand-500 bg-brand-50'
      : 'border-brand-100 bg-white hover:border-brand-200'
  }`;

  if (props.kind === 'summary') {
    return (
      <article className={`${articleClassName} shadow-lg`}>
        <Link
          href={href}
          className="link-unadorned flex min-w-0 flex-1 gap-3 text-left"
        >
          <SummaryBody
            locale={props.locale}
            listing={props.listing}
            imageFallbackLabel={props.imageFallbackLabel}
          />
        </Link>
      </article>
    );
  }

  return (
    <article className={articleClassName}>
      <button
        type="button"
        className="flex min-w-0 flex-1 gap-3 text-left"
        onClick={props.onSelect}
      >
        <SummaryBody
          locale={props.locale}
          listing={props.listing}
          imageFallbackLabel={props.imageFallbackLabel}
        />
      </button>
      <Link
        href={href}
        className="self-center text-xs font-semibold text-brand-600 hover:underline"
      >
        →
      </Link>
    </article>
  );
}
