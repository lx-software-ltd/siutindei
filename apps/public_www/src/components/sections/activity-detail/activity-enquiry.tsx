'use client';

import type { ReactNode } from 'react';

import { TrackedWhatsappLink } from '@/components/shared/tracked-whatsapp-link';
import { ShareButton } from '@/components/shared/ui/share-button';
import type { AnalyticsItemFields } from '@/lib/analytics/data-layer';

import { ActivityKeyFacts, type KeyFact } from './activity-key-facts';
import { DetailIcon } from './detail-icon';
import type { ActivityDetailCopy } from './types';

export interface EnquiryProps {
  readonly href: string | null;
  readonly item: AnalyticsItemFields;
  readonly locationId: string;
  readonly activityId: string;
  readonly label: string;
}

const PRIMARY_CLASS_NAME =
  'link-unadorned inline-flex min-h-12 items-center justify-center rounded-lg border ' +
  'border-ink-900/20 bg-accent-500 px-5 text-sm font-semibold text-ink-900 transition ' +
  'hover:bg-accent-600';

export function EnquiryLink({
  enquiry,
  className = '',
  children,
}: {
  readonly enquiry: EnquiryProps;
  readonly className?: string;
  readonly children?: ReactNode;
}) {
  if (!enquiry.href) {
    return null;
  }
  return (
    <TrackedWhatsappLink
      href={enquiry.href}
      leadType="whatsapp_activity"
      item={enquiry.item}
      locationId={enquiry.locationId}
      activityId={enquiry.activityId}
      target="_blank"
      rel="noreferrer noopener"
      className={`${PRIMARY_CLASS_NAME} ${className}`}
    >
      {children ?? enquiry.label}
    </TrackedWhatsappLink>
  );
}

/** Sticky card beside the content on iPad landscape and wider. */
export function ActivitySummaryCard({
  price,
  priceDetail,
  facts,
  enquiry,
  directionsHref,
  title,
  copy,
}: {
  readonly price: string | null;
  readonly priceDetail: string | null;
  readonly facts: readonly KeyFact[];
  readonly enquiry: EnquiryProps;
  readonly directionsHref: string | null;
  readonly title: string;
  readonly copy: ActivityDetailCopy;
}) {
  return (
    <aside
      aria-label={copy.keyFactsLabel}
      className="activity-summary-card sticky top-24 space-y-4 rounded-2xl border border-brand-100 bg-white p-5 shadow-sm"
    >
      <div>
        <p className="text-2xl font-bold text-ink-900">{price ?? copy.askForPriceLabel}</p>
        {priceDetail ? <p className="text-sm text-ink-500">{priceDetail}</p> : null}
      </div>
      <ActivityKeyFacts
        facts={facts.filter((fact) => fact.id !== 'price')}
        copy={copy}
        enquiryHref={enquiry.href}
        compact
      />
      <EnquiryLink enquiry={enquiry} className="w-full" />
      <div className="grid grid-cols-2 gap-2">
        {directionsHref ? (
          <a
            href={directionsHref}
            target="_blank"
            rel="noreferrer noopener"
            className="link-unadorned inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-ink-900/15 bg-white px-3 text-sm font-semibold text-ink-900 hover:bg-brand-50"
          >
            <DetailIcon name="directions" className="h-[18px] w-[18px]" />
            {copy.directionsLabel}
          </a>
        ) : null}
        <ShareButton
          title={title}
          label={copy.shareLabel}
          copiedLabel={copy.linkCopiedLabel}
          className={directionsHref ? '' : 'col-span-2'}
        />
      </div>
    </aside>
  );
}

/** Bottom bar with the price and the enquiry on phones and iPad portrait. */
export function ActivityActionBar({
  price,
  enquiry,
}: {
  readonly price: string | null;
  readonly enquiry: EnquiryProps;
}) {
  if (!enquiry.href) {
    return null;
  }
  return (
    <div className="activity-action-bar fixed inset-x-0 bottom-0 z-40 border-t border-brand-100 bg-white/95 px-4 py-3 shadow-[0_-4px_16px_rgba(46,29,18,0.08)] backdrop-blur lg:hidden short:hidden">
      <div className="mx-auto flex max-w-3xl items-center gap-3">
        {price ? (
          <p className="min-w-0 flex-1 truncate text-base font-semibold text-ink-900">{price}</p>
        ) : (
          <span className="flex-1" />
        )}
        <EnquiryLink enquiry={enquiry} className="shrink-0" />
      </div>
    </div>
  );
}
